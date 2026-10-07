"""Construction de `registre.duckdb` sur un mini-jeu de parquets générés.

Tous les noms sont inventés (règle produit 6) : « SOCIETE ALPHA », « PERSONNE FICTIVE 1 ».
"""

from datetime import date
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from cartofr.registre import journal
from cartofr.registre.construire import (
    DATE_STOCK,
    NOM_REGISTRE,
    ErreurConstruction,
    RegistreExistant,
    construire,
    main,
)
from cartofr.registre.schema import creer_tables

ALPHA, BETA, GAMMA, DELTA = "100000001", "100000002", "100000003", "100000004"


def _ecrire(chemin: Path, colonnes: dict[str, list]) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table(colonnes), chemin)


@pytest.fixture
def donnees(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Un dossier `data` miniature, désigné par CARTOFR_DATA."""
    _ecrire(
        tmp_path / "rne_links/liens.parquet",
        {
            "parent": [ALPHA, ALPHA, BETA],
            "enfant": [BETA, GAMMA, DELTA],
            "role": ["5132", "5132", "5132"],
            "actif": [True, False, None],
            "parent_nom": ["SOCIETE ALPHA", "SOCIETE ALPHA", "SOCIETE BETA"],
        },
    )
    _ecrire(
        tmp_path / "rne_links/societes.parquet",
        {
            "siren": [ALPHA, BETA, GAMMA, DELTA, DELTA],
            "denomination": [
                "SOCIETE ALPHA",
                "SOCIETE BETA",
                "SOCIETE GAMMA",
                "DELTA ANCIEN",
                "DELTA NOUVEAU",
            ],
            "diffusion_commerciale": [True, False, True, True, True],
            "diffusion_insee": ["O", "O", "O", "O", "O"],
            "salaries": [10, 0, 3, 1, 2],
            "maj": [
                "2025-01-01T00:00:00+01:00",
                "2025-01-01T00:00:00+01:00",
                "2025-01-01T00:00:00+01:00",
                "2024-01-01T00:00:00+01:00",
                "2025-06-01T00:00:00+01:00",
            ],
        },
    )
    _ecrire(
        tmp_path / "rne_links/personnes.parquet",
        {
            "siren": [ALPHA, BETA],
            "personne": ["PERSONNE FICTIVE 1|A|1970-01", "PERSONNE FICTIVE 2|B|1980-01"],
            "role": ["5132", "5132"],
            "actif": [True, False],
        },
    )
    _ecrire(
        tmp_path / "sieges.parquet",
        {
            "siren": [ALPHA],
            "siret_siege": [ALPHA + "00011"],
            "num": ["1"],
            "type_voie": ["RUE"],
            "voie": ["DE TEST"],
            "cp": ["75001"],
            "commune": ["PARIS"],
            "adresse_cle": ["1 RUE DE TEST 75001"],
            "nom": ["SOCIETE ALPHA"],
            "cj": [5710],
            "naf": ["70.10Z"],
            "tranche": ["11"],
        },
    )
    _ecrire(
        tmp_path / "unite_legale.parquet",
        {
            "siren": [ALPHA, BETA, GAMMA],
            "statutDiffusionUniteLegale": ["O", "P", "O"],
            "dateCreationUniteLegale": [date(2000, 1, 1), date(2010, 5, 2), None],
            "etatAdministratifUniteLegale": ["A", "A", "C"],
            "prenom1UniteLegale": [None, "PRENOM FICTIF", None],
            "sexeUniteLegale": [None, "M", None],
            "nomUniteLegale": [None, "PERSONNE FICTIVE 3", None],
        },
    )
    monkeypatch.setenv("CARTOFR_DATA", str(tmp_path))
    return tmp_path


def _lire(chemin: Path, sql: str) -> list[tuple]:
    con = duckdb.connect(str(chemin), read_only=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def _colonnes(chemin: Path, table: str) -> set[str]:
    return {r[0] for r in _lire(chemin, f"select column_name from (describe {table})")}


def test_construit_toutes_les_tables_avec_debut_et_fin(donnees: Path) -> None:
    comptes = construire()
    registre = donnees / NOM_REGISTRE
    assert registre.is_file()
    for table in ("societes", "liens", "dirigeants_personnes"):
        assert {"debut", "fin"} <= _colonnes(registre, table)
    assert comptes["liens"] == 3
    assert comptes["sieges"] == 1
    assert _lire(registre, "select count(*) from societes where debut <> $$2026-03-04$$::date") == [(0,)]


def test_lien_actif_ou_vide_reste_ouvert_et_inactif_est_ferme(donnees: Path) -> None:
    construire()
    lignes = _lire(
        donnees / NOM_REGISTRE, "select enfant, debut, fin, fin_inconnue, source from liens order by enfant"
    )
    assert lignes == [
        (BETA, DATE_STOCK, None, False, "rne_stock"),  # actif = true
        (GAMMA, DATE_STOCK, DATE_STOCK, True, "rne_stock"),  # actif = false : déjà fermé au stock
        (DELTA, DATE_STOCK, None, False, "rne_stock"),  # actif vide : actif, comme le moteur
    ]


def test_dirigeant_inactif_est_ferme(donnees: Path) -> None:
    construire()
    lignes = _lire(
        donnees / NOM_REGISTRE, "select siren, fin, fin_inconnue from dirigeants_personnes order by siren"
    )
    assert lignes == [(ALPHA, None, False), (BETA, DATE_STOCK, True)]


def test_diffusion_sirene_et_opposition(donnees: Path) -> None:
    construire()
    lignes = _lire(
        donnees / NOM_REGISTRE,
        "select siren, non_diffusible, opposition_prospection, etat_administratif"
        " from societes order by siren",
    )
    assert lignes == [
        (ALPHA, False, False, "A"),
        (BETA, True, True, "A"),  # statut 'P' et refus de prospection
        (GAMMA, False, False, "C"),
        (DELTA, None, False, None),  # absente de SIRENE : inconnu, pas « diffusible »
    ]


def test_doublon_rne_garde_la_fiche_la_plus_recente(donnees: Path) -> None:
    construire()
    assert _lire(donnees / NOM_REGISTRE, f"select denomination from societes where siren = '{DELTA}'") == [
        ("DELTA NOUVEAU",)
    ]


def test_aucune_colonne_personnelle_hors_dirigeants(donnees: Path) -> None:
    construire()
    registre = donnees / NOM_REGISTRE
    for table in ("societes", "liens", "sieges"):
        colonnes = {c.lower() for c in _colonnes(registre, table)}
        assert not colonnes & {
            "prenom1unitelegale",
            "sexeunitelegale",
            "nomunitelegale",
            "personne",
            "parent_nom",
        }
    for table in ("societes", "liens", "sieges"):
        assert "FICTI" not in repr(_lire(registre, f"select * from {table}"))


def test_journal_succes(donnees: Path) -> None:
    construire()
    lignes = _lire(
        donnees / NOM_REGISTRE, "select source, statut, ajoutes, fermes, fin_le is not null from mises_a_jour"
    )
    assert lignes == [("construction_initiale", "succes", 4 + 3, 1, True)]


def test_refuse_de_remplacer_sans_option(donnees: Path) -> None:
    registre = donnees / NOM_REGISTRE
    registre.write_bytes(b"registre en place")
    with pytest.raises(RegistreExistant):
        construire()
    assert main([]) == 1
    assert registre.read_bytes() == b"registre en place"
    assert list(donnees.glob("*.en-construction*")) == []


def test_remplace_avec_option(donnees: Path) -> None:
    construire()
    assert main(["--remplacer"]) == 0
    assert _lire(donnees / NOM_REGISTRE, "select count(*) from mises_a_jour") == [(1,)]


def test_echec_ne_laisse_ni_registre_ni_temporaire(donnees: Path) -> None:
    (donnees / "sieges.parquet").unlink()
    with pytest.raises(ErreurConstruction):
        construire()
    assert list(donnees.glob(NOM_REGISTRE + "*")) == []


def test_echec_pendant_le_chargement_ne_laisse_rien(donnees: Path) -> None:
    (donnees / "sieges.parquet").write_bytes(b"pas un parquet")
    with pytest.raises(duckdb.Error):
        construire()
    assert list(donnees.glob(NOM_REGISTRE + "*")) == []


def test_echec_garde_le_registre_en_place_et_le_journalise(donnees: Path) -> None:
    construire()
    (donnees / "sieges.parquet").write_bytes(b"pas un parquet")
    with pytest.raises(duckdb.Error):
        construire(remplacer=True)
    registre = donnees / NOM_REGISTRE
    assert _lire(registre, "select count(*) from liens") == [(3,)]
    journal_maj = _lire(registre, "select statut, erreur from mises_a_jour order by id")
    assert [statut for statut, _ in journal_maj] == ["succes", "echec"]
    assert journal_maj[1][1] == "InvalidInputException pendant la construction"  # type seul, pas le message
    assert list(donnees.glob("*.en-construction*")) == []


def test_journal_ouvrir_terminer_echouer() -> None:
    con = duckdb.connect()
    creer_tables(con)
    a = journal.ouvrir(con, "inpi_diff")
    b = journal.ouvrir(con, "inpi_diff")
    assert con.execute("select statut from mises_a_jour where id = ?", [a]).fetchall() == [("en_cours",)]
    journal.terminer(con, a, ajoutes=5, fermes=2)
    journal.echouer(con, b, "x" * 1000)
    assert con.execute("select statut, ajoutes, fermes from mises_a_jour where id = ?", [a]).fetchall() == [
        ("succes", 5, 2)
    ]
    ligne = con.execute("select statut, length(erreur) from mises_a_jour where id = ?", [b]).fetchall()
    assert ligne == [("echec", journal.LONGUEUR_ERREUR)]
    with pytest.raises(duckdb.ConstraintException):
        con.execute("update mises_a_jour set statut = 'inconnu' where id = ?", [a])
