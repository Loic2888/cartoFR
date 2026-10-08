"""Export d'une carto au format du skill account-mapping (T029, FR-010).

Vérifie :
- la forme des 6 tables (fichiers, colonnes, une ligne par société, un lien par société
  rattachée) et que `validate_mapping.py` du skill les lit avec 0 erreur (C1) ;
- aucun nom de personne dans les 6 tables (C2, garde-fou 6), avec le comparateur de
  `test_aucune_personne.py`, et aucune colonne de personne ;
- `opposition_prospection` porté sur la société, jamais cachée ;
- une carto vide, et les caractères spéciaux (virgule, guillemet, saut de ligne,
  point-virgule, accents, début de formule) ;
- la route interne `/export/skill/<carto>` : paramètres, base absente, et, avec
  DATABASE_URL, le cloisonnement (la carto de A n'existe pas pour B) ;
- registre réel (CARTOFR_DATA) : LVMH, VINCI et CMAF passent la validation du skill (C1)
  et leur export ne contient aucun nom de dirigeant. Sauté en CI, avec la raison.

Jeux de test : mini-registre inventé (règle produit 6). Aucun nom de personne n'est
affiché : les assertions portent sur des nombres.
"""

import csv
import dataclasses
import io
import json
import os
import sys
import threading
import uuid
import zipfile
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import urlopen

import psycopg
import pytest
from psycopg.types.json import Jsonb

RACINE = Path(__file__).resolve().parents[3]
TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "moteur"))
sys.path.insert(0, str(TESTS))
sys.path.insert(0, str(RACINE / "skills" / "account-mapping" / "scripts"))
from fabrique import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    PRESIDENT,
    MiniRegistre,
    reglages,
    siren,
)
from test_aucune_personne import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    confronter,
    personnes_impliquees,
)
from validate_mapping import check, load_tables  # noqa: E402  # pyright: ignore[reportMissingImports]

from cartofr.api_recherche import Serveur  # noqa: E402
from cartofr.db import VARIABLE_URL, ConfigurationManquante, connecter  # noqa: E402
from cartofr.exports.skill import (  # noqa: E402
    COLONNES,
    TABLES,
    CartoEnregistree,
    SocieteEnregistree,
    Table,
    construire_tables,
    exporter,
    zip_des_tables,
)
from cartofr.jobs.carto import lignes_societes  # noqa: E402
from cartofr.moteur import Carto, cartographier  # noqa: E402

JOUR = date(2026, 10, 1)
TETE, FILIALE, SOUS_FILIALE, ZETA, HORS = siren(1), siren(10), siren(11), siren(20), siren(90)
CLE_A = "FICTIFNOM|ZÉPHYRIN|1970-01"
CLE_B = "DUPOND-INVENTÉ|MARIE, CLAIRE|1980-02"
DIRIGEANTS = {
    TETE: [CLE_A, CLE_B],
    ZETA: [CLE_A, CLE_B],  # dirigeants communs avec la tête : font entrer ZETA
    FILIALE: ["AUTRENOM|ÉLODIE|1975-05"],
    HORS: ["HORSGROUPE|PRENOMHORS|1960-06"],
}
CLES = [c for liste in DIRIGEANTS.values() for c in liste]
MOTS_DE_PERSONNE = (
    "dirigeant",
    "personne",
    "prenom",
    "prénom",
    "naissance",
    "person",
    "first_name",
    "last_name",
)


def depuis_moteur(carto: Carto, organigramme: list[str] | None = None) -> CartoEnregistree:
    """La carto telle que `jobs/carto.py` l'enregistre (lignes `carto_societes`)."""
    zero = uuid.UUID(int=0)
    return CartoEnregistree(
        groupe=carto.groupe,
        tete_siren=carto.tete,
        date_donnees=JOUR,
        organigramme=tuple(organigramme or ()),
        societes=tuple(SocieteEnregistree(*ligne[2:]) for ligne in lignes_societes(carto, zero, zero)),
    )


def deplier(contenu: bytes, dossier: Path) -> Path:
    with zipfile.ZipFile(io.BytesIO(contenu)) as archive:
        archive.extractall(dossier)
    return dossier


