"""Travail `carto` : lancer le moteur depuis la file et enregistrer le résultat (T021).

Vérifie : refus d'une version de réglages non validée (C1) ; chaque ligne
`carto_*` porte l'`organisation_id` du travail (C2) ; date des données et durée
enregistrées (C3) ; tête sans lien réduite à la tête avec un avertissement
(C4). Plus : familles exclues par empreinte lues en base, aucun nom de
personne écrit (garde-fou 6), échecs avec un message français sûr et sans
ligne à moitié écrite, carto d'une autre organisation introuvable.

Prérequis : supabase/migrations/ appliqué, DATABASE_URL vers la base (rôle
postgres). Chaque test crée ses organisations (noms marqués) et les supprime
à la fin : la cascade emporte groupes, réglages, cartos, résultats et
travaux. Le registre est un mini-registre fabriqué (noms inventés, règle
produit 6), écrit dans tmp_path.

Sans DATABASE_URL : tests base ignorés en local, échec en CI (variable CI).
"""

import os
import sys
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
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
from cartofr.empreinte import VARIABLE_CLE, empreinte  # noqa: E402
from cartofr.jobs import TRAVAUX  # noqa: E402
from cartofr.jobs import carto as job  # noqa: E402
from cartofr.jobs.synchro import RNE, SIRENE, Jours  # noqa: E402
from cartofr.moteur import cartographier  # noqa: E402
from cartofr.registre.construire import DATE_STOCK  # noqa: E402
from cartofr.reglages import valider  # noqa: E402
from cartofr.travaux import Travail  # noqa: E402

Connexion = psycopg.Connection[tuple[Any, ...]]

TETE = siren(1)
F1, F2, X = siren(10), siren(11), siren(50)
ADRESSE_GROUPE = "1 PLACE DU GROUPE INVENTE 75008"
FAMILLE = "FAMILLEINVENTEE"
CLE = "cle-de-test-FAKE"
MARQUEUR = "test_t021"

CONTENU: dict[str, Any] = {"groupe": "TEST T021", "tete": TETE, "marques_sures": ["Alphamark"]}


# --- Registre fabriqué ------------------------------------------------------------------------


def registre_groupe() -> MiniRegistre:
    """Une tête, une filiale présidée, sa sous-filiale, une société de marque, et une holding
    familiale qui n'entre que par ses dirigeants communs avec la tête."""
    mini = MiniRegistre()
    mini.societe(TETE, "TETE INVENTEE", naf="70.10Z", tranche="22", adresse=ADRESSE_GROUPE)
    mini.societe(F1, "FILIALE INVENTEE UN", adresse=ADRESSE_GROUPE, diffusion_commerciale=False)
    mini.lien(TETE, F1, PRESIDENT)
    mini.societe(F2, "ALPHAMARK SERVICES")
    mini.lien(F1, F2, PRESIDENT)
    mini.societe(X, "HOLDING PATRIMONIALE INVENTEE", naf="64.20Z", adresse=ADRESSE_GROUPE)
    for i in (1, 2):
        mini.dirigeant(TETE, personne(i, famille=FAMILLE))
        mini.dirigeant(X, personne(i, famille=FAMILLE))
    mini.dirigeants_communs(F1, F2, premier=3)  # « PERSONNE INVENTEE » : jamais écrite
    return mini


def registre_tete_seule() -> MiniRegistre:
    mini = MiniRegistre()
    mini.societe(TETE, "TETE INVENTEE", naf="70.10Z", tranche="22")
    mini.dirigeant(TETE, personne(1))
    return mini


