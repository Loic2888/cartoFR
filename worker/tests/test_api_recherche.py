"""Route interne de recherche de la tête d'un groupe (T019).

Vérifie : la recherche par nom et par SIREN (C1), l'absence de tout champ de
personne dans la réponse (C2), 503 quand la synchro tient le verrou
d'écriture, 400 sur une saisie trop courte, et le classement (actives et
grosses sociétés d'abord).

Registre généré dans tmp_path avec le schéma du worker ; noms de sociétés et
de personnes inventés (règle produit 6).
"""

import json
import subprocess
import sys
import threading
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import urlopen

import duckdb
import pytest

from cartofr.api_recherche import (
    MAX_RESULTATS,
    RegistreIndisponible,
    RequeteInvalide,
    Serveur,
    normaliser,
    rechercher,
)
from cartofr.registre.schema import creer_tables

JOUR = date(2026, 3, 4)
CHAMPS = {"siren", "nom", "sigle", "ville", "statut"}

# Une personne inventée : dirigeante, et entrepreneur individuel sous son nom.
PERSONNE = "ZORGLUB"
CLE_PERSONNE = f"{PERSONNE}|ARMANDINE|1970-01"


def _registre(chemin: Path, avec_unites_legales: bool) -> Path:
    con = duckdb.connect(str(chemin))
    creer_tables(con)
    societes = [
        # siren, denomination, etat, fin
        ("100000001", "Fromagerie Éthérée", "A", None),
        ("100000002", "FROMAGERIE ETHEREE DISTRIBUTION", "A", None),
        ("100000003", "LA GRANDE FROMAGERIE ETHEREE", "A", None),
        ("100000004", "FROMAGERIE ETHEREE", "C", None),  # cessée
        ("100000005", "FROMAGERIE ETHEREE ANCIENNE", "A", date(2026, 6, 1)),  # radiée
        ("100000006", "BOULONNERIE QUANTIQUE", "A", None),
    ]
    for siren, nom, etat, fin in societes:
        con.execute(
            "insert into societes (siren, denomination, etat_administratif, debut, fin) "
            "values (?, ?, ?, ?, ?)",
            [siren, nom, etat, JOUR, fin],
        )
    sieges = [
        # siren, commune, nom, cj, tranche
        ("100000001", "VILLEFICTIVE", "FROMAGERIE ETHEREE", 5710, "41"),
        ("100000002", "BOURG-IMAGINAIRE", "FROMAGERIE ETHEREE DISTRIBUTION", 5499, "11"),
        ("100000003", "VILLEFICTIVE", "LA GRANDE FROMAGERIE ETHEREE", 5499, "01"),
        ("100000006", "PORT-INVENTE", "BOULONNERIE QUANTIQUE", 5710, "21"),
        # Entrepreneur individuel : son nom est celui d'une personne.
        ("100000009", "VILLEFICTIVE", f"{PERSONNE} ARMANDINE", 1000, "00"),
    ]
    for siren, commune, nom, cj, tranche in sieges:
        con.execute(
            "insert into sieges (siren, commune, nom, cj, tranche) values (?, ?, ?, ?, ?)",
            [siren, commune, nom, cj, tranche],
        )
    con.execute(
        "insert into dirigeants_personnes (siren, personne, role, debut) values (?, ?, '30', ?)",
        ["100000001", CLE_PERSONNE, JOUR],
    )
    if not avec_unites_legales:
        # Registre d'avant T016 : la table n'existait pas, la recherche s'en passe.
        con.execute("drop table unites_legales")
    else:
        # Table réelle de creer_tables : sa contrainte refuse déjà les entrepreneurs
        # individuels (cj 1000) ; celui de `sieges` sert au test « aucune personne ».
        unites = [
            ("100000001", "FROMAGERIE ETHEREE", "FEQ", 5710, "41", "A"),
            ("100000006", "BOULONNERIE QUANTIQUE", "BQ", 5710, "21", "A"),
            ("100000007", "SOCIETE SANS RNE", "FEQ2", 5499, "03", "A"),
        ]
        for siren, nom, sigle, cj, tranche, etat in unites:
            con.execute(
                "insert into unites_legales (siren, denomination, sigle, categorie_juridique, "
                "tranche_effectifs, etat_administratif, debut) values (?, ?, ?, ?, ?, ?, ?)",
                [siren, nom, sigle, cj, tranche, etat, JOUR],
            )
    con.close()
    return chemin