def lire(dossier: Path, table: str) -> list[dict[str, str]]:
    texte = (dossier / f"{table}.csv").read_bytes().decode("utf-8")
    return list(csv.DictReader(io.StringIO(texte, newline="")))


def valider(dossier: Path) -> list[str]:
    tables, entetes, fmt = load_tables(dossier)
    erreurs, _ = check(tables, entetes, fmt)
    return erreurs


@pytest.fixture
def carto_fabriquee(tmp_path: Path) -> CartoEnregistree:
    """Un groupe inventé : des dirigeants personnes font entrer ZETA ; FILIALE s'oppose à la prospection."""
    mini = MiniRegistre()
    mini.societe(TETE, "TETE INVENTEE", naf="70.10Z", tranche="22")
    mini.societe(FILIALE, "ALPHAMARK DISTRIBUTION", diffusion_commerciale=False)
    mini.societe(SOUS_FILIALE, "DELTA LOGISTIQUE")
    mini.societe(ZETA, "ZETA CONSEIL")
    mini.societe(HORS, "SANS LIEN")
    mini.lien(TETE, FILIALE, PRESIDENT)
    mini.lien(FILIALE, SOUS_FILIALE, PRESIDENT)
    for societe, cles in DIRIGEANTS.items():
        for cle in cles:
            mini.dirigeant(societe, cle)
    registre = mini.ecrire(tmp_path / "registre.duckdb")
    carto = cartographier(reglages(TETE, marques_sures=["Alphamark"], marques_ambigues=["Zeta"]), registre)
    return depuis_moteur(carto, organigramme=["Delta", "Marque Sans Société"])


# ---------- forme des 6 tables (C1) ----------


def test_forme_des_six_tables(carto_fabriquee: CartoEnregistree, tmp_path: Path) -> None:
    contenu = zip_des_tables(construire_tables(carto_fabriquee), carto_fabriquee)
    with zipfile.ZipFile(io.BytesIO(contenu)) as archive:
        assert sorted(archive.namelist()) == sorted([*(f"{t}.csv" for t in TABLES), "LISEZMOI.txt"])
    dossier = deplier(contenu, tmp_path / "export")
    for table in TABLES:
        entete = (dossier / f"{table}.csv").read_bytes().decode("utf-8").split("\r\n", 1)[0]
        assert tuple(entete.split(",")) == COLONNES[table]

    sirens = {s.siren for s in carto_fabriquee.societes}
    assert {TETE, FILIALE, SOUS_FILIALE, ZETA} <= sirens and HORS not in sirens
    companies = lire(dossier, "companies")
    assert [c["company_id"] for c in companies][0] == TETE  # la tête d'abord
    assert {c["company_id"] for c in companies} == sirens
    assert all(c["targetable"] in {"yes", "no"} for c in companies)
    assert next(c for c in companies if c["siren"] == TETE)["entity_type"] == "holding_operating_group"

    liens = lire(dossier, "relationships")
    assert len(liens) == len(sirens) - 1  # un lien par société rattachée, pas pour la tête
    lien = next(r for r in liens if r["child_id"] == SOUS_FILIALE)
    assert (lien["parent_id"], lien["confidence"], lien["relationship_status"]) == (
        FILIALE,
        "high",
        "confirmed",
    )
    assert lien["source_url"].startswith("https://data.inpi.fr/")
    assert lien["source_date"] == "2026-10-01"
    assert "entrée dans le groupe" not in lien["notes"]

    marques = lire(dossier, "brands")
    assert [m["brand_name"] for m in marques] == ["Delta", "Marque Sans Société"]
    assert [m["mapping_status"] for m in marques] == ["unresolved", "unresolved"]
    assert lire(dossier, "entities_to_resolve") == []
    assert [s["source_id"] for s in lire(dossier, "evidence_sources")] == ["S1", "S2", "S3"]
    couverture = {m["metric"]: m["value"] for m in lire(dossier, "coverage")}
    assert couverture["root_company_id"] == TETE
    assert couverture["companies_resolved"] == str(len(sirens))
    assert couverture["orphan_count"] == "0"

    assert valider(dossier) == []


