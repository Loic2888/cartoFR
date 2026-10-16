"""Le périmètre publié dans le moteur (T043, règle produit 8) : entrée, preuve, confiance, contrôle.

Une société inscrite en intégration globale entre avec sa preuve (document, ligne, méthode, taux) ;
ses filiales entrent par les règles du registre. Une société inscrite sans contrôle n'entre pas,
même présidée par le groupe : le document l'emporte (décision de Loïc, 2026-10-16).

Tous les noms et toutes les lignes de document sont inventés (règle produit 6).
"""

from pathlib import Path
from typing import Any

import pytest
from fabrique import CJ_ASSOCIATION, CJ_ETRANGERE, PRESIDENT, MiniRegistre, personne, reglages, siren

from cartofr.moteur import Carto, cartographier
from cartofr.moteur.modele import Decision, Mandat, Societe
from cartofr.perimetre import Candidat, LignePerimetre, PerimetrePublie

TETE = siren(1)
X = siren(50)  # la société inscrite au périmètre
F1, F2 = siren(10), siren(11)
SOURCE = "Liste inventée des sociétés consolidées 2025"


@pytest.fixture
def mini() -> MiniRegistre:
    registre = MiniRegistre()
    registre.societe(TETE, "TETE INVENTEE", naf="70.10Z", tranche="22")
    return registre


def ligne(nom: str, methode: str = "IG", taux: float = 100.0) -> LignePerimetre:
    libelle = {"IG": "Intégration globale", "MEE": "Mise en équivalence"}.get(methode, "Autre")
    return LignePerimetre((Candidat(nom, None),), methode, taux, f"{nom} France {taux:.2f} {libelle}")


def lancer(
    mini: MiniRegistre,
    tmp_path: Path,
    *lignes: LignePerimetre,
    perimetre: bool = True,
    decisions: dict[str, Decision] | None = None,
    **reg: Any,
) -> Carto:
    """La carto du groupe sans aucune marque (tête seule), avec le périmètre donné. Le registre est
    réécrit à chaque appel : il suit toujours `mini`."""
    doc = PerimetrePublie(SOURCE, lignes) if perimetre else None
    chemin = tmp_path / "registre.duckdb"
    chemin.unlink(missing_ok=True)
    mini.ecrire(chemin)
    return cartographier(reglages(TETE, **reg), chemin, perimetre=doc, decisions=decisions)


def societes(carto: Carto) -> dict[str, Societe]:
    return {s.siren: s for s in carto.societes}


def test_societe_du_perimetre_entre_avec_sa_preuve(mini: MiniRegistre, tmp_path: Path) -> None:
    mini.societe(X, "ALPHAMARK INVENTEE")
    x = societes(lancer(mini, tmp_path, ligne("Alphamark Inventée", taux=99.5)))[X]
    assert x.pourquoi_dans_le_groupe == (
        f"inscrite au périmètre publié du groupe : {SOURCE}, ligne « Alphamark Inventée France 99.50 "
        "Intégration globale » (intégration globale, 99,5 %)"
    )
    assert "perimetre" in x.indices
    assert (x.maison_mere_siren, x.preuve, x.confiance) == (
        TETE, "Déduit : rattachée à la tête du groupe", "B"
    )  # fmt: skip


def test_sans_perimetre_la_meme_societe_n_entre_pas(mini: MiniRegistre, tmp_path: Path) -> None:
    mini.societe(X, "ALPHAMARK INVENTEE")
    assert X not in societes(lancer(mini, tmp_path, perimetre=False))


def test_filiales_descendues_par_les_regles_du_registre(mini: MiniRegistre, tmp_path: Path) -> None:
    mini.societe(X, "ALPHAMARK INVENTEE")
    mini.societe(F1, "FILIALE UN INVENTEE")
    mini.societe(F2, "FILIALE DEUX INVENTEE")
    mini.lien(X, F1, PRESIDENT)
    mini.lien(F1, F2, PRESIDENT)
    s = societes(lancer(mini, tmp_path, ligne("Alphamark Inventée")))
    assert (s[F1].maison_mere_siren, s[F1].confiance, s[F1].niveau) == (X, "A", 2)
    assert (s[F2].maison_mere_siren, s[F2].confiance, s[F2].niveau) == (F1, "A", 3)
    assert s[F1].pourquoi_dans_le_groupe == "mandat fort au registre"


def test_inscrite_et_reliee_par_un_mandat_confiance_a(mini: MiniRegistre, tmp_path: Path) -> None:
    """La raison d'entrée cite le document ; le rattachement, lu au registre, est en confiance A."""
    mini.societe(X, "ALPHAMARK INVENTEE")
    mini.lien(TETE, X, PRESIDENT)
    x = societes(lancer(mini, tmp_path, ligne("Alphamark Inventée")))[X]
    assert x.pourquoi_dans_le_groupe.startswith("inscrite au périmètre publié du groupe")
    assert (x.preuve, x.confiance) == ("Mandat au registre : Président", "A")


