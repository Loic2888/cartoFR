"""Chaque règle du moteur qui décide, testée seule sur un mini-registre fabriqué (T017, règle produit 8).

Une règle par test (ou par groupe paramétré) : le test vérifie la décision **et** sa preuve
(raison d'entrée, preuve du rattachement, confiance, raison ciblable). Sources des règles :
`skills/account-mapping/references/moteur-france.md` §4 et `rapport.md` (2026-10-06).

Tous les noms sont inventés (règle produit 6). Les écarts entre le moteur et la règle écrite
sont marqués `xfail(strict=True)` avec la raison : on ne corrige pas le moteur ici, chaque
correction sera une tâche mesurée par la non-régression (principe 5).
"""

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fabrique import (
    ADMINISTRATEUR,
    AUTRE,
    CJ_ASSOCIATION,
    CJ_ETRANGERE,
    CJ_GIE,
    CJ_SCI,
    COMMANDITE,
    COMMISSAIRE_AUX_COMPTES,
    GERANT,
    MEMBRE,
    PRESIDENT,
    MiniRegistre,
    personne,
    reglages,
    siren,
)

from cartofr.moteur import Carto, cartographier
from cartofr.moteur.modele import Mandat, Societe

TETE = siren(1)
F1, F2, F3, F4, F5, F6, F7, F8, F9 = (siren(i) for i in range(10, 19))
X = siren(50)  # la société dont le test décide le sort
EXT = siren(90)  # une société hors du groupe
ADRESSE_GROUPE = "1 PLACE DU GROUPE INVENTE 75008"
FERME = date(2026, 4, 1)

OPE = "Société opérationnelle"
HOLDING = "Holding ou société immobilière sans salarié déclaré"
PROPRE = "nom de marque propre au groupe"
HOMONYME = {"marques_sures": ["Kappa"], "marques_sures_homonymes": ["KAPPA"]}  # type « VINCI », « ASF »
SIGLE = {"marques_sures": ["AMK"], "marques_sigles": ["AMK"]}

MARQUES: dict[str, Any] = {"marques_sures": ["Alphamark"], "marques_ambigues": ["Zeta"]}


@pytest.fixture
def mini() -> MiniRegistre:
    """Un registre qui ne contient que la tête du groupe."""
    registre = MiniRegistre()
    registre.societe(TETE, "TETE INVENTEE", naf="70.10Z", tranche="22")
    return registre


def lancer(mini: MiniRegistre, tmp_path: Path, **surcharges: Any) -> Carto:
    """Écrit le registre et calcule la carto avec les marques de test et les réglages donnés."""
    return cartographier(reglages(TETE, **(MARQUES | surcharges)), mini.ecrire(tmp_path / "registre.duckdb"))


def societes(carto: Carto) -> dict[str, Societe]:
    return {s.siren: s for s in carto.societes}


def filiale(
    mini: MiniRegistre, s: str, nom: str, parent: str = TETE, role: str = PRESIDENT, **kw: Any
) -> str:
    """Une société dirigée par `parent` avec un mandat fort : elle entre sans autre indice."""
    mini.societe(s, nom, **kw)
    mini.lien(parent, s, role)
    return s


# ---------------------------------------------------------------- C1 : confiance A, B, C


def test_confiance_a_lien_lu_au_registre(mini: MiniRegistre, tmp_path: Path) -> None:
    """Confiance A : le rattachement est un mandat lu au registre (moteur-france.md §4, « Maison mère directe
    »)."""
    filiale(mini, F1, "FILIALE INVENTEE UN")
    carto = lancer(mini, tmp_path)
    f1 = societes(carto)[F1]
    assert (f1.maison_mere_siren, f1.preuve, f1.confiance) == (TETE, "Mandat au registre : Président", "A")
    assert f1.pourquoi_dans_le_groupe == "mandat fort au registre"
    assert f1.indices == ("registre",)
    assert [(lien.parent, lien.enfant, lien.preuve, lien.confiance) for lien in carto.liens] == [
        (TETE, F1, "Mandat au registre : Président", "A")
    ]


def test_confiance_b_marque_sure_et_adresse_du_groupe(mini: MiniRegistre, tmp_path: Path) -> None:
    """Confiance B : deux indices de types différents, ici marque sûre et adresse du groupe (§4)."""
    mini.domicilier(ADRESSE_GROUPE, TETE)
    filiale(mini, F1, "FILIALE INVENTEE UN", adresse=ADRESSE_GROUPE)
    mini.societe(X, "ALPHAMARK NEGOCE", adresse=ADRESSE_GROUPE)
    x = societes(lancer(mini, tmp_path))[X]
    assert x.pourquoi_dans_le_groupe == "nom de marque propre au groupe"
    assert x.indices == ("adresse", "marque_sure")
    assert (x.maison_mere_siren, x.preuve, x.confiance) == (
        TETE,
        "Déduit : rattachée à la tête du groupe",
        "B",
    )


