"""Départage d'une société réclamée par deux groupes (T047), sur des réclamations inventées.

Chaque étape de la règle est testée seule (C1), puis l'indépendance à l'ordre (C2), les raisons
(C3) et les parents sans boucle (C4). Tous les SIREN sont inventés, de la forme 9000000NN.
"""

import itertools
import random
import re

import pytest

from cartofr.pays import Departage, Groupe, GroupeRange, Rangement, Reclamation, departager

A, B, C, D = "900000001", "900000002", "900000003", "900000004"
S1, S2, S3 = "900000011", "900000012", "900000013"


def inscription(groupe: str, societe: str, taux: float = 100.0) -> Reclamation:
    return Reclamation(groupe, societe, "inscription", taux=taux)


def descente(groupe: str, societe: str, niveau: int = 1) -> Reclamation:
    return Reclamation(groupe, societe, "descente", niveau=niveau)


def arbre(groupe: str, societe: str) -> Reclamation:
    return Reclamation(groupe, societe, "arbre")


def groupe(tete: str, taille: int = 10, inscrites: tuple[str, ...] = ()) -> Groupe:
    return Groupe(tete, taille, frozenset(inscrites))


def rangement(resultat: Departage, societe: str) -> Rangement:
    (r,) = [r for r in resultat.societes if r.societe == societe]
    return r


def parents(resultat: Departage) -> dict[str, str | None]:
    return {g.tete: g.parent for g in resultat.groupes}


# C1 — groupes emboîtés


def test_societe_reclamee_par_un_groupe_et_son_sous_groupe_reste_dans_le_sous_groupe():
    # A (Dior) inscrit la tête de B (LVMH) ; S1 est inscrite par A et atteinte sous B.
    resultat = departager(
        [inscription(A, B), descente(B, B, 0), inscription(A, S1), descente(B, S1, 2)],
        [groupe(A, 900, (B,)), groupe(B, 800)],
    )
    assert rangement(resultat, S1).groupe == B
    # Chercher la tête de B rend B, filiale de A.
    assert rangement(resultat, B).groupe == B
    assert parents(resultat) == {A: None, B: A}


def test_emboitement_passe_avant_inscription_contre_descente_et_taux():
    # Hors emboîtement, l'inscription de A à 100 % battrait la descente de B : l'emboîtement prime.
    resultat = departager(
        [inscription(A, S1, 100.0), descente(B, S1, 5)],
        [groupe(A, 900, (B,)), groupe(B, 1)],
    )
    assert rangement(resultat, S1).groupe == B


def test_trois_niveaux_la_societe_va_au_plus_bas():
    resultat = departager(
        [inscription(A, S1), inscription(B, S1), descente(C, S1)],
        [groupe(A, inscrites=(B,)), groupe(B, inscrites=(C,)), groupe(C)],
    )
    assert rangement(resultat, S1).groupe == C
    assert parents(resultat) == {A: None, B: A, C: B}


def test_trois_niveaux_le_parent_est_le_document_le_plus_proche():
    # A inscrit B et C, B inscrit C : C est sous B, pas directement sous A.
    resultat = departager([], [groupe(A, inscrites=(B, C)), groupe(B, inscrites=(C,)), groupe(C)])
    assert parents(resultat) == {A: None, B: A, C: B}


def test_boucle_de_deux_le_parent_est_la_plus_petite_tete():
    resultat = departager(
        [inscription(A, S1), inscription(B, S1)],
        [groupe(A, 1, (B,)), groupe(B, 999, (A,))],
    )
    assert parents(resultat) == {A: None, B: A}
    # B, sous-groupe de A, garde la société malgré la boucle et sa taille.
    assert rangement(resultat, S1).groupe == B


def test_tete_inscrite_dans_son_propre_document_n_est_pas_son_parent():
    resultat = departager([], [groupe(A, inscrites=(A,))])
    assert parents(resultat) == {A: None}


# C1 — hors emboîtement


def test_inscription_passe_avant_descente():
    resultat = departager([descente(A, S1, 0), inscription(B, S1, 51.0)], [groupe(A, 999), groupe(B, 1)])
    assert rangement(resultat, S1).groupe == B


def test_entre_deux_inscriptions_le_taux_le_plus_haut():
    resultat = departager(
        [inscription(A, S1, 60.0), inscription(B, S1, 99.5)], [groupe(A, 999), groupe(B, 1)]
    )
    assert rangement(resultat, S1).groupe == B


def test_a_taux_egal_le_groupe_le_plus_grand():
    resultat = departager(
        [inscription(A, S1, 100.0), inscription(B, S1, 100.0)], [groupe(A, 10), groupe(B, 20)]
    )
    assert rangement(resultat, S1).groupe == B


