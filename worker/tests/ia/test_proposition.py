"""Proposition des réglages par l'IA (T025, FR-008, US3) : API simulée, jamais d'appel réel.

Vérifie : la proposition est enregistrée sans `valide_le`, et la base refuse de la valider
(C1) ; aucun nom de `dirigeants_personnes` n'entre dans ce qui part vers l'API (C2) ; une
marque qui a des homonymes au registre est rangée en ambiguë, cas limites compris : zéro
homonyme, la tête elle-même, ses filiales directes ou non, casse et accents, mot entier
(C3). Plus : chaque élément garde porte une source http(s), la boucle d'appel à OpenRouter
(relance, refus, réponse illisible), le client HTTP (erreurs sans fuite de la clé, T037), et
le contenu proposé reste au schéma des réglages.

Le registre est un mini-registre fabriqué (noms inventés, règle produit 6). Les tests base
demandent DATABASE_URL (migrations appliquées) : ignorés en local sans elle, échec en CI.
"""

import json
import os
import re
import sys
import uuid
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
import pytest
from psycopg.types.json import Jsonb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "moteur"))
from fabrique import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    PRESIDENT,
    MiniRegistre,
    personne,
    siren,
)

from cartofr import travaux  # noqa: E402
from cartofr.db import VARIABLE_URL, connecter  # noqa: E402
from cartofr.ia import proposition as ia  # noqa: E402
from cartofr.ia.proposition import ElementBrut, ElementRange  # noqa: E402
from cartofr.jobs import TRAVAUX  # noqa: E402
from cartofr.jobs import proposition as job  # noqa: E402
from cartofr.reglages import valider  # noqa: E402
from cartofr.travaux import Travail  # noqa: E402

Connexion = psycopg.Connection[tuple[Any, ...]]

TETE = siren(1)
F1, F2, F3 = siren(10), siren(11), siren(12)
DEHORS, DEHORS_SIGLE, ACCENT, PROCHE, INACTIVE, ANCIENNE = (siren(n) for n in (50, 51, 52, 53, 54, 55))
NOM_DIRIGEANT = "ZORGLUBINVENTE"
PRENOM_DIRIGEANT = "PRENOMINVENTEZ"
CLE_DIRIGEANT = f"{NOM_DIRIGEANT}|{PRENOM_DIRIGEANT}|1970-01"
MARQUEUR = "test_t025"
SOURCE = "https://groupe-invente.example/marques"


def registre() -> MiniRegistre:
    """La tête « ALPHAMARK HOLDING », une filiale et une sous-filiale qui portent la marque,
    une société dehors qui la porte aussi (homonyme), et des presque-homonymes."""
    mini = MiniRegistre()
    mini.societe(TETE, "ALPHAMARK HOLDING", tranche="52")
    mini.societe(F1, "ALPHAMARK SERVICES", tranche="32")
    mini.lien(TETE, F1, PRESIDENT)
    mini.societe(F2, "ALPHAMARK DISTRIBUTION")
    mini.lien(F1, F2, PRESIDENT)  # sous-filiale : dans le groupe aussi
    mini.societe(F3, "GAMMAMARK FRANCE")
    mini.lien(TETE, F3, PRESIDENT)
    mini.societe(DEHORS, "SAS ALPHAMARK CONSEIL")  # forme juridique devant : homonyme
    mini.societe(DEHORS_SIGLE, "ALPHAMARKET")  # mot plus long : pas un homonyme
    mini.societe(ACCENT, "BÉTA-MARQUE SARL")  # accents et ponctuation : homonyme de « Béta Marque »
    mini.societe(PROCHE, "OMEGAMARK")  # dans aucun réglage
    mini.societe(INACTIVE, "DELTAMARK ANCIENNE", active=False)  # cessée : jamais comptée
    mini.societe(ANCIENNE, "GAMMAMARK CEDEE")
    mini.lien(TETE, ANCIENNE, PRESIDENT, fin=date(2026, 3, 10))  # lien fermé : hors du groupe
    for s in (TETE, F1, DEHORS):
        mini.dirigeant(s, CLE_DIRIGEANT)
        mini.dirigeant(s, personne(1))
    return mini


@pytest.fixture
def chemin(tmp_path: Path) -> Path:
    return registre().ecrire(tmp_path / "registre.duckdb")


def lecture(chemin: Path) -> Any:
    import duckdb

    return duckdb.connect(str(chemin), read_only=True)


# --- API simulée -----------------------------------------------------------------------------


def outil(entree: dict[str, Any], nom: str = ia.OUTIL) -> dict[str, Any]:
    """Un appel de fonction au format OpenAI (arguments en texte JSON)."""
    return {"id": "call_test", "type": "function", "function": {"name": nom, "arguments": json.dumps(entree)}}