@pytest.mark.parametrize("methode", ["MEE", "autre"])
def test_sans_controle_n_entre_pas_meme_presidee_par_le_groupe(
    mini: MiniRegistre, tmp_path: Path, methode: str
) -> None:
    mini.societe(X, "ALPHAMARK INVENTEE")
    mini.societe(F1, "FILIALE UN INVENTEE")
    mini.lien(TETE, X, PRESIDENT)
    mini.lien(X, F1, PRESIDENT)
    carto = lancer(mini, tmp_path, ligne("Alphamark Inventée", methode, 30.0))
    assert X not in societes(carto) and F1 not in societes(carto)
    clair = {"MEE": "mise en équivalence", "autre": "autre méthode"}[methode]
    # Le mandat fort, qui n'a pas suffi, est dit dans la participation.
    assert [(p.siren, p.mandats) for p in carto.participations] == [(X, (Mandat(TETE, "Président"),))]
    cas = {c.siren: c for c in carto.cas}[X]
    assert "participation" in cas.types and not cas.retenue
    assert cas.regle.startswith("Non retenue : non contrôlée selon le périmètre publié")
    assert f"Le périmètre publié du groupe la dit non contrôlée : {clair}" in cas.indices_contre
    assert f"Inscrite au périmètre publié du groupe, sans contrôle ({clair})" in cas.indices_pour


def test_sans_controle_retenue_par_le_consultant(mini: MiniRegistre, tmp_path: Path) -> None:
    """Retenue par le consultant, elle entre ; l'inscription sans contrôle ne compte pas comme indice :
    avec une seule marque ambiguë, le rattachement reste en confiance C."""
    mini.societe(X, "ALPHAMARK INVENTEE")
    mee = ligne("Alphamark Inventée", "MEE", 30.0)
    x = societes(lancer(mini, tmp_path, mee, decisions={X: "retenir"}, marques_ambigues=["Alphamark"]))[X]
    assert x.pourquoi_dans_le_groupe == "retenue par décision du consultant"
    assert x.confiance == "C"


def test_tete_inscrite_au_perimetre_reste_la_tete(mini: MiniRegistre, tmp_path: Path) -> None:
    s = societes(lancer(mini, tmp_path, ligne("Tete Inventée", "MEE", 50.0)))
    assert (s[TETE].pourquoi_dans_le_groupe, s[TETE].niveau) == ("tête du groupe", 0)


def test_inscrite_deux_fois_l_integration_globale_l_emporte(mini: MiniRegistre, tmp_path: Path) -> None:
    mini.societe(X, "ALPHAMARK INVENTEE")
    carto = lancer(mini, tmp_path, ligne("Alphamark Inventée", "MEE", 30.0), ligne("Alphamark Inventée"))
    assert X in societes(carto) and not carto.participations


def test_exclue_par_les_reglages_ou_ecartee_par_le_consultant(mini: MiniRegistre, tmp_path: Path) -> None:
    mini.societe(X, "ALPHAMARK INVENTEE")
    assert X not in societes(lancer(mini, tmp_path, ligne("Alphamark Inventée"), exclus=[X]))
    carto = lancer(mini, tmp_path, ligne("Alphamark Inventée"), decisions={X: "ecarter"})
    assert X not in societes(carto)
    assert {c.siren: c for c in carto.cas}[X].regle.startswith("Écartée par le consultant")


def test_association_ecartee_etrangere_rangee_a_part(mini: MiniRegistre, tmp_path: Path) -> None:
    mini.societe(X, "ALPHAMARK INVENTEE", cj=CJ_ASSOCIATION)
    mini.societe(F1, "FILIALE ETRANGERE INVENTEE", cj=CJ_ETRANGERE)
    carto = lancer(mini, tmp_path, ligne("Alphamark Inventée"), ligne("Filiale Etrangere Inventée"))
    assert X not in societes(carto) and F1 not in societes(carto)
    assert [e.siren for e in carto.etrangeres] == [F1]


def test_ligne_refusee_sans_effet(mini: MiniRegistre, tmp_path: Path) -> None:
    """Deux homonymes sans lien au groupe : la ligne est refusée, la carto est celle sans périmètre."""
    mini.societe(X, "ALPHAMARK INVENTEE")
    mini.societe(F1, "ALPHAMARK INVENTEE", commune="LYON")
    avec = lancer(mini, tmp_path, ligne("Alphamark Inventée"), ligne("Introuvable Inventée"))
    assert avec == lancer(mini, tmp_path, perimetre=False)


def test_aucun_nom_de_personne_dans_la_carto(mini: MiniRegistre, tmp_path: Path) -> None:
    mini.societe(X, "ALPHAMARK INVENTEE")
    mini.societe(F1, "FILIALE UN INVENTEE")
    mini.dirigeants_communs(X, F1)
    mini.dirigeant(TETE, personne(1))
    mini.lien(X, F1, PRESIDENT)
    carto = lancer(mini, tmp_path, ligne("Alphamark Inventée"), ligne("Filiale Un Inventée", "MEE", 20.0))
    assert "PERSONNE INVENTEE" not in repr(carto) and "PRENOM" not in repr(carto)