def test_a_taux_et_taille_egaux_la_plus_petite_tete():
    resultat = departager([inscription(B, S1), inscription(A, S1)], [groupe(A, 10), groupe(B, 10)])
    assert rangement(resultat, S1).groupe == A


def test_entre_deux_descentes_le_niveau_le_plus_bas():
    resultat = departager([descente(A, S1, 3), descente(B, S1, 1)], [groupe(A, 999), groupe(B, 1)])
    assert rangement(resultat, S1).groupe == B


def test_a_niveau_egal_la_plus_petite_tete():
    resultat = departager([descente(B, S1, 2), descente(A, S1, 2)], [groupe(A, 1), groupe(B, 999)])
    assert rangement(resultat, S1).groupe == A


def test_arbre_non_reclame_reste_son_propre_groupe():
    resultat = departager([arbre(D, D), arbre(D, S1)], [])
    assert {r.societe: r.groupe for r in resultat.societes} == {D: D, S1: D}
    assert all(r.raison is None for r in resultat.societes)
    assert parents(resultat) == {D: None}


def test_arbre_perd_contre_inscription_et_descente():
    resultat = departager(
        [arbre(D, S1), descente(A, S1, 9), arbre(D, S2), inscription(B, S2, 1.0)],
        [groupe(A), groupe(B), groupe(D, 99_999)],
    )
    assert rangement(resultat, S1).groupe == A
    assert rangement(resultat, S2).groupe == B


def test_un_groupe_qui_reclame_deux_fois_n_est_pas_un_departage():
    resultat = departager([descente(A, S1, 3), inscription(A, S1, 70.0)], [groupe(A)])
    assert rangement(resultat, S1) == Rangement(S1, A, None)


def test_un_groupe_concourt_avec_sa_meilleure_reclamation():
    # A inscrit S1 et l'atteint aussi au niveau 3 : son inscription bat la descente de B au niveau 1.
    for ordre in ([inscription(A, S1), descente(A, S1, 3)], [descente(A, S1, 3), inscription(A, S1)]):
        resultat = departager([*ordre, descente(B, S1, 1)], [groupe(A), groupe(B)])
        assert rangement(resultat, S1).groupe == A


def test_reclamation_incomplete_refusee():
    with pytest.raises(ValueError):
        Reclamation(A, S1, "inscription")
    with pytest.raises(ValueError):
        Reclamation(A, S1, "descente")


# C2 — l'ordre ne compte pas, chaque société sort une fois


RECLAMATIONS = [
    inscription(A, B),
    descente(B, B, 0),
    inscription(A, S1, 100.0),
    descente(B, S1, 2),
    inscription(C, S2, 100.0),
    inscription(D, S2, 100.0),
    descente(A, S2, 1),
    descente(C, S3, 2),
    descente(D, S3, 2),
    arbre(S3, S3),
]
GROUPES = [groupe(A, 50, (B,)), groupe(B, 40), groupe(C, 30, (D,)), groupe(D, 30, (C,))]


def test_le_resultat_ne_depend_pas_de_l_ordre():
    attendu = departager(RECLAMATIONS, GROUPES)
    # Toutes les permutations des six dernières réclamations, puis des tirages de l'ensemble.
    for fin in itertools.permutations(RECLAMATIONS[4:]):
        assert departager([*RECLAMATIONS[:4], *fin], reversed(GROUPES)) == attendu
    tirage = random.Random(47)
    for _ in range(200):
        melange = RECLAMATIONS[:]
        tirage.shuffle(melange)
        assert departager(melange, GROUPES) == attendu


def test_chaque_societe_sort_une_fois_et_une_seule():
    resultat = departager(RECLAMATIONS, GROUPES)
    sorties = [r.societe for r in resultat.societes]
    assert sorted(sorties) == sorted({r.societe for r in RECLAMATIONS})
    assert len(sorties) == len(set(sorties))


# C3 — raisons


def test_raisons_du_choix():
    resultat = departager(RECLAMATIONS, GROUPES)
    assert rangement(resultat, B).raison == "atteinte par le registre sous 900000002, niveau 0 ; " + (
        "dans le sous-groupe 900000002 de 900000001"
    )
    # C et D s'inscrivent l'un l'autre : D est sous-groupe de C, et garde S2 contre C et contre A.
    assert rangement(resultat, S2).raison == (
        "inscrite au document de 900000004 (100 %) ; dans le sous-groupe 900000004 de 900000003 ; "
        "l'inscription passe avant la descente depuis 900000001"
    )
    assert rangement(resultat, S3).raison == (
        "atteinte par le registre sous 900000004, niveau 2 ; dans le sous-groupe 900000004 de 900000003 ; "
        "l'emporte sur l'arbre non réclamé 900000013"
    )