def reponse(fin: str, *appels: dict[str, Any], contenu: str | None = None, **message: Any) -> dict[str, Any]:
    """Une réponse OpenRouter (/chat/completions) : un choix, sa raison de fin, son message."""
    corps = {"role": "assistant", "content": contenu, "tool_calls": list(appels) or None, **message}
    return {"id": "gen-test", "choices": [{"finish_reason": fin, "message": corps}]}


class ClientSimule:
    """Remplace ClientOpenRouter : rend les réponses données, garde chaque requête."""

    def __init__(self, *reponses: dict[str, Any]) -> None:
        self.reponses = list(reponses)
        self.requetes: list[dict[str, Any]] = []

    def envoyer(self, corps: dict[str, Any]) -> dict[str, Any]:
        # Copie des messages : la boucle les complète après coup.
        self.requetes.append({**corps, "messages": list(corps["messages"])})
        return self.reponses.pop(0)


def element(nom: str, source: str = SOURCE) -> dict[str, str]:
    return {"nom": nom, "source": source}


PROPOSITION = {
    "marques": [element("Alphamark"), element("Gammamark"), element("Béta Marque")],
    "sigles": [element("AMH")],
    "maisons": [element("Alphamark Services")],
    "exclusions": [element("Alphamark Conseil")],
}


# --- C2 : rien de `dirigeants_personnes` dans ce qui part vers l'API --------------------------


def test_aucun_nom_de_dirigeant_dans_la_requete(chemin: Path) -> None:
    """C2 : tout ce qui est envoyé (système, messages, outils) est confronté aux dirigeants."""
    con = lecture(chemin)
    try:
        entree = ia.lire_entree(con, "ALPHAMARK", TETE)
        personnes = [p for (p,) in con.execute("select personne from dirigeants_personnes").fetchall()]
    finally:
        con.close()
    client = ClientSimule(reponse("tool_calls", outil(PROPOSITION)))
    ia.proposer(entree, client, "modele-test")

    envoye = json.dumps(client.requetes, ensure_ascii=False, default=str).upper()
    assert len(personnes) == 6
    # Clé brute, « NOM PRÉNOM » et « PRÉNOM NOM » de chaque dirigeant ; plus le nom et le
    # prénom inventés seuls, qui n'existent nulle part ailleurs.
    cherches = {NOM_DIRIGEANT, PRENOM_DIRIGEANT}
    for p in personnes:
        nom, prenom, _ = p.split("|")
        cherches |= {p, f"{nom} {prenom}", f"{prenom} {nom}"}
    trouves = sum(1 for c in cherches if c.upper() in envoye)
    assert trouves == 0
    # Le contexte est bien celui du registre : des sociétés seulement.
    assert "ALPHAMARK HOLDING" in envoye and F1 in envoye and F3 in envoye
    assert ANCIENNE not in envoye  # lien fermé
    assert F2 in envoye  # T039 : sous-filiale, au-delà des filiales directes


def test_le_code_ne_lit_jamais_la_table_des_dirigeants() -> None:
    """C2, côté code : aucune requête des modules de la proposition ne lit cette table."""
    racine = Path(ia.__file__).resolve().parents[1]
    for fichier in (racine / "ia" / "proposition.py", racine / "jobs" / "proposition.py"):
        texte = fichier.read_text(encoding="utf-8")
        assert not re.search(r"\b(from|join)\s+dirigeants_personnes\b", texte, re.IGNORECASE), fichier.name


# --- C3 : la règle des homonymes ---------------------------------------------------------------


def test_compter_homonymes_cas_limites(chemin: Path) -> None:
    con = lecture(chemin)
    try:
        groupe = ia.societes_du_groupe(con, TETE)
        comptes = ia.compter_homonymes(
            con, ["Alphamark", "alphamark", "Gammamark", "Béta Marque", "Zetamark", "Deltamark"], groupe
        )
    finally:
        con.close()
    assert groupe == {TETE, F1, F2, F3}  # sous-filiale comprise, lien fermé exclu
    # La tête, la filiale et la sous-filiale ne comptent pas ; « SAS ALPHAMARK CONSEIL » oui,
    # « ALPHAMARKET » non (mot entier). Même compte quelle que soit la casse.
    assert comptes["Alphamark"] == 1
    assert comptes["alphamark"] == 1
    assert comptes["Gammamark"] == 1  # la société cédée (lien fermé) est un homonyme
    assert comptes["Béta Marque"] == 1  # accents et tiret ignorés
    assert comptes["Zetamark"] == 0  # zéro homonyme
    assert comptes["Deltamark"] == 0  # société cessée : pas comptée


