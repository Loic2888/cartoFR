"""Contrôle de fraîcheur du registre (T015, SC-003).

Fiches et unités générées (`tests/fixtures/rne/`, `tests/fixtures/sirene/`) : noms inventés,
SIREN factices (règle produit 6). Aucun réseau : les clients INPI et Sirene sont simulés.
"""

from __future__ import annotations

import json
import random
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
import httpx
import pytest

from cartofr.registre import fraicheur
from cartofr.registre.formalite import Fiche, lire_fiche
from cartofr.registre.inpi_diff import Curseur, Page
from cartofr.registre.schema import creer_tables
from cartofr.registre.synchro_rne import appliquer
from cartofr.registre.synchro_sirene import Bilan, Client, Limiteur, appliquer_unites

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
AUJOURDHUI = date(2026, 10, 13)
DEBUT = date(2026, 3, 4)
TABLES = ("societes", "liens", "dirigeants_personnes", "unites_legales", "mises_a_jour")


def json_fixture(chemin: str) -> Any:
    return json.loads((FIXTURES / chemin).read_text(encoding="utf-8"))


def fiche(nom: str) -> Fiche:
    lue = lire_fiche(json_fixture(f"rne/{nom}.json"))
    assert lue is not None
    return lue


def unite(siren: str) -> dict[str, Any]:
    unites = json_fixture("sirene/unites_page1.json")["unitesLegales"]
    return next(u for u in unites if u["siren"] == siren)


@pytest.fixture
def con() -> Iterator[duckdb.DuckDBPyConnection]:
    c = duckdb.connect(":memory:")
    creer_tables(c)
    yield c
    c.close()


def photo(con: duckdb.DuckDBPyConnection) -> dict[str, list[tuple[Any, ...]]]:
    return {t: sorted(con.execute(f"select * from {t}").fetchall(), key=repr) for t in TABLES}


def tirage_rne(nom: str) -> fraicheur.Tirage:
    f = fiche(nom)
    return fraicheur.Tirage("rne", date(2026, 10, 10), f.siren, f)


def tirage_sirene(siren: str) -> fraicheur.Tirage:
    return fraicheur.Tirage("sirene", date(2026, 10, 10), siren, unite(siren))


# --- Fenêtre -----------------------------------------------------------------------------------


def test_fenetre_de_j_moins_7_a_hier_sans_aujourd_hui() -> None:
    jours = fraicheur.fenetre(AUJOURDHUI)
    assert jours[0] == date(2026, 10, 6)
    assert jours[-1] == date(2026, 10, 12)
    assert len(jours) == 7 and AUJOURDHUI not in jours


# --- Vérification : rejeu annulé ---------------------------------------------------------------


def test_fiche_rne_appliquee_est_retrouvee(con: duckdb.DuckDBPyConnection) -> None:
    appliquer(con, [fiche("societe_a_v1")], DEBUT)
    verdict = fraicheur.verifier(con, tirage_rne("societe_a_v1"), AUJOURDHUI)
    assert verdict.retrouve and verdict.ecarts == {}


def test_fiche_rne_non_appliquee_manque_et_dit_ce_qui_changerait(con: duckdb.DuckDBPyConnection) -> None:
    appliquer(con, [fiche("societe_a_v1")], DEBUT)
    avant = photo(con)
    verdict = fraicheur.verifier(con, tirage_rne("societe_a_v2"), AUJOURDHUI)
    assert not verdict.retrouve
    assert set(verdict.ecarts) & {"liens_ouverts", "liens_fermes", "societes_maj"}
    assert photo(con) == avant  # le registre n'a pas bougé


def test_societe_absente_du_registre_manque(con: duckdb.DuckDBPyConnection) -> None:
    verdict = fraicheur.verifier(con, tirage_rne("societe_a_v1"), AUJOURDHUI)
    assert verdict.ecarts.get("societes_creees") == 1
    assert photo(con)["societes"] == []


