"""Cas douteux et décisions du consultant (T027, FR-009, règle produit 8).

Le moteur range les cas douteux (confiance C, co-entreprise, participation sans contrôle,
société étrangère), chacun avec la règle qui l'a placé là et ses indices pour et contre (C1).
Le consultant tranche ; sa décision est reprise à la carto suivante du même groupe (C2), et la
règle qui aurait joué reste écrite dans le cas (principe 1).

Tous les noms sont inventés (règle produit 6), sur le mini-registre de `fabrique.py`.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fabrique import (
    ADMINISTRATEUR,
    CJ_ETRANGERE,
    PRESIDENT,
    MiniRegistre,
    reglages,
    siren,
)

from cartofr.moteur import Carto, Cas, Decision, cartographier, decisions_en_vigueur
from cartofr.moteur.moteur import RETENUE_PAR_DECISION

TETE = siren(1)
F1 = siren(10)
X = siren(50)  # la société dont le test range le cas
Y = siren(51)
EXT = siren(90)  # une société hors du groupe

MARQUES: dict[str, Any] = {"marques_sures": ["Alphamark"], "marques_ambigues": ["Zeta"]}
SANS_MANDAT = "Aucun mandat au registre tenu par une société du groupe"
SANS_MANDAT_FORT = "Aucun mandat fort (président, gérant…) tenu par une société du groupe"
UN_SEUL_INDICE = "Un seul indice : rattachement déduit, pas lu au registre"
T0 = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


@pytest.fixture
def mini() -> MiniRegistre:
    """Un registre qui ne contient que la tête du groupe."""
    registre = MiniRegistre()
    registre.societe(TETE, "TETE INVENTEE", naf="70.10Z", tranche="22")
    return registre


def lancer(mini: MiniRegistre, tmp_path: Path, decisions: dict[str, Decision] | None = None) -> Carto:
    chemin = tmp_path / "registre.duckdb"
    if not chemin.exists():
        mini.ecrire(chemin)
    return cartographier(reglages(TETE, **MARQUES), chemin, decisions=decisions)


def cas(carto: Carto) -> dict[str, Cas]:
    return {c.siren: c for c in carto.cas}


def retenues(carto: Carto) -> set[str]:
    return {s.siren for s in carto.societes}


def textes(c: Cas) -> list[str]:
    return [c.regle, *c.indices_pour, *c.indices_contre]


# ---------------------------------------------------------------- C1 : chaque cas, sa règle et ses indices


def test_confiance_c_rangee_avec_sa_regle_et_ses_indices(mini: MiniRegistre, tmp_path: Path) -> None:
    mini.societe(X, "ALPHAMARK SERVICES")
    c = cas(lancer(mini, tmp_path))[X]
    assert c == Cas(
        siren=X,
        nom="ALPHAMARK SERVICES",
        types=("confiance_c",),
        regle="Entrée dans le groupe : nom de marque propre au groupe"
        " · rattachement : Déduit : rattachée à la tête du groupe",
        retenue=True,
        indices_pour=("Porte une marque sûre du groupe",),
        indices_contre=(SANS_MANDAT, UN_SEUL_INDICE),
        decision=None,
    )


def test_filiale_au_registre_n_est_pas_un_cas(mini: MiniRegistre, tmp_path: Path) -> None:
    """Confiance A, aucun mandat extérieur : rien à trancher."""
    mini.societe(X, "FILIALE INVENTEE")
    mini.lien(TETE, X, PRESIDENT)
    carto = lancer(mini, tmp_path)
    assert X in retenues(carto)
    assert carto.cas == ()


def test_co_entreprise_retenue_rangee(mini: MiniRegistre, tmp_path: Path) -> None:
    """Présidée par le groupe, mais une société extérieure y tient un mandat : co-entreprise."""
    mini.societe(EXT, "EXTERIEURE INVENTEE")
    mini.societe(X, "COENTREPRISE INVENTEE")
    mini.lien(TETE, X, PRESIDENT)
    mini.lien(EXT, X, ADMINISTRATEUR)
    c = cas(lancer(mini, tmp_path))[X]
    assert (c.types, c.retenue) == (("co_entreprise",), True)
    assert (
        c.regle
        == "Entrée dans le groupe : mandat fort au registre · rattachement : Mandat au registre : Président"
    )
    assert c.indices_pour == (f"Mandat au registre : Président, tenu par la société du groupe {TETE}",)
    assert c.indices_contre == (
        f"Mandat au registre : Administrateur, tenu par la société {EXT} hors du groupe",
    )


@pytest.mark.parametrize(
    ("dirigee_par_une_exterieure", "regle", "contre"),
    [
        (
            False,
            "Non retenue : participation sans contrôle (mandat moyen sans indice indépendant)",
            (SANS_MANDAT_FORT,),
        ),
        (
            True,
            "Non retenue : contrôle partagé avec une société hors du groupe (mandat fort)",
            (SANS_MANDAT_FORT, f"Mandat au registre : Président, tenu par la société {EXT} hors du groupe"),
        ),
    ],
)
def test_participation_rangee(
    mini: MiniRegistre, tmp_path: Path, dirigee_par_une_exterieure: bool, regle: str, contre: tuple[str, ...]
) -> None:
    mini.societe(EXT, "EXTERIEURE INVENTEE")
    mini.societe(X, "PARTICIPATION INVENTEE")
    mini.lien(TETE, X, ADMINISTRATEUR)
    if dirigee_par_une_exterieure:
        mini.lien(EXT, X, PRESIDENT)
    carto = lancer(mini, tmp_path)
    c = cas(carto)[X]
    assert X not in retenues(carto)
    assert (c.types, c.retenue, c.regle, c.indices_contre) == (("participation",), False, regle, contre)
    assert c.indices_pour == (f"Mandat au registre : Administrateur, tenu par la société du groupe {TETE}",)


def test_societe_etrangere_rangee(mini: MiniRegistre, tmp_path: Path) -> None:
    mini.societe(X, "ALPHAMARK LIMITED", cj=CJ_ETRANGERE)
    c = cas(lancer(mini, tmp_path))[X]
    assert (c.types, c.retenue) == (("etrangere",), False)
    assert c.regle == "Non retenue : société étrangère, jamais retenue par le moteur"
    assert c.indices_pour == ("Porte une marque sûre du groupe",)
    assert c.indices_contre == (
        SANS_MANDAT,
        f"Société étrangère (catégorie juridique {CJ_ETRANGERE}) : hors du périmètre France",
    )


def test_dirigeants_communs_comptes_jamais_nommes(mini: MiniRegistre, tmp_path: Path) -> None:
    """Un dirigeant personne commun est un nombre dans les indices, jamais un nom (garde-fou 6)."""
    mini.societe(X, "PARTICIPATION INVENTEE")
    mini.lien(TETE, X, ADMINISTRATEUR)
    mini.dirigeants_communs(TETE, X, n=1)
    c = cas(lancer(mini, tmp_path))[X]
    assert "Dirigeants en commun avec d'autres sociétés du groupe : 1" in c.indices_pour
    assert not any("PERSONNE" in t or "PRENOM" in t or "|" in t for t in textes(c))


def test_entite_exterieure_inconnue_jamais_designee(mini: MiniRegistre, tmp_path: Path) -> None:
    """Un dirigeant extérieur absent de SIRENE (entrepreneur individuel, société cessée) n'est pas
    désigné : le SIREN d'un entrepreneur individuel désignerait une personne (garde-fou 6)."""
    mini.societe(X, "COENTREPRISE INVENTEE")
    mini.lien(TETE, X, PRESIDENT)
    mini.lien(EXT, X, ADMINISTRATEUR)
    c = cas(lancer(mini, tmp_path))[X]
    assert c.indices_contre == ("Mandat au registre : Administrateur, tenu par une entité hors du groupe",)
    assert not any(EXT in t for t in textes(c))