def test_la_tete_seule_n_est_pas_un_homonyme(tmp_path: Path) -> None:
    mini = MiniRegistre()
    mini.societe(TETE, "ALPHAMARK")
    chemin = mini.ecrire(tmp_path / "r.duckdb")
    con = lecture(chemin)
    try:
        assert ia.compter_homonymes(con, ["Alphamark"], ia.societes_du_groupe(con, TETE)) == {"Alphamark": 0}
    finally:
        con.close()


def test_ranger_une_marque_avec_homonymes_est_ambigue() -> None:
    elements = [
        ElementBrut("marque", "Alphamark", SOURCE),
        ElementBrut("marque", "Zetamark", SOURCE),
        ElementBrut("marque", "Sanscompte", SOURCE),
        ElementBrut("sigle", "AMH", SOURCE),
        ElementBrut("maison", "Alphamark Services", SOURCE),
        ElementBrut("exclusion", "Alphamark Conseil", SOURCE),
    ]
    ranges = ia.ranger(elements, {"Alphamark": 3, "Zetamark": 0})
    assert [(r.liste, r.valeur, r.homonymes) for r in ranges] == [
        ("marques_ambigues", "Alphamark", 3),
        ("marques_sures", "Zetamark", 0),
        ("marques_ambigues", "Sanscompte", None),  # compte manquant : dans le doute, ambiguë
        ("marques_sigles", "AMH", None),
        ("organigramme", "Alphamark Services", None),
        ("exclus_noms", "Alphamark Conseil", None),
    ]
    assert all(r.source == SOURCE for r in ranges)


# --- Sources et forme --------------------------------------------------------------------------


def test_nettoyer_exige_une_source_et_un_texte_valide() -> None:
    bruts = [
        ElementBrut("marque", "  Alphamark ", f" {SOURCE} "),
        ElementBrut("marque", "ALPHAMARK", SOURCE),  # doublon (casse)
        ElementBrut("marque", "Alphamàrk", SOURCE),  # doublon (accent)
        ElementBrut("sigle", "Alphamark", SOURCE),  # autre type : gardé
        ElementBrut("marque", "Sanssource", ""),
        ElementBrut("marque", "Ftp", "ftp://groupe.example/x"),
        ElementBrut("marque", "Script", "javascript:alert(1)"),
        ElementBrut("marque", "Deux\nlignes", SOURCE),
        ElementBrut("marque", "x" * 201, SOURCE),
        ElementBrut("marque", "--", SOURCE),  # rien après normalisation
        ElementBrut("maison", "Url longue", "https://a.example/" + "a" * 600),
    ]
    assert ia.nettoyer(bruts) == [
        ElementBrut("marque", "Alphamark", SOURCE),
        ElementBrut("sigle", "Alphamark", SOURCE),
    ]


def test_contenu_propose_garde_les_cles_de_la_derniere_version_validee() -> None:
    base = {
        "groupe": "ANCIEN NOM",
        "tete": TETE,
        "marques_sures": ["Ancienne"],
        "exclus": [siren(99)],
        "familles_exclues_empreintes": ["a" * 64],
        "priorite": [F1],
    }
    ranges = [
        ElementRange("marques_sures", "Zetamark", SOURCE, 0),
        ElementRange("marques_ambigues", "Alphamark", SOURCE, 1),
        ElementRange("organigramme", "Alphamark Services", SOURCE),
    ]
    contenu = ia.contenu_propose("ALPHAMARK", TETE, ranges, base)
    assert contenu["groupe"] == "ALPHAMARK"
    assert contenu["marques_sures"] == ["Zetamark"]  # la proposition remplace les listes proposées
    assert contenu["marques_ambigues"] == ["Alphamark"]
    assert contenu["exclus"] == [siren(99)] and contenu["priorite"] == [F1]
    assert contenu["familles_exclues_empreintes"] == ["a" * 64]
    valider(contenu)  # au schéma des réglages


# --- Principe 2 : rien de validé ne se perd en silence ---------------------------------------


IA_RANGES = [
    ElementRange("marques_sures", "Zetamark", SOURCE, 0),
    ElementRange("marques_ambigues", "Alphamark", SOURCE, 2),
]


def test_garder_validees_sans_version_validee() -> None:
    assert ia.garder_validees(IA_RANGES, None) == IA_RANGES
    assert ia.garder_validees(IA_RANGES, {"groupe": "G", "tete": TETE}) == IA_RANGES


def test_garder_validees_repropose_a_l_identique_affiche_une_fois() -> None:
    sortie = ia.garder_validees(IA_RANGES, {"marques_sures": ["ZÉTAMARK"]})  # casse et accent
    assert [(r.liste, r.valeur, r.origine, r.deja_valide_en) for r in sortie] == [
        ("marques_sures", "Zetamark", "ia", "marques_sures"),
        ("marques_ambigues", "Alphamark", "ia", None),
    ]


