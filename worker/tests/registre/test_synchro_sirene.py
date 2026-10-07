"""Synchro SIRENE : client de l'API (sans réseau, httpx.MockTransport) et application au registre.

Les réponses d'API sont générées (`tests/fixtures/sirene/`) : SIREN factices,
noms de sociétés inventés, aucun nom de personne (règle produit 6).
"""

from __future__ import annotations

import copy
import json
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
import httpx
import pytest

from cartofr.registre import synchro_sirene
from cartofr.registre.schema import creer_tables
from cartofr.registre.synchro_sirene import (
    CHAMPS_ETABLISSEMENTS,
    CHAMPS_UNITES,
    Bilan,
    CleManquante,
    Client,
    ErreurSirene,
    Limiteur,
    appliquer_unites,
    lignes_sieges,
    synchroniser,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "sirene"
JOUR = date(2026, 10, 5)
DEBUT = date(2026, 3, 4)
CLE_FACTICE = "cle-FAKE"

# Champs de personne physique de l'API Sirene : jamais demandés, jamais stockés.
CHAMPS_PERSONNE = {
    "nomUniteLegale",
    "nomUsageUniteLegale",
    "prenom1UniteLegale",
    "prenom2UniteLegale",
    "prenom3UniteLegale",
    "prenom4UniteLegale",
    "prenomUsuelUniteLegale",
    "pseudonymeUniteLegale",
    "sexeUniteLegale",
}


def fixture(nom: str) -> dict[str, Any]:
    return json.loads((FIXTURES / nom).read_text(encoding="utf-8"))


class Horloge:
    """Horloge simulée : `dormir` avance le temps au lieu d'attendre."""

    def __init__(self) -> None:
        self.t = 0.0
        self.siestes: list[float] = []

    def maintenant(self) -> float:
        return self.t

    def dormir(self, secondes: float) -> None:
        self.siestes.append(secondes)
        self.t += secondes


class FauxSirene:
    """Serveur Sirene factice : rend les fixtures selon le chemin et le curseur, garde les appels."""

    def __init__(
        self,
        unites: dict[str, dict[str, Any]] | None = None,
        sieges: dict[str, dict[str, Any]] | None = None,
        codes: list[int] | None = None,
    ) -> None:
        self.unites = (
            unites
            if unites is not None
            else {"*": fixture("unites_page1.json"), "CURSEUR-2": fixture("unites_page2.json")}
        )
        self.sieges = sieges if sieges is not None else {"*": fixture("sieges_page1.json")}
        self.codes = list(codes or [])  # codes à rendre avant les réponses normales
        self.appels: list[httpx.Request] = []

    def __call__(self, requete: httpx.Request) -> httpx.Response:
        self.appels.append(requete)
        if self.codes:
            code = self.codes.pop(0)
            return httpx.Response(code, headers={"Retry-After": "7"} if code == 429 else {})
        pages = self.unites if requete.url.path.endswith("/siren") else self.sieges
        page = pages.get(requete.url.params["curseur"])
        if page is None:
            return httpx.Response(404, json={"header": {"statut": 404, "message": "Aucun élément trouvé"}})
        return httpx.Response(200, json=page)


def client(serveur: FauxSirene, horloge: Horloge | None = None, **options: Any) -> Client:
    h = horloge or Horloge()
    return Client(
        http=httpx.Client(transport=httpx.MockTransport(serveur)),
        cle=CLE_FACTICE,
        limiteur=Limiteur(horloge=h.maintenant, dormir=h.dormir),
        dormir=h.dormir,
        **options,
    )


@pytest.fixture
def con() -> duckdb.DuckDBPyConnection:
    """Un registre miniature : quatre sociétés, deux sièges."""
    c = duckdb.connect()
    creer_tables(c)
    c.execute(
        "insert into societes (siren, denomination, diffusion_commerciale, opposition_prospection,"
        " non_diffusible, etat_administratif, date_creation, debut) values"
        " ('000000001', 'SOCIETE ALPHA', true, false, false, 'A', '2001-01-01', $d),"
        " ('000000002', 'SOCIETE BETA', true, false, false, 'A', '2010-05-06', $d),"
        " ('000000003', 'SOCIETE GAMMA', true, false, false, 'A', '2015-07-08', $d),"
        " ('000000007', 'SOCIETE ZETA', true, false, false, 'C', '1990-01-01', $d)",
        {"d": DEBUT},
    )
    c.execute(
        "insert into sieges values"
        " ('000000001', '00000000100013', '3', 'RUE', 'ANCIENNE', '75002', 'PARIS 2',"
        "  '3 RUE ANCIENNE 75002', 'SOCIETE ALPHA', 5710, '70.10Z', '21'),"
        " ('000000002', '00000000200015', '1', 'AVENUE', 'DU TEST', '33000', 'BORDEAUX',"
        "  '1 AVENUE DU TEST 33000', 'SOCIETE BETA', 5499, '46.90Z', 'NN')"
    )
    return c


def societe(c: duckdb.DuckDBPyConnection, siren: str) -> dict[str, Any] | None:
    cur = c.execute(
        "select siren, denomination, non_diffusible, etat_administratif, date_creation, debut, fin,"
        " diffusion_commerciale from societes where siren = ?",
        [siren],
    )
    ligne = cur.fetchone()
    if ligne is None:
        return None
    return dict(zip([d[0] for d in cur.description], ligne, strict=True))


def instantane(c: duckdb.DuckDBPyConnection) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    return (
        c.execute("select * from societes order by siren").fetchall(),
        c.execute("select * from sieges order by siren").fetchall(),
    )


def journal_lignes(c: duckdb.DuckDBPyConnection) -> list[tuple[Any, ...]]:
    # Pas de colonne horodatée : leur lecture demande pytz, absent du worker.
    return c.execute(
        "select source, statut, ajoutes, fermes, erreur from mises_a_jour order by id"
    ).fetchall()


# --- C1 : création, modification, cessation ----------------------------------------


def test_creation_modification_cessation(con: duckdb.DuckDBPyConnection) -> None:
    bilan = synchroniser(con, JOUR, client(FauxSirene()))

    modifiee = societe(con, "000000001")
    assert modifiee is not None
    assert modifiee["date_creation"] == date(2001, 2, 3)  # 2001-01-01 avant
    assert modifiee["denomination"] == "SOCIETE ALPHA"  # la dénomination reste celle du RNE
    assert modifiee["fin"] is None

    cessee = societe(con, "000000002")
    assert cessee is not None
    assert cessee["etat_administratif"] == "C"
    assert cessee["fin"] == date(2026, 9, 30)  # début de la période cessée : fermée, pas supprimée

    creee = societe(con, "000000004")
    assert creee is not None
    assert (creee["denomination"], creee["etat_administratif"]) == ("SOCIETE DELTA NOUVELLE", "A")
    assert (creee["debut"], creee["fin"], creee["date_creation"]) == (JOUR, None, date(2026, 10, 1))
    assert creee["diffusion_commerciale"] is None  # donnée RNE, inconnue de SIRENE

    assert societe(con, "000000006") is None  # déjà cessée à son arrivée : pas une création
    deja_cessee = societe(con, "000000007")
    assert deja_cessee is not None and deja_cessee["fin"] is None  # non touchée

    assert (bilan.unites_lues, bilan.societes_ajoutees, bilan.societes_cessees) == (5, 1, 1)
    assert bilan.societes_modifiees == 3  # date de création, cessation, non-diffusion
    assert con.execute("select count(*) from societes").fetchone() == (5,)
    assert journal_lignes(con) == [("sirene", "succes", 2, 1, None)]


def test_cessation_jamais_avant_le_debut(con: duckdb.DuckDBPyConnection) -> None:
    unites = fixture("unites_page1.json")["unitesLegales"][1:2]
    unites[0]["periodesUniteLegale"][0]["dateDebut"] = "2001-01-01"  # avant DEBUT
    appliquer_unites(con, unites, JOUR, Bilan())
    cessee = societe(con, "000000002")
    assert cessee is not None and cessee["fin"] == DEBUT  # contrainte fin >= debut tenue


def test_reactivation_rouvre_la_societe(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("update societes set etat_administratif = 'C', fin = '2026-06-01' where siren = '000000001'")
    bilan = Bilan()
    appliquer_unites(con, fixture("unites_page1.json")["unitesLegales"][:1], JOUR, bilan)
    reactivee = societe(con, "000000001")
    assert reactivee is not None
    assert (reactivee["etat_administratif"], reactivee["fin"]) == ("A", None)
    assert bilan.societes_reactivees == 1


def test_sieges_mis_a_jour_comme_build_sieges(con: duckdb.DuckDBPyConnection) -> None:
    bilan = synchroniser(con, JOUR, client(FauxSirene()))
    sieges = {r[0]: r for r in con.execute("select * from sieges order by siren").fetchall()}
    assert sieges["000000001"] == (
        "000000001",
        "00000000100021",
        "12B",
        "RUE",
        "DES EXEMPLES",
        "75001",
        "PARIS 1",
        "12 RUE DES EXEMPLES 75001",
        "SOCIETE ALPHA",
        5710,
        "70.10Z",
        "21",
    )
    assert sieges["000000004"][7] == "ZI DE LA FORET FICTIVE 69001"
    # Siège fermé : rien n'est supprimé ni modifié. Siège non diffusible : ignoré.
    assert sieges["000000002"][7] == "1 AVENUE DU TEST 33000"
    assert "000000003" not in sieges
    assert (bilan.sieges_lus, bilan.sieges_modifies, bilan.sieges_ajoutes) == (3, 1, 1)
    assert bilan.sieges_inactifs_ignores == 1


def test_adresse_identique_a_la_requete_de_build_sieges() -> None:
    """`num` et `adresse_cle` reproduisent les expressions SQL de build_sieges.py."""
    cas = [
        ("12", "b", "RUE", "des Exemples", "75001"),
        (None, None, "ZI", "DE LA FORET", "69001"),
        ("5", None, None, "LIEU DIT", "01000"),
        (None, None, None, None, None),
    ]
    sql = duckdb.connect()
    for numero, indice, type_voie, voie, cp in cas:
        e = {
            "siren": "000000009",
            "siret": "00000000900010",
            "etablissementSiege": True,
            "statutDiffusionEtablissement": "O",
            "uniteLegale": {"etatAdministratifUniteLegale": "A", "categorieJuridiqueUniteLegale": "5710"},
            "adresseEtablissement": {
                "numeroVoieEtablissement": numero,
                "indiceRepetitionDernierNumeroVoieEtablissement": indice,
                "typeVoieEtablissement": type_voie,
                "libelleVoieEtablissement": voie,
                "codePostalEtablissement": cp,
            },
            "periodesEtablissement": [{"dateFin": None, "etatAdministratifEtablissement": "A"}],
        }
        ligne = lignes_sieges([e])[0]
        attendu = sql.execute(
            "select upper(trim(coalesce($n,'') || coalesce($i,''))),"
            " upper(trim(coalesce($n,'') || ' ' || coalesce($t,'') || ' ' || coalesce($v,'') || ' '"
            " || coalesce($c,'')))",
            {"n": numero, "i": indice, "t": type_voie, "v": voie, "c": cp},
        ).fetchone()
        assert (ligne["num"], ligne["adresse_cle"]) == attendu


# --- C2 : passage en non diffusible ------------------------------------------------


def test_passage_en_non_diffusible(con: duckdb.DuckDBPyConnection) -> None:
    bilan = synchroniser(con, JOUR, client(FauxSirene()))
    gamma = societe(con, "000000003")
    assert gamma is not None
    assert gamma["non_diffusible"] is True
    assert gamma["denomination"] == "SOCIETE GAMMA"  # le masque [ND] n'écrase rien
    assert gamma["fin"] is None  # marquée, jamais cachée ni fermée
    assert bilan.passages_non_diffusible == 1


# --- C3 : 30 requêtes par minute ----------------------------------------------------


def test_limiteur_30_requetes_par_minute() -> None:
    h = Horloge()
    limiteur = Limiteur(horloge=h.maintenant, dormir=h.dormir)
    instants = []
    for _ in range(61):
        limiteur.attendre()
        instants.append(h.t)
    assert instants[29] == 0.0  # les 30 premières partent tout de suite
    assert instants[30] >= 60.0  # la 31e attend la fin de la minute
    for i in range(len(instants) - 30):
        assert instants[i + 30] - instants[i] >= 60.0  # jamais 31 dans une même minute


def test_client_respecte_la_limite_sur_31_pages() -> None:
    pages = {}
    for i in range(31):
        courant, suivant = ("*" if i == 0 else f"C{i}"), f"C{i + 1}" if i < 30 else f"C{i}"
        page = copy.deepcopy(fixture("unites_page2.json"))
        page["header"].update(curseur=courant, curseurSuivant=suivant)
        pages[courant] = page
    h = Horloge()
    serveur = FauxSirene(unites=pages)
    lues = list(client(serveur, h).unites_du_jour(JOUR))
    assert len(lues) == 31 and len(serveur.appels) == 31
    assert h.t >= 60.0


# --- Client : pagination, 404, 429, erreurs ------------------------------------------


def test_pagination_par_curseur_et_parametres() -> None:
    serveur = FauxSirene()
    pages = list(client(serveur).unites_du_jour(JOUR))
    assert [len(p) for p in pages] == [3, 3]
    params = [a.url.params for a in serveur.appels]
    assert [p["curseur"] for p in params] == ["*", "CURSEUR-2"]
    assert all(p["nombre"] == "1000" for p in params)
    assert params[0]["q"] == (
        "dateDernierTraitementUniteLegale:[2026-10-05T00:00:00 TO 2026-10-05T23:59:59]"
        " AND -periode(categorieJuridiqueUniteLegale:1000)"
    )
    assert all(a.headers["X-INSEE-Api-Key-Integration"] == CLE_FACTICE for a in serveur.appels)


def test_jour_vide_en_404(con: duckdb.DuckDBPyConnection) -> None:
    avant = instantane(con)
    bilan = synchroniser(con, JOUR, client(FauxSirene(unites={}, sieges={})))
    assert (bilan.unites_lues, bilan.sieges_lus, bilan.requetes) == (0, 0, 2)
    assert instantane(con) == avant
    assert journal_lignes(con) == [("sirene", "succes", 0, 0, None)]


def test_429_attend_retry_after_puis_reprend() -> None:
    h = Horloge()
    serveur = FauxSirene(codes=[429])
    pages = list(client(serveur, h).unites_du_jour(JOUR))
    assert len(pages) == 2 and len(serveur.appels) == 3
    assert 7.0 in h.siestes


def test_429_persistant_est_une_erreur() -> None:
    with pytest.raises(ErreurSirene, match="429"):
        list(client(FauxSirene(codes=[429] * 10), essais=2).unites_du_jour(JOUR))


def test_cle_refusee_ne_cite_pas_la_cle() -> None:
    with pytest.raises(ErreurSirene) as erreur:
        list(client(FauxSirene(codes=[401])).unites_du_jour(JOUR))
    assert "INSEE_API_KEY" in str(erreur.value) and CLE_FACTICE not in str(erreur.value)


def test_cle_manquante(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INSEE_API_KEY", raising=False)
    c = Client(http=httpx.Client(transport=httpx.MockTransport(FauxSirene())))
    with pytest.raises(CleManquante, match="INSEE_API_KEY"):
        list(c.unites_du_jour(JOUR))


# --- Transaction et journal --------------------------------------------------------


def test_panne_reseau_registre_inchange(con: duckdb.DuckDBPyConnection) -> None:
    # La 1re page passe, la 2e tombe en 503 à chaque essai.
    serveur = FauxSirene(unites={"*": fixture("unites_page1.json")})
    avant = instantane(con)

    def panne(requete: httpx.Request) -> httpx.Response:
        if requete.url.params["curseur"] == "CURSEUR-2":
            return httpx.Response(503)
        return serveur(requete)

    c = client(serveur, essais=1)
    c.http = httpx.Client(transport=httpx.MockTransport(panne))
    with pytest.raises(ErreurSirene, match="503"):
        synchroniser(con, JOUR, c)
    assert instantane(con) == avant
    assert journal_lignes(con) == [("sirene", "echec", None, None, "Erreur Sirene 503 après 1 essais.")]


def test_erreur_pendant_l_application_annule_tout(
    con: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    avant = instantane(con)

    def casse(*_: Any) -> None:
        raise RuntimeError("valeur 000000001 SOCIETE ALPHA")  # un message qui citerait des données

    monkeypatch.setattr(synchro_sirene, "appliquer_sieges", casse)
    with pytest.raises(RuntimeError):
        synchroniser(con, JOUR, client(FauxSirene()))
    assert instantane(con) == avant  # les sociétés déjà modifiées sont annulées aussi
    assert journal_lignes(con) == [
        ("sirene", "echec", None, None, "RuntimeError pendant la synchro SIRENE")  # le type seul
    ]


def test_meme_jour_deux_fois_ne_change_rien(con: duckdb.DuckDBPyConnection) -> None:
    synchroniser(con, JOUR, client(FauxSirene()))
    apres_un = instantane(con)
    bilan = synchroniser(con, JOUR, client(FauxSirene()))
    assert instantane(con) == apres_un
    assert (bilan.societes_modifiees, bilan.societes_ajoutees, bilan.societes_cessees) == (0, 0, 0)
    assert (bilan.societes_reactivees, bilan.passages_non_diffusible) == (0, 0)
    assert (bilan.sieges_modifies, bilan.sieges_ajoutes) == (0, 0)
    assert journal_lignes(con)[-1] == ("sirene", "succes", 0, 0, None)


# --- Données personnelles ----------------------------------------------------------


def test_aucun_champ_de_personne_demande() -> None:
    serveur = FauxSirene()
    c = client(serveur)
    list(c.unites_du_jour(JOUR))
    list(c.sieges_du_jour(JOUR))
    for appel in serveur.appels:
        champs = set(appel.url.params["champs"].split(","))
        assert champs in (set(CHAMPS_UNITES), set(CHAMPS_ETABLISSEMENTS))
        assert not champs & CHAMPS_PERSONNE
    q_sieges = serveur.appels[-1].url.params["q"]
    assert "etablissementSiege:true" in q_sieges and "-categorieJuridiqueUniteLegale:1000" in q_sieges


def test_entrepreneur_individuel_jamais_ecrit(con: duckdb.DuckDBPyConnection) -> None:
    # Même si l'API en rendait un malgré le filtre de la requête.
    sieges = copy.deepcopy(fixture("sieges_page1.json"))
    ei = copy.deepcopy(sieges["etablissements"][1])
    ei["siren"], ei["uniteLegale"]["categorieJuridiqueUniteLegale"] = "000000005", "1000"
    sieges["etablissements"].append(ei)
    synchroniser(con, JOUR, client(FauxSirene(sieges={"*": sieges})))
    assert societe(con, "000000005") is None
    assert con.execute("select count(*) from sieges where siren = '000000005' or cj = 1000").fetchone() == (
        0,
    )


# --- unites_legales (T013) : la recherche des marques suit SIRENE --------------------------


def unite(
    siren: str, cj: str | None = "5710", etat: str = "A", statut: str = "O", **champs: str | None
) -> dict[str, Any]:
    """Une unité légale brute de l'API, avec les champs de `CHAMPS_UNITES` seulement."""
    periode = {
        "dateFin": None,
        "dateDebut": "2020-01-01",
        "etatAdministratifUniteLegale": etat,
        "denominationUniteLegale": champs.get("denomination", f"SOCIETE {siren}"),
        "categorieJuridiqueUniteLegale": cj,
        "denominationUsuelle1UniteLegale": champs.get("du1"),
        "denominationUsuelle2UniteLegale": None,
        "denominationUsuelle3UniteLegale": None,
        "activitePrincipaleUniteLegale": champs.get("naf", "70.10Z"),
    }
    return {
        "siren": siren,
        "statutDiffusionUniteLegale": statut,
        "dateCreationUniteLegale": "2001-01-01",
        "sigleUniteLegale": champs.get("sigle"),
        "trancheEffectifsUniteLegale": champs.get("tranche", "11"),
        "periodesUniteLegale": [periode],
    }


def unites_legales(c: duckdb.DuckDBPyConnection) -> dict[str, tuple[Any, ...]]:
    lignes = c.execute(
        "select siren, denomination, sigle, denomination_usuelle_1, categorie_juridique, naf,"
        " tranche_effectifs, etat_administratif, debut, fin from unites_legales order by siren"
    ).fetchall()
    return {ligne[0]: ligne[1:] for ligne in lignes}


@pytest.fixture
def con_ul(con: duckdb.DuckDBPyConnection) -> duckdb.DuckDBPyConnection:
    """Le registre miniature, avec deux unités légales issues du stock."""
    con.execute(
        "insert into unites_legales values"
        " ('000000001', 'SOCIETE ALPHA', 'VIEUX', 'ENSEIGNE ALPHA', null, null, 5710, '70.10Z', '11', 'A',"
        "  $d, null),"
        " ('000000003', 'SOCIETE GAMMA', 'SG', 'ENSEIGNE GAMMA', null, null, 5710, '68.20B', '12', 'A',"
        "  $d, null)",
        {"d": DEBUT},
    )
    return con


def test_unites_legales_mises_a_jour_et_ajoutees(con_ul: duckdb.DuckDBPyConnection) -> None:
    lot = [
        unite("000000001", denomination="SOCIETE ALPHA", sigle="SA1", naf="70.22Z", tranche="21"),
        # Non diffusible : valeurs masquées, la valeur connue reste.
        unite(
            "000000003", statut="P", denomination="[ND]", sigle="[ND]", du1="[ND]", naf="68.20B", tranche="12"
        ),
        unite("000000004", denomination="SOCIETE DELTA", sigle="SD"),
        unite("000000006", etat="C", denomination="SOCIETE CESSEE"),  # cessée : entre, comme au stock
    ]
    bilan = Bilan()
    appliquer_unites(con_ul, lot, JOUR, bilan)
    ul = unites_legales(con_ul)
    # Diffusible : la fiche fait foi, une enseigne retirée est vidée.
    assert ul["000000001"] == ("SOCIETE ALPHA", "SA1", None, 5710, "70.22Z", "21", "A", DEBUT, None)
    assert ul["000000003"] == (
        "SOCIETE GAMMA",
        "SG",
        "ENSEIGNE GAMMA",
        5710,
        "68.20B",
        "12",
        "A",
        DEBUT,
        None,
    )
    assert ul["000000004"] == ("SOCIETE DELTA", "SD", None, 5710, "70.10Z", "11", "A", JOUR, None)
    assert ul["000000006"][6:] == ("C", JOUR, None)
    assert (bilan.unites_legales_modifiees, bilan.unites_legales_ajoutees) == (1, 2)

    # Rejouer le même lot ne change rien.
    bilan = Bilan()
    appliquer_unites(con_ul, lot, JOUR, bilan)
    assert unites_legales(con_ul) == ul
    assert (bilan.unites_legales_modifiees, bilan.unites_legales_ajoutees) == (0, 0)


def test_unites_legales_cessation_sans_rien_vider(con_ul: duckdb.DuckDBPyConnection) -> None:
    appliquer_unites(con_ul, [unite("000000001", cj=None, etat="C", denomination=None)], JOUR, Bilan())
    ligne = unites_legales(con_ul)["000000001"]
    # Nom et catégorie gardés, cessation lue dans l'état ; la ligne n'est ni fermée ni supprimée.
    assert (ligne[0], ligne[3], ligne[6], ligne[8]) == ("SOCIETE ALPHA", 5710, "C", None)


def test_unites_legales_jamais_d_entrepreneur_individuel(con_ul: duckdb.DuckDBPyConnection) -> None:
    lot = [unite("000000005", cj="1000"), unite("000000008", cj=None), unite("000000009", cj="abc")]
    bilan = Bilan()
    appliquer_unites(con_ul, lot, JOUR, bilan)
    assert set(unites_legales(con_ul)) == {"000000001", "000000003"}
    assert bilan.unites_legales_ajoutees == 0


def test_unites_legales_par_la_synchro(con_ul: duckdb.DuckDBPyConnection) -> None:
    synchroniser(con_ul, JOUR, client(FauxSirene()))
    ul = unites_legales(con_ul)
    # Fixtures : 002, 004 et 006 (cessée) entrent ; 005 est un entrepreneur individuel.
    assert set(ul) == {"000000001", "000000002", "000000003", "000000004", "000000006"}
    assert ul["000000004"][0] == "SOCIETE DELTA NOUVELLE" and ul["000000004"][7] == JOUR
    assert ul["000000003"][0] == "SOCIETE GAMMA"  # [ND] n'écrase pas le nom
    assert con_ul.execute(
        "select count(*) from unites_legales where categorie_juridique = 1000"
    ).fetchone() == (0,)


def test_unites_legales_annulees_avec_le_reste(
    con_ul: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    avant = unites_legales(con_ul)

    def casse(*_: Any) -> None:
        raise RuntimeError("panne simulée")

    monkeypatch.setattr(synchro_sirene, "appliquer_sieges", casse)
    with pytest.raises(RuntimeError):
        synchroniser(con_ul, JOUR, client(FauxSirene()))
    assert unites_legales(con_ul) == avant


def test_champs_des_unites_legales_demandes_sans_personne() -> None:
    attendus = {
        "sigleUniteLegale",
        "denominationUsuelle1UniteLegale",
        "denominationUsuelle2UniteLegale",
        "denominationUsuelle3UniteLegale",
        "activitePrincipaleUniteLegale",
        "trancheEffectifsUniteLegale",
    }
    assert attendus <= set(CHAMPS_UNITES)
    assert not set(CHAMPS_UNITES) & CHAMPS_PERSONNE
