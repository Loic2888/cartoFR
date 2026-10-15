"""Arbre à une mère du registre (T045) : choix de la mère, sommet, table et synchro.

Mini-registres inventés : SIREN factices, aucun nom (règle produit 6). Aucun Postgres :
le branchement dans le travail de synchro est testé par `recalculer_arbre`, sur DuckDB seul.
"""

from __future__ import annotations

import itertools
import random
from collections.abc import Iterator
from datetime import date

import duckdb
import pyarrow as pa
import pytest

from cartofr.jobs import synchro
from cartofr.registre import arbre, journal, synchro_rne, synchro_sirene
from cartofr.registre.schema import creer_tables

DEBUT = date(2026, 3, 4)
FIN = date(2026, 6, 1)


@pytest.fixture
def con() -> Iterator[duckdb.DuckDBPyConnection]:
    c = duckdb.connect(":memory:")
    creer_tables(c)
    yield c
    c.close()


def lier(
    con: duckdb.DuckDBPyConnection, parent: str, enfant: str, role: str | None = "73", fin: date | None = None
) -> None:
    con.execute(
        "insert into liens (parent, enfant, role, debut, fin) values (?, ?, ?, ?, ?)",
        [parent, enfant, role, DEBUT, fin],
    )


def table(con: duckdb.DuckDBPyConnection) -> dict[str, tuple[str, str, str, int, bool]]:
    lignes = con.execute("select siren, mere, role_mere, sommet, profondeur, boucle from arbre").fetchall()
    return {s: (m, r, t, p, b) for s, m, r, t, p, b in lignes}


def mere(con: duckdb.DuckDBPyConnection, enfant: str, max_enfants: int = arbre.MAX_ENFANTS) -> str | None:
    choisie = arbre.meres(con, max_enfants).get(enfant)
    return choisie[0] if choisie else None


def calcul(con: duckdb.DuckDBPyConnection) -> dict[str, tuple[str, str, str, int, bool]]:
    return {x.siren: (x.mere, x.role_mere, x.sommet, x.profondeur, x.boucle) for x in arbre.calculer(con)}


# --- C1 : choix de la mère ----------------------------------------------------------------------


def test_c1_le_role_le_plus_fort_l_emporte(con: duckdb.DuckDBPyConnection) -> None:
    lier(con, "100000001", "900000001", "99")  # autre
    lier(con, "100000002", "900000001", "65")  # administrateur
    lier(con, "100000003", "900000001", "30")  # gérant
    assert mere(con, "900000001") == "100000003"
    lier(con, "100000004", "900000001", "73")  # président
    assert arbre.meres(con)["900000001"] == ("100000004", "73")


@pytest.mark.parametrize(
    ("fort", "faible"), list(itertools.pairwise(sorted(arbre.RANGS, key=lambda r: arbre.RANGS[r])))
)
def test_c1_ordre_des_roles(con: duckdb.DuckDBPyConnection, fort: str, faible: str) -> None:
    # SIREN du rôle fort plus grand : le départage par SIREN ne peut pas le faire gagner.
    lier(con, "200000009", "900000001", fort)
    lier(con, "200000001", "900000001", faible)
    attendu = "200000009" if arbre.RANGS[fort] < arbre.RANGS[faible] else "200000001"
    assert mere(con, "900000001") == attendu


@pytest.mark.parametrize("role", ["71", "72", "77", "12", None])
def test_c1_roles_ecartes(con: duckdb.DuckDBPyConnection, role: str | None) -> None:
    """Commissaires aux comptes, rôle hors liste, rôle vide : jamais une mère."""
    lier(con, "100000001", "900000001", role)
    assert mere(con, "900000001") is None
    lier(con, "100000002", "900000001", "99")
    assert mere(con, "900000001") == "100000002"


def test_c1_parent_de_plus_de_500_enfants_ecarte(con: duckdb.DuckDBPyConnection) -> None:
    lier(con, "100000001", "900000000", "99")
    for i in range(arbre.MAX_ENFANTS):
        lier(con, "100000009", f"9{i + 1:08d}")
    # 500 enfants : encore mère, avec son président face à un « autre ».
    assert mere(con, "900000001") == "100000009"
    # Le 501e lien, même d'un rôle écarté, compte : il n'est plus la mère de personne.
    lier(con, "100000009", "800000001", "71")
    assert mere(con, "900000001") is None
    assert mere(con, "900000000") == "100000001"