def test_garder_validees_repropose_dans_une_autre_liste() -> None:
    sortie = ia.garder_validees(IA_RANGES, {"marques_sures": ["Alphamark"]})
    assert len(sortie) == 2
    assert (sortie[1].liste, sortie[1].deja_valide_en, sortie[1].source) == (
        "marques_ambigues",
        "marques_sures",
        SOURCE,
    )


def test_garder_validees_non_reproposees_sont_ajoutees_et_gardees() -> None:
    base = {
        "groupe": "G",
        "tete": TETE,
        "marques_sures": ["Ancienne", "Ancienne"],
        "organigramme": ["Maison Validee"],
        "exclus_noms": ["Maison Validee"],  # même valeur, autre liste : les deux restent
        "marques_sures_homonymes": ["Hors revue"],  # liste non proposée : reprise telle quelle
        "exclus": [siren(99)],
    }
    sortie = ia.garder_validees(IA_RANGES, base)
    assert [(r.liste, r.valeur, r.origine, r.source) for r in sortie[2:]] == [
        ("marques_sures", "Ancienne", "validee", None),
        ("organigramme", "Maison Validee", "validee", None),
        ("exclus_noms", "Maison Validee", "validee", None),
    ]
    contenu = ia.contenu_propose("G", TETE, sortie, base)
    assert contenu["marques_sures"] == ["Zetamark", "Ancienne"]
    assert contenu["organigramme"] == ["Maison Validee"]
    assert contenu["exclus_noms"] == ["Maison Validee"]
    assert contenu["marques_sures_homonymes"] == ["Hors revue"]
    valider(contenu)


def test_lire_reponse_ignore_ce_qui_n_a_pas_la_forme() -> None:
    bruts = ia.lire_reponse(
        {"marques": [element("A"), {"nom": "B"}, "C", {"nom": 1, "source": SOURCE}], "sigles": "X"}
    )
    assert bruts == [ElementBrut("marque", "A", SOURCE)]


# --- Boucle d'appel ----------------------------------------------------------------------------


def entree_test() -> ia.Entree:
    return ia.Entree("ALPHAMARK", ia.SocietePublique(TETE, "ALPHAMARK HOLDING"))


def test_appel_relance_sans_outil_et_requete_openrouter() -> None:
    client = ClientSimule(
        reponse("stop", contenu="Voici."),
        reponse("tool_calls", outil(PROPOSITION)),
    )
    bruts = ia.proposer(entree_test(), client, "modele-test")
    assert len(bruts) == 6
    assert len(client.requetes) == 2
    # Après une fin sans outil : la réponse gardée, puis une relance.
    assert client.requetes[1]["messages"][-2:] == [
        {"role": "assistant", "content": "Voici."},
        {"role": "user", "content": ia.RELANCE},
    ]
    premiere = client.requetes[0]
    assert premiere["model"] == "modele-test"
    assert premiere["tool_choice"] == "auto"
    assert premiere["messages"][0] == {"role": "system", "content": ia.SYSTEME}
    types = [o["type"] for o in premiere["tools"]]
    assert types == ["openrouter:web_search", "openrouter:web_fetch", "function"]
    fonction = premiere["tools"][2]["function"]
    assert fonction["name"] == ia.OUTIL and fonction["strict"] is True
    assert fonction["parameters"]["required"] == list(ia.CLES_OUTIL)
    # R5 : seulement des fournisseurs sans conservation ni collecte des données.
    assert premiere["provider"] == {"data_collection": "deny", "zdr": True}


def test_appel_ignore_un_autre_outil_puis_lit_la_proposition() -> None:
    client = ClientSimule(reponse("tool_calls", outil({"x": 1}, nom="autre"), outil(PROPOSITION)))
    assert len(ia.proposer(entree_test(), client, "modele-test")) == 6


@pytest.mark.parametrize(
    "rendu",
    [
        reponse("stop", refusal="Je ne peux pas."),
        reponse("content_filter"),
        reponse("length", contenu="Début…"),
        reponse(
            "tool_calls",
            {"id": "c", "type": "function", "function": {"name": ia.OUTIL, "arguments": "pas du json"}},
        ),
        reponse(
            "tool_calls",
            {"id": "c", "type": "function", "function": {"name": ia.OUTIL, "arguments": "[1, 2]"}},
        ),
        {"error": {"code": 502, "message": "Upstream error"}},
        {"choices": []},
        {"choices": [{"finish_reason": "stop"}]},
    ],
    ids=[
        "refus",
        "filtre",
        "tronque",
        "json-illisible",
        "pas-un-objet",
        "erreur",
        "sans-choix",
        "sans-message",
    ],
)
def test_appel_refus_tronque_ou_illisible(rendu: dict[str, Any]) -> None:
    with pytest.raises(ia.PropositionImpossible):
        ia.proposer(entree_test(), ClientSimule(rendu), "modele-test")