def test_chaque_cas_porte_sa_regle_et_ses_indices(mini: MiniRegistre, tmp_path: Path) -> None:
    """Sur un registre qui mêle les quatre sortes de cas : chacun a une règle, un indice pour et un
    indice contre, et les cas sont triés par SIREN, sans la tête."""
    mini.societe(EXT, "EXTERIEURE INVENTEE")
    mini.societe(siren(20), "ALPHAMARK SERVICES")  # confiance C
    mini.societe(siren(21), "COENTREPRISE INVENTEE")  # co-entreprise
    mini.lien(TETE, siren(21), PRESIDENT)
    mini.lien(EXT, siren(21), ADMINISTRATEUR)
    mini.societe(siren(22), "PARTICIPATION INVENTEE")  # participation
    mini.lien(TETE, siren(22), ADMINISTRATEUR)
    mini.societe(siren(23), "ALPHAMARK LIMITED", cj=CJ_ETRANGERE)  # étrangère
    carto = lancer(mini, tmp_path)
    assert [(c.siren, c.types) for c in carto.cas] == [
        (siren(20), ("confiance_c",)),
        (siren(21), ("co_entreprise",)),
        (siren(22), ("participation",)),
        (siren(23), ("etrangere",)),
    ]
    for c in carto.cas:
        assert c.regle and c.indices_pour and c.indices_contre, c.siren