@pytest.fixture(params=[False, True], ids=["sans_unites_legales", "avec_unites_legales"])
def registre(request: pytest.FixtureRequest, tmp_path: Path) -> Path:
    return _registre(tmp_path / "registre.duckdb", avec_unites_legales=request.param)


@pytest.fixture
def serveur(registre: Path) -> Iterator[str]:
    """La route HTTP sur un port libre de 127.0.0.1 ; rend l'URL de base."""
    srv = Serveur(("127.0.0.1", 0), registre)
    fil = threading.Thread(target=srv.serve_forever, daemon=True)
    fil.start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()
        srv.server_close()


def _get(url: str) -> tuple[int, dict[str, Any]]:
    try:
        with urlopen(url, timeout=10) as reponse:
            return reponse.status, json.loads(reponse.read())
    except HTTPError as exc:
        return exc.code, json.loads(exc.read())


# --- C1 : par nom et par SIREN ---------------------------------------------------------


def test_recherche_par_nom_sans_accents_ni_casse(registre: Path) -> None:
    resultats = rechercher("fromagerie éthérée", registre)
    sirens = [r.siren for r in resultats]
    assert {"100000001", "100000002", "100000003"} <= set(sirens)
    assert "100000006" not in sirens


def test_recherche_par_siren(registre: Path) -> None:
    resultats = rechercher("100000006", registre)
    assert [(r.siren, r.nom, r.ville, r.statut) for r in resultats] == [
        ("100000006", "BOULONNERIE QUANTIQUE", "PORT-INVENTE", "active")
    ]
    # Un SIREN tapé avec des espaces est le même SIREN.
    assert [r.siren for r in rechercher("100 000 006", registre)] == ["100000006"]


def test_siren_inconnu_ou_nom_absurde_ne_rend_rien(registre: Path) -> None:
    assert rechercher("999999999", registre) == []
    assert rechercher("zzzzqqq", registre) == []


def test_classement_actives_et_grosses_d_abord(registre: Path) -> None:
    resultats = rechercher("FROMAGERIE ETHEREE", registre)
    sirens = [r.siren for r in resultats]
    # Famille « commence par » : la plus grosse active d'abord, puis l'autre active,
    # puis la cessée et la radiée. « Contient » (100000003) vient après.
    assert sirens[:2] == ["100000001", "100000002"]
    assert set(sirens[2:4]) == {"100000004", "100000005"}
    assert sirens.index("100000003") > sirens.index("100000005")


def test_statuts(registre: Path) -> None:
    statuts = {r.siren: r.statut for r in rechercher("FROMAGERIE", registre)}
    assert statuts["100000001"] == "active"
    assert statuts["100000004"] == "cessee"
    assert statuts["100000005"] == "radiee"


def test_par_sigle_si_unites_legales(tmp_path: Path) -> None:
    chemin = _registre(tmp_path / "r.duckdb", avec_unites_legales=True)
    resultats = rechercher("FEQ", chemin)
    assert [r.siren for r in resultats][:2] == ["100000001", "100000007"]
    assert resultats[0].sigle == "FEQ"


def test_vingt_resultats_au_plus(tmp_path: Path) -> None:
    chemin = _registre(tmp_path / "r.duckdb", avec_unites_legales=False)
    con = duckdb.connect(str(chemin))
    for i in range(30):
        con.execute(
            "insert into societes (siren, denomination, debut) values (?, ?, ?)",
            [f"2000000{i:02d}", f"PAPETERIE NEBULEUSE {i}", JOUR],
        )
    con.close()
    assert len(rechercher("PAPETERIE NEBULEUSE", chemin)) == MAX_RESULTATS