@pytest.mark.parametrize(
    ("reclamations", "groupes", "motif"),
    [
        ([inscription(A, S1, 60.0), inscription(B, S1, 99.5)], [], "taux le plus haut"),
        ([inscription(A, S1), inscription(B, S1)], [groupe(B, 20)], "à taux égal, le groupe le plus grand"),
        ([inscription(A, S1), inscription(B, S1)], [], "à taux et taille égaux, la plus petite tête"),
        ([descente(A, S1, 3), descente(B, S1, 1)], [], "la plus proche de la tête de son groupe"),
        ([descente(A, S1, 2), descente(B, S1, 2)], [], "à niveau égal, la plus petite tête"),
        (
            [descente(A, S1), inscription(B, S1, 99.5)],
            [],
            "l'inscription passe avant la descente depuis 900000001",
        ),
    ],
)
def test_chaque_etape_donne_sa_raison(reclamations: list[Reclamation], groupes: list[Groupe], motif: str):
    (r,) = departager(reclamations, groupes).societes
    assert r.raison is not None and r.raison.endswith(motif)


def test_raison_ne_cite_que_des_siren():
    resultat = departager(RECLAMATIONS, GROUPES)
    for r in resultat.societes:
        if r.raison is not None:
            # Aucun mot en majuscule (un nom propre) : seulement le texte de la règle et des SIREN.
            assert not re.search(r"\b[A-Z][a-z]", r.raison)
            assert set(re.findall(r"\d{9}", r.raison)) <= {A, B, C, D, S3}


# C4 — parents sans boucle


def _sans_boucle(liste: tuple[GroupeRange, ...]) -> bool:
    parent = {g.tete: g.parent for g in liste}
    for depart in parent:
        vus: set[str] = set()
        t: str | None = depart
        while t is not None:
            if t in vus:
                return False
            vus.add(t)
            t = parent[t]
    return True


def test_parents_sans_boucle_meme_avec_une_boucle_de_trois():
    # A inscrit B, B inscrit C, C inscrit A : la boucle se casse à A, la plus petite tête.
    resultat = departager(
        [], [groupe(A, inscrites=(B,)), groupe(B, inscrites=(C,)), groupe(C, inscrites=(A,))]
    )
    assert parents(resultat) == {A: None, B: A, C: B}
    assert _sans_boucle(resultat.groupes)


def test_parents_sans_boucle_sur_des_inscriptions_tirees_au_hasard():
    tetes = [f"9000000{n:02d}" for n in range(1, 9)]
    tirage = random.Random(4747)
    for _ in range(300):
        groupes = [groupe(t, inscrites=tuple(x for x in tetes if tirage.random() < 0.3)) for t in tetes]
        resultat = departager([], groupes)
        assert _sans_boucle(resultat.groupes)
        assert {g.tete for g in resultat.groupes} == set(tetes)
        for g in resultat.groupes:
            # Un parent inscrit toujours la tête de son sous-groupe dans son document.
            if g.parent is not None:
                assert g.tete in next(x for x in groupes if x.tete == g.parent).tetes_inscrites


def test_chaque_groupe_reclamant_porte_son_parent_ou_aucun():
    resultat = departager(RECLAMATIONS, GROUPES)
    assert parents(resultat) == {A: None, B: A, C: None, D: C, S3: None}


def test_a_l_echelle_du_pays() -> None:
    """100 000 arbres et quelques documents : les parents se calculent depuis les documents seuls.
    Comparer chaque tête à chaque autre prendrait des heures (revue du 2026-10-16)."""
    import time

    arbres = [f"{800_000_000 + i}" for i in range(100_000)]
    a, b, c = "900000001", "900000002", "900000003"
    groupes = [Groupe(a, 10, frozenset({b})), Groupe(b, 5, frozenset({c})), Groupe(c, 2)]
    groupes += [Groupe(t, 2) for t in arbres]
    reclamations = [Reclamation(t, t, "arbre") for t in arbres] + [
        Reclamation(c, arbres[0], "descente", niveau=1)
    ]
    debut = time.monotonic()
    resultat = departager(reclamations, groupes)
    assert time.monotonic() - debut < 10
    parents = {g.tete: g.parent for g in resultat.groupes}
    assert (parents[b], parents[c], parents[arbres[1]]) == (a, b, None)
    assert {r.societe: r.groupe for r in resultat.societes}[arbres[0]] == c