def test_marque_rattachee_a_sa_tete_de_maison() -> None:
    tete_de_maison = SocieteEnregistree(
        siren(30), "MAISON D'ALPHA", 1, TETE, "B",
        "Déduit : adresse du groupe · entrée dans le groupe : tête de maison (organigramme public du groupe)",
        True, "Société opérationnelle", False, False,
    )  # fmt: skip
    carto = CartoEnregistree("TEST", TETE, JOUR, ("Maison d'Alpha",), (_tete(), tete_de_maison))
    marques = _lignes(construire_tables(carto), "brands")
    assert (marques[0]["legal_entity_id"], marques[0]["legal_entity_name"]) == (siren(30), "MAISON D'ALPHA")
    assert marques[0]["mapping_status"] == "mapped"


# ---------- aucune personne (C2) ----------


def test_aucun_nom_de_personne_dans_les_six_tables(carto_fabriquee: CartoEnregistree) -> None:
    tables = construire_tables(carto_fabriquee)
    cellules = [v for t in tables for ligne in t.lignes for v in ligne if v]
    constat = confronter(cellules, CLES)
    assert constat.noms_cherches > 0 and constat.textes > 0
    assert constat.fuites == 0
    # Aucune colonne qui puisse porter une personne.
    colonnes = [c.lower() for t in tables for c in t.colonnes]
    assert not [c for c in colonnes if any(m in c for m in MOTS_DE_PERSONNE)]
    # Le LISEZMOI non plus.
    contenu = zip_des_tables(tables, carto_fabriquee)
    with zipfile.ZipFile(io.BytesIO(contenu)) as archive:
        lisezmoi = archive.read("LISEZMOI.txt").decode("utf-8")
    assert confronter([lisezmoi], CLES).fuites == 0


def test_un_nom_glisse_dans_une_preuve_serait_trouve(carto_fabriquee: CartoEnregistree) -> None:
    """Le contrôle n'est pas creux : un nom glissé dans une preuve ressort dans l'export, et est vu."""
    piegee = dataclasses.replace(carto_fabriquee.societes[-1], preuve="Dirigeant : zéphyrin fictifnom")
    carto = dataclasses.replace(carto_fabriquee, societes=(*carto_fabriquee.societes[:-1], piegee))
    cellules = [v for t in construire_tables(carto) for ligne in t.lignes for v in ligne if v]
    assert confronter(cellules, CLES).personnes_trouvees == 1


# ---------- opposition à la prospection ----------


def test_opposition_prospection_portee_jamais_cachee(
    carto_fabriquee: CartoEnregistree, tmp_path: Path
) -> None:
    opposee = next(s for s in carto_fabriquee.societes if s.siren == FILIALE)
    assert opposee.opposition_prospection is True
    dossier = deplier(zip_des_tables(construire_tables(carto_fabriquee), carto_fabriquee), tmp_path / "e")
    companies = {c["siren"]: c for c in lire(dossier, "companies")}
    assert companies[FILIALE]["opposition_prospection"] == "True"
    assert {c["opposition_prospection"] for s, c in companies.items() if s != FILIALE} == {"False"}
    couverture = {m["metric"]: m["value"] for m in lire(dossier, "coverage")}
    assert couverture["opposition_prospection_count"] == "1"
    assert "opposition_prospection = True" in (dossier / "LISEZMOI.txt").read_text(encoding="utf-8")


# ---------- carto vide ----------


def test_carto_vide(tmp_path: Path) -> None:
    carto = CartoEnregistree("VIDE", TETE, None, (), ())
    tables = construire_tables(carto)
    assert [t.nom for t in tables] == list(TABLES)
    assert all(t.lignes == () for t in tables if t.nom not in {"evidence_sources", "coverage"})
    couverture = {m["metric"]: m["value"] for m in _lignes(tables, "coverage")}
    assert couverture["companies_resolved"] == "0"
    assert couverture["orphan_count"] == "0"
    assert couverture["mapping_status"] == "not_started"
    dossier = deplier(zip_des_tables(tables, carto), tmp_path / "vide")
    assert lire(dossier, "companies") == []
    assert valider(dossier) == []


# ---------- caractères spéciaux ----------

