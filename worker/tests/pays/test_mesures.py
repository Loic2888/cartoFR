"""Mesures de la carto du pays (T052) : non-régression depuis `pays.duckdb`, fraîcheur, couverture.

Carto du pays, référence et liste de sociétés cotées inventées (règle produit 6) : aucune référence
Basile ni carto client n'est lue.
"""

import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import pytest

from cartofr.pays.schema import DDL as DDL_PAYS
from cartofr.registre.fraicheur import FENETRE_JOURS, fraicheur_pays
from cartofr.registre.schema import creer_tables

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import controle_fraicheur  # noqa: E402  # pyright: ignore[reportMissingImports]
import mesure_couverture  # noqa: E402  # pyright: ignore[reportMissingImports]
import non_regression  # noqa: E402  # pyright: ignore[reportMissingImports]

TETE = "900000000"
AUTRE_TETE = "800000000"
DONNEES = date(2026, 10, 11)


def siren(n: int) -> str:
    return f"9{n:08d}"


def ecrire_pays(chemin: Path, filles: list[tuple[str, str]], date_donnees: date | None = DONNEES) -> Path:
    """Une carto du pays : TETE et ses filles (siren, maniere), plus un autre groupe documenté."""
    con = duckdb.connect(str(chemin))
    con.execute(DDL_PAYS)
    con.execute(
        "insert into pays_groupes values (?, 'TETE INVENTEE', ?, null, false, null, ?)",
        [TETE, len(filles) + 1, date_donnees],
    )
    con.execute(
        "insert into pays_groupes values (?, 'AUTRE INVENTEE', 2, 'autre.pdf', false, null, ?)",
        [AUTRE_TETE, date_donnees],
    )
    lignes = [(TETE, TETE, None, 0, "inscription"), (AUTRE_TETE, AUTRE_TETE, None, 0, "inscription")]
    lignes += [(s, TETE, TETE, 1, maniere) for s, maniere in filles]
    lignes.append(("800000001", AUTRE_TETE, AUTRE_TETE, 1, "descente"))
    for s, groupe, mere, niveau, maniere in lignes:
        con.execute(
            "insert into pays_societes values (?, ?, 'SOCIETE INVENTEE', ?, ?, 'preuve', 'A', 'raison', ?,"
            " null, true, 'Société opérationnelle', false, false)",
            [s, groupe, mere, niveau, maniere],
        )
    con.execute(
        "insert into pays_bilan values (?, ?, 2, ?, 1, 0, 1.0)",
        [datetime(2026, 10, 12, 3, 0, tzinfo=UTC), date_donnees, len(lignes)],
    )
    con.close()
    return chemin


def ecrire_reference(dossier: Path, groupe: str, sirens: list[str]) -> None:
    with (dossier / f"{groupe}_entites.csv").open("w", encoding="utf-8") as f:
        f.write("SIREN\n" + "".join(f"{s}\n" for s in sirens))


