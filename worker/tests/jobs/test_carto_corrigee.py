"""Carto corrigée (T051) : la tête, son document et les corrections, et l'effet des corrections.
Sans base.

Vérifie, sur un mini-registre et un document inventés (règle produit 6), déposés par la vraie
commande de T046 :
- le document en vigueur de la tête est lu par le calcul ; illisible, la carto se fait sans lui ;
- sans correction, l'effet est 0/0, sans second passage du moteur ;
- l'effet ne compte que ce que les corrections changent (décision de Loïc du 2026-10-19) : une
  exclusion retire, une marque ajoute, une décision du consultant compte aussi. Il ne compte pas
  l'écart de méthode avec la carto du pays (arbre du registre, départage) ;
- sans correction, sur un groupe à document sans départage, la carto est celle du pays (T048).
"""

import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import duckdb
import pytest

from cartofr.jobs import carto as job
from cartofr.moteur import Decision
from cartofr.moteur.modele import Carto
from cartofr.pays import calcul
from cartofr.pays.lecture import attacher_pays, lire_groupe
from cartofr.perimetre.deposer import Demande, deposer
from cartofr.reglages import valider

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "moteur"))
from fabrique import PRESIDENT, MiniRegistre, siren  # noqa: E402  # pyright: ignore[reportMissingImports]

# A publie un document qui inscrit P. P a pour mère au registre la holding H2, qui dirige aussi
# SOEUR. P dirige PF. Une société de marque, MARQUE, sans lien au groupe.
A, H2, P, SOEUR, PF, MARQUE = siren(1), siren(20), siren(21), siren(22), siren(23), siren(24)
LE = datetime(2026, 10, 19, 6, 0, tzinfo=UTC)


def _preparer(
    racine: Path, document: str | None = "Prima Inventée France 100,00 Intégration globale\n"
) -> Path:
    data = racine / "data"
    data.mkdir()
    mini = MiniRegistre()
    for s, nom in (
        (A, "TETE A INVENTEE"), (H2, "HOLDING DEUX INVENTEE"), (P, "PRIMA INVENTEE"),
        (SOEUR, "SOEUR INVENTEE"), (PF, "PRIMA FILLE INVENTEE"), (MARQUE, "ZORGLUB SERVICES"),
    ):  # fmt: skip
        mini.societe(s, nom)
    for parent, enfant in ((H2, P), (H2, SOEUR), (P, PF)):
        mini.lien(parent, enfant, PRESIDENT)
    registre = mini.ecrire(data / "registre.duckdb")
    if document is not None:
        chemin = racine / "a.txt"
        chemin.write_text(document, encoding="utf-8")
        deposer([Demande(A, chemin)], data, maintenant=LE)
    return registre


def _contenu(**corrections: list[str]) -> dict[str, Any]:
    return valider({"groupe": "TETE A INVENTEE", "tete": A, **corrections}).model_dump()


def _sirens(carto: Carto) -> set[str]:
    return {s.siren for s in carto.societes}


