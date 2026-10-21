"""Étape 6 de la correspondance (T055) : les lignes encore introuvables, règle par règle.

Mini-registres inventés (règle produit 6). Chaque règle est testée seule, avec ses refus : la
justesse passe avant le rappel, et chaque cas refusé vient de la relecture du 2026-10-21.
"""

import sys
from pathlib import Path

import duckdb

from cartofr.perimetre import Correspondance, correspondre, extraire
from cartofr.perimetre.correspondance import (
    COMPACTE,
    CONFLIT,
    DEBUT,
    FERMEE,
    FONDS,
    HOMONYMES,
    INTROUVABLE,
    UNIQUE,
    USUELLE,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "moteur"))
from fabrique import PRESIDENT, MiniRegistre, siren  # noqa: E402  # pyright: ignore[reportMissingImports]

TETE = siren(1)


def _mini() -> MiniRegistre:
    mini = MiniRegistre()
    mini.societe(TETE, "TETE INVENTEE")
    return mini


def _correspondre(mini: MiniRegistre, tmp_path: Path, *noms: str) -> list[Correspondance]:
    chemin = mini.ecrire(tmp_path / "r.duckdb")
    con = duckdb.connect(str(chemin), read_only=True)
    try:
        texte = "".join(f"{n} France 100,00 Intégration globale\n" for n in noms)
        return correspondre(con, TETE, extraire(texte))
    finally:
        con.close()


def test_ligne_de_fonds_refusee_comme_fonds(tmp_path: Path):
    lignes = _correspondre(
        _mini(), tmp_path, "FCP Inventé Actions", "Cap Inventé 3 Part A", "Fonds Inventé Euro"
    )
    assert [c.raison for c in lignes] == [FONDS, FONDS, FONDS]


def test_nom_sans_ses_espaces(tmp_path: Path):
    mini = _mini()
    a = mini.societe(siren(10), "CRFP 22")
    (c,) = _correspondre(mini, tmp_path, "CRFP22")
    assert (c.raison, c.siren) == (COMPACTE, a)


def test_nom_sans_espaces_trop_court_jamais_essaye(tmp_path: Path):
    """« CPR AM » n'est pas « C'PRAM » : une clé sans espaces de moins de 6 caractères n'est pas essayée."""
    mini = _mini()
    mini.societe(siren(10), "SCI C'PRAM")
    (c,) = _correspondre(mini, tmp_path, "CPR AM")
    assert c.raison == INTROUVABLE


def test_nom_sans_espaces_homonymes_departages_par_le_registre(tmp_path: Path):
    mini = _mini()
    b = mini.societe(siren(10), "DISTRI FLEURY")
    mini.societe(siren(11), "DIS TRIFLEURY")
    mini.lien(TETE, b, PRESIDENT)
    (c,) = _correspondre(mini, tmp_path, "DISTRIFLEURY")
    assert (c.raison, c.siren) == (COMPACTE, b)


def test_nom_sans_espaces_seul_en_france_hors_du_groupe(tmp_path: Path):
    """Un nom-code (un chiffre, ou 10 caractères) seul en France suffit ; un nom ordinaire, non."""
    mini = _mini()
    mini.societe(siren(10), "SCI GAMMASOL")
    mini.societe(siren(11), "SOLAIRE INVENTE 1")
    lignes = _correspondre(mini, tmp_path, "GAMMA SOL", "SolaireInventé1")
    assert [c.raison for c in lignes] == [INTROUVABLE, COMPACTE]


def test_denomination_usuelle_d_une_societe_du_groupe(tmp_path: Path):
    mini = _mini()
    a = mini.societe(siren(10), "SOCIETE MONTEREAU INVENTEE DE DISTRIBUTION", usuelle="SOMONTINVENTE")
    mini.lien(TETE, a, PRESIDENT)
    (c,) = _correspondre(mini, tmp_path, "Somontinventé")
    assert (c.raison, c.siren) == (USUELLE, a)


def test_enseigne_seule_en_france_hors_du_groupe_refusee(tmp_path: Path):
    """« Franck & Fils » était la dénomination usuelle d'une société de travaux sans lien (revue T055)."""
    mini = _mini()
    mini.societe(siren(10), "STORY INVENTEE", usuelle="FRANCK INVENTE ET FILS", commune="MENTON")
    (c,) = _correspondre(mini, tmp_path, "Franck Inventé & Fils")
    assert c.raison == INTROUVABLE


def test_enseigne_retenue_dans_la_ville_du_document(tmp_path: Path):
    mini = _mini()
    a = mini.societe(siren(10), "STORY INVENTEE", usuelle="FRANCK INVENTE ET FILS", commune="PARIS")
    mini.societe(siren(11), "AUTRE INVENTEE", usuelle="FRANCK INVENTE ET FILS", commune="MENTON")
    chemin = mini.ecrire(tmp_path / "r.duckdb")
    con = duckdb.connect(str(chemin), read_only=True)
    try:
        (c,) = correspondre(con, TETE, extraire("Franck Inventé & Fils Paris, France IG 100 %\n"))
    finally:
        con.close()
    assert (c.raison, c.siren) == (USUELLE, a)