NOMS_SPECIAUX = {
    siren(41): 'SOCIETE "LA VIRGULE", ET CIE',
    siren(42): "POINT;VIRGULE\nET SAUT DE LIGNE",
    siren(43): "ÉTABLISSEMENTS ÇA & LÀ — ŒUVRE",
    siren(44): '=HYPERLINK("http://exemple.invalid")',
    siren(45): "+33 SERVICES",
    siren(46): "@ACCUEIL",
    siren(47): "-MOINS",
}


def test_caracteres_speciaux(tmp_path: Path) -> None:
    filles = tuple(
        SocieteEnregistree(s, nom, 1, TETE, "A", f"Mandat au registre : Président, « {nom} »", True,
                           "Société opérationnelle", False, False)
        for s, nom in NOMS_SPECIAUX.items()
    )  # fmt: skip
    carto = CartoEnregistree(
        'GROUPE "SPÉCIAL", ; =', TETE, JOUR, ("Ça & Là, « marque »",), (_tete(), *filles)
    )
    contenu = zip_des_tables(construire_tables(carto), carto)
    dossier = deplier(contenu, tmp_path / "speciaux")
    noms = {c["siren"]: c["legal_name"] for c in lire(dossier, "companies")}
    for s, nom in NOMS_SPECIAUX.items():
        attendu = f"'{nom}" if nom[0] in "=+-@" else nom
        assert noms[s] == attendu
    brut = (dossier / "companies.csv").read_bytes()
    assert not brut.startswith(b"\xef\xbb\xbf")  # UTF-8 sans BOM : format par défaut du skill
    assert "ÉTABLISSEMENTS ÇA & LÀ — ŒUVRE".encode() in brut
    assert lire(dossier, "brands")[0]["brand_name"] == "Ça & Là, « marque »"
    assert valider(dossier) == []


# ---------- route interne /export/skill ----------


@pytest.fixture
def service() -> Iterator[tuple[str, dict[str, Any]]]:
    """La route interne sur un port libre ; `etat["connecter"]` choisit la connexion."""
    etat: dict[str, Any] = {"connecter": connecter}
    serveur = Serveur(("127.0.0.1", 0), connecter=lambda: etat["connecter"]())
    fil = threading.Thread(target=serveur.serve_forever, daemon=True)
    fil.start()
    try:
        yield f"http://127.0.0.1:{serveur.server_address[1]}", etat
    finally:
        serveur.shutdown()
        serveur.server_close()


def appeler(url: str) -> tuple[int, bytes, str]:
    try:
        with urlopen(url, timeout=10) as r:
            return r.status, r.read(), r.headers.get("Content-Type", "")
    except HTTPError as e:
        return e.code, e.read(), e.headers.get("Content-Type", "")


def test_route_parametres_invalides(service: tuple[str, dict[str, Any]]) -> None:
    base, _ = service
    org = uuid.uuid4()
    for chemin in ("/export/skill/pas-un-uuid?organisation=" + str(org), f"/export/skill/{uuid.uuid4()}",
                   f"/export/skill/{uuid.uuid4()}?organisation=x"):  # fmt: skip
        statut, corps, _ = appeler(base + chemin)
        assert statut == 400
        assert json.loads(corps) == {"erreur": "parametre_invalide"}


def test_route_base_indisponible(service: tuple[str, dict[str, Any]]) -> None:
    base, etat = service

    def sans_base() -> Any:
        raise ConfigurationManquante("DATABASE_URL")

    etat["connecter"] = sans_base
    statut, corps, _ = appeler(f"{base}/export/skill/{uuid.uuid4()}?organisation={uuid.uuid4()}")
    assert (statut, json.loads(corps)) == (503, {"erreur": "base_indisponible"})


# --- avec la base : cloisonnement ---

MARQUEUR = "test_t029"


@pytest.fixture
def conn() -> Iterator[psycopg.Connection[tuple[Any, ...]]]:
    if not os.environ.get(VARIABLE_URL):
        message = f"{VARIABLE_URL} n'est pas définie : l'export lit la carto dans la base de l'app."
        if os.environ.get("CI"):
            pytest.fail(message)
        pytest.skip(message)
    connexion = connecter()
    try:
        yield connexion
    finally:
        connexion.close()