def test_confiance_b_marque_et_second_indice(mini: MiniRegistre, tmp_path: Path) -> None:
    """Confiance B : entrée par « nom de marque et second indice » (marque ambiguë, dirigeants, §4)."""
    mini.societe(X, "ZETA CONSEIL")
    mini.dirigeants_communs(TETE, X)
    x = societes(lancer(mini, tmp_path))[X]
    assert x.pourquoi_dans_le_groupe == "nom de marque et second indice"
    assert x.indices == ("marque_ambigue",)
    assert (x.preuve, x.confiance) == ("Déduit : rattachée à la tête du groupe", "B")


def test_confiance_c_un_seul_indice(mini: MiniRegistre, tmp_path: Path) -> None:
    """Confiance C, à vérifier : un seul indice, ici un nom de marque sûre (§4)."""
    mini.societe(X, "ALPHAMARK SERVICES")
    x = societes(lancer(mini, tmp_path))[X]
    assert x.pourquoi_dans_le_groupe == "nom de marque propre au groupe"
    assert x.indices == ("marque_sure",)
    assert (x.maison_mere_siren, x.preuve, x.confiance) == (
        TETE,
        "Déduit : rattachée à la tête du groupe",
        "C",
    )


# ---------------------------------------------------------------- C2 : maison mère directe


def test_maison_mere_mandat_fort_avant_mandat_moyen(mini: MiniRegistre, tmp_path: Path) -> None:
    """Maison mère directe : le mandat le plus fort (fort, puis « Autre », puis moyen), même face à la tête
    (§4)."""
    filiale(mini, F1, "FILIALE INVENTEE UN")
    filiale(mini, X, "SOUS FILIALE INVENTEE", parent=F1)
    mini.lien(TETE, X, ADMINISTRATEUR)
    carto = lancer(mini, tmp_path)
    x = societes(carto)[X]
    assert (x.maison_mere_siren, x.preuve, x.confiance, x.niveau) == (
        F1,
        "Mandat au registre : Président",
        "A",
        2,
    )
    assert {(lien.parent, lien.role) for lien in carto.liens if lien.enfant == X} == {
        (F1, "Président"),
        (TETE, "Administrateur"),
    }


@pytest.mark.parametrize("ordre", ["haut_d_abord", "bas_d_abord"])
def test_maison_mere_egalite_departagee_par_le_plus_petit_siren(
    mini: MiniRegistre, tmp_path: Path, ordre: str
) -> None:
    """À égalité de force, hors tête et `priorite`, le plus petit SIREN gagne, quel que soit l'ordre du
    registre.

    Source : rapport.md 2026-10-07 (le portage trie de façon stable, le prototype non)."""
    filiale(mini, F1, "FILIALE INVENTEE UN")
    filiale(mini, F2, "FILIALE INVENTEE DEUX")
    mini.societe(X, "COMMUNE INVENTEE")
    liens = [(F2, PRESIDENT), (F1, GERANT)]
    for parent, role in liens if ordre == "haut_d_abord" else reversed(liens):
        mini.lien(parent, X, role)
    x = societes(lancer(mini, tmp_path))[X]
    assert (x.maison_mere_siren, x.preuve, x.confiance) == (F1, "Mandat au registre : Gérant", "A")


def test_maison_mere_egalite_priorite_des_reglages(mini: MiniRegistre, tmp_path: Path) -> None:
    """À égalité de force, une société listée dans `priorite` passe avant un SIREN plus petit (§3, §4)."""
    filiale(mini, F1, "FILIALE INVENTEE UN")
    filiale(mini, F2, "FILIALE INVENTEE DEUX")
    mini.societe(X, "COMMUNE INVENTEE")
    mini.lien(F1, X, GERANT)
    mini.lien(F2, X, PRESIDENT)
    x = societes(lancer(mini, tmp_path, priorite=[F2]))[X]
    assert (x.maison_mere_siren, x.preuve) == (F2, "Mandat au registre : Président")


def test_maison_mere_egalite_la_tete_passe_en_premier(tmp_path: Path) -> None:
    """À égalité de force, la tête du groupe passe avant toute autre, même de SIREN plus petit (§4)."""
    tete = siren(99)
    mini = MiniRegistre()
    mini.societe(tete, "TETE INVENTEE", tranche="22")
    filiale(mini, F1, "FILIALE INVENTEE UN", parent=tete)
    mini.societe(X, "COMMUNE INVENTEE")
    mini.lien(F1, X, PRESIDENT)
    mini.lien(tete, X, GERANT)
    carto = cartographier(reglages(tete), mini.ecrire(tmp_path / "registre.duckdb"))
    x = societes(carto)[X]
    assert (x.maison_mere_siren, x.preuve, x.niveau) == (tete, "Mandat au registre : Gérant", 1)