# ---------------------------------------------------------------- C2 : décisions reprises


def test_ecarter_est_repris_a_la_carto_suivante(mini: MiniRegistre, tmp_path: Path) -> None:
    mini.societe(X, "ALPHAMARK SERVICES")
    avant = lancer(mini, tmp_path)
    assert X in retenues(avant)

    apres = lancer(mini, tmp_path, decisions_en_vigueur([(X, "ecarter", T0, 1)]))
    assert X not in retenues(apres)
    c = cas(apres)[X]
    assert (c.types, c.retenue, c.decision) == (("decision",), False, "ecarter")
    # La règle reste écrite : le cas dit laquelle aurait fait entrer la société.
    assert c.regle == (
        "Écartée par le consultant ; règle du moteur qui l'aurait retenue : nom de marque propre au groupe"
    )
    assert "Écartée par le consultant" in c.indices_contre


def test_ecarter_fait_sortir_les_societes_qui_n_entraient_que_par_elle(
    mini: MiniRegistre, tmp_path: Path
) -> None:
    """Écartée, la société n'est plus du groupe : ses filiales n'y entrent plus par elle."""
    mini.societe(X, "ALPHAMARK SERVICES")
    mini.societe(Y, "SOUS FILIALE INVENTEE")
    mini.lien(X, Y, PRESIDENT)
    assert {X, Y} <= retenues(lancer(mini, tmp_path))
    apres = lancer(mini, tmp_path, {X: "ecarter"})
    assert not {X, Y} & retenues(apres)


def test_retenir_une_participation(mini: MiniRegistre, tmp_path: Path) -> None:
    mini.societe(X, "PARTICIPATION INVENTEE")
    mini.lien(TETE, X, ADMINISTRATEUR)
    carto = lancer(mini, tmp_path, {X: "retenir"})
    x = {s.siren: s for s in carto.societes}[X]
    assert (x.pourquoi_dans_le_groupe, x.maison_mere_siren, x.confiance) == (RETENUE_PAR_DECISION, TETE, "A")
    assert carto.participations == ()
    c = cas(carto)[X]
    assert (c.types, c.retenue, c.decision) == (("decision",), True, "retenir")
    assert c.regle.startswith(f"Entrée dans le groupe : {RETENUE_PAR_DECISION}")


def test_retenir_une_societe_etrangere(mini: MiniRegistre, tmp_path: Path) -> None:
    mini.societe(X, "ALPHAMARK LIMITED", cj=CJ_ETRANGERE)
    carto = lancer(mini, tmp_path, {X: "retenir"})
    assert X in retenues(carto)
    assert carto.etrangeres == ()
    c = cas(carto)[X]
    # Entrée sur un seul indice (la marque) : confiance C, et toujours une société étrangère.
    assert (c.types, c.retenue, c.decision) == (("confiance_c", "etrangere"), True, "retenir")