@pytest.fixture
def donnees(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Le dossier CARTOFR_DATA du test (vide : à remplir avec `ecrire`)."""
    dossier = tmp_path / "data"
    dossier.mkdir()
    monkeypatch.setenv("CARTOFR_DATA", str(dossier))
    monkeypatch.setenv(VARIABLE_CLE, CLE)
    return dossier


def ecrire(mini: MiniRegistre, donnees: Path) -> Path:
    return mini.ecrire(donnees / "registre.duckdb")


# --- Base ----------------------------------------------------------------------------------------


@pytest.fixture
def conn() -> Iterator[Connexion]:
    if not os.environ.get(VARIABLE_URL):
        message = (
            f"{VARIABLE_URL} n'est pas définie : le travail carto écrit dans la base. "
            "Démarrer la base locale (infra/README.md), appliquer les migrations, puis exporter DATABASE_URL."
        )
        if os.environ.get("CI"):
            pytest.fail(message)
        pytest.skip(message)
    connexion = connecter()
    if connexion.execute("select to_regclass('public.carto_societes')").fetchone() == (None,):
        connexion.close()
        pytest.fail("Table carto_societes absente : appliquer supabase/migrations/.")
    try:
        yield connexion
    finally:
        connexion.close()


@dataclass(frozen=True)
class Monde:
    conn: Connexion
    org: uuid.UUID
    autre_org: uuid.UUID
    groupe: uuid.UUID


def _un(conn: Connexion, requete: Any, params: tuple[Any, ...]) -> Any:
    ligne = conn.execute(requete, params).fetchone()
    assert ligne is not None
    return ligne[0]


@pytest.fixture
def monde(conn: Connexion) -> Iterator[Monde]:
    """Deux organisations de test, un groupe dans la première ; tout est supprimé à la fin."""
    marque = f"{MARQUEUR} {uuid.uuid4().hex}"
    org = _un(conn, "insert into public.organisations (nom) values (%s) returning id", (marque + " A",))
    autre = _un(conn, "insert into public.organisations (nom) values (%s) returning id", (marque + " B",))
    groupe = _un(
        conn,
        "insert into public.groupes (organisation_id, tete_siren, nom)"
        " values (%s, %s, 'TEST T021') returning id",
        (org, TETE),
    )
    conn.commit()
    try:
        yield Monde(conn, org, autre, groupe)
    finally:
        conn.rollback()
        conn.execute("delete from public.organisations where id in (%s, %s)", (org, autre))
        conn.commit()


def creer_reglages(m: Monde, contenu: dict[str, Any], *, valide: bool = True, version: int = 1) -> uuid.UUID:
    ident = _un(
        m.conn,
        "insert into public.reglages (groupe_id, organisation_id, version, contenu, valide_le)"
        " values (%s, %s, %s, %s, case when %s then now() end) returning id",
        (m.groupe, m.org, version, Jsonb(contenu), valide),
    )
    m.conn.commit()
    return ident


def creer_carto(m: Monde, reglages_id: uuid.UUID, *, contourner_declencheur: bool = False) -> uuid.UUID:
    """Une carto en attente. `contourner_declencheur` : sur une version non validée, que le
    déclencheur refuse ; désactivé le temps de cette seule transaction (C1 côté worker)."""
    if contourner_declencheur:
        m.conn.execute("alter table public.cartos disable trigger cartos_reglages_valides")
    ident = _un(
        m.conn,
        "insert into public.cartos (organisation_id, groupe_id, reglages_id)"
        " values (%s, %s, %s) returning id",
        (m.org, m.groupe, reglages_id),
    )
    if contourner_declencheur:
        m.conn.execute("alter table public.cartos enable trigger cartos_reglages_valides")
    m.conn.commit()
    return ident


def creer_travail(m: Monde, carto_id: uuid.UUID | str, org: uuid.UUID | None = None) -> Travail:
    """Un travail `carto` déjà pris (en_cours), comme après `travaux.prendre`."""
    org = org or m.org
    parametres = {"carto_id": str(carto_id)}
    ident = _un(
        m.conn,
        "insert into public.travaux (type, organisation_id, parametres, statut, debut_le)"
        " values ('carto', %s, %s, 'en_cours', now()) returning id",
        (org, Jsonb(parametres)),
    )
    m.conn.commit()
    return Travail(id=ident, type="carto", organisation_id=org, parametres=parametres)


def lancer(m: Monde, carto_id: uuid.UUID, org: uuid.UUID | None = None) -> tuple[str, Travail]:
    t = creer_travail(m, carto_id, org)
    return travaux.executer(m.conn, t), t


def lire_carto(m: Monde, carto_id: uuid.UUID) -> dict[str, Any]:
    cur = m.conn.execute(
        "select statut, travail_id, date_donnees, fin_le, duree_ms, avertissement from public.cartos"
        " where id = %s",
        (carto_id,),
    )
    noms = [d.name for d in cur.description or []]
    ligne = cur.fetchone()
    m.conn.commit()
    assert ligne is not None
    return dict(zip(noms, ligne, strict=True))


def lire_travail(m: Monde, ident: int) -> dict[str, Any]:
    ligne = m.conn.execute("select statut, erreur from public.travaux where id = %s", (ident,)).fetchone()
    m.conn.commit()
    assert ligne is not None
    return {"statut": ligne[0], "erreur": ligne[1]}


def societes(m: Monde, carto_id: uuid.UUID) -> dict[str, dict[str, Any]]:
    cur = m.conn.execute("select * from public.carto_societes where carto_id = %s", (carto_id,))
    noms = [d.name for d in cur.description or []]
    lignes = {r[noms.index("siren")]: dict(zip(noms, r, strict=True)) for r in cur.fetchall()}
    m.conn.commit()
    return lignes


def liens(m: Monde, carto_id: uuid.UUID) -> list[dict[str, Any]]:
    cur = m.conn.execute("select * from public.carto_liens where carto_id = %s", (carto_id,))
    noms = [d.name for d in cur.description or []]
    lignes = [dict(zip(noms, r, strict=True)) for r in cur.fetchall()]
    m.conn.commit()
    return lignes


# --- Sans base ------------------------------------------------------------------------------------


def test_type_carto_enregistre() -> None:
    assert TRAVAUX["carto"] is job.travail_carto


def test_c1_version_non_validee_refusee_sans_base() -> None:
    with pytest.raises(job.CartoEnEchec) as e:
        job.verifier_reglages(None, CONTENU)
    assert str(e.value) == job.NON_VALIDEE


@pytest.mark.parametrize(
    "contenu",
    [
        pytest.param(CONTENU | {"familles_exclues": ["Inventee"]}, id="famille_en_clair"),
        pytest.param({"groupe": "TEST"}, id="tete_absente"),
        pytest.param(["pas", "un", "objet"], id="pas_un_objet"),
    ],
)
def test_reglages_valides_mais_illisibles_refuses_sans_recopier(contenu: Any) -> None:
    with pytest.raises(job.CartoEnEchec) as e:
        job.verifier_reglages(datetime(2026, 10, 7), contenu)
    assert str(e.value) == job.REGLAGES_ILLISIBLES
    assert "Inventee" not in str(e.value)


def test_avertissement_frais_et_complet_vide(tmp_path: Path) -> None:
    mini = registre_groupe()
    carto = cartographier(valider(CONTENU).model_dump(), mini.ecrire(tmp_path / "r.duckdb"))
    assert job.avertissement(carto, date(2026, 10, 1), date(2026, 10, 8)) is None  # 7 jours : à l'heure
    vieux = job.avertissement(carto, date(2026, 3, 4), date(2026, 10, 7))
    assert vieux is not None and "04/03/2026" in vieux and "7 jours" in vieux


# --- C1 : version non validée -----------------------------------------------------------------------


def test_c1_version_non_validee_refusee(monde: Monde, donnees: Path) -> None:
    ecrire(registre_groupe(), donnees)
    brouillon = creer_reglages(monde, CONTENU, valide=False)
    carto_id = creer_carto(monde, brouillon, contourner_declencheur=True)

    statut, t = lancer(monde, carto_id)

    assert statut == "echec"
    c = lire_carto(monde, carto_id)
    assert c["statut"] == "echec"
    assert c["avertissement"] == job.NON_VALIDEE
    assert c["fin_le"] is not None and c["travail_id"] == t.id
    assert societes(monde, carto_id) == {} and liens(monde, carto_id) == []
    assert lire_travail(monde, t.id) == {"statut": "echec", "erreur": "échec du travail (CartoEnEchec)"}


def test_c1_declencheur_refuse_aussi_une_carto_non_validee(monde: Monde) -> None:
    """Le refus a deux étages : la base refuse déjà l'insertion (T018)."""
    brouillon = creer_reglages(monde, CONTENU, valide=False)
    with pytest.raises(psycopg.errors.CheckViolation):
        creer_carto(monde, brouillon)
    monde.conn.rollback()


# --- C2 et C3 : résultat complet, organisation, date, durée ------------------------------------------


def test_c2_c3_resultat_ecrit_avec_l_organisation_la_date_et_la_duree(monde: Monde, donnees: Path) -> None:
    registre = ecrire(registre_groupe(), donnees)
    carto_id = creer_carto(monde, creer_reglages(monde, CONTENU))
    attendu = cartographier(valider(CONTENU).model_dump(), registre)

    statut, t = lancer(monde, carto_id)

    assert statut == "termine"
    assert lire_travail(monde, t.id) == {"statut": "termine", "erreur": None}
    c = lire_carto(monde, carto_id)
    assert c["statut"] == "terminee" and c["travail_id"] == t.id
    # C3 : sans fichier de synchro, la date du stock ; la durée du calcul.
    assert c["date_donnees"] == DATE_STOCK
    assert c["duree_ms"] is not None and c["duree_ms"] >= 0 and c["fin_le"] is not None
    assert c["avertissement"] is not None and "04/03/2026" in c["avertissement"]  # stock vieux de 7 mois

    s, li = societes(monde, carto_id), liens(monde, carto_id)
    # C2 : chaque ligne porte l'organisation du travail.
    assert {r["organisation_id"] for r in s.values()} == {monde.org}
    assert {r["organisation_id"] for r in li} == {monde.org}
    # Tout le résultat du moteur, rien de plus.
    assert set(s) == {x.siren for x in attendu.societes} == {TETE, F1, F2, X}
    assert {(r["parent_siren"], r["enfant_siren"], r["role"]) for r in li} == {
        (x.parent, x.enfant, x.role) for x in attendu.liens
    }
    tete, f1, f2 = s[TETE], s[F1], s[F2]
    assert tete["niveau"] == 0 and tete["maison_mere_siren"] is None and tete["confiance"] is None
    assert tete["preuve"] == "Tête du groupe"
    assert f1["maison_mere_siren"] == TETE and f1["confiance"] == "A" and f1["niveau"] == 1
    assert f1["preuve"].startswith("Mandat au registre : Président")
    assert "entrée dans le groupe : mandat fort au registre" in f1["preuve"]
    assert f2["maison_mere_siren"] == F1 and f2["niveau"] == 2
    # Opposition à la prospection : marquée, jamais cachée.
    assert f1["opposition_prospection"] is True and f2["opposition_prospection"] is False
    assert all(r["non_diffusible"] is False for r in s.values())
    assert all(r["preuve"] and r["confiance"] == "A" for r in li)


def test_c3_date_des_donnees_la_plus_ancienne_des_synchros(monde: Monde, donnees: Path) -> None:
    ecrire(registre_groupe(), donnees)
    jours = Jours(donnees / "synchro" / "jours.json", "")  # registre fabriqué : aucune construction
    jours.noter(RNE, date(2026, 10, 5))
    jours.noter(SIRENE, date(2026, 10, 3))
    carto_id = creer_carto(monde, creer_reglages(monde, CONTENU))

    lancer(monde, carto_id)

    assert lire_carto(monde, carto_id)["date_donnees"] == date(2026, 10, 3)


def test_c2_carto_d_une_autre_organisation_introuvable(monde: Monde, donnees: Path) -> None:
    """Un travail de B ne lit ni n'écrit la carto de A, même en rôle service."""
    ecrire(registre_groupe(), donnees)
    carto_id = creer_carto(monde, creer_reglages(monde, CONTENU))

    statut, _ = lancer(monde, carto_id, org=monde.autre_org)

    assert statut == "echec"
    c = lire_carto(monde, carto_id)
    assert c["statut"] == "en_attente" and c["avertissement"] is None and c["travail_id"] is None
    assert societes(monde, carto_id) == {}


def test_carto_deja_prise_par_un_autre_travail_intacte(monde: Monde, donnees: Path) -> None:
    ecrire(registre_groupe(), donnees)
    carto_id = creer_carto(monde, creer_reglages(monde, CONTENU))
    premier = creer_travail(monde, carto_id)
    monde.conn.execute("update public.cartos set travail_id = %s where id = %s", (premier.id, carto_id))
    monde.conn.commit()

    statut, _ = lancer(monde, carto_id)

    assert statut == "echec"
    c = lire_carto(monde, carto_id)
    assert c["statut"] == "en_attente" and c["travail_id"] == premier.id and c["avertissement"] is None


# --- C4 : tête sans lien -----------------------------------------------------------------------------


def test_c4_tete_sans_lien_reduite_a_la_tete_avec_avertissement(monde: Monde, donnees: Path) -> None:
    ecrire(registre_tete_seule(), donnees)
    carto_id = creer_carto(monde, creer_reglages(monde, CONTENU))

    statut, _ = lancer(monde, carto_id)

    assert statut == "termine"
    c = lire_carto(monde, carto_id)
    assert c["statut"] == "terminee"
    assert c["avertissement"] is not None and job.TETE_SEULE in c["avertissement"]
    s = societes(monde, carto_id)
    assert list(s) == [TETE] and s[TETE]["niveau"] == 0 and s[TETE]["organisation_id"] == monde.org
    assert liens(monde, carto_id) == []


def test_avertissement_tete_seule_absent_quand_le_groupe_a_des_filiales(monde: Monde, donnees: Path) -> None:
    ecrire(registre_groupe(), donnees)
    carto_id = creer_carto(monde, creer_reglages(monde, CONTENU))
    lancer(monde, carto_id)
    assert job.TETE_SEULE not in (lire_carto(monde, carto_id)["avertissement"] or "")


# --- Familles exclues par empreinte, lues en base ------------------------------------------------------


@pytest.mark.parametrize("exclue", [False, True])
def test_famille_exclue_par_empreinte_depuis_les_reglages(monde: Monde, donnees: Path, exclue: bool) -> None:
    """La holding de la famille entre par ses dirigeants communs ; l'empreinte du nom l'écarte."""
    ecrire(registre_groupe(), donnees)
    contenu = CONTENU | {"familles_exclues_empreintes": [empreinte(FAMILLE, CLE)] if exclue else []}
    carto_id = creer_carto(monde, creer_reglages(monde, contenu))

    statut, _ = lancer(monde, carto_id)

    assert statut == "termine"
    assert (X in societes(monde, carto_id)) is not exclue


def test_empreintes_sans_cle_echec_clair(
    monde: Monde, donnees: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ecrire(registre_groupe(), donnees)
    monkeypatch.delenv(VARIABLE_CLE)
    contenu = CONTENU | {"familles_exclues_empreintes": [empreinte(FAMILLE, CLE)]}
    carto_id = creer_carto(monde, creer_reglages(monde, contenu))

    statut, _ = lancer(monde, carto_id)

    assert statut == "echec"
    c = lire_carto(monde, carto_id)
    assert c["statut"] == "echec" and c["avertissement"] == job.CLE_MANQUANTE
    assert societes(monde, carto_id) == {}


# --- Garde-fou 6 : aucun nom de personne écrit -----------------------------------------------------------


def test_aucun_nom_de_personne_dans_le_resultat(monde: Monde, donnees: Path) -> None:
    mini = registre_groupe()
    ecrire(mini, donnees)
    carto_id = creer_carto(monde, creer_reglages(monde, CONTENU))
    lancer(monde, carto_id)

    morceaux = {m for _, cle, _, _ in mini.dirigeants for m in cle.split("|")[:2] if m}
    assert morceaux  # le registre a bien des dirigeants personnes
    textes = [
        str(v)
        for ligne in [*societes(monde, carto_id).values(), *liens(monde, carto_id)]
        for v in ligne.values()
        if isinstance(v, str)
    ]
    textes.append(lire_carto(monde, carto_id)["avertissement"] or "")
    assert textes
    assert not [m for m in morceaux for t in textes if m in t.upper()]


# --- Échecs : message sûr, rien d'écrit à moitié -----------------------------------------------------------


def test_registre_absent_echec_clair(monde: Monde, donnees: Path) -> None:
    carto_id = creer_carto(monde, creer_reglages(monde, CONTENU))

    statut, t = lancer(monde, carto_id)

    assert statut == "echec"
    c = lire_carto(monde, carto_id)
    assert c["statut"] == "echec" and c["avertissement"] == job.REGISTRE_ABSENT
    assert c["duree_ms"] is not None and c["fin_le"] is not None
    assert lire_travail(monde, t.id)["erreur"] == "échec du travail (CartoEnEchec)"


def test_exception_du_moteur_message_sur_sans_texte(
    monde: Monde, donnees: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ecrire(registre_groupe(), donnees)

    def echoue(*args: Any, **kwargs: Any) -> Any:
        raise ValueError("PERSONNE INVENTEE, donnée à ne pas recopier")

    monkeypatch.setattr(job, "cartographier", echoue)
    carto_id = creer_carto(monde, creer_reglages(monde, CONTENU))

    statut, t = lancer(monde, carto_id)

    assert statut == "echec"
    c = lire_carto(monde, carto_id)
    assert c["statut"] == "echec" and c["avertissement"] == job.ECHEC
    assert "PERSONNE" not in (lire_travail(monde, t.id)["erreur"] or "")


def test_ecriture_qui_echoue_n_ecrit_aucune_ligne(
    monde: Monde, donnees: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sociétés, liens et statut partent ensemble : un lien refusé par la base annule tout."""
    ecrire(registre_groupe(), donnees)
    vrai = job.lignes_liens

    def lien_invalide(*args: Any) -> list[tuple[Any, ...]]:
        lignes = vrai(*args)
        return [*lignes, (*lignes[0][:2], "PASUNSIREN", *lignes[0][3:])]

    monkeypatch.setattr(job, "lignes_liens", lien_invalide)
    carto_id = creer_carto(monde, creer_reglages(monde, CONTENU))

    statut, _ = lancer(monde, carto_id)

    assert statut == "echec"
    assert lire_carto(monde, carto_id)["statut"] == "echec"
    assert societes(monde, carto_id) == {} and liens(monde, carto_id) == []