def test_maison_mere_tete_de_maison_de_sa_marque(mini: MiniRegistre, tmp_path: Path) -> None:
    """Sans mandat, la maison mère est la tête de maison de sa marque : la société de la marque qui a le plus
    de salariés ; à défaut, la tête du groupe (§4, « Maison mère directe »)."""
    mini.societe(F1, "ALPHAMARK FRANCE", salaries=200)
    mini.societe(X, "ALPHAMARK SERVICES", salaries=12)
    s = societes(lancer(mini, tmp_path))
    assert (s[X].maison_mere_siren, s[X].preuve, s[X].confiance) == (
        F1,
        "Déduit : même maison (ALPHAMARK)",
        "C",
    )
    assert (s[F1].maison_mere_siren, s[F1].preuve) == (TETE, "Déduit : rattachée à la tête du groupe")
    assert (s[F1].niveau, s[X].niveau) == (1, 2)


# ---------------------------------------------------------------- C3 : ciblable Oui et Non


@pytest.mark.parametrize(
    ("cj", "naf", "tranche", "salaries", "ciblable", "raison"),
    [
        pytest.param(5710, "46.45Z", "11", None, True, OPE, id="salaries_insee"),
        pytest.param(5710, "64.20Z", "NN", 25, True, OPE, id="holding_avec_salaries_rne"),
        pytest.param(5710, "70.22Z", "NN", None, True, OPE, id="NN_non_renseigne_pas_zero"),
        pytest.param(CJ_SCI, "68.20B", "NN", None, False, "Société civile ou SCI", id="sci"),
        pytest.param(CJ_GIE, "70.22Z", "NN", None, False, "GIE de moyens", id="gie"),
        pytest.param(
            5710, "64.20Z", "NN", None, False, HOLDING, id="holding_vide"
        ),
        pytest.param(
            5710, "64.30Z", "01", None, False, HOLDING,
            id="vehicule_financier",
        ),
        pytest.param(5710, "46.45Z", "00", None, False, "Aucun salarié", id="aucun_salarie"),
    ],
)  # fmt: skip
def test_ciblable_oui_et_non_avec_la_raison(
    mini: MiniRegistre,
    tmp_path: Path,
    cj: int,
    naf: str,
    tranche: str,
    salaries: int | None,
    ciblable: bool,
    raison: str,
) -> None:
    """Ciblable : Oui pour une société opérationnelle (salariés), Non pour SCI, GIE, holding ou véhicule
    financier sans salarié déclaré ; « NN » veut dire non renseigné, pas zéro (§4, rapport.md 2026-10-03
    étape 8)."""
    filiale(mini, X, "FILIALE INVENTEE", cj=cj, naf=naf, tranche=tranche, salaries=salaries)
    x = societes(lancer(mini, tmp_path))[X]
    assert (x.ciblable, x.raison_ciblable) == (ciblable, raison)


def test_ciblable_tete_tete_de_maison_et_compte_de_rattachement(mini: MiniRegistre, tmp_path: Path) -> None:
    """Ciblable Oui pour la tête et une tête de maison, même sans salarié ; une société non ciblable se
    rattache au compte ciblable le plus proche au-dessus (§3 organigramme, §4 ciblable)."""
    mini.societe(F1, "OMEGA MAISON", naf="64.20Z", tranche="NN")
    mini.societe(F2, "OMEGA MAISON", naf="64.20Z", tranche="21")  # la plus grande : tête de maison
    filiale(mini, F3, "HOLDING INVENTEE", naf="64.20Z", tranche="NN")
    filiale(mini, F4, "OPERATIONS INVENTEES", parent=F3)
    s = societes(lancer(mini, tmp_path, organigramme=["Omega Maison"]))
    assert (s[TETE].ciblable, s[TETE].raison_ciblable) == (True, "Société mère du groupe")
    assert F1 not in s
    assert s[F2].pourquoi_dans_le_groupe == "tête de maison (organigramme public du groupe)"
    assert (s[F2].ciblable, s[F2].raison_ciblable) == (True, "Tête de maison")
    assert (s[F3].ciblable, s[F3].compte_de_rattachement) == (False, TETE)
    assert (s[F4].ciblable, s[F4].compte_de_rattachement) == (True, F4)


# ---------------------------------------------------------------- C4 : l'adresse seule ne suffit pas


def _adresse_du_groupe_a_87_pourcent(mini: MiniRegistre) -> None:
    """La tête et six filiales au même siège, plus X : le groupe y est 7 sur 8, soit 87,5 %."""
    mini.domicilier(ADRESSE_GROUPE, TETE)
    for i, s in enumerate((F1, F2, F3, F4, F5, F6), start=1):
        filiale(mini, s, f"FILIALE INVENTEE {i}", adresse=ADRESSE_GROUPE)
    mini.societe(X, "FONDS INVENTE DOMICILIE", adresse=ADRESSE_GROUPE)