def test_raison_sociale_fermee_passe_avant_l_enseigne(tmp_path: Path):
    mini = _mini()
    mini.societe(siren(10), "FRANCK INVENTE ET FILS", active=False)
    b = mini.societe(siren(11), "STORY INVENTEE", usuelle="FRANCK INVENTE ET FILS")
    mini.lien(TETE, b, PRESIDENT)
    (c,) = _correspondre(mini, tmp_path, "Franck Inventé & Fils")
    assert (c.raison, c.siren) == (FERMEE, None)


def test_l_etape_6_ne_reprend_pas_une_societe_deja_retenue(tmp_path: Path):
    """Avant : « Beta Inventée » trouvait la même société par sa dénomination usuelle, et les deux
    lignes passaient en conflit ; la règle la moins sûre faisait perdre la plus sûre."""
    mini = _mini()
    a = mini.societe(siren(10), "ALPHAMARK", usuelle="BETA INVENTEE")
    mini.lien(TETE, a, PRESIDENT)
    lignes = _correspondre(mini, tmp_path, "Alphamark", "Beta Inventée")
    assert [(c.raison, c.siren) for c in lignes] == [(UNIQUE, a), (INTROUVABLE, None)]


def test_debut_de_raison_sociale_d_une_societe_du_groupe(tmp_path: Path):
    mini = _mini()
    a = mini.societe(siren(10), "BUREAU INVENTE MARINE OFFSHORE - REGISTRE INTERNATIONAL INVENTE")
    mini.lien(TETE, a, PRESIDENT)
    (c,) = _correspondre(mini, tmp_path, "Bureau Inventé Marine Offshore SAS")
    assert (c.raison, c.siren) == (DEBUT, a)


def test_debut_de_raison_sociale_hors_du_groupe_trop_court_ou_la_tete_refuse(tmp_path: Path):
    mini = MiniRegistre()
    mini.societe(TETE, "SOCIETE INVENTEE GENERALE")
    mini.societe(siren(10), "BUREAU INVENTE MARINE OFFSHORE - REGISTRE INTERNATIONAL INVENTE")  # sans lien
    b = mini.societe(siren(11), "OMEGAMARK INVENTE INTERNATIONAL")
    mini.lien(TETE, b, PRESIDENT)
    lignes = _correspondre(
        mini, tmp_path, "Bureau Inventé Marine Offshore", "Omegamark Inventé", "Société Inventée"
    )
    assert [c.raison for c in lignes] == [INTROUVABLE, INTROUVABLE, INTROUVABLE]


def test_nom_porte_seulement_par_une_societe_fermee(tmp_path: Path):
    mini = _mini()
    mini.societe(siren(10), "SOCIETE INVENTEE VENTURES", active=False)
    (c,) = _correspondre(mini, tmp_path, "Société Inventée Ventures")
    assert (c.raison, c.siren, c.retenue) == (FERMEE, None, False)


def test_l_etape_6_ne_touche_ni_aux_retenues_ni_aux_homonymes(tmp_path: Path):
    mini = _mini()
    a = mini.societe(siren(10), "ALPHAMARK")
    mini.societe(siren(11), "GAMMAMARK")
    mini.societe(siren(12), "GAMMAMARK")
    mini.societe(siren(13), "GAMMA MARK", usuelle="GAMMAMARK")
    lignes = _correspondre(mini, tmp_path, "Alphamark", "Gammamark")
    assert [(c.raison, c.siren) for c in lignes] == [(UNIQUE, a), (HOMONYMES, None)]


def test_conflit_entre_deux_lignes_de_l_etape_6(tmp_path: Path):
    """Deux noms différents qui mènent à la même société par l'étape 6 : aucune des deux n'est retenue."""
    mini = _mini()
    a = mini.societe(siren(10), "CRFP 22", usuelle="CARREFOUR INVENTE VINGT DEUX")
    mini.lien(TETE, a, PRESIDENT)
    lignes = _correspondre(mini, tmp_path, "CRFP22", "Carrefour Inventé Vingt Deux")
    assert [c.raison for c in lignes] == [CONFLIT, CONFLIT]


def test_motif_fonds_sans_faux_positifs():
    from cartofr.perimetre.extraction import MOTIF_FONDS

    assert MOTIF_FONDS.search("CAP SANTE 3 PART A") and MOTIF_FONDS.search("FCP Inventé")
    assert MOTIF_FONDS.search("Fonds Inventé Euro") and MOTIF_FONDS.search(
        "SOGEINVENT DIVERSIFIED LOANS FUND"
    )
    assert not MOTIF_FONDS.search("CACEIS Inventé Fund Administration")
    assert not MOTIF_FONDS.search("Société de prise de part de capital")