def test_retenir_un_cas_deja_retenu_garde_le_cas(mini: MiniRegistre, tmp_path: Path) -> None:
    """Le consultant confirme une confiance C : rien ne change, le cas montre sa décision."""
    mini.societe(X, "ALPHAMARK SERVICES")
    sans = lancer(mini, tmp_path)
    avec = lancer(mini, tmp_path, {X: "retenir"})
    assert avec.societes == sans.societes
    assert cas(avec)[X].decision == "retenir"
    assert cas(avec)[X].types == ("confiance_c",)


@pytest.mark.parametrize("decision", ["retenir", "ecarter"])
def test_decision_sur_une_societe_disparue_sans_objet(
    mini: MiniRegistre, tmp_path: Path, decision: Decision
) -> None:
    """La société a cessé (plus de siège actif) : la décision ne fait rien, et aucun cas."""
    mini.societe(F1, "FILIALE INVENTEE")
    mini.lien(TETE, F1, PRESIDENT)
    mini.societe(X, "ALPHAMARK DISPARUE", active=False)
    mini.lien(TETE, X, PRESIDENT)
    sans = lancer(mini, tmp_path)
    avec = lancer(mini, tmp_path, {X: decision})
    assert X not in retenues(avec)
    assert (avec.societes, avec.cas) == (sans.societes, sans.cas)


def test_retenir_une_societe_sans_lien_avec_le_groupe_sans_objet(mini: MiniRegistre, tmp_path: Path) -> None:
    """Le registre ne la lie plus au groupe (aucun indice) : « retenir » ne la fait pas entrer."""
    mini.societe(X, "SANS RAPPORT INVENTEE")
    carto = lancer(mini, tmp_path, {X: "retenir"})
    assert X not in retenues(carto)
    assert carto.cas == ()


def test_decision_sur_la_tete_ignoree(mini: MiniRegistre, tmp_path: Path) -> None:
    mini.societe(X, "FILIALE INVENTEE")
    mini.lien(TETE, X, PRESIDENT)
    carto = lancer(mini, tmp_path, {TETE: "ecarter"})
    assert retenues(carto) == {TETE, X}
    assert carto.cas == ()


def test_sans_decision_la_carto_ne_change_pas(mini: MiniRegistre, tmp_path: Path) -> None:
    mini.societe(X, "ALPHAMARK SERVICES")
    mini.societe(Y, "PARTICIPATION INVENTEE")
    mini.lien(TETE, Y, ADMINISTRATEUR)
    assert lancer(mini, tmp_path, {}) == lancer(mini, tmp_path)


# ---------------------------------------------------------------- décision en vigueur


def test_la_decision_la_plus_recente_l_emporte() -> None:
    lignes = [
        (X, "ecarter", T0, 1),
        (X, "retenir", T0 + timedelta(days=1), 2),  # contradictoire, plus récente
        (Y, "retenir", T0 + timedelta(days=2), 3),
        (Y, "ecarter", T0 + timedelta(days=1), 4),  # enregistrée après, mais datée avant
    ]
    assert decisions_en_vigueur(lignes) == {X: "retenir", Y: "retenir"}
    assert decisions_en_vigueur(reversed(lignes)) == {X: "retenir", Y: "retenir"}


def test_a_date_egale_la_derniere_enregistree_l_emporte() -> None:
    lignes = [(X, "ecarter", T0, 7), (X, "retenir", T0, 3)]
    assert decisions_en_vigueur(lignes) == {X: "ecarter"}


def test_une_valeur_inconnue_ne_masque_pas_la_decision_precedente() -> None:
    lignes = [(X, "retenir", T0, 1), (X, "peut-etre", T0 + timedelta(days=1), 2)]
    assert decisions_en_vigueur(lignes) == {X: "retenir"}
    assert decisions_en_vigueur([]) == {}