def test_c1_seuil_reglable(con: duckdb.DuckDBPyConnection) -> None:
    lier(con, "100000001", "900000001")
    lier(con, "100000001", "900000002")
    assert mere(con, "900000001", max_enfants=2) == "100000001"
    assert mere(con, "900000001", max_enfants=1) is None


def test_c1_a_role_egal_le_parent_aux_plus_d_enfants(con: duckdb.DuckDBPyConnection) -> None:
    lier(con, "100000001", "900000001", "30")
    lier(con, "100000009", "900000001", "30")
    lier(con, "100000009", "900000002", "65")  # un enfant de plus, tout rôle compte
    assert mere(con, "900000001") == "100000009"


def test_c1_a_role_et_enfants_egaux_le_plus_petit_siren(con: duckdb.DuckDBPyConnection) -> None:
    lier(con, "100000009", "900000001", "30")
    lier(con, "100000001", "900000001", "51")  # même rang que le gérant
    assert mere(con, "900000001") == "100000001"


def test_c1_lien_ferme_ignore(con: duckdb.DuckDBPyConnection) -> None:
    lier(con, "100000001", "900000001", "73", fin=FIN)
    lier(con, "100000002", "900000001", "99")
    assert mere(con, "900000001") == "100000002"
    # Les liens fermés ne comptent pas non plus parmi les enfants.
    for i in range(arbre.MAX_ENFANTS + 1):
        lier(con, "100000002", f"8{i:08d}", "73", fin=FIN)
    assert mere(con, "900000001") == "100000002"


def test_c1_lien_vers_soi_ignore(con: duckdb.DuckDBPyConnection) -> None:
    lier(con, "900000001", "900000001")
    assert mere(con, "900000001") is None
    assert arbre.calculer(con) == []


def test_c1_doublons_du_rne_une_seule_ligne(con: duckdb.DuckDBPyConnection) -> None:
    lier(con, "100000001", "900000001")
    lier(con, "100000001", "900000001")
    arbre.recalculer(con)
    assert table(con) == {"900000001": ("100000001", "73", "100000001", 1, False)}


# --- C2 : sommet, profondeur, boucles -----------------------------------------------------------


def test_c2_chaine(con: duckdb.DuckDBPyConnection) -> None:
    # S -> A -> B -> C, et S -> D
    lier(con, "100000000", "100000001")
    lier(con, "100000001", "100000002", "30")
    lier(con, "100000002", "100000003")
    lier(con, "100000000", "100000004")
    arbre.recalculer(con)
    assert table(con) == {
        "100000001": ("100000000", "73", "100000000", 1, False),
        "100000002": ("100000001", "30", "100000000", 2, False),
        "100000003": ("100000002", "73", "100000000", 3, False),
        "100000004": ("100000000", "73", "100000000", 1, False),
    }
    assert "100000000" not in table(con)  # le sommet est son propre sommet : pas de ligne


def test_c2_boucle_de_deux(con: duckdb.DuckDBPyConnection) -> None:
    lier(con, "300000002", "300000001")
    lier(con, "300000001", "300000002")
    assert {s: (t, p, b) for s, (_, _, t, p, b) in calcul(con).items()} == {
        "300000001": ("300000001", 0, True),
        "300000002": ("300000001", 1, True),
    }


def test_c2_boucle_de_trois_avec_une_societe_qui_y_mene(con: duckdb.DuckDBPyConnection) -> None:
    # Mères : 7 a pour mère 5, 5 a pour mère 3, 3 a pour mère 7 (boucle, sommet 3).
    # En dessous : 20 a pour mère 7, 21 a pour mère 20.
    lier(con, "300000005", "300000007")
    lier(con, "300000003", "300000005")
    lier(con, "300000007", "300000003")
    lier(con, "300000007", "300000020")
    lier(con, "300000020", "300000021")
    assert {s: (t, p, b) for s, (_, _, t, p, b) in calcul(con).items()} == {
        "300000003": ("300000003", 0, True),
        "300000005": ("300000003", 1, True),
        "300000007": ("300000003", 2, True),
        "300000020": ("300000003", 3, True),
        "300000021": ("300000003", 4, True),
    }