@pytest.fixture
def dossier(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Un dépôt inventé : config/cmaf.json (tête TETE), données et références dans tmp_path."""
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "cmaf.json").write_text(json.dumps({"groupe": "CMAF", "tete": TETE}))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CARTOFR_DATA", str(tmp_path))
    monkeypatch.setenv("CARTOFR_REFERENCES", str(tmp_path))
    monkeypatch.delenv("CARTOFR_PAYS", raising=False)
    return tmp_path


# --- C1 : non-régression depuis la carto du pays -----------------------------------------------

REFERENCE = [siren(n) for n in range(1, 53)]  # 52 sociétés, comme la référence CMAF


def test_c1_mesure_la_descente_de_la_tete(dossier: Path) -> None:
    filles = [(s, "descente") for s in REFERENCE[:45]] + [(siren(100), "inscription"), (siren(101), "arbre")]
    ecrire_reference(dossier, "cmaf", REFERENCE)
    pays = ecrire_pays(dossier / "pays.duckdb", filles)
    r = non_regression.mesurer_depuis_pays("cmaf", pays, dossier, dossier / "config")
    assert (r.reference, r.retrouvees, r.manquees) == (52, 45, 7)
    assert r.nous == 48  # la tête, 45 retrouvées, 2 en plus ; jamais l'autre groupe
    assert r.en_plus == 3 and r.en_plus_inscrites == 2  # la tête et siren(100) sont inscrites
    assert r.memoire_go is None


def test_c1_rend_0_quand_le_seuil_est_tenu(dossier: Path) -> None:
    ecrire_reference(dossier, "cmaf", REFERENCE)
    ecrire_pays(dossier / "pays.duckdb", [(s, "descente") for s in REFERENCE[:43]])
    assert non_regression.main(["cmaf", "--depuis-pays"]) == 0


def test_c1_rend_1_tant_qu_un_seuil_manque(dossier: Path, capsys: pytest.CaptureFixture[str]) -> None:
    ecrire_reference(dossier, "cmaf", REFERENCE)
    ecrire_pays(dossier / "pays.duckdb", [(s, "descente") for s in REFERENCE[:42]])
    assert non_regression.main(["cmaf", "--depuis-pays"]) == 1
    assert "retrouvées 42/52 < 43/52" in capsys.readouterr().out


def test_c1_rend_2_sans_carto_du_pays_ou_sans_la_tete(dossier: Path) -> None:
    ecrire_reference(dossier, "cmaf", REFERENCE)
    assert non_regression.main(["cmaf", "--depuis-pays"]) == 2
    (dossier / "config" / "cmaf.json").write_text(json.dumps({"groupe": "CMAF", "tete": "700000000"}))
    ecrire_pays(dossier / "pays.duckdb", [])
    assert non_regression.main(["cmaf", "--depuis-pays"]) == 2


def test_c1_options_incompatibles(dossier: Path) -> None:
    with pytest.raises(SystemExit):
        non_regression.main(["cmaf", "--depuis-pays", "--depuis-postgres"])
    with pytest.raises(SystemExit):
        non_regression.main(["cmaf", "--depuis-pays", "--sans-reglages"])


def _resultat(groupe: str, retrouvees: int, reference: int, en_plus: int, inscrites: int):  # noqa: ANN202
    r = non_regression.comparer(groupe, [], {}, 0.0, None)
    return non_regression.replace(
        r, reference=reference, retrouvees=retrouvees, en_plus=en_plus, en_plus_inscrites=inscrites
    )


def test_c1_seuils_de_sc001() -> None:
    verdict = non_regression.verdict
    assert verdict(_resultat("lvmh", 154, 172, 16, 0), depuis_pays=True) == []
    assert verdict(_resultat("lvmh", 153, 172, 0, 0), depuis_pays=True) == ["retrouvées 153/172 < 154/172"]
    # Les « en plus » inscrits par le document ne comptent pas dans le plafond.
    assert verdict(_resultat("lvmh", 160, 172, 76, 60), depuis_pays=True) == []
    assert verdict(_resultat("lvmh", 160, 172, 77, 60), depuis_pays=True) == ["en plus hors document 17 > 16"]
    assert verdict(_resultat("vinci", 813, 1007, 193, 0), depuis_pays=True) == []
    assert verdict(_resultat("vinci", 813, 1007, 194, 0), depuis_pays=True) == [
        "en plus hors document 194 > 193"
    ]
    assert verdict(_resultat("cmaf", 43, 52, 500, 0), depuis_pays=True) == []


# --- C2 : fraîcheur de la carto du pays ------------------------------------------------------


def test_c2_carto_du_pays_a_jour_jusqu_a_7_jours(tmp_path: Path) -> None:
    pays = ecrire_pays(tmp_path / "pays.duckdb", [])
    a_jour = fraicheur_pays(pays, date(2026, 10, 18))
    assert a_jour.date_donnees == DONNEES and a_jour.retard_jours == FENETRE_JOURS and a_jour.a_jour
    en_retard = fraicheur_pays(pays, date(2026, 10, 19))
    assert en_retard.retard_jours == 8 and not en_retard.a_jour
    assert "RETARD" in controle_fraicheur.ligne_pays(en_retard)
    assert "11/10/2026" in controle_fraicheur.ligne_pays(a_jour)
    assert "à jour" in controle_fraicheur.ligne_pays(a_jour)


def test_c2_carto_du_pays_absente_ou_sans_date_est_en_retard(tmp_path: Path) -> None:
    absente = fraicheur_pays(tmp_path / "pays.duckdb", date(2026, 10, 18))
    assert not absente.a_jour and absente.date_donnees is None
    assert "RETARD" in controle_fraicheur.ligne_pays(absente)
    assert not fraicheur_pays(ecrire_pays(tmp_path / "futur.duckdb", []), date(2026, 10, 10)).a_jour
    sans_date = fraicheur_pays(
        ecrire_pays(tmp_path / "pays.duckdb", [], date_donnees=None), date(2026, 10, 18)
    )
    assert not sans_date.a_jour


# --- C3 : couverture ------------------------------------------------------------------------


def _registre(chemin: Path, actives: list[str]) -> Path:
    con = duckdb.connect(str(chemin))
    creer_tables(con)
    for s in actives:
        con.execute("insert into sieges (siren, nom, cj) values (?, 'SOCIETE INVENTEE', 5710)", [s])
    con.close()
    return chemin


def test_c3_couverture_et_groupes_cotes(tmp_path: Path) -> None:
    pays = ecrire_pays(tmp_path / "pays.duckdb", [(siren(1), "descente"), (siren(2), "descente")])
    seule = "700000001"
    registre = _registre(
        tmp_path / "registre.duckdb", [TETE, siren(1), siren(2), AUTRE_TETE, "800000001", seule]
    )
    con = mesure_couverture.ouvrir(registre, pays)
    try:
        c = mesure_couverture.couverture(con)
        cotes = mesure_couverture.cotation(con, [siren(1), TETE, AUTRE_TETE, seule, "600000000", siren(1)])
    finally:
        con.close()
    assert (c.actives, c.rangees) == (6, 5)
    assert mesure_couverture.pourcent(c.part) == "83,3 %"
    assert [(g.tete, g.document, g.cotees) for g in cotes.groupes] == [
        (AUTRE_TETE, True, 1),
        (TETE, False, 2),
    ]
    assert [g.tete for g in cotes.sans_document] == [TETE]
    assert cotes.seules == [seule] and cotes.absentes == ["600000000"]


def test_c3_lire_cotees(tmp_path: Path) -> None:
    chemin = tmp_path / "cotees.csv"
    chemin.write_text("﻿Nom;SIREN\nA;900 000 001\nB;abc\nC;900000002\n", encoding="utf-8")
    assert mesure_couverture.lire_cotees(chemin) == ["900000001", "900000002"]
    chemin.write_text("siren,nom\n900000003,D\n", encoding="utf-8")
    assert mesure_couverture.lire_cotees(chemin) == ["900000003"]


@pytest.mark.parametrize(
    "contenu",
    [
        "SIREN\n900000001\n",
        "SIREN\r\n900000001\r\n",
        "Siren\tNom\n900000001\tA\n",
        "nom;Siren\nA;900\u00a0000\u00a0001\n",
    ],
    ids=["une-colonne", "crlf", "tabulation", "insecables"],
)
def test_c3_lire_cotees_formats_courants(tmp_path: Path, contenu: str) -> None:
    chemin = tmp_path / "cotees.csv"
    chemin.write_text(contenu, encoding="utf-8", newline="")
    assert mesure_couverture.lire_cotees(chemin) == ["900000001"]


def test_c3_liste_sans_siren_lisible(dossier: Path, capsys: pytest.CaptureFixture[str]) -> None:
    ecrire_pays(dossier / "pays.duckdb", [])
    _registre(dossier / "registre.duckdb", [TETE])
    (dossier / "vide.csv").write_text("SIREN\n", encoding="utf-8")
    (dossier / "autre.csv").write_text("code\n900000001\n", encoding="utf-8")
    assert mesure_couverture.main(["--cotees", str(dossier / "vide.csv")]) == 2
    assert mesure_couverture.main(["--cotees", str(dossier / "autre.csv")]) == 2
    assert "Aucun SIREN lu" in capsys.readouterr().err


def test_c3_main(dossier: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert mesure_couverture.main([]) == 2
    ecrire_pays(dossier / "pays.duckdb", [])
    _registre(dossier / "registre.duckdb", [TETE, AUTRE_TETE, "800000001"])
    assert mesure_couverture.main([]) == 0
    sortie = capsys.readouterr().out
    assert "Sociétés actives : 3 ; dans un groupe : 3 (100,0 %)" in sortie
    assert "non mesurés" in sortie