def test_appel_coupe_dit_tronquee_pas_illisible() -> None:
    """T039 : un appel d'outil coupé par la limite de sortie est une réponse tronquée."""
    coupe = {"id": "c", "type": "function", "function": {"name": ia.OUTIL, "arguments": '{"marques": [{"nom'}}
    with pytest.raises(ia.PropositionImpossible, match="tronquée"):
        ia.proposer(entree_test(), ClientSimule(reponse("length", coupe)), "modele-test")


def test_appel_abandonne_apres_trop_de_tours() -> None:
    client = ClientSimule(*(reponse("stop", contenu="Rien.") for _ in range(ia.MAX_TOURS)))
    with pytest.raises(ia.PropositionImpossible):
        ia.proposer(entree_test(), client, "modele-test")
    assert len(client.requetes) == ia.MAX_TOURS


def test_modele_et_cle(monkeypatch: pytest.MonkeyPatch) -> None:
    # Pas de modèle par défaut (T038) : absent ou vide, le travail s'arrête avec un message clair.
    monkeypatch.delenv(ia.VARIABLE_MODELE, raising=False)
    with pytest.raises(ia.ModeleIaManquant):
        ia.modele()
    monkeypatch.setenv(ia.VARIABLE_MODELE, "   ")
    with pytest.raises(ia.ModeleIaManquant):
        ia.modele()
    monkeypatch.setenv(ia.VARIABLE_MODELE, "autre/modele")
    assert ia.modele() == "autre/modele"
    monkeypatch.delenv(ia.VARIABLE_CLE_API, raising=False)
    with pytest.raises(ia.CleIaManquante):
        ia.client_ia()
    monkeypatch.setenv(ia.VARIABLE_CLE_API, "  ")
    with pytest.raises(ia.CleIaManquante):
        ia.client_ia()
    monkeypatch.setenv(ia.VARIABLE_CLE_API, "cle-factice")
    assert isinstance(ia.client_ia(), ia.ClientOpenRouter)


def test_consigne_vise_les_pages_de_marques_pas_les_filiales() -> None:
    """T038 : le moteur trouve les filiales au registre ; l'IA cherche les marques sur les pages
    courtes du site, et n'ouvre pas un rapport annuel en entier."""
    assert "ne cherche pas" in ia.SYSTEME and "liste des filiales" in ia.SYSTEME
    assert "nos marques" in ia.SYSTEME
    assert "jamais en entier" in ia.SYSTEME
    # T039 : le rappel compte, sans rien inventer.
    assert "exhaustif" in ia.SYSTEME and "rien d'inventé" in ia.SYSTEME
    assert "Préfère peu" not in ia.SYSTEME


def test_consommation_additionnee_et_journalisee(caplog: pytest.LogCaptureFixture) -> None:
    usage1 = {
        "prompt_tokens": 1200,
        "completion_tokens": 80,
        "cost": 0.0021,
        "server_tool_use": {"web_search_requests": 3},
    }
    usage2 = {"prompt_tokens": 3400, "completion_tokens": 400, "cost": 0.004}
    client = ClientSimule(
        {**reponse("stop", contenu="Voici."), "usage": usage1},
        {**reponse("tool_calls", outil(PROPOSITION)), "usage": usage2},
    )
    with caplog.at_level("INFO", logger=ia.log.name):
        ia.proposer(entree_test(), client, "modele/test")
    ligne = next(m for m in caplog.messages if "jetons" in m)
    assert ligne == (
        "proposition IA : modèle modele/test, 2 requêtes, 4600 jetons en entrée, 480 en sortie, "
        "3 recherches web, coût 0.0061 $"
    )
    # Des nombres seulement : rien de la proposition ni du texte de l'IA.
    assert "Voici" not in caplog.text and "Alphamark" not in caplog.text


def test_consommation_journalisee_meme_en_erreur(caplog: pytest.LogCaptureFixture) -> None:
    client = ClientSimule({**reponse("length", contenu="Début"), "usage": {"prompt_tokens": 50, "cost": "x"}})
    with caplog.at_level("INFO", logger=ia.log.name), pytest.raises(ia.PropositionImpossible):
        ia.proposer(entree_test(), client, "modele/test")
    assert any(
        "1 requêtes, 50 jetons en entrée, 0 en sortie, 0 recherches web, coût inconnu" in m
        for m in caplog.messages
    )


def test_consommation_lit_le_champ_d_openrouter() -> None:
    """T039 : OpenRouter range les recherches dans `server_tool_use_details`."""
    conso = ia.Consommation()
    conso.ajouter({"usage": {"server_tool_use_details": {"web_search_requests": 5}}})
    conso.ajouter({"usage": {"server_tool_use": {"web_search_requests": 2}}})
    assert conso.recherches_web == 7