def test_adresse_seule_refusee_meme_a_plus_de_85_pourcent(mini: MiniRegistre, tmp_path: Path) -> None:
    """L'adresse du groupe seule ne fait jamais entrer une société, même à plus de 85 % du siège
    (règle retirée le 2026-10-06 après-midi : fonds domiciliés chez la société de gestion)."""
    _adresse_du_groupe_a_87_pourcent(mini)
    carto = lancer(mini, tmp_path)
    assert X not in societes(carto)
    assert len(carto.societes) == 7
    assert max(t.adresses_du_groupe for t in carto.tours) == 1  # l'adresse a bien été reconnue du groupe
    assert X not in {p.siren for p in carto.participations}


def test_adresse_et_dirigeant_commun_retenue(mini: MiniRegistre, tmp_path: Path) -> None:
    """Témoin de C4 : à une adresse du groupe, un seul dirigeant commun suffit comme deuxième indice (§4 règle
    7)."""
    _adresse_du_groupe_a_87_pourcent(mini)
    mini.dirigeants_communs(TETE, X, n=1)
    x = societes(lancer(mini, tmp_path))[X]
    assert x.pourquoi_dans_le_groupe == "adresse du groupe et second indice"
    assert x.indices == ("adresse",)
    assert x.confiance == "B"


# ---------------------------------------------------------------- C5 : marques


def test_marque_ambigue_seule_refusee(mini: MiniRegistre, tmp_path: Path) -> None:
    """Une marque ambiguë (prénom, mot courant) ne suffit jamais seule : deuxième preuve exigée (§3, §4 règle
    6)."""
    mini.societe(X, "ZETA CONSEIL", tranche="32", salaries=300)
    assert X not in societes(lancer(mini, tmp_path))


def _deux_dirigeants(mini: MiniRegistre) -> None:
    mini.dirigeants_communs(TETE, X)


def _un_cadre_du_groupe(mini: MiniRegistre) -> None:
    filiale(mini, F1, "FILIALE INVENTEE UN")
    mini.dirigeant(TETE, personne(1))
    mini.dirigeant(F1, personne(1))  # elle dirige deux sociétés du groupe : cadre du groupe
    mini.dirigeant(X, personne(1))


def _un_dirigeant_ordinaire(mini: MiniRegistre) -> None:
    mini.dirigeants_communs(TETE, X, n=1)


def _adresse_du_groupe(mini: MiniRegistre) -> None:
    mini.domicilier(ADRESSE_GROUPE, TETE)
    filiale(mini, F1, "FILIALE INVENTEE UN", adresse=ADRESSE_GROUPE)
    mini.domicilier(ADRESSE_GROUPE, X)


def _deux_dirigeants_fermes(mini: MiniRegistre) -> None:
    for i in (1, 2):
        mini.dirigeant(TETE, personne(i))
        mini.dirigeant(X, personne(i), fin=FERME)


@pytest.mark.parametrize(
    ("preuve", "cj", "raison"),
    [
        pytest.param(_deux_dirigeants, 5710, "nom de marque et second indice", id="deux_dirigeants_communs"),
        pytest.param(_un_cadre_du_groupe, 5710, "nom de marque et second indice", id="un_cadre_du_groupe"),
        pytest.param(_adresse_du_groupe, 5710, "nom de marque et second indice", id="adresse_du_groupe"),
        pytest.param(_un_dirigeant_ordinaire, 5710, None, id="un_seul_dirigeant_ordinaire"),
        pytest.param(_deux_dirigeants_fermes, 5710, None, id="dirigeants_fermes"),
        pytest.param(_deux_dirigeants, CJ_SCI, None, id="sci_au_nom_ambigu"),
    ],
)
def test_marque_ambigue_exige_une_deuxieme_preuve(
    mini: MiniRegistre, tmp_path: Path, preuve: Any, cj: int, raison: str | None
) -> None:
    """Marque ambiguë + deuxième preuve : dirigeants communs (deux, ou un cadre qui dirige déjà deux sociétés
    du groupe) ou adresse du groupe. Les dirigeants ne comptent pas pour une société civile au nom ambigu,
    ni fermés au registre (§4 règle 6 et « Dirigeants communs »)."""
    mini.societe(X, "SCI ZETA" if cj == CJ_SCI else "ZETA CONSEIL", cj=cj)
    preuve(mini)
    x = societes(lancer(mini, tmp_path)).get(X)
    assert (x.pourquoi_dans_le_groupe if x else None) == raison