# --- C2 : aucun champ de personne ------------------------------------------------------


def test_reponse_sans_champ_de_personne(serveur: str) -> None:
    statut, corps = _get(f"{serveur}/recherche?q=FROMAGERIE")
    assert statut == 200
    assert corps["resultats"]
    for resultat in corps["resultats"]:
        assert set(resultat) == CHAMPS
    texte = json.dumps(corps)
    assert PERSONNE not in texte
    assert "ARMANDINE" not in texte


def test_entrepreneur_individuel_et_dirigeants_jamais_rendus(registre: Path) -> None:
    # Le nom de l'entrepreneur individuel (cj 1000) et la clé du dirigeant ne sortent pas.
    assert rechercher(PERSONNE, registre) == []
    assert rechercher("ARMANDINE", registre) == []
    assert rechercher("100000009", registre) == []


# --- Erreurs : saisie, registre verrouillé ou absent -----------------------------------


def test_saisie_trop_courte(registre: Path, serveur: str) -> None:
    with pytest.raises(RequeteInvalide):
        rechercher(" a ", registre)
    for q in ["", "a", "%20"]:
        statut, corps = _get(f"{serveur}/recherche?q={q}")
        assert (statut, corps) == (400, {"erreur": "requete_trop_courte"})
    statut, _ = _get(f"{serveur}/recherche")
    assert statut == 400


def test_saisie_trop_longue(registre: Path) -> None:
    with pytest.raises(RequeteInvalide):
        rechercher("A" * 101, registre)


def test_503_quand_la_synchro_tient_le_verrou(registre: Path, serveur: str) -> None:
    # Un autre processus ouvre le registre en écriture, comme la synchro de nuit.
    ecrivain = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import duckdb, sys; c = duckdb.connect(sys.argv[1]); "
            "print('pret', flush=True); sys.stdin.read()",
            str(registre),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert ecrivain.stdout is not None
        assert ecrivain.stdout.readline().strip() == "pret"
        with pytest.raises(RegistreIndisponible) as exc:
            rechercher("FROMAGERIE", registre)
        assert exc.value.code == "registre_occupe"
        statut, corps = _get(f"{serveur}/recherche?q=FROMAGERIE")
        assert (statut, corps) == (503, {"erreur": "registre_occupe"})
    finally:
        ecrivain.communicate(timeout=10)
    # Verrou rendu : la recherche repart.
    assert _get(f"{serveur}/recherche?q=FROMAGERIE")[0] == 200


def test_503_quand_le_registre_est_absent(tmp_path: Path) -> None:
    srv = Serveur(("127.0.0.1", 0), tmp_path / "absent.duckdb")
    fil = threading.Thread(target=srv.serve_forever, daemon=True)
    fil.start()
    try:
        statut, corps = _get(f"http://127.0.0.1:{srv.server_address[1]}/recherche?q=FROMAGERIE")
    finally:
        srv.shutdown()
        srv.server_close()
    assert (statut, corps) == (503, {"erreur": "registre_absent"})


def test_sante_et_routes_inconnues(serveur: str) -> None:
    assert _get(f"{serveur}/sante") == (200, {"statut": "ok"})
    assert _get(f"{serveur}/dirigeants?q=x")[0] == 404


def test_journal_sans_la_saisie(registre: Path, serveur: str, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO", logger="cartofr.recherche")
    _get(f"{serveur}/recherche?q={PERSONNE}")
    _get(f"{serveur}/recherche?q=x")
    assert caplog.records
    assert all(PERSONNE not in r.getMessage() for r in caplog.records)


def test_normaliser() -> None:
    assert normaliser("  Société   Générale ") == "SOCIETE GENERALE"
    assert normaliser("Crédit Mutuel") == "CREDIT MUTUEL"
