"""Lecture de la carto d'une société dans la carto du pays (T050), sur le mini-registre de T048.

Le registre et les documents inventés sont ceux de `test_calcul.py` (règle produit 6) : le vrai
calcul T048 écrit `pays.duckdb`, puis `lire_groupe` le lit comme la route `/groupe`.
"""

from collections.abc import Iterator
from dataclasses import asdict
from pathlib import Path

import duckdb
import pytest
from test_calcul import (  # pyright: ignore[reportMissingImports]
    BETA,
    DIRIGEANT,
    E1,
    E2,
    E11,
    F1,
    H2,
    PF,
    SEULE,
    SOEUR,
    X1,
    Z0,
    A,
    B,
    D,
    E,
    F,
    H,
    P,
    X,
    Y,
    _preparer,
)

from cartofr.pays import calcul
from cartofr.pays.lecture import CartoSociete, attacher_pays, groupes_de, lire_groupe


@pytest.fixture(scope="module")
def data(tmp_path_factory: pytest.TempPathFactory) -> Path:
    data = _preparer(tmp_path_factory.mktemp("lecture"))
    calcul.lancer(data)
    return data


@pytest.fixture
def con(data: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    connexion = duckdb.connect(str(data / "registre.duckdb"), read_only=True)
    assert attacher_pays(connexion, data / "pays.duckdb")
    try:
        yield connexion
    finally:
        connexion.close()


def lire(con: duckdb.DuckDBPyConnection, siren: str) -> CartoSociete:
    carto = lire_groupe(con, siren)
    assert carto is not None
    return carto


def sirens(carto: CartoSociete) -> set[str]:
    return {s.siren for s in carto.societes}


# --- C1 : la société et sa descendance, jamais ses sœurs ---------------------------------------


def test_c1_tete_rend_le_groupe_entier(con: duckdb.DuckDBPyConnection) -> None:
    carto = lire(con, H)
    assert sirens(carto) == {H, X, Y, Z0, X1}
    assert carto.mere is None
    assert carto.groupe_entier is None
    assert carto.groupe is not None and carto.groupe.tete == H and carto.groupe.taille == 5
    niveaux = {s.siren: s.niveau for s in carto.societes}
    assert niveaux == {H: 0, X: 1, Y: 1, Z0: 1, X1: 2}


def test_c1_filiale_sans_ses_soeurs(con: duckdb.DuckDBPyConnection) -> None:
    carto = lire(con, X)
    assert sirens(carto) == {X, X1}
    assert carto.mere is not None and carto.mere.siren == H
    assert carto.mere.nom == "HOLDING ARBRE INVENTEE"
    racine = carto.societes[0]
    assert racine.siren == X and racine.niveau == 0 and racine.maison_mere_siren is None
    assert {s.siren: s.maison_mere_siren for s in carto.societes[1:]} == {X1: X}
    assert carto.groupe_entier is not None and carto.groupe_entier.tete == H


def test_c1_jamais_les_autres_filiales_de_la_mere_du_registre(con: duckdb.DuckDBPyConnection) -> None:
    carto = lire(con, P)
    assert SOEUR not in sirens(carto) and H2 not in sirens(carto)
    assert sirens(carto) == {P, PF}
    assert carto.mere is not None and carto.mere.siren == A


def test_c1_societe_absente_de_la_carto_du_pays_rend_elle_seule(con: duckdb.DuckDBPyConnection) -> None:
    carto = lire(con, SEULE)
    assert sirens(carto) == {SEULE}
    assert carto.nom == "SEULE INVENTEE"
    assert carto.groupe is None and carto.groupe_entier is None and carto.mere is None
    assert carto.mere_personne_physique is False
    seule = carto.societes[0]
    assert seule.niveau == 0 and seule.confiance is None and seule.ciblable is True
    assert carto.date_donnees is not None


@pytest.mark.parametrize("siren", ["999999999", F, E])
def test_c1_inconnu_ferme_ou_entrepreneur_individuel(con: duckdb.DuckDBPyConnection, siren: str) -> None:
    assert lire_groupe(con, siren) is None


# --- C6 : groupes emboîtés -------------------------------------------------------------------


def test_c6_sous_groupe_nomme_le_groupe_entier(con: duckdb.DuckDBPyConnection) -> None:
    carto = lire(con, B)
    assert sirens(carto) == {B, BETA}
    assert carto.groupe is not None and carto.groupe.tete == B
    assert carto.groupe_entier is not None and carto.groupe_entier.tete == D
    assert carto.mere is not None


def test_c6_tete_du_groupe_entier_rend_ses_sous_groupes(con: duckdb.DuckDBPyConnection) -> None:
    carto = lire(con, D)
    assert {B, BETA} <= sirens(carto)
    assert carto.groupe_entier is None
    entier = lire(con, BETA).groupe_entier
    assert entier is not None and entier.tete == D and entier.taille == len(sirens(carto))


# --- C3 : aucune personne --------------------------------------------------------------------


def test_c3_mere_entrepreneur_individuel_sans_siren_ni_nom(con: duckdb.DuckDBPyConnection) -> None:
    carto = lire(con, E1)
    assert sirens(carto) == {E1, E11}
    assert carto.mere is None
    assert carto.mere_personne_physique is True
    seule = lire(con, E2)
    assert seule.mere is None and seule.mere_personne_physique is True
    for c in (carto, seule):
        texte = repr(asdict(c))
        assert E not in texte
        assert "ENTREPRENEUR" not in texte
        assert DIRIGEANT.split("|")[0] not in texte


def test_c3_mere_fermee_non_nommee(con: duckdb.DuckDBPyConnection) -> None:
    carto = lire(con, F1)
    assert carto.mere is None and carto.mere_personne_physique is False
    assert F not in repr(asdict(carto))


# --- Recherche ---------------------------------------------------------------------------------


def test_groupes_de_pour_la_recherche(con: duckdb.DuckDBPyConnection) -> None:
    groupes = groupes_de(con, [X, SEULE, BETA])
    assert set(groupes) == {X, BETA}
    assert groupes[X].tete == H and groupes[X].taille == 5
    assert groupes[BETA].tete == B
    assert groupes_de(con, []) == {}


def test_attacher_pays_absent(tmp_path: Path, data: Path) -> None:
    connexion = duckdb.connect(str(data / "registre.duckdb"), read_only=True)
    try:
        assert attacher_pays(connexion, tmp_path / "pays.duckdb") is False
    finally:
        connexion.close()