@pytest.mark.parametrize(
    ("nom", "cj", "tranche", "salaries", "reglages_en_plus", "raison"),
    [
        pytest.param("ALPHAMARK SERVICES", 5710, "11", None, {}, PROPRE, id="sure"),
        pytest.param("SCI ALPHAMARK", CJ_SCI, "NN", None, {}, None, id="sure_mais_societe_civile"),
        pytest.param("ALPHAMARK", 5710, "NN", None, {}, None, id="nom_reduit_a_la_marque_sans_salarie"),
        pytest.param("ALPHAMARK", 5710, "NN", 12, {}, PROPRE, id="nom_reduit_avec_salaries"),
        pytest.param(
            "KAPPA AUDIT", 5710, "11", None, HOMONYME, None, id="homonyme_type_vinci_asf",
        ),
        pytest.param(
            "AMK SA", 5710, "11", None, SIGLE, None,
            id="sigle_presque_seul",
        ),
        pytest.param(
            "AMK DISTRIBUTION FRANCE", 5710, "11", None, SIGLE,
            PROPRE, id="sigle_dans_un_nom_long",
        ),
    ],
)  # fmt: skip
def test_marque_sure_suffit_sauf_exceptions(
    mini: MiniRegistre,
    tmp_path: Path,
    nom: str,
    cj: int,
    tranche: str,
    salaries: int | None,
    reglages_en_plus: dict[str, Any],
    raison: str | None,
) -> None:
    """Une marque sûre suffit seule, sauf société civile, marque homonyme (« VINCI », « ASF »), sigle presque
    seul, ou nom réduit à la marque sans salarié (§3, §4 règle 5 ; rapport.md 2026-10-06)."""
    mini.societe(X, nom, cj=cj, tranche=tranche, salaries=salaries)
    x = societes(lancer(mini, tmp_path, **reglages_en_plus)).get(X)
    assert (x.pourquoi_dans_le_groupe if x else None) == raison
    if x:
        assert (x.indices, x.confiance) == (("marque_sure",), "C")


def test_marque_homonyme_entre_avec_une_deuxieme_preuve(mini: MiniRegistre, tmp_path: Path) -> None:
    """Une marque sûre homonyme entre avec une deuxième preuve, comme une marque ambiguë (§3)."""
    mini.societe(X, "KAPPA AUDIT")
    mini.dirigeants_communs(TETE, X)
    carto = lancer(mini, tmp_path, marques_sures=["Kappa"], marques_sures_homonymes=["KAPPA"])
    x = societes(carto)[X]
    assert (x.pourquoi_dans_le_groupe, x.confiance) == ("nom de marque et second indice", "B")


def test_societe_civile_de_la_marque_entre_par_un_mandat(mini: MiniRegistre, tmp_path: Path) -> None:
    """Une SCI à la marque du groupe n'entre pas par son nom, un mandat fort suffit (§4 règles 1 et 5)."""
    filiale(mini, X, "SCI ALPHAMARK", cj=CJ_SCI, tranche="NN")
    x = societes(lancer(mini, tmp_path))[X]
    assert (x.pourquoi_dans_le_groupe, x.confiance) == ("mandat fort au registre", "A")
    assert (x.ciblable, x.raison_ciblable) == (False, "Société civile ou SCI")


def test_marque_sure_et_mandat_autre(mini: MiniRegistre, tmp_path: Path) -> None:
    """Les règles d'entrée sont des « ou » : un mandat « Autre » en plus ne retire pas la règle de la marque
    sûre (§4 règle 5, « Faibles » ; T033)."""
    mini.societe(X, "ALPHAMARK SERVICES")
    mini.lien(TETE, X, AUTRE)
    x = societes(lancer(mini, tmp_path)).get(X)
    assert x is not None and x.pourquoi_dans_le_groupe == "nom de marque propre au groupe"


def test_adresse_dirigeant_commun_et_mandat_autre(mini: MiniRegistre, tmp_path: Path) -> None:
    """Un mandat « Autre » en plus ne retire pas non plus la règle « adresse du groupe et second indice » :
    à une adresse du groupe, un seul dirigeant commun suffit encore (§4 règle 7, « Faibles » ; T033)."""
    _adresse_du_groupe_a_87_pourcent(mini)
    mini.dirigeants_communs(TETE, X, n=1)
    mini.lien(TETE, X, AUTRE)
    x = societes(lancer(mini, tmp_path)).get(X)
    assert x is not None and x.pourquoi_dans_le_groupe == "adresse du groupe et second indice"


def test_mandat_autre_et_un_seul_indice_refuse(mini: MiniRegistre, tmp_path: Path) -> None:
    """Témoin de T033 : un mandat « Autre » plus un seul indice qui ne fait rien entrer seul (une marque
    ambiguë) reste refusé ; la correction n'ouvre aucune nouvelle voie d'entrée."""
    mini.societe(X, "ZETA GESTION")
    mini.lien(TETE, X, AUTRE)
    assert X not in societes(lancer(mini, tmp_path))


# ---------------------------------------------------------------- mandats, GIE, co-entreprises


@pytest.mark.parametrize(
    ("role", "libelle"),
    [
        (PRESIDENT, "Président"),
        (GERANT, "Gérant"),
        ("28", "Gérant et associé indéfiniment et solidairement responsable"),
        ("29", "Gérant et associé indéfiniment responsable"),
        ("74", "Associé indéfiniment et solidairement responsable"),
        ("75", "Associé indéfiniment responsable"),
        (COMMANDITE, "Associé commandité"),
    ],
)
def test_mandat_fort_fait_entrer_seul(mini: MiniRegistre, tmp_path: Path, role: str, libelle: str) -> None:
    """Un mandat fort d'une société du groupe (président, gérant, associé responsable) fait entrer seul (§4
    règle 1)."""
    filiale(mini, X, "FILIALE INVENTEE", role=role)
    x = societes(lancer(mini, tmp_path))[X]
    assert (x.pourquoi_dans_le_groupe, x.preuve, x.confiance) == (
        "mandat fort au registre",
        f"Mandat au registre : {libelle}",
        "A",
    )