def test_lire_entree_prend_les_plus_grosses_societes_du_groupe(chemin: Path) -> None:
    """T039 : tout le groupe (sous-filiales comprises), sans la tête ni les liens fermés,
    les plus grosses d'abord, dans la limite donnée."""
    con = lecture(chemin)
    try:
        entree = ia.lire_entree(con, "ALPHAMARK", TETE)
        une = ia.lire_entree(con, "ALPHAMARK", TETE, max_filiales=1)
    finally:
        con.close()
    sirens = [f.siren for f in entree.filiales]
    assert set(sirens) == {F1, F2, F3}
    assert sirens[0] == F1  # tranche 32 : la plus grosse
    assert [f.siren for f in une.filiales] == [F1]


def test_consommation_ignore_les_valeurs_bizarres() -> None:
    conso = ia.Consommation()
    conso.ajouter({"usage": {"prompt_tokens": -5, "completion_tokens": True, "cost": None}})
    conso.ajouter({"usage": "rien"})
    conso.ajouter({})
    assert (conso.requetes, conso.jetons_entree, conso.jetons_sortie, conso.cout) == (3, 0, 0, None)


# --- Client OpenRouter (HTTP simulé, jamais d'appel réel) -----------------------------------------

CLE_FACTICE = "sk-or-cle-factice-jamais-journalisee"


def poser_http(monkeypatch: pytest.MonkeyPatch, rendu: Any) -> list[dict[str, Any]]:
    """Remplace httpx.post : rend `rendu` (une réponse, ou une exception à lever), garde l'appel."""
    import httpx

    appels: list[dict[str, Any]] = []

    def post(url: str, **kwargs: Any) -> httpx.Response:
        appels.append({"url": url, **kwargs})
        if isinstance(rendu, Exception):
            raise rendu
        return rendu

    monkeypatch.setattr(httpx, "post", post)
    return appels


