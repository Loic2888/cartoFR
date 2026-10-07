"""Synchro RNE : lecture des fiches et application au registre (T011).

Fiches générées dans `tests/fixtures/rne/` : noms inventés (« SOCIETE FICTIVE A »,
« PERSONNE FICTIVE 1 »), SIREN factices (règle produit 6). Aucun réseau : le
client INPI est remplacé par un faux lecteur de pages.
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
import pytest

from cartofr.registre import synchro_rne
from cartofr.registre.formalite import Fiche, FormaliteInvalide, lire_fiche
from cartofr.registre.inpi_diff import Curseur, Page, QuotaAtteint
from cartofr.registre.schema import creer_tables
from cartofr.registre.synchro_rne import MESSAGE_QUOTA, appliquer, lire_fiches, synchroniser

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "rne"
J0, J1, J2, J3 = date(2026, 3, 4), date(2026, 1, 14), date(2026, 1, 15), date(2026, 1, 16)
A, RADIEE = "000000001", "000000002"
MERE, B, C, D = "000000010", "000000011", "000000012", "000000013"
TABLES = ("societes", "liens", "dirigeants_personnes")


def fiche_json(nom: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{nom}.json").read_text(encoding="utf-8"))


def fiche(nom: str) -> Fiche:
    lue = lire_fiche(fiche_json(nom))
    assert lue is not None
    return lue


@pytest.fixture
def con() -> Iterator[duckdb.DuckDBPyConnection]:
    connexion = duckdb.connect(":memory:")
    creer_tables(connexion)
    yield connexion
    connexion.close()


def lignes(con: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None) -> list[tuple]:
    return con.execute(sql, params).fetchall()


def photo(con: duckdb.DuckDBPyConnection) -> dict[str, list[tuple]]:
    """Contenu complet des tables du registre, trié."""
    return {t: sorted(con.execute(f"select * from {t}").fetchall(), key=repr) for t in TABLES}


def liens(con: duckdb.DuckDBPyConnection, enfant: str = A) -> list[tuple]:
    return lignes(
        con,
        "select parent, role, source, debut, fin from liens where enfant = ? order by parent, debut",
        [enfant],
    )


# --- Lecture d'une fiche (formalite.py) -------------------------------------------------------------


def test_lire_fiche_reprend_les_champs_de_build_links() -> None:
    f = fiche("societe_a_v1")
    assert (f.siren, f.denomination, f.diffusion_commerciale, f.salaries, f.radiee) == (
        A,
        "SOCIETE FICTIVE A",
        True,
        12,
        False,
    )
    # actif vide = actif (MEMORY.md, 2026-10-06)
    assert f.liens == {(MERE, "5132"), (B, "5110")}
    assert f.personnes == {("PERSONNE FICTIVE 1|PRENOM FICTIF|1970-01", "5132")}


def test_lire_fiche_ecarte_un_pouvoir_inactif() -> None:
    f = fiche("societe_a_v2")
    assert f.liens == {(B, "5110"), (C, "5132")}
    assert f.diffusion_commerciale is False


def test_lire_fiche_radiee() -> None:
    assert fiche("societe_radiee").radiee is True


def test_lire_fiche_ignore_ce_qui_n_est_pas_une_personne_morale() -> None:
    assert lire_fiche(fiche_json("entreprise_individuelle")) is None
    assert lire_fiche({"formality": {"content": {"personneMorale": {}}}}) is None


@pytest.mark.parametrize(
    "mauvaise",
    [None, [], {"formality": "texte"}, {"formality": {"siren": 1, "content": {"personneMorale": {"a": 1}}}}],
)
def test_lire_fiche_invalide(mauvaise: Any) -> None:
    with pytest.raises(FormaliteInvalide):
        lire_fiche(mauvaise)
    with pytest.raises(FormaliteInvalide):
        lire_fiche(fiche_json("formalite_invalide"))


def test_lire_fiche_accepte_l_enveloppe_de_l_api_diff() -> None:
    assert lire_fiche({"company": fiche_json("societe_a_v1")}) == fiche("societe_a_v1")


def test_lire_fiches_compte_les_ecartees() -> None:
    noms = ("societe_a_v1", "entreprise_individuelle", "formalite_invalide")
    fiches, bilan = lire_fiches([fiche_json(n) for n in noms])
    assert [f.siren for f in fiches] == [A]
    assert (bilan.ignorees, bilan.invalides) == (1, 1)


def test_la_cle_de_personne_ne_s_affiche_pas() -> None:
    assert "FICTIVE 1" not in repr(fiche("societe_a_v1"))


# --- Application au registre (synchro_rne.appliquer) -------------------------------------------------


def test_c1_nouveau_lien_ouvert_avec_sa_date_de_debut(con: duckdb.DuckDBPyConnection) -> None:
    bilan = appliquer(con, [fiche("societe_a_v1")], J1)
    assert liens(con) == [(MERE, "5132", "rne_diff", J1, None), (B, "5110", "rne_diff", J1, None)]
    assert lignes(
        con, "select siren, denomination, opposition_prospection, salaries, debut, fin from societes"
    ) == [(A, "SOCIETE FICTIVE A", False, 12, J1, None)]
    assert (bilan.societes_creees, bilan.liens_ouverts, bilan.personnes_ouvertes) == (1, 2, 1)
    assert (bilan.ajoutes, bilan.fermes) == (3, 0)


def test_c2_lien_disparu_ferme_et_non_supprime(con: duckdb.DuckDBPyConnection) -> None:
    appliquer(con, [fiche("societe_a_v1")], J1)
    bilan = appliquer(con, [fiche("societe_a_v2")], J2)
    assert liens(con) == [
        (MERE, "5132", "rne_diff", J1, J2),  # disparu : fermé, la ligne reste
        (B, "5110", "rne_diff", J1, None),  # inchangé : rien ne bouge
        (C, "5132", "rne_diff", J2, None),  # nouveau
    ]
    assert lignes(con, "select count(*) from liens where parent = ?", [D]) == [(0,)]  # actif = false
    assert lignes(con, "select personne, debut, fin from dirigeants_personnes order by debut") == [
        ("PERSONNE FICTIVE 1|PRENOM FICTIF|1970-01", J1, J2),
        ("PERSONNE FICTIVE 2|PRENOM FICTIF|1980-02", J2, None),
    ]
    assert lignes(
        con,
        "select denomination, diffusion_commerciale, opposition_prospection, salaries, debut from societes",
    ) == [("SOCIETE FICTIVE A RENOMMEE", False, True, 15, J1)]
    assert (bilan.societes_maj, bilan.liens_ouverts, bilan.liens_fermes) == (1, 1, 1)
    assert (bilan.personnes_ouvertes, bilan.personnes_fermees) == (1, 1)


def test_idempotence_la_meme_fiche_deux_fois_ne_change_rien(con: duckdb.DuckDBPyConnection) -> None:
    appliquer(con, [fiche("societe_a_v1")], J1)
    appliquer(con, [fiche("societe_a_v2")], J2)
    avant = photo(con)
    for jour in (J2, J3):
        bilan = appliquer(con, [fiche("societe_a_v2"), fiche("societe_a_v2")], jour)
        assert photo(con) == avant
        assert bilan.ajoutes == bilan.fermes == bilan.societes_maj == 0
        assert bilan.personnes_ouvertes == bilan.personnes_fermees == 0


def test_doublons_du_registre_tous_fermes_et_jamais_recrees(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("insert into societes (siren, debut) values (?, ?)", [A, J1])
    for parent, role in [(MERE, "5132"), (MERE, "5132"), (B, "5110"), (B, "5110")]:
        con.execute(
            "insert into liens (parent, enfant, role, debut) values (?, ?, ?, ?)", [parent, A, role, J1]
        )
    bilan = appliquer(con, [fiche("societe_a_v2")], J2)
    assert lignes(
        con, "select parent, source, fin from liens where parent in (?, ?) order by all", [MERE, B]
    ) == [
        (MERE, "rne_stock", J2),
        (MERE, "rne_stock", J2),
        (B, "rne_stock", None),
        (B, "rne_stock", None),
    ]
    assert (bilan.liens_fermes, bilan.liens_ouverts) == (2, 1)  # seul C est ouvert


def test_role_vide_compare_comme_une_valeur(con: duckdb.DuckDBPyConnection) -> None:
    sans_role = copy.deepcopy(fiche_json("societe_a_v2"))
    for pouvoir in sans_role["formality"]["content"]["personneMorale"]["composition"]["pouvoirs"]:
        pouvoir.pop("roleEntreprise")
    f = lire_fiche(sans_role)
    assert f is not None
    appliquer(con, [f], J1)
    avant = photo(con)
    bilan = appliquer(con, [f], J2)
    assert photo(con) == avant
    assert bilan.liens_ouverts == bilan.liens_fermes == 0


def test_societe_radiee_fermee_puis_rouverte(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("insert into societes (siren, debut) values (?, ?)", [RADIEE, J0.replace(year=2025)])
    con.execute(
        "insert into liens (parent, enfant, role, debut) values (?, ?, ?, ?)", [MERE, RADIEE, "5132", J1]
    )
    con.execute(
        "insert into dirigeants_personnes (siren, personne, role, debut) values (?, ?, ?, ?)",
        [RADIEE, "PERSONNE FICTIVE 9|X|1990-01", "5132", J1],
    )
    bilan = appliquer(con, [fiche("societe_radiee")], J2)
    assert lignes(con, "select fin from societes where siren = ?", [RADIEE]) == [(J2,)]
    assert lignes(con, "select fin from liens where enfant = ?", [RADIEE]) == [(J2,)]
    assert lignes(con, "select fin from dirigeants_personnes where siren = ?", [RADIEE]) == [(J2,)]
    assert (bilan.societes_fermees, bilan.liens_fermes, bilan.personnes_fermees, bilan.fermes) == (1, 1, 1, 2)

    revenue = copy.deepcopy(fiche_json("societe_radiee"))
    del revenue["formality"]["content"]["personneMorale"]["detailCessationEntreprise"]
    f = lire_fiche(revenue)
    assert f is not None
    bilan = appliquer(con, [f], J3)
    assert lignes(con, "select fin from societes where siren = ?", [RADIEE]) == [(None,)]
    assert liens(con, RADIEE) == [(MERE, "5132", "rne_stock", J1, J2), (MERE, "5132", "rne_diff", J3, None)]
    assert (bilan.societes_rouvertes, bilan.liens_ouverts) == (1, 1)


def test_nouvelle_societe_deja_radiee(con: duckdb.DuckDBPyConnection) -> None:
    bilan = appliquer(con, [fiche("societe_radiee")], J2)
    assert lignes(con, "select debut, fin from societes") == [(J2, J2)]
    assert lignes(con, "select count(*) from liens") == [(0,)]
    assert bilan.societes_creees == 1


def test_une_opposition_ne_se_perd_pas_par_un_champ_vide(con: duckdb.DuckDBPyConnection) -> None:
    appliquer(con, [fiche("societe_a_v2")], J1)
    sans_diffusion = copy.deepcopy(fiche_json("societe_a_v2"))
    del sans_diffusion["formality"]["diffusionCommerciale"]
    f = lire_fiche(sans_diffusion)
    assert f is not None
    appliquer(con, [f], J2)
    assert lignes(con, "select diffusion_commerciale, opposition_prospection from societes") == [
        (False, True)
    ]


def test_c3_erreur_en_cours_de_lot_laisse_le_registre_inchange(con: duckdb.DuckDBPyConnection) -> None:
    appliquer(con, [fiche("societe_a_v1")], J1)
    # Lien de la société radiée ouvert après le jour appliqué : le fermer viole fin >= debut.
    con.execute(
        "insert into liens (parent, enfant, role, debut) values (?, ?, ?, ?)", [MERE, RADIEE, "5132", J3]
    )
    avant = photo(con)
    with pytest.raises(duckdb.ConstraintException):
        appliquer(con, [fiche("societe_a_v2"), fiche("societe_radiee")], J2)
    assert photo(con) == avant  # ni la société A renommée, ni ses liens, ni RADIEE créée
    # La connexion reste utilisable : la transaction a bien été annulée.
    assert appliquer(con, [fiche("societe_a_v2")], J2).liens_ouverts == 1


# --- Passage complet (synchro_rne.synchroniser) ------------------------------------------------------


class FauxLecteur:
    """Rend des pages préparées ; une exception dans la liste est levée à son tour."""

    def __init__(self, pages: list[list[dict[str, Any]] | BaseException]) -> None:
        self.pages = pages
        self.requetes = 0
        self.curseur_recu: Curseur | None = None

    def lire(
        self,
        depuis: date,
        jusqua: date,
        curseur: Curseur | None = None,
        page_size: int = 100,
        chemin: Path | None = None,
    ) -> Iterator[Page]:
        self.curseur_recu = curseur
        for numero, page in enumerate(self.pages, 1):
            self.requetes += 1
            if isinstance(page, BaseException):
                raise page
            # Forme réelle d'une page `/diff` : une liste de `{"company": ...}`.
            yield Page(numero, [{"company": c} for c in page], None)


def journal(con: duckdb.DuckDBPyConnection) -> list[tuple]:
    return lignes(con, "select source, statut, ajoutes, fermes, erreur from mises_a_jour order by id")


def test_synchroniser_succes(con: duckdb.DuckDBPyConnection, tmp_path: Path) -> None:
    lecteur = FauxLecteur([[fiche_json("societe_a_v1"), fiche_json("entreprise_individuelle")]])
    r = synchroniser(con, J1, J1, client=lecteur, chemin=tmp_path / "curseur.json")
    assert (r.statut, r.pages, r.bilan.fiches, r.bilan.ignorees) == ("succes", 1, 1, 1)
    assert journal(con) == [("rne_diff", "succes", 3, 0, None)]


def test_c3_synchroniser_erreur_page_annulee_et_journalisee(
    con: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    con.execute(
        "insert into liens (parent, enfant, role, debut) values (?, ?, ?, ?)", [MERE, RADIEE, "5132", J3]
    )
    lecteur = FauxLecteur(
        [[fiche_json("societe_a_v1")], [fiche_json("societe_a_v2"), fiche_json("societe_radiee")]]
    )
    with pytest.raises(duckdb.ConstraintException):
        synchroniser(con, J1, J1, client=lecteur, chemin=tmp_path / "curseur.json")
    # Page 1 validée, page 2 annulée en entier.
    assert liens(con) == [(MERE, "5132", "rne_diff", J1, None), (B, "5110", "rne_diff", J1, None)]
    assert lignes(con, "select denomination from societes") == [("SOCIETE FICTIVE A",)]
    [(source, statut, ajoutes, fermes, erreur)] = journal(con)
    assert (source, statut, ajoutes, fermes) == ("rne_diff", "echec", 3, 0)
    assert erreur == "ConstraintException pendant la synchro RNE, page 2"


def test_quota_atteint_arret_propre(con: duckdb.DuckDBPyConnection, tmp_path: Path) -> None:
    lecteur = FauxLecteur([[fiche_json("societe_a_v1")], QuotaAtteint(None)])
    r = synchroniser(con, J1, J1, client=lecteur, chemin=tmp_path / "curseur.json")
    assert (r.statut, r.pages, r.erreur) == ("echec", 1, MESSAGE_QUOTA)
    assert journal(con) == [("rne_diff", "echec", 3, 0, MESSAGE_QUOTA)]


def test_reprise_au_curseur_de_la_meme_periode(con: duckdb.DuckDBPyConnection, tmp_path: Path) -> None:
    chemin = tmp_path / "curseur.json"
    Curseur(J1, J1, search_after="000000001", pages=3).sauver(chemin)
    lecteur = FauxLecteur([])
    synchroniser(con, J1, J1, client=lecteur, chemin=chemin)
    assert lecteur.curseur_recu is not None and lecteur.curseur_recu.pages == 3
    # Autre période, ou période finie : on repart du début.
    synchroniser(con, J2, J2, client=lecteur, chemin=chemin)
    assert lecteur.curseur_recu is None


def test_les_personnes_restent_dans_dirigeants_personnes(
    con: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    lecteur = FauxLecteur([[fiche_json("societe_a_v1")], [fiche_json("societe_a_v2")]])
    synchroniser(con, J1, J1, client=lecteur, chemin=tmp_path / "curseur.json")
    exposees = [
        "select * from societes",
        "select * from liens",
        "select source, statut, erreur from mises_a_jour",
    ]
    for sql in exposees:
        assert "PERSONNE" not in repr(lignes(con, sql)).upper()
    assert lignes(con, "select count(*) from dirigeants_personnes") == [(2,)]


def test_cli_n_affiche_que_des_volumes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    registre = tmp_path / "registre.duckdb"
    with duckdb.connect(str(registre)) as c:
        creer_tables(c)
    monkeypatch.setenv("CARTOFR_DATA", str(tmp_path))
    monkeypatch.setenv("CARTOFR_ENV_FILE", str(tmp_path / "absent.env"))
    monkeypatch.setattr(synchro_rne, "Client", lambda: FauxLecteur([[fiche_json("societe_a_v1")]]))
    assert synchro_rne.main(["--jour", J1.isoformat()]) == 0
    sortie = capsys.readouterr().out
    assert "liens_ouverts : 2" in sortie and "statut : succes" in sortie
    assert "FICTIVE" not in sortie
    assert synchro_rne.main(["--jour", J1.isoformat(), "--registre", str(tmp_path / "absent.duckdb")]) == 1


# --- Critères C4 et C5 ---------------------------------------------------------------------------------


def test_c4_aucun_delete_sql() -> None:
    source = Path(synchro_rne.__file__).read_text(encoding="utf-8")
    assert re.search(r"\bdelete\b", source, re.IGNORECASE) is None


def test_c5_fixtures_aux_noms_inventes() -> None:
    noms: list[str] = []

    def parcourir(o: Any) -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("nom", "nomUsage", "denomination") and isinstance(v, str):
                    noms.append(v)
                parcourir(v)
        elif isinstance(o, list):
            for v in o:
                parcourir(v)

    for chemin in FIXTURES.glob("*.json"):
        parcourir(json.loads(chemin.read_text(encoding="utf-8")))
    assert noms and all("FICTIVE" in n.upper() for n in noms)