@pytest.mark.parametrize(
    ("role", "participation"),
    [
        pytest.param(ADMINISTRATEUR, True, id="administrateur"),
        pytest.param(MEMBRE, True, id="membre"),
        pytest.param(AUTRE, False, id="autre"),
        pytest.param(COMMISSAIRE_AUX_COMPTES, False, id="commissaire_aux_comptes"),
        pytest.param("999", False, id="role_inconnu"),
    ],
)
def test_mandat_moyen_faible_ou_exclu_ne_suffit_pas_seul(
    mini: MiniRegistre, tmp_path: Path, role: str, participation: bool
) -> None:
    """Un mandat moyen seul range la société en participation sans contrôle ; « Autre », commissaire aux
    comptes ou rôle inconnu ne font rien entrer (§4, codes de rôle)."""
    mini.societe(X, "PARTICIPATION INVENTEE")
    mini.lien(TETE, X, role)
    carto = lancer(mini, tmp_path)
    assert X not in societes(carto)
    assert (X in {p.siren for p in carto.participations}) is participation


def test_mandat_moyen_et_indice_independant(mini: MiniRegistre, tmp_path: Path) -> None:
    """Un mandat moyen plus un indice indépendant (ici une marque ambiguë) fait entrer (§4 règle 4)."""
    mini.societe(X, "ZETA PARTICIPATIONS")
    mini.lien(TETE, X, ADMINISTRATEUR)
    x = societes(lancer(mini, tmp_path))[X]
    assert x.pourquoi_dans_le_groupe == "mandat au registre et indice indépendant"
    assert (x.preuve, x.confiance) == ("Mandat au registre : Administrateur", "A")


def test_mandat_autre_et_deux_indices(mini: MiniRegistre, tmp_path: Path) -> None:
    """Un mandat « Autre » plus deux indices (marque ambiguë et dirigeants communs) fait entrer (§4, « Faibles
    »)."""
    mini.societe(X, "ZETA GESTION")
    mini.lien(TETE, X, AUTRE)
    mini.dirigeants_communs(TETE, X)
    x = societes(lancer(mini, tmp_path))[X]
    assert x.pourquoi_dans_le_groupe == "mandat 'Autre' et deux indices"
    assert (x.preuve, x.confiance) == ("Mandat au registre : Autre", "A")


def test_descente_par_les_mandats_sur_trois_niveaux(mini: MiniRegistre, tmp_path: Path) -> None:
    """Le moteur descend par les mandats forts, de société retenue en société retenue (rapport.md 2026-10-03,
    étape 6)."""
    filiale(mini, F1, "FILIALE INVENTEE UN")
    filiale(mini, F2, "SOUS FILIALE INVENTEE", parent=F1, role=GERANT)
    filiale(mini, F3, "SOUS SOUS FILIALE INVENTEE", parent=F2, role=COMMANDITE)
    s = societes(lancer(mini, tmp_path))
    assert [(s[x].niveau, s[x].maison_mere_siren) for x in (F1, F2, F3)] == [(1, TETE), (2, F1), (3, F2)]
    assert s[F3].preuve == "Mandat au registre : Associé commandité"


def test_gie_dont_tous_les_membres_sont_du_groupe(mini: MiniRegistre, tmp_path: Path) -> None:
    """Un GIE dont tous les membres sont du groupe entre ; il est non ciblable (rapport.md 2026-10-06, règle
    Basile)."""
    filiale(mini, F1, "FILIALE INVENTEE UN")
    mini.societe(X, "GIE MOYENS INVENTES", cj=CJ_GIE, tranche="NN")
    mini.lien(TETE, X, MEMBRE)
    mini.lien(F1, X, MEMBRE)
    x = societes(lancer(mini, tmp_path))[X]
    assert x.pourquoi_dans_le_groupe == "GIE dont tous les membres sont du groupe"
    assert (x.maison_mere_siren, x.preuve, x.confiance) == (TETE, "Mandat au registre : Membre", "A")
    assert (x.ciblable, x.raison_ciblable) == (False, "GIE de moyens")


def test_gie_avec_un_membre_exterieur_reste_en_participation(mini: MiniRegistre, tmp_path: Path) -> None:
    """Un GIE dont un membre est hors du groupe n'entre pas : il est rangé en participation (rapport.md
    2026-10-06)."""
    mini.societe(EXT, "EXTERIEURE INVENTEE")
    mini.societe(X, "GIE MOYENS PARTAGES", cj=CJ_GIE, tranche="NN")
    mini.lien(TETE, X, MEMBRE)
    mini.lien(EXT, X, MEMBRE)
    carto = lancer(mini, tmp_path)
    assert X not in societes(carto)
    assert [(p.siren, p.mandats) for p in carto.participations] == [(X, (Mandat(TETE, "Membre"),))]