def _un(conn: psycopg.Connection[tuple[Any, ...]], requete: Any, params: tuple[Any, ...]) -> Any:
    ligne = conn.execute(requete, params).fetchone()
    assert ligne is not None
    return ligne[0]


@pytest.fixture
def deux_organisations(conn: psycopg.Connection[tuple[Any, ...]]) -> Iterator[dict[str, uuid.UUID]]:
    """A a une carto terminée et une carto en attente ; B a son propre groupe, sans carto."""
    marque = f"{MARQUEUR} {uuid.uuid4().hex}"
    a = _un(conn, "insert into public.organisations (nom) values (%s) returning id", (marque + " A",))
    b = _un(conn, "insert into public.organisations (nom) values (%s) returning id", (marque + " B",))
    ids: dict[str, uuid.UUID] = {"a": a, "b": b}
    try:
        groupe = _un(conn, "insert into public.groupes (organisation_id, tete_siren, nom) values (%s, %s, %s)"
                     " returning id", (a, TETE, 'GROUPE "A", TEST'))  # fmt: skip
        reglages_id = _un(
            conn,
            "insert into public.reglages (groupe_id, organisation_id, version, contenu, valide_le)"
            " values (%s, %s, 1, %s, now()) returning id",
            (groupe, a, Jsonb({"groupe": "A", "tete": TETE, "organigramme": ["Delta"]})),
        )
        for nom, statut in (("terminee", "terminee"), ("attente", "en_attente")):
            ids[nom] = _un(
                conn,
                "insert into public.cartos (organisation_id, groupe_id, reglages_id, statut, date_donnees)"
                " values (%s, %s, %s, %s, %s) returning id",
                (a, groupe, reglages_id, statut, JOUR),
            )
        lignes = [
            (TETE, "TETE INVENTEE", 0, None, None, "Tête du groupe", True, "Tête", False, False),
            (FILIALE, "FILIALE, INVENTEE", 1, TETE, "A", "Mandat au registre : Président", True,
             "Société opérationnelle", True, False),
        ]  # fmt: skip
        for ligne in lignes:
            conn.execute(
                "insert into public.carto_societes (carto_id, organisation_id, siren, nom, niveau,"
                " maison_mere_siren, confiance, preuve, ciblable, raison_ciblable, opposition_prospection,"
                " non_diffusible) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (ids["terminee"], a, *ligne),
            )
        conn.execute(
            "insert into public.groupes (organisation_id, tete_siren, nom) values (%s, %s, 'B')", (b, TETE)
        )
        conn.commit()
        yield ids
    finally:
        conn.rollback()
        conn.execute("delete from public.organisations where id in (%s, %s)", (a, b))
        conn.commit()


def test_export_lu_en_base_pour_son_organisation(
    conn: psycopg.Connection[tuple[Any, ...]], deux_organisations: dict[str, uuid.UUID], tmp_path: Path
) -> None:
    ids = deux_organisations
    contenu = exporter(conn, ids["terminee"], ids["a"])
    assert contenu is not None
    dossier = deplier(contenu, tmp_path / "base")
    companies = {c["siren"]: c for c in lire(dossier, "companies")}
    assert set(companies) == {TETE, FILIALE}
    assert companies[FILIALE]["legal_name"] == "FILIALE, INVENTEE"
    assert companies[FILIALE]["opposition_prospection"] == "True"
    assert lire(dossier, "brands")[0]["brand_name"] == "Delta"
    assert valider(dossier) == []
    # Cloisonnement : pour B, la carto de A n'existe pas.
    assert exporter(conn, ids["terminee"], ids["b"]) is None


def test_route_cloisonnee_par_organisation(
    service: tuple[str, dict[str, Any]], deux_organisations: dict[str, uuid.UUID]
) -> None:
    base, _ = service
    ids = deux_organisations
    statut, corps, type_ = appeler(f"{base}/export/skill/{ids['terminee']}?organisation={ids['a']}")
    assert (statut, type_) == (200, "application/zip")
    assert zipfile.ZipFile(io.BytesIO(corps)).testzip() is None

    statut, corps, _ = appeler(f"{base}/export/skill/{ids['terminee']}?organisation={ids['b']}")
    assert (statut, json.loads(corps)) == (404, {"erreur": "carto_introuvable"})
    statut, corps, _ = appeler(f"{base}/export/skill/{uuid.uuid4()}?organisation={ids['a']}")
    assert (statut, json.loads(corps)) == (404, {"erreur": "carto_introuvable"})
    statut, corps, _ = appeler(f"{base}/export/skill/{ids['attente']}?organisation={ids['a']}")
    assert (statut, json.loads(corps)) == (409, {"erreur": "carto_non_terminee"})