def test_c2_profondeur_coherente_avec_la_mere() -> None:
    """Sur un graphe tiré au hasard : profondeur = celle de la mère + 1, sauf au sommet d'une boucle."""
    tirage = random.Random(45)
    mere_de = {f"{i:09d}": f"{tirage.randrange(400):09d}" for i in range(300)}
    mere_de = {s: m for s, m in mere_de.items() if s != m}
    hauts = arbre.sommets(mere_de)
    assert set(hauts) == set(mere_de)
    for siren, (sommet, profondeur, boucle) in hauts.items():
        m = mere_de[siren]
        if m in hauts:
            assert hauts[m][0] == sommet and hauts[m][2] == boucle
            assert profondeur == (0 if siren == sommet else hauts[m][1] + 1)
        else:
            assert (sommet, profondeur, boucle) == (m, 1, False)


def test_c2_resultat_independant_de_l_ordre_des_liens() -> None:
    tirage = random.Random(15)
    mere_de = {f"{i:09d}": f"{tirage.randrange(200):09d}" for i in range(150)}
    mere_de = {s: m for s, m in mere_de.items() if s != m}
    attendu = arbre.sommets(mere_de)
    for graine in range(5):
        cles = list(mere_de)
        random.Random(graine).shuffle(cles)
        assert arbre.sommets({c: mere_de[c] for c in cles}) == attendu


def test_c2_resultat_independant_de_l_ordre_d_insertion() -> None:
    liens = [
        ("100000000", "100000001", "30"),
        ("100000002", "100000001", "30"),
        ("100000001", "100000003", "73"),
    ]
    resultats = []
    for ordre in itertools.permutations(liens):
        c = duckdb.connect(":memory:")
        creer_tables(c)
        for parent, enfant, role in ordre:
            lier(c, parent, enfant, role)
        resultats.append(arbre.calculer(c))
        c.close()
    assert all(r == resultats[0] for r in resultats)


# --- C3 : table remplacée dans une transaction, journal -------------------------------------------


def journal_arbre(con: duckdb.DuckDBPyConnection) -> list[tuple[str, int | None, int | None, str | None]]:
    return con.execute(
        "select statut, ajoutes, fermes, erreur from mises_a_jour where source = 'arbre' order by id"
    ).fetchall()


def test_c3_succes_journalise_les_sommets_changes(con: duckdb.DuckDBPyConnection) -> None:
    lier(con, "100000000", "100000001")
    lier(con, "100000001", "100000002")
    bilan = arbre.recalculer(con)
    assert (bilan.lignes, bilan.sommets_changes, bilan.boucles) == (2, 2, 0)
    # Rien ne change : 0 sommet changé.
    assert arbre.recalculer(con).sommets_changes == 0
    # Une nouvelle mère au-dessus du sommet : les 3 sociétés changent de sommet.
    lier(con, "100000009", "100000000")
    assert arbre.recalculer(con).sommets_changes == 3
    # Le lien du haut se ferme : retour à l'état d'avant, même compte.
    con.execute("update liens set fin = ? where parent = '100000009'", [FIN])
    assert arbre.recalculer(con).sommets_changes == 3
    assert journal_arbre(con) == [
        ("succes", 2, 0, None),
        ("succes", 0, 0, None),
        ("succes", 3, 0, None),
        ("succes", 3, 0, None),
    ]