def test_radiation_non_appliquee_manque(con: duckdb.DuckDBPyConnection) -> None:
    radiee = fiche("societe_radiee")
    ouverte = Fiche(radiee.siren, radiee.denomination, radiee.diffusion_commerciale, radiee.salaries, False)
    appliquer(con, [ouverte], DEBUT)
    verdict = fraicheur.verifier(con, tirage_rne("societe_radiee"), AUJOURDHUI)
    assert verdict.ecarts.get("societes_fermees") == 1
    appliquer(con, [radiee], DEBUT)
    assert fraicheur.verifier(con, tirage_rne("societe_radiee"), AUJOURDHUI).retrouve


def test_unite_sirene_appliquee_est_retrouvee(con: duckdb.DuckDBPyConnection) -> None:
    appliquer_unites(con, [unite("000000001")], DEBUT, Bilan())
    assert fraicheur.verifier(con, tirage_sirene("000000001"), AUJOURDHUI).retrouve


def test_cessation_sirene_non_appliquee_manque(con: duckdb.DuckDBPyConnection) -> None:
    cessee = unite("000000002")
    active = json.loads(json.dumps(cessee))
    active["periodesUniteLegale"][0]["etatAdministratifUniteLegale"] = "A"
    appliquer_unites(con, [active], DEBUT, Bilan())
    avant = photo(con)
    verdict = fraicheur.verifier(con, tirage_sirene("000000002"), AUJOURDHUI)
    assert verdict.ecarts.get("societes_cessees") == 1
    assert photo(con) == avant


# --- Tirage RNE --------------------------------------------------------------------------------


class FauxInpi:
    """Rend une page par lecture et garde les appels. `pages` vides : rien ce jour-là."""

    def __init__(self, pages: list[list[dict[str, Any]]]) -> None:
        self.pages = list(pages)
        self.appels: list[tuple[date, Curseur | None, int, Path | None]] = []
        self.requetes = 0

    def lire(
        self,
        depuis: date,
        jusqua: date,
        curseur: Curseur | None = None,
        page_size: int = 100,
        chemin: Path | None = None,
    ) -> Iterator[Page]:
        self.appels.append((depuis, curseur, page_size, chemin))
        self.requetes += 1
        formalites = self.pages.pop(0) if self.pages else []
        if formalites:
            yield Page(1, formalites, None)