# ---------- registre réel : LVMH, VINCI, CMAF (C1, C2) ----------


def _registre_reel() -> Path | None:
    dossier = os.environ.get("CARTOFR_DATA")
    if not dossier:
        return None
    chemin = Path(dossier) / "registre.duckdb"
    return chemin if chemin.is_file() else None


REGISTRE_REEL = _registre_reel()


@pytest.mark.skipif(
    REGISTRE_REEL is None,
    reason="registre réel absent en CI (2,4 Go) : CARTOFR_DATA doit désigner un dossier avec registre.duckdb",
)
@pytest.mark.parametrize("groupe", ["lvmh", "vinci", "cmaf"])
def test_registre_reel_export_valide_et_sans_personne(
    groupe: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert REGISTRE_REEL is not None
    config = json.loads((RACINE / "config" / f"{groupe}.json").read_text(encoding="utf-8"))
    carto = cartographier(config, REGISTRE_REEL)
    enregistree = depuis_moteur(carto, config.get("organigramme", []))
    tables = construire_tables(enregistree)
    dossier = deplier(zip_des_tables(tables, enregistree), tmp_path / groupe)
    tables_lues, entetes, fmt = load_tables(dossier)
    erreurs, avertissements = check(tables_lues, entetes, fmt)

    _, cles = personnes_impliquees(REGISTRE_REEL, carto)
    # Deux sortes de cellules, comme dans test_aucune_personne.py :
    # - recopiées : dénominations SIRENE (`legal_name`, `legal_entity_name`) et marques de
    #   l'organigramme validé (`brand_name`). Une maison peut porter le nom de son fondateur
    #   (décision T023) : on vérifie qu'elles sont des copies exactes, et les homonymies sont
    #   comptées sans faire échouer (mesure du 2026-10-08 : LVMH 1, VINCI 2, CMAF 0) ;
    # - tout le reste (texte du moteur, constantes) : aucun nom complet de dirigeant.
    recopiees = {"legal_name", "legal_entity_name", "brand_name"}
    cellules = [
        (c, v) for t in tables for ligne in t.lignes for c, v in zip(t.colonnes, ligne, strict=True) if v
    ]
    constat = confronter([v for c, v in cellules if c not in recopiees], cles)
    homonymies = confronter([v for c, v in cellules if c in recopiees], cles)
    noms = {s.siren: s.nom or "" for s in carto.societes}
    assert all(c["legal_name"] == noms[c["company_id"]] for c in _lignes(tables, "companies"))
    assert [b["brand_name"] for b in _lignes(tables, "brands")] == config.get("organigramme", [])
    with capsys.disabled():
        print(
            f"\nT029 {groupe} : {len(_lignes(tables, 'companies'))} sociétés, "
            f"{len(_lignes(tables, 'relationships'))} liens, {len(_lignes(tables, 'brands'))} marques ; "
            f"validate_mapping : {len(erreurs)} erreur(s), {len(avertissements)} avertissement(s) ; "
            f"{constat.personnes} dirigeants confrontés, {constat.fuites} fuite(s) ; "
            f"{homonymies.personnes_trouvees} homonymie(s) dans une dénomination ou une marque"
        )
    assert erreurs == []
    assert constat.personnes > 0
    assert constat.fuites == 0
    assert homonymies.cles_brutes == 0


# ---------- outils ----------


def _tete() -> SocieteEnregistree:
    return SocieteEnregistree(
        TETE, "TETE INVENTEE", 0, None, None, "Tête du groupe", True, "Tête", False, False
    )


def _lignes(tables: list[Table], nom: str) -> list[dict[str, str]]:
    table = next(t for t in tables if t.nom == nom)
    return [dict(zip(table.colonnes, ligne, strict=True)) for ligne in table.lignes]