def test_c3_echec_garde_l_ancienne_table(
    con: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    lier(con, "100000000", "100000001")
    arbre.recalculer(con)
    avant = table(con)
    lier(con, "100000009", "100000000")

    def en_panne(_: object) -> object:
        raise duckdb.IOException("disque plein")

    monkeypatch.setattr(arbre, "_table", en_panne)
    with pytest.raises(duckdb.IOException):
        arbre.recalculer(con)
    assert table(con) == avant
    assert journal_arbre(con)[-1] == ("echec", None, None, "IOException pendant le calcul de l'arbre")


def test_c3_echec_pendant_l_ecriture_annule_tout(
    con: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    lier(con, "100000000", "100000001")
    arbre.recalculer(con)
    avant = table(con)
    lier(con, "100000009", "100000000")
    # La table nouvelle est mal formée : l'insertion échoue après le `delete`.
    monkeypatch.setattr(arbre, "_SOMMETS_CHANGES", "select 0")
    monkeypatch.setattr(
        arbre,
        "_table",
        lambda lignes: pa.table(
            {
                "siren": [None],
                "mere": ["1"],
                "role_mere": ["1"],
                "sommet": ["1"],
                "profondeur": [1],
                "boucle": [False],
            }
        ),
    )
    with pytest.raises(duckdb.Error):
        arbre.recalculer(con)
    assert table(con) == avant
    assert journal_arbre(con)[-1][0] == "echec"


def test_c3_registre_construit_avant_t045(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("drop table arbre")
    lier(con, "100000000", "100000001")
    arbre.recalculer(con)
    assert table(con) == {"100000001": ("100000000", "73", "100000000", 1, False)}


def test_c3_aucun_nom_dans_la_table(con: duckdb.DuckDBPyConnection) -> None:
    colonnes = [c[0] for c in con.execute("describe arbre").fetchall()]
    assert colonnes == ["siren", "mere", "role_mere", "sommet", "profondeur", "boucle"]


def test_c3_dirigeants_personnes_jamais_lue(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("drop table dirigeants_personnes")
    lier(con, "100000000", "100000001")
    assert arbre.recalculer(con).lignes == 1


# --- C4 : recalcul par la synchro -----------------------------------------------------------------


def passage(
    con: duckdb.DuckDBPyConnection, source: str, ajoutes: int, fermes: int, statut: str = "succes"
) -> None:
    """Une ligne de journal comme celles de la synchro, volumes écrits même en échec (quota)."""
    id_maj = journal.ouvrir(con, source)
    if statut == "succes":
        journal.terminer(con, id_maj, ajoutes=ajoutes, fermes=fermes)
    else:
        journal.echouer(con, id_maj, "échec simulé")
        con.execute("update mises_a_jour set ajoutes = ?, fermes = ? where id = ?", [ajoutes, fermes, id_maj])


def calculs(con: duckdb.DuckDBPyConnection) -> int:
    return len(journal_arbre(con))


def test_c4_premier_passage_calcule_meme_sans_changement(con: duckdb.DuckDBPyConnection) -> None:
    lier(con, "100000000", "100000001")
    passage(con, synchro_rne.SOURCE, 0, 0)
    assert synchro.recalculer_arbre(con)
    assert len(table(con)) == 1


@pytest.mark.parametrize(
    ("source", "ajoutes", "fermes", "statut", "recalcule"),
    [
        (synchro_rne.SOURCE, 0, 0, "succes", False),
        (synchro_rne.SOURCE, 1, 0, "succes", True),
        (synchro_rne.SOURCE, 0, 1, "succes", True),
        # Arrêt sur quota : la ligne est en échec, mais ses pages validées ont changé `liens`.
        (synchro_rne.SOURCE, 3, 0, "echec", True),
        (synchro_rne.SOURCE, 0, 0, "echec", False),
        # SIRENE ne touche jamais `liens`.
        (synchro_sirene.SOURCE, 2, 1, "succes", False),
        ("construction_initiale", 5, 0, "succes", False),
    ],
)
def test_c4_recalcul_seulement_si_le_rne_a_change_quelque_chose(
    con: duckdb.DuckDBPyConnection, source: str, ajoutes: int, fermes: int, statut: str, recalcule: bool
) -> None:
    lier(con, "100000000", "100000001")
    arbre.recalculer(con)
    avant = calculs(con)
    passage(con, source, ajoutes, fermes, statut)
    assert synchro.recalculer_arbre(con)
    assert calculs(con) == avant + recalcule


def test_c4_changements_d_avant_le_dernier_calcul_ignores(con: duckdb.DuckDBPyConnection) -> None:
    passage(con, synchro_rne.SOURCE, 10, 0)
    arbre.recalculer(con)
    assert arbre.recalculer_si_change(con) is None


def test_c4_changements_hors_du_travail_comptent(con: duckdb.DuckDBPyConnection) -> None:
    """Un jour appliqué à la main (`synchro_rne --jour`) entre deux nuits déclenche le calcul."""
    arbre.recalculer(con)
    lier(con, "100000000", "100000001")
    passage(con, synchro_rne.SOURCE, 1, 0)  # à la main
    passage(con, synchro_rne.SOURCE, 0, 0)  # la nuit : rien de neuf
    assert arbre.recalculer_si_change(con) is not None
    assert len(table(con)) == 1


def test_c4_un_calcul_en_echec_est_refait_la_nuit_suivante(
    con: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    arbre.recalculer(con)
    lier(con, "100000000", "100000001")
    passage(con, synchro_rne.SOURCE, 1, 0)
    with monkeypatch.context() as m:
        m.setattr(arbre, "calculer", en_panne)
        assert synchro.recalculer_arbre(con) is False
    passage(con, synchro_rne.SOURCE, 0, 0)  # nuit suivante, aucun changement
    assert synchro.recalculer_arbre(con)
    assert len(table(con)) == 1
    assert [statut for statut, *_ in journal_arbre(con)] == ["succes", "echec", "succes"]


def en_panne(*_: object) -> object:
    raise duckdb.IOException("disque plein")


def test_c4_echec_du_calcul_signale_sans_defaire_la_synchro(
    con: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    lier(con, "100000000", "100000001")
    passage(con, synchro_rne.SOURCE, 1, 0)
    monkeypatch.setattr(arbre, "calculer", en_panne)
    assert synchro.recalculer_arbre(con) is False
    # La synchro reste : son lien et sa ligne de journal sont là.
    assert con.execute("select count(*) from liens").fetchone() == (1,)
    assert con.execute(
        "select statut from mises_a_jour where source = ?", [synchro_rne.SOURCE]
    ).fetchall() == [("succes",)]
    assert journal_arbre(con)[-1][0] == "echec"


# --- C3 suite : interruption, sortie et journaux sans SIREN ---------------------------------------


def test_c3_interruption_ne_laisse_pas_la_ligne_en_cours(
    con: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    def interrompu(*_: object) -> object:
        raise KeyboardInterrupt

    monkeypatch.setattr(arbre, "calculer", interrompu)
    with pytest.raises(KeyboardInterrupt):
        arbre.recalculer(con)
    assert journal_arbre(con) == [("echec", None, None, "KeyboardInterrupt pendant le calcul de l'arbre")]


def test_c3_boucle_qui_se_forme_sans_changer_de_sommet(con: duckdb.DuckDBPyConnection) -> None:
    """1 mère de 2, puis 2 mère de 1 : la boucle a pour sommet 1, comme avant. Rien ne change."""
    lier(con, "100000001", "100000002")
    arbre.recalculer(con)
    lier(con, "100000002", "100000001")
    assert arbre.recalculer(con).sommets_changes == 0
    assert table(con)["100000001"] == ("100000002", "73", "100000001", 0, True)


SIREN_INVENTES = ("100000000", "100000001", "100000002")


def test_c3_main_registre_absent(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CARTOFR_DATA", str(tmp_path))
    assert arbre.main([]) == 2


def test_c3_main_ne_rend_que_des_volumes(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    chemin = f"{tmp_path}/{arbre.NOM_REGISTRE}"
    c = duckdb.connect(chemin)
    creer_tables(c)
    lier(c, "100000000", "100000001")
    lier(c, "100000001", "100000002")
    c.close()
    monkeypatch.setenv("CARTOFR_DATA", str(tmp_path))
    assert arbre.main([]) == 0
    sortie = capsys.readouterr()
    assert "2 sociétés avec une mère" in sortie.out
    assert not any(s in sortie.out + sortie.err for s in SIREN_INVENTES)
    c = duckdb.connect(chemin, read_only=True)
    assert c.execute("select statut, ajoutes from mises_a_jour where source = 'arbre'").fetchall() == [
        ("succes", 2)
    ]
    c.close()


def test_c3_journaux_sans_siren(
    con: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("DEBUG")
    lier(con, "100000000", "100000001")
    assert synchro.recalculer_arbre(con)
    monkeypatch.setattr(arbre, "calculer", en_panne)
    passage(con, synchro_rne.SOURCE, 1, 0)
    assert synchro.recalculer_arbre(con) is False
    assert caplog.records
    assert not any(s in caplog.text for s in SIREN_INVENTES)
    erreurs = con.execute("select erreur from mises_a_jour where erreur is not null").fetchall()
    assert not any(s in str(erreurs) for s in SIREN_INVENTES)