@pytest.fixture(scope="module")
def registre(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _preparer(tmp_path_factory.mktemp("corrigee"))


def test_sans_correction_effet_nul_et_document_lu(registre: Path) -> None:
    resultat = job.calculer(_contenu(), registre)
    assert _sirens(resultat.carto) == {A, P, PF}  # le document a fait entrer P, et P descend vers PF
    assert resultat.effet == job.Effet(ajoutees=0, retirees=0)
    assert resultat.avertissements == ()


def test_sans_correction_un_seul_passage_du_moteur(registre: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    appels: list[dict[str, Any]] = []
    vrai = job.cartographier

    def compter(reglages: dict[str, Any], *args: Any, **kwargs: Any) -> Carto:
        appels.append(reglages)
        return vrai(reglages, *args, **kwargs)

    monkeypatch.setattr(job, "cartographier", compter)
    job.calculer(_contenu(), registre)
    assert len(appels) == 1
    job.calculer(_contenu(exclus=[PF]), registre)
    assert len(appels) == 3


def test_sans_correction_groupe_a_document_comme_la_carto_du_pays(tmp_path: Path) -> None:
    """Sans départage, la carto du pays d'un groupe à document est le même moteur : mêmes sociétés."""
    registre = _preparer(tmp_path)
    calcul.lancer(registre.parent)
    con = duckdb.connect(str(registre), read_only=True)
    try:
        assert attacher_pays(con, registre.parent / calcul.NOM_PAYS)
        pays = lire_groupe(con, A)
    finally:
        con.close()
    assert pays is not None
    assert _sirens(job.calculer(_contenu(), registre).carto) == {s.siren for s in pays.societes}


def test_une_exclusion_compte_comme_retiree(registre: Path) -> None:
    resultat = job.calculer(_contenu(exclus=[PF]), registre)
    assert PF not in _sirens(resultat.carto)
    assert resultat.effet == job.Effet(ajoutees=0, retirees=1)


def test_une_marque_compte_comme_ajoutee(registre: Path) -> None:
    resultat = job.calculer(_contenu(marques_sures=["Zorglub"]), registre)
    assert MARQUE in _sirens(resultat.carto)
    assert resultat.effet == job.Effet(ajoutees=1, retirees=0)


def test_une_decision_du_consultant_compte_aussi(registre: Path) -> None:
    decisions: dict[str, Decision] = {PF: "ecarter"}
    resultat = job.calculer(_contenu(), registre, decisions=decisions)
    assert PF not in _sirens(resultat.carto)
    assert resultat.effet == job.Effet(ajoutees=0, retirees=1)


def test_sans_document_la_tete_seule_du_registre(tmp_path: Path) -> None:
    registre = _preparer(tmp_path, document=None)
    resultat = job.calculer(_contenu(), registre)
    assert _sirens(resultat.carto) == {A}
    assert resultat.avertissements == ()


def test_document_illisible_carto_sans_lui_et_dit(tmp_path: Path) -> None:
    registre = _preparer(tmp_path)
    deposes = list((registre.parent / calcul.DOSSIER_DOCUMENTS).iterdir())
    assert len(deposes) == 1
    deposes[0].unlink()  # le fichier en vigueur a disparu du disque : illisible
    resultat = job.calculer(_contenu(exclus=[PF]), registre)
    assert resultat.avertissements == (job.DOCUMENT_ILLISIBLE,)
    assert _sirens(resultat.carto) == {A}
    assert resultat.effet == job.Effet(0, 0)


@pytest.mark.parametrize(
    ("avant", "ajoutees", "retirees"),
    [
        pytest.param({A, P}, 0, 0, id="identiques"),
        pytest.param({A}, 1, 0, id="une_ajoutee"),
        pytest.param({A, P, PF}, 0, 1, id="une_retiree"),
        pytest.param({A, SOEUR}, 1, 1, id="une_de_chaque"),
    ],
)
def test_effet(avant: set[str], ajoutees: int, retirees: int) -> None:
    def carto(sirens: set[str]) -> Carto:
        return cast(Carto, SimpleNamespace(societes=tuple(SimpleNamespace(siren=s) for s in sirens)))

    assert job.effet(carto({A, P}), carto(avant)) == job.Effet(ajoutees, retirees)


@pytest.mark.parametrize(
    ("contenu", "decisions", "attendu"),
    [
        pytest.param({"groupe": "G", "tete": A, "exclus": [], "marques_sures": []}, None, True, id="vide"),
        pytest.param({"groupe": "G", "tete": A, "exclus": [PF]}, None, False, id="une_exclusion"),
        pytest.param(
            {"groupe": "G", "tete": A, "familles_exclues_empreintes": ["e" * 64]}, None, False, id="famille"
        ),
        pytest.param({"groupe": "G", "tete": A}, {PF: "ecarter"}, False, id="une_decision"),
    ],
)
def test_sans_correction(contenu: dict[str, Any], decisions: Any, attendu: bool) -> None:
    assert job.sans_correction(contenu, decisions) is attendu
