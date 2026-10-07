"""Familles exclues par empreinte dans le moteur (T021, garde-fou 6, principe 5).

Les réglages lus en base ne portent pas les noms de famille exclus, seulement
leur empreinte HMAC (`cartofr.empreinte`). Le moteur doit écarter une holding
familiale par l'empreinte exactement comme par le nom en clair (règle de
`test_regles.py::test_holding_familiale_exclue_par_le_nom_de_famille`), et
rendre la même carto, champ par champ.

Tous les noms sont inventés (règle produit 6).
"""

from pathlib import Path
from typing import Any

import pytest
from fabrique import PRESIDENT, MiniRegistre, personne, reglages, siren

from cartofr.empreinte import VARIABLE_CLE, CleManquante, empreinte
from cartofr.moteur import Carto, cartographier

TETE, F1, X = siren(1), siren(10), siren(50)
ADRESSE_GROUPE = "1 PLACE DU GROUPE INVENTE 75008"
FAMILLE = "FAMILLEINVENTEE"
CLE = "cle-de-test-FAKE"


@pytest.fixture
def registre(tmp_path: Path) -> Path:
    """La tête et sa filiale au même siège, et une holding de la famille qui dirige la tête :
    elle n'entre que par ses deux dirigeants communs avec la tête (adresse et second indice)."""
    mini = MiniRegistre()
    mini.societe(TETE, "TETE INVENTEE", naf="70.10Z", tranche="22", adresse=ADRESSE_GROUPE)
    mini.societe(F1, "FILIALE INVENTEE UN", adresse=ADRESSE_GROUPE)
    mini.lien(TETE, F1, PRESIDENT)
    mini.societe(X, "HOLDING FAMILIALE INVENTEE", naf="64.20Z", adresse=ADRESSE_GROUPE)
    for i in (1, 2):
        mini.dirigeant(TETE, personne(i, famille=FAMILLE))
        mini.dirigeant(X, personne(i, famille=FAMILLE))
    return mini.ecrire(tmp_path / "registre.duckdb")


def sans_noms(**surcharges: Any) -> dict[str, Any]:
    """Des réglages comme ceux de l'app : sans la clé `familles_exclues` en clair."""
    r = reglages(TETE, **surcharges)
    r.pop("familles_exclues")
    return r


def ensembles(carto: Carto) -> tuple[frozenset[Any], ...]:
    return tuple(frozenset(getattr(carto, n)) for n in ("societes", "liens", "participations", "etrangeres"))


def test_temoin_sans_exclusion_la_holding_entre(registre: Path) -> None:
    carto = cartographier(sans_noms(), registre)
    assert X in {s.siren for s in carto.societes}


def test_holding_familiale_exclue_par_empreinte_comme_par_nom(registre: Path) -> None:
    par_nom = cartographier(reglages(TETE, familles_exclues=["FamilleInventee"]), registre)
    par_empreinte = cartographier(
        sans_noms(familles_exclues_empreintes=[empreinte("FamilleInventee", CLE)]),
        registre,
        cle_empreinte=CLE,
    )
    assert X not in {s.siren for s in par_empreinte.societes}
    assert ensembles(par_empreinte) == ensembles(par_nom)


def test_empreinte_normalisee_comme_le_seed(registre: Path) -> None:
    """Le seed et l'interface hachent upper(trim(nom)) : la casse et les blancs saisis ne comptent pas."""
    carto = cartographier(
        sans_noms(familles_exclues_empreintes=[empreinte("  familleinventee ", CLE)]),
        registre,
        cle_empreinte=CLE,
    )
    assert X not in {s.siren for s in carto.societes}


def test_cle_lue_dans_l_environnement(registre: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VARIABLE_CLE, CLE)
    carto = cartographier(sans_noms(familles_exclues_empreintes=[empreinte(FAMILLE, CLE)]), registre)
    assert X not in {s.siren for s in carto.societes}


def test_autre_cle_n_exclut_rien(registre: Path) -> None:
    """Une empreinte calculée avec une autre clé ne correspond à aucun nom."""
    carto = cartographier(
        sans_noms(familles_exclues_empreintes=[empreinte(FAMILLE, "autre-cle-FAKE")]),
        registre,
        cle_empreinte=CLE,
    )
    assert X in {s.siren for s in carto.societes}


def test_empreintes_sans_cle_refusees(registre: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Jamais de comparaison sans clé : le moteur refuse au lieu d'ignorer l'exclusion."""
    monkeypatch.delenv(VARIABLE_CLE, raising=False)
    with pytest.raises(CleManquante):
        cartographier(sans_noms(familles_exclues_empreintes=[empreinte(FAMILLE, CLE)]), registre)


def test_liste_vide_sans_cle_acceptee(registre: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(VARIABLE_CLE, raising=False)
    carto = cartographier(sans_noms(familles_exclues_empreintes=[]), registre)
    assert X in {s.siren for s in carto.societes}
