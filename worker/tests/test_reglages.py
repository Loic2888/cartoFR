"""Schéma des réglages (T020) : mêmes verdicts que Zod sur les fixtures partagées.

Chaque fixture de tests/fixtures/reglages/ porte son verdict dans son nom :
`valide_*.json` doit passer, `invalide_*.json` doit être refusée. Le même
parcours tourne côté web (web/lib/reglages/schema.test.ts) : C1.
"""

import json
from pathlib import Path

import pytest

from cartofr.empreinte import empreinte
from cartofr.reglages import Reglages, ReglagesInvalides, valider

FIXTURES = Path(__file__).parent / "fixtures" / "reglages"
VALIDES = sorted(FIXTURES.glob("valide_*.json"))
INVALIDES = sorted(FIXTURES.glob("invalide_*.json"))
CONFIG = Path(__file__).resolve().parents[2] / "config"


def _lire(chemin: Path) -> object:
    return json.loads(chemin.read_text(encoding="utf-8"))


def test_les_fixtures_existent():
    assert len(VALIDES) >= 3 and len(INVALIDES) >= 10


@pytest.mark.parametrize("chemin", VALIDES, ids=lambda p: p.name)
def test_fixture_valide_acceptee(chemin: Path):
    assert isinstance(valider(_lire(chemin)), Reglages)


@pytest.mark.parametrize("chemin", INVALIDES, ids=lambda p: p.name)
def test_fixture_invalide_refusee(chemin: Path):
    with pytest.raises(ReglagesInvalides):
        valider(_lire(chemin))


def test_famille_en_clair_refusee_avec_un_message_clair():
    with pytest.raises(ReglagesInvalides) as e:
        valider({"groupe": "Groupe Fictif", "tete": "123456789", "familles_exclues": ["NOM FICTIF"]})
    assert "familles_exclues" in str(e.value)
    # Le nom saisi n'est jamais recopié dans l'erreur.
    assert "NOM FICTIF" not in str(e.value)


def test_erreur_sans_la_valeur_saisie():
    with pytest.raises(ReglagesInvalides) as e:
        valider({"groupe": "Groupe Fictif", "tete": "123456789", "exclus_noms": ["NOM\nFICTIF"]})
    assert "FICTIF" not in str(e.value)
    assert "exclus_noms.0" in str(e.value)


def test_listes_absentes_vides_par_defaut():
    r = valider({"groupe": "Groupe Fictif", "tete": "123456789"})
    assert r.marques_sures == [] and r.familles_exclues_empreintes == []


@pytest.mark.parametrize("nom", ["cmaf", "lvmh", "vinci"])
def test_fixture_reprend_la_config(nom: str):
    """La fixture valide est la config du prototype, familles remplacées par leurs empreintes."""
    config = _lire(CONFIG / f"{nom}.json")
    fixture = _lire(FIXTURES / f"valide_{nom}.json")
    assert isinstance(config, dict) and isinstance(fixture, dict)
    familles = config.pop("familles_exclues", [])
    empreintes = fixture.pop("familles_exclues_empreintes")
    assert fixture == config
    assert empreintes == [empreinte(n, "cle-de-test-FAKE") for n in familles]


def test_vecteurs_d_empreinte():
    """Mêmes vecteurs que web/lib/reglages/empreinte.test.ts."""
    vecteurs = _lire(FIXTURES / "empreintes.json")
    assert isinstance(vecteurs, dict)
    assert len(vecteurs["vecteurs"]) >= 10
    for v in vecteurs["vecteurs"]:
        assert empreinte(v["nom"], v["cle"]) == v["empreinte"]