def test_tirage_rne_prend_une_personne_morale_au_hasard_sans_toucher_au_curseur(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CARTOFR_DATA", str(tmp_path))
    page = [
        json_fixture("rne/entreprise_individuelle.json"),
        {"company": json_fixture("rne/societe_a_v1.json")},
    ]
    client = FauxInpi([page])
    tirage = fraicheur.tirer_rne(client, fraicheur.fenetre(AUJOURDHUI), random.Random(1))
    assert tirage is not None and tirage.source == "rne"
    assert tirage.siren == fiche("societe_a_v1").siren
    jour, curseur, taille, chemin = client.appels[0]
    assert jour in fraicheur.fenetre(AUJOURDHUI)
    assert curseur is not None and curseur.search_after is not None and len(curseur.search_after) == 9
    assert taille == fraicheur.TAILLE_PAGE_RNE
    assert chemin is not None and tmp_path not in chemin.parents
    assert not (tmp_path / "inpi_diff").exists()


def test_tirage_rne_abandonne_apres_quelques_pages_vides() -> None:
    client = FauxInpi([])
    assert fraicheur.tirer_rne(client, fraicheur.fenetre(AUJOURDHUI), random.Random(1)) is None
    assert client.requetes == fraicheur.ESSAIS_PAR_TIRAGE


# --- Tirage SIRENE -----------------------------------------------------------------------------


class FauxSirene:
    def __init__(self, unite_rendue: dict[str, Any] | None) -> None:
        self.unite_rendue = unite_rendue
        self.appels: list[tuple[date, str]] = []

    def premiere_unite_depuis(self, jour: date, siren_min: str) -> dict[str, Any] | None:
        self.appels.append((jour, siren_min))
        return self.unite_rendue


def test_tirage_sirene_part_d_un_siren_tire_au_hasard() -> None:
    client = FauxSirene(unite("000000003"))
    tirage = fraicheur.tirer_sirene(client, fraicheur.fenetre(AUJOURDHUI), random.Random(3))
    assert tirage is not None and tirage.siren == "000000003"
    jour, plancher = client.appels[0]
    assert jour in fraicheur.fenetre(AUJOURDHUI)
    assert len(plancher) == 9 and plancher.isdigit()


def test_tirage_sirene_sans_changement_rend_rien() -> None:
    client = FauxSirene(None)
    assert fraicheur.tirer_sirene(client, fraicheur.fenetre(AUJOURDHUI), random.Random(3)) is None
    assert len(client.appels) == fraicheur.ESSAIS_PAR_TIRAGE


def test_client_sirene_demande_la_premiere_unite_au_dela_du_plancher() -> None:
    vues: list[httpx.Request] = []

    def serveur(requete: httpx.Request) -> httpx.Response:
        vues.append(requete)
        page = json_fixture("sirene/unites_page1.json")
        return httpx.Response(
            200, json={"header": page["header"], "unitesLegales": page["unitesLegales"][:1]}
        )

    client = Client(
        http=httpx.Client(transport=httpx.MockTransport(serveur)),
        cle="cle-FAKE",
        limiteur=Limiteur(horloge=lambda: 0.0, dormir=lambda _s: None),
    )
    brute = client.premiere_unite_depuis(date(2026, 10, 10), "420000000")
    assert brute is not None and brute["siren"] == "000000001"
    params = vues[0].url.params
    assert params["nombre"] == "1" and params["tri"] == "siren"
    assert "siren:[420000000 TO 999999999]" in params["q"]
    assert "2026-10-10T00:00:00" in params["q"] and "categorieJuridiqueUniteLegale:1000" in params["q"]


def test_client_sirene_sans_resultat_rend_none() -> None:
    client = Client(
        http=httpx.Client(transport=httpx.MockTransport(lambda _r: httpx.Response(404, json={}))),
        cle="cle-FAKE",
        limiteur=Limiteur(horloge=lambda: 0.0, dormir=lambda _s: None),
    )
    assert client.premiere_unite_depuis(date(2026, 10, 10), "999999990") is None


# --- Contrôle complet --------------------------------------------------------------------------


def test_controle_compte_les_tirages_impossibles_comme_manquants(con: duckdb.DuckDBPyConnection) -> None:
    appliquer(con, [fiche("societe_a_v1")], DEBUT)
    tirages: dict[fraicheur.Source, Any] = {
        "rne": lambda _jours: tirage_rne("societe_a_v1"),
        "sirene": lambda _jours: None,
    }
    resultat = fraicheur.controler(con, AUJOURDHUI, tirages, {"rne": 3, "sirene": 2})
    # La même fiche revient à chaque tirage : vérifiée une fois, les deux autres sont des doublons.
    assert resultat.retrouves == 1
    assert resultat.non_tires == 4
    assert resultat.demandes == 5


def test_controle_tire_de_nouveau_un_doublon(con: duckdb.DuckDBPyConnection) -> None:
    appliquer(con, [fiche("societe_a_v1"), fiche("societe_radiee")], DEBUT)
    suite = iter(["societe_a_v1", "societe_a_v1", "societe_radiee"])
    tirages: dict[fraicheur.Source, Any] = {"rne": lambda _jours: tirage_rne(next(suite))}
    resultat = fraicheur.controler(con, AUJOURDHUI, tirages, {"rne": 2})
    assert [v.tirage.siren for v in resultat.verdicts] == [
        fiche("societe_a_v1").siren,
        fiche("societe_radiee").siren,
    ]
    assert resultat.non_tires == 0