@pytest.mark.parametrize("dirigee_par_une_exterieure", [False, True])
def test_co_entreprise_rangee_en_participation(
    mini: MiniRegistre, tmp_path: Path, dirigee_par_une_exterieure: bool
) -> None:
    """Mandat moyen + indice, mais une société extérieure la préside aussi : co-entreprise, rangée en
    participation sans contrôle (§4 règle 4 ; rapport.md 2026-10-06 après-midi)."""
    mini.societe(EXT, "EXTERIEURE INVENTEE")
    mini.societe(X, "ZETA COENTREPRISE")
    mini.lien(TETE, X, ADMINISTRATEUR)
    if dirigee_par_une_exterieure:
        mini.lien(EXT, X, PRESIDENT)
    carto = lancer(mini, tmp_path)
    if dirigee_par_une_exterieure:
        assert X not in societes(carto)
        assert [(p.siren, p.mandats) for p in carto.participations] == [
            (X, (Mandat(TETE, "Administrateur"),))
        ]
    else:
        assert societes(carto)[X].pourquoi_dans_le_groupe == "mandat au registre et indice indépendant"
        assert carto.participations == ()


# ---------------------------------------------------------------- exclusions


@pytest.mark.parametrize("famille_exclue", [False, True])
def test_holding_familiale_exclue_par_le_nom_de_famille(
    mini: MiniRegistre, tmp_path: Path, famille_exclue: bool
) -> None:
    """Les dirigeants d'une famille listée dans `familles_exclues` ne comptent jamais comme dirigeants
    communs : la holding familiale domiciliée au siège n'entre pas (§3 ; contrat actuel par nom, T021 le
    remplacera par une empreinte)."""
    mini.domicilier(ADRESSE_GROUPE, TETE)
    filiale(mini, F1, "FILIALE INVENTEE UN", adresse=ADRESSE_GROUPE)
    mini.societe(X, "HOLDING FAMILIALE INVENTEE", naf="64.20Z", adresse=ADRESSE_GROUPE)
    for i in (1, 2):
        mini.dirigeant(TETE, personne(i, famille="FAMILLEINVENTEE"))
        mini.dirigeant(X, personne(i, famille="FAMILLEINVENTEE"))
    carto = lancer(mini, tmp_path, familles_exclues=["FamilleInventee"] if famille_exclue else [])
    x = societes(carto).get(X)
    if famille_exclue:
        assert x is None
    else:  # témoin : sans l'exclusion, la famille fait entrer sa holding
        assert x is not None and x.pourquoi_dans_le_groupe == "adresse du groupe et second indice"


@pytest.mark.parametrize(
    "exclusion",
    [
        pytest.param({"exclus": [X]}, id="par_siren"),
        pytest.param({"exclus_noms": ["Actionnaire"]}, id="par_nom"),
    ],
)
def test_actionnaire_exclu_par_les_reglages(
    mini: MiniRegistre, tmp_path: Path, exclusion: dict[str, Any]
) -> None:
    """Une société listée dans `exclus` ou `exclus_noms` n'entre jamais, même présidée par le groupe (§3)."""
    filiale(mini, X, "ACTIONNAIRE INVENTE")
    filiale(mini, F1, "FILIALE DE L ACTIONNAIRE", parent=X)
    s = societes(lancer(mini, tmp_path, **exclusion))
    assert X not in s and F1 not in s


@pytest.mark.parametrize(
    ("nom", "cj"),
    [
        pytest.param("CSE TETE INVENTEE", 5710, id="cse"),
        pytest.param("COMITE D ENTREPRISE INVENTE", 5710, id="comite"),
        pytest.param("AMICALE DU PERSONNEL INVENTEE", 5710, id="amicale"),
        pytest.param("ASSOCIATION SPORTIVE INVENTEE", 5710, id="association_par_le_nom"),
        pytest.param("CLUB INVENTE", CJ_ASSOCIATION, id="association_par_la_forme"),
        # T034 : le nom est normalisé (majuscules, accents retirés) avant le filtre.
        pytest.param("COMITÉ SOCIAL ET ÉCONOMIQUE INVENTÉ", 5710, id="comite_accentue"),
        pytest.param("Comité d'Établissement Inventé", 5710, id="comite_accentue_casse_mixte"),
        pytest.param("comite-d-entreprise inventé", 5710, id="comite_minuscules_tirets"),
    ],
)
def test_comite_d_entreprise_et_association_jamais_filiales(
    mini: MiniRegistre, tmp_path: Path, nom: str, cj: int
) -> None:
    """Comités d'entreprise, amicales, associations et fondations ne sont jamais des filiales, même présidés
    par le groupe (§4 ; rapport.md 2026-10-06 après-midi)."""
    filiale(mini, X, nom, cj=cj)
    carto = lancer(mini, tmp_path)
    assert X not in societes(carto)