def test_client_envoie_la_requete_avec_la_cle(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    corps = reponse("tool_calls", outil(PROPOSITION))
    appels = poser_http(monkeypatch, httpx.Response(200, json=corps))
    assert ia.ClientOpenRouter(CLE_FACTICE).envoyer({"model": "m"}) == corps
    assert appels[0]["url"] == ia.URL_OPENROUTER
    assert appels[0]["headers"]["Authorization"] == f"Bearer {CLE_FACTICE}"
    assert appels[0]["json"] == {"model": "m"}
    assert appels[0]["timeout"] == ia.DELAI_S


@pytest.mark.parametrize(
    ("statut", "attendu"),
    [(401, "clé"), (403, "clé"), (402, "crédit"), (429, "Réessayez"), (502, "Réessayez")],
)
def test_client_erreurs_http_sans_fuite(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, statut: int, attendu: str
) -> None:
    import httpx

    poser_http(monkeypatch, httpx.Response(statut, json={"error": {"message": f"détail {CLE_FACTICE}"}}))
    with caplog.at_level("DEBUG"), pytest.raises(ia.PropositionImpossible) as erreur:
        ia.ClientOpenRouter(CLE_FACTICE).envoyer({"model": "m"})
    assert attendu in str(erreur.value)
    assert CLE_FACTICE not in str(erreur.value) and CLE_FACTICE not in caplog.text
    assert "détail" not in caplog.text  # le corps de l'erreur n'est jamais journalisé


def test_client_injoignable_ou_reponse_illisible(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    poser_http(monkeypatch, httpx.ConnectTimeout("délai dépassé"))
    with pytest.raises(ia.PropositionImpossible, match="injoignable"):
        ia.ClientOpenRouter(CLE_FACTICE).envoyer({})
    poser_http(monkeypatch, httpx.Response(200, text="<html>pas du json</html>"))
    with pytest.raises(ia.PropositionImpossible, match="illisible"):
        ia.ClientOpenRouter(CLE_FACTICE).envoyer({})
    poser_http(monkeypatch, httpx.Response(200, json=[1, 2]))
    with pytest.raises(ia.PropositionImpossible, match="illisible"):
        ia.ClientOpenRouter(CLE_FACTICE).envoyer({})


# --- C1 : le travail enregistre une version non validée -----------------------------------------


@pytest.fixture
def conn() -> Iterator[Connexion]:
    if not os.environ.get(VARIABLE_URL):
        message = f"{VARIABLE_URL} n'est pas définie : le travail proposition écrit dans la base."
        if os.environ.get("CI"):
            pytest.fail(message)
        pytest.skip(message)
    connexion = connecter()
    if (
        connexion.execute(
            "select 1 from information_schema.columns"
            " where table_name = 'reglages' and column_name = 'proposition'"
        ).fetchone()
        is None
    ):
        connexion.close()
        pytest.fail("Colonne reglages.proposition absente : appliquer supabase/migrations/.")
    try:
        yield connexion
    finally:
        connexion.close()


@pytest.fixture
def monde(conn: Connexion, chemin: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    """Deux organisations, un groupe dans la première, le registre fabriqué en CARTOFR_DATA."""
    monkeypatch.setenv("CARTOFR_DATA", str(chemin.parent))
    marque = f"{MARQUEUR} {uuid.uuid4().hex}"

    def un(sql: str, params: tuple[Any, ...]) -> Any:
        ligne = conn.execute(sql, params).fetchone()  # pyright: ignore[reportArgumentType]
        assert ligne is not None
        return ligne[0]

    org = un("insert into public.organisations (nom) values (%s) returning id", (marque + " A",))
    autre = un("insert into public.organisations (nom) values (%s) returning id", (marque + " B",))
    groupe = un(
        "insert into public.groupes (organisation_id, tete_siren, nom)"
        " values (%s, %s, 'ALPHAMARK') returning id",
        (org, TETE),
    )
    conn.execute(
        "insert into public.reglages (groupe_id, organisation_id, version, contenu, valide_le)"
        " values (%s, %s, 1, %s, now())",
        (
            groupe,
            org,
            Jsonb(
                {
                    "groupe": "ALPHAMARK",
                    "tete": TETE,
                    "marques_sures": ["Ancienne Marque", "ALPHAMARK"],
                    "familles_exclues_empreintes": ["b" * 64],
                }
            ),
        ),
    )
    conn.commit()
    try:
        yield {"org": org, "autre": autre, "groupe": groupe}
    finally:
        conn.rollback()
        conn.execute("delete from public.organisations where id in (%s, %s)", (org, autre))
        conn.commit()


def lancer(conn: Connexion, org: uuid.UUID, parametres: dict[str, Any]) -> tuple[str, int]:
    ligne = conn.execute(
        "insert into public.travaux (type, organisation_id, parametres, statut, debut_le)"
        " values ('proposition', %s, %s, 'en_cours', now()) returning id",
        (org, Jsonb(parametres)),
    ).fetchone()
    conn.commit()
    assert ligne is not None
    t = Travail(id=ligne[0], type="proposition", organisation_id=org, parametres=parametres)
    return travaux.executer(conn, t), ligne[0]


def test_le_type_est_enregistre() -> None:
    assert TRAVAUX["proposition"] is job.travail_proposition


def test_c1_proposition_enregistree_sans_validation(
    conn: Connexion, monde: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    client = ClientSimule(reponse("tool_calls", outil(PROPOSITION)))
    monkeypatch.setattr(job, "client_ia", lambda: client)
    monkeypatch.setenv(ia.VARIABLE_MODELE, "modele-test")

    statut, _ = lancer(
        conn, monde["org"], {"groupe_id": str(monde["groupe"]), "demande_par": str(uuid.uuid4())}
    )
    assert statut == "termine"

    ligne = conn.execute(
        "select version, origine, valide_le, valide_par, cree_par, contenu, proposition, organisation_id"
        " from public.reglages where groupe_id = %s order by version desc limit 1",
        (monde["groupe"],),
    ).fetchone()
    conn.commit()
    assert ligne is not None
    version, origine, valide_le, valide_par, cree_par, contenu, proposition, org = ligne
    assert (version, origine, valide_le, valide_par) == (2, "proposition", None, None)
    assert cree_par is None  # compte inconnu de auth.users : rien d'inventé
    assert org == monde["org"]
    reglages = valider(contenu)
    # C3 de bout en bout : Alphamark et Gammamark ont un homonyme, Béta Marque aussi.
    assert reglages.marques_ambigues == ["Alphamark", "Gammamark", "Béta Marque"]
    # Principe 2 : la marque validée que l'IA ne repropose pas reste ; celle qu'elle repropose
    # (dans une autre liste) n'apparaît qu'une fois, là où l'IA la range.
    assert reglages.marques_sures == ["Ancienne Marque"]
    assert reglages.marques_sigles == ["AMH"]
    assert reglages.organigramme == ["Alphamark Services"]
    assert reglages.exclus_noms == ["Alphamark Conseil"]
    assert reglages.familles_exclues_empreintes == ["b" * 64]  # repris de la version validée
    assert proposition["modele"] == "modele-test"
    assert len(proposition["elements"]) == 7
    ia_seule = [e for e in proposition["elements"] if e["origine"] == "ia"]
    assert len(ia_seule) == 6 and all(e["source"] == SOURCE for e in ia_seule)
    assert [e for e in proposition["elements"] if e["origine"] == "validee"] == [
        {
            "liste": "marques_sures",
            "valeur": "Ancienne Marque",
            "source": None,
            "homonymes": None,
            "origine": "validee",
            "deja_valide_en": "marques_sures",
        }
    ]
    alpha = next(e for e in ia_seule if e["valeur"] == "Alphamark")
    assert (alpha["liste"], alpha["deja_valide_en"]) == ("marques_ambigues", "marques_sures")

    # Principe 1 : la base refuse de valider une proposition telle quelle.
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(
            "update public.reglages set valide_le = now() where groupe_id = %s and version = 2",
            (monde["groupe"],),
        )
    conn.rollback()


def test_version_validee_tiree_d_une_proposition(
    conn: Connexion, monde: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Migration 0004 : la version revue porte sa proposition et ses corrections, figées une fois validée."""
    monkeypatch.setattr(job, "client_ia", lambda: ClientSimule(reponse("tool_calls", outil(PROPOSITION))))
    monkeypatch.setenv(ia.VARIABLE_MODELE, "modele-test")
    assert lancer(conn, monde["org"], {"groupe_id": str(monde["groupe"])})[0] == "termine"
    prop = conn.execute(
        "select id from public.reglages where groupe_id = %s and origine = 'proposition'", (monde["groupe"],)
    ).fetchone()
    assert prop is not None
    ligne = conn.execute(
        "insert into public.reglages (groupe_id, organisation_id, version, contenu, proposition_id,"
        " corrections, valide_le) values (%s, %s, 3, %s, %s, 2, now()) returning id",
        (monde["groupe"], monde["org"], Jsonb({"groupe": "ALPHAMARK", "tete": TETE}), prop[0]),
    ).fetchone()
    conn.commit()
    assert ligne is not None
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("update public.reglages set corrections = 0 where id = %s", (ligne[0],))
    conn.rollback()
    # Une proposition d'un autre groupe ou d'une autre organisation : refusée.
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        conn.execute(
            "insert into public.reglages (groupe_id, organisation_id, version, contenu, proposition_id,"
            " corrections) values (%s, %s, 4, %s, %s, 0)",
            (monde["groupe"], monde["org"], Jsonb({"groupe": "ALPHAMARK", "tete": TETE}), uuid.uuid4()),
        )
    conn.rollback()


def test_groupe_d_une_autre_organisation_introuvable(
    conn: Connexion, monde: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    client = ClientSimule(reponse("tool_calls", outil(PROPOSITION)))
    monkeypatch.setattr(job, "client_ia", lambda: client)
    statut, ident = lancer(conn, monde["autre"], {"groupe_id": str(monde["groupe"])})
    assert statut == "echec"
    assert client.requetes == []  # l'IA n'a pas été appelée
    erreur = conn.execute("select erreur from public.travaux where id = %s", (ident,)).fetchone()
    nb = conn.execute(
        "select count(*) from public.reglages where groupe_id = %s and origine = 'proposition'",
        (monde["groupe"],),
    ).fetchone()
    conn.commit()
    assert erreur == ("échec du travail (PropositionEnEchec)",)
    assert nb == (0,)


@pytest.mark.parametrize("parametres", [{}, {"groupe_id": "pas-un-uuid"}])
def test_parametres_invalides(conn: Connexion, monde: dict[str, Any], parametres: dict[str, Any]) -> None:
    assert lancer(conn, monde["org"], parametres)[0] == "echec"


def test_sans_cle_api_le_travail_echoue(
    conn: Connexion, monde: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ia.VARIABLE_MODELE, "modele-test")
    monkeypatch.delenv(ia.VARIABLE_CLE_API, raising=False)
    statut, ident = lancer(conn, monde["org"], {"groupe_id": str(monde["groupe"])})
    erreur = conn.execute("select erreur from public.travaux where id = %s", (ident,)).fetchone()
    conn.commit()
    assert statut == "echec"
    assert erreur == ("échec du travail (CleIaManquante)",)


def test_sans_modele_le_travail_echoue_sans_appel(
    conn: Connexion, monde: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """T038 : pas de modèle par défaut. Sans CARTOFR_MODELE_IA, aucun appel à l'IA."""
    client = ClientSimule()
    monkeypatch.setattr(job, "client_ia", lambda: client)
    monkeypatch.delenv(ia.VARIABLE_MODELE, raising=False)
    statut, ident = lancer(conn, monde["org"], {"groupe_id": str(monde["groupe"])})
    erreur = conn.execute("select erreur from public.travaux where id = %s", (ident,)).fetchone()
    conn.commit()
    assert statut == "echec"
    assert erreur == ("échec du travail (ModeleIaManquant)",)
    assert client.requetes == []