@pytest.mark.parametrize(
    "nom",
    [
        pytest.param("COMITÉVA INVENTÉE", id="mot_qui_commence_par_comite"),
        pytest.param("SOCIÉTÉ DES COMITÉS INVENTÉE", id="comite_hors_debut"),
        pytest.param("Éditions Amicalement Inventées", id="amical_accentue_casse_mixte"),
    ],
)
def test_nom_proche_d_un_comite_reste_filiale(mini: MiniRegistre, tmp_path: Path, nom: str) -> None:
    """Le filtre des comités ne retient qu'un mot entier en tête du nom normalisé : une société commerciale
    dont le nom ressemble à « COMITÉ » ou « AMICALE » entre par son mandat comme les autres (T034)."""
    filiale(mini, X, nom)
    assert X in societes(lancer(mini, tmp_path))


def test_societe_etrangere_rangee_a_part(mini: MiniRegistre, tmp_path: Path) -> None:
    """Une société de droit étranger à la marque sûre est rangée à part, pas dans l'arbre (§4)."""
    mini.societe(X, "ALPHAMARK LIMITED", cj=CJ_ETRANGERE)
    carto = lancer(mini, tmp_path)
    assert X not in societes(carto)
    assert [(e.siren, e.nom) for e in carto.etrangeres] == [(X, "ALPHAMARK LIMITED")]


def test_societe_cessee_ecartee(mini: MiniRegistre, tmp_path: Path) -> None:
    """Une société sans siège actif dans SIRENE est écartée, même présidée par le groupe (moteur.py,
    load_info)."""
    filiale(mini, X, "FILIALE CESSEE INVENTEE", active=False)
    assert X not in societes(lancer(mini, tmp_path))


def test_societe_opposee_a_la_prospection_gardee_et_marquee(mini: MiniRegistre, tmp_path: Path) -> None:
    """Une société avec `diffusionCommerciale = false` reste dans l'arbre, marquée, jamais cachée
    (garde-fou 6 ; rapport.md 2026-10-03)."""
    filiale(mini, X, "FILIALE DISCRETE INVENTEE", diffusion_commerciale=False)
    filiale(mini, F1, "FILIALE INVENTEE UN")
    s = societes(lancer(mini, tmp_path))
    assert s[X].opposition_prospection is True
    assert s[X].pourquoi_dans_le_groupe == "mandat fort au registre"
    assert s[F1].opposition_prospection is False


def test_lien_ferme_ignore(mini: MiniRegistre, tmp_path: Path) -> None:
    """Un lien fermé au registre (date de fin posée) ne compte plus (principe 4)."""
    mini.societe(X, "ANCIENNE FILIALE INVENTEE")
    mini.lien(TETE, X, PRESIDENT, fin=FERME)
    carto = lancer(mini, tmp_path)
    assert X not in societes(carto)
    assert carto.liens == ()


# ---------------------------------------------------------------- point fixe


def test_point_fixe_societe_trouvee_au_troisieme_tour(mini: MiniRegistre, tmp_path: Path) -> None:
    """La boucle recommence jusqu'à ce que plus rien ne change : une société présidée par une société entrée
    au tour précédent est trouvée au tour suivant (rapport.md 2026-10-05, « jusqu'à ce que plus rien ne
    change »)."""
    mini.societe(F1, "ALPHAMARK INDUSTRIE")  # tour 1 : par la marque
    filiale(mini, F2, "ATELIERS INVENTES", parent=F1)  # tour 2 : présidée par F1
    filiale(mini, F3, "USINE INVENTEE", parent=F2, role=GERANT)  # tour 3 : gérée par F2
    carto = lancer(mini, tmp_path)
    s = societes(carto)
    assert [t.retenues for t in carto.tours] == [2, 3, 4, 4]
    assert [(s[x].niveau, s[x].maison_mere_siren) for x in (F1, F2, F3)] == [(1, TETE), (2, F1), (3, F2)]


@pytest.mark.xfail(
    strict=True,
    reason="Écart : la boucle s'arrête après MAX_TOURS = 8 tours même si elle n'a pas atteint "
    "le point fixe ; une chaîne de 9 mandats forts sous la tête perd son 9ᵉ niveau sans le signaler.",
)
def test_point_fixe_atteint_au_dela_de_huit_niveaux(mini: MiniRegistre, tmp_path: Path) -> None:
    """Le point fixe ne dépend pas de la profondeur du groupe : le 9ᵉ niveau d'une chaîne de mandats est
    trouvé."""
    chaine = [TETE, F1, F2, F3, F4, F5, F6, F7, F8, F9]
    for i, (parent, enfant) in enumerate(zip(chaine, chaine[1:], strict=False), start=1):
        filiale(mini, enfant, f"NIVEAU INVENTE {i}", parent=parent)
    s = societes(lancer(mini, tmp_path))
    assert s[F9].niveau == 9
