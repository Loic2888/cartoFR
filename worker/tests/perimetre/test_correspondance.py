"""Correspondance d'un périmètre publié avec le registre (T042 C2), sur des mini-registres inventés.

Chaque étape de la règle est testée seule : porteur unique, homonymes départagés par la commune
puis par le registre, refus. Tous les noms et SIREN sont inventés (règle produit 6).
"""

import sys
from datetime import date
from pathlib import Path

import duckdb
import pyarrow as pa
import pytest

from cartofr.perimetre import Correspondance, LignePerimetre, cle, correspondre, extraire
from cartofr.perimetre.correspondance import (
    COMMUNE,
    CONFLIT,
    HOMONYMES,
    INTROUVABLE,
    REGISTRE,
    UNIQUE,
    _conflits,  # pyright: ignore[reportPrivateUsage]
    cle_arrow,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "moteur"))
from fabrique import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    COMMISSAIRE_AUX_COMPTES,
    PRESIDENT,
    MiniRegistre,
    siren,
)

TETE = siren(1)


def _correspondre(mini: MiniRegistre, tmp_path: Path, texte: str) -> list[Correspondance]:
    chemin = mini.ecrire(tmp_path / "r.duckdb")
    con = duckdb.connect(str(chemin), read_only=True)
    try:
        return correspondre(con, TETE, extraire(texte))
    finally:
        con.close()


def _vinci(nom: str) -> str:
    return f"{nom} France 100,00 Intégration globale"


def _mini() -> MiniRegistre:
    mini = MiniRegistre()
    mini.societe(TETE, "TETE INVENTEE")
    return mini


@pytest.mark.parametrize(
    ("nom", "attendu"),
    [
        ("Sté Inventée & Cie SAS", "SOCIETE INVENTEE COMPAGNIE"),
        ("SAS Alphamark", "ALPHAMARK"),
        ("Alphamark S.A.", "ALPHAMARK"),
        ("S.A.S. Alphamark", "ALPHAMARK"),
        ("Alpha SA Beta SAS", "ALPHA SA BETA"),  # une forme au milieu du nom reste
        ("SCI SAS Alphamark", "ALPHAMARK"),
        ("STEPHANE SAS", "STEPHANE"),
        ("ETS Betamark et Fils", "ETABLISSEMENTS BETAMARK FILS"),
        ("Gammamark-Été", "GAMMAMARK ETE"),
        ("SAS", ""),
        (None, ""),
        # T053
        ("Château d’Inventé", "CHATEAU D INVENTE"),  # apostrophe typographique, comme « ' »
        ("CHATEAU D'INVENTE", "CHATEAU D INVENTE"),
        ("M H C S", "MHCS"),  # sigle espacé recollé
        ("Inventé M H C S Vins", "INVENTE MHCS VINS"),
        ("LVMH METIERS D ART", "LVMH METIERS D ART"),  # une lettre seule reste seule
        ("Cheval Inventé ST-Tropez", "CHEVAL INVENTE SAINT TROPEZ"),
        ("Œuvre Deltamark", "OEUVRE DELTAMARK"),
        ("S.N.C.F.", "SNCF"),  # le sigle entier, pas « SNC F » puis « F » (revue T053)
        ("J.S.A.", "JSA"),
        ("Alphamark S.A.R.L.", "ALPHAMARK"),
    ],
)
def test_cle(nom: str | None, attendu: str):
    assert cle(nom) == attendu


def test_cle_arrow_identique_a_cle():
    noms = [
        "Sté Inventée & Cie SAS",
        "SAS Alphamark",
        "ETS Betamark et Fils",
        "Œuvre Deltamark",
        "STEPHANE SAS",
        "Alphamark S.A.",
        "S.A.S. Alphamark",
        "Alpha SA Beta SAS",
        "SCI SAS Alphamark",
        "SAS",
        "",
        "Château d’Inventé",
        "M H C S",
        "A B C Deltamark D E",
        "X",
        "Cheval Inventé ST-Tropez",
        "Straße Inventée",
        "S.N.C.F.",
        "Alphamark S.A.R.L.",
    ]
    assert cle_arrow(pa.array(noms)).to_pylist() == [cle(n) for n in noms]


def test_porteur_unique(tmp_path: Path):
    mini = _mini()
    a = mini.societe(siren(10), "ALPHAMARK SERVICES")
    (c,) = _correspondre(mini, tmp_path, _vinci("Alphamark Services SAS"))
    assert (c.raison, c.siren, c.nom, c.porteurs, c.retenue) == (UNIQUE, a, "Alphamark Services SAS", 1, True)


def test_abreviation_et_forme_juridique(tmp_path: Path):
    mini = _mini()
    a = mini.societe(siren(10), "STE INVENTEE DE TRAVAUX SAS")
    (c,) = _correspondre(mini, tmp_path, _vinci("Société Inventée de Travaux"))
    assert (c.raison, c.siren) == (UNIQUE, a)


def test_societe_fermee_introuvable(tmp_path: Path):
    mini = _mini()
    mini.societe(siren(10), "ALPHAMARK", active=False)
    (c,) = _correspondre(mini, tmp_path, _vinci("Alphamark"))
    assert (c.raison, c.siren, c.porteurs, c.retenue) == (INTROUVABLE, None, 0, False)


def test_societe_fermee_ne_compte_pas_comme_homonyme(tmp_path: Path):
    mini = _mini()
    a = mini.societe(siren(10), "ALPHAMARK")
    mini.societe(siren(11), "ALPHAMARK", active=False)
    (c,) = _correspondre(mini, tmp_path, _vinci("Alphamark"))
    assert (c.raison, c.siren) == (UNIQUE, a)


def test_homonymes_departages_par_la_commune(tmp_path: Path):
    mini = _mini()
    mini.societe(siren(10), "BETAMARK", commune="PARIS 8")
    lyon = mini.societe(siren(11), "BETAMARK", commune="LYON 3")
    (c,) = _correspondre(mini, tmp_path, "Betamark Lyon, France IG 100 %")
    assert (c.raison, c.siren, c.porteurs) == (COMMUNE, lyon, 2)


def test_arrondissement_de_paris(tmp_path: Path):
    mini = _mini()
    paris = mini.societe(siren(10), "BETAMARK", commune="PARIS 8")
    mini.societe(siren(11), "BETAMARK", commune="LYON 3")
    (c,) = _correspondre(mini, tmp_path, "Betamark Paris, France IG 100 %")
    assert (c.raison, c.siren) == (COMMUNE, paris)


def test_commune_qui_commence_pareil_ne_suffit_pas(tmp_path: Path):
    mini = _mini()
    mini.societe(siren(10), "BETAMARK", commune="SAINT DENIS")
    mini.societe(siren(11), "BETAMARK", commune="SAINT MALO")
    (c,) = _correspondre(mini, tmp_path, "Betamark Saint, France IG 100 %")
    assert (c.raison, c.siren, c.porteurs) == (HOMONYMES, None, 2)


def test_homonymes_departages_par_le_registre_depuis_la_tete(tmp_path: Path):
    mini = _mini()
    filiale = mini.societe(siren(10), "GAMMAMARK")
    mini.societe(siren(11), "GAMMAMARK")
    mini.lien(TETE, filiale, PRESIDENT)
    (c,) = _correspondre(mini, tmp_path, _vinci("Gammamark"))
    assert (c.raison, c.siren, c.porteurs) == (REGISTRE, filiale, 2)


def test_homonymes_departages_sous_une_societe_retenue(tmp_path: Path):
    mini = _mini()
    a = mini.societe(siren(10), "ALPHAMARK")
    sous = mini.societe(siren(11), "GAMMAMARK")
    mini.societe(siren(12), "GAMMAMARK")
    mini.lien(a, sous, PRESIDENT)
    resultats = _correspondre(mini, tmp_path, _vinci("Alphamark") + "\n" + _vinci("Gammamark"))
    assert [(c.raison, c.siren) for c in resultats] == [(UNIQUE, a), (REGISTRE, sous)]


def test_lien_de_commissaire_aux_comptes_ou_ferme_ne_departage_pas(tmp_path: Path):
    mini = _mini()
    g1 = mini.societe(siren(10), "GAMMAMARK")
    g2 = mini.societe(siren(11), "GAMMAMARK")
    mini.lien(TETE, g1, COMMISSAIRE_AUX_COMPTES)
    mini.lien(TETE, g2, PRESIDENT, fin=date(2026, 6, 1))
    (c,) = _correspondre(mini, tmp_path, _vinci("Gammamark"))
    assert (c.raison, c.siren, c.porteurs) == (HOMONYMES, None, 2)


def test_deux_homonymes_dans_le_groupe_restent_homonymes(tmp_path: Path):
    mini = _mini()
    g1 = mini.societe(siren(10), "GAMMAMARK")
    g2 = mini.societe(siren(11), "GAMMAMARK")
    mini.lien(TETE, g1, PRESIDENT)
    mini.lien(TETE, g2, PRESIDENT)
    (c,) = _correspondre(mini, tmp_path, _vinci("Gammamark"))
    assert (c.raison, c.siren) == (HOMONYMES, None)


def test_apostrophe_typographique_du_document(tmp_path: Path):
    mini = _mini()
    a = mini.societe(siren(10), "SA DU CHATEAU D'INVENTE", commune="SAUTERNES")
    (c,) = _correspondre(mini, tmp_path, "SA Du Château d’Inventé Sauternes, France IG 97 %")
    assert (c.raison, c.siren) == (UNIQUE, a)


def test_sigle_espace_au_registre_departage_par_la_commune(tmp_path: Path):
    mini = _mini()
    epernay = mini.societe(siren(10), "M H C S", commune="EPERNAY")
    mini.societe(siren(11), "MHCS", commune="LYON 3")  # un autre MHCS, ailleurs
    (c,) = _correspondre(mini, tmp_path, "MHCS Épernay, France IG 66 %")
    assert (c.raison, c.siren, c.porteurs) == (COMMUNE, epernay, 2)


def test_ville_comprise_dans_le_nom(tmp_path: Path):
    mini = _mini()
    a = mini.societe(siren(10), "HOTEL INVENTE COURCHEVEL", commune="COURCHEVEL")
    (c,) = _correspondre(mini, tmp_path, "SNC HOTEL INVENTE Courchevel, France IG 100 %")
    assert (c.raison, c.siren) == (COMMUNE, a)


def test_ville_comprise_dans_le_nom_exige_le_siege_dans_la_ville(tmp_path: Path):
    mini = _mini()
    mini.societe(siren(10), "HOTEL INVENTE COURCHEVEL", commune="PARIS 8")
    (c,) = _correspondre(mini, tmp_path, "SNC HOTEL INVENTE Courchevel, France IG 100 %")
    assert c.raison == INTROUVABLE


def test_le_secours_ne_passe_pas_devant_le_registre(tmp_path: Path):
    """« L . P. M . Paris » : deux L.P.M. à Paris, dont un relié au groupe ; « LPM PARIS » existe
    aussi. Le registre départage les L.P.M., le nom ville comprise n'est pas essayé."""
    mini = _mini()
    filiale = mini.societe(siren(10), "L.P.M.", commune="PARIS 8")
    mini.societe(siren(11), "LPM", commune="PARIS 15")
    mini.societe(siren(12), "LPM PARIS", commune="PARIS 1")
    mini.lien(TETE, filiale, PRESIDENT)
    (c,) = _correspondre(mini, tmp_path, "L . P. M . Paris, France IG 100 %")
    assert (c.raison, c.siren) == (REGISTRE, filiale)


def test_le_secours_essaye_si_rien_n_attend(tmp_path: Path):
    mini = _mini()
    a = mini.societe(siren(10), "ALPHAMARK INVENTE FRANCE", commune="LEVALLOIS PERRET")
    (c,) = _correspondre(mini, tmp_path, "AB Inventé – Alphamark Inventé France Courbevoie, France IG 66 %")
    assert (c.raison, c.siren, c.nom) == (UNIQUE, a, "Alphamark Inventé France")


def test_un_secours_a_homonymes_n_arrete_pas_le_secours_suivant(tmp_path: Path):
    mini = _mini()
    mini.societe(siren(10), "AB INVENTE", commune="METZ")
    mini.societe(siren(11), "AB INVENTE", commune="LYON 3")
    a = mini.societe(siren(12), "ALPHAMARK INVENTE FRANCE", commune="LEVALLOIS PERRET")
    (c,) = _correspondre(mini, tmp_path, "AB Inventé – Alphamark Inventé France Courbevoie, France IG 66 %")
    assert (c.raison, c.siren) == (UNIQUE, a)


def test_ligne_coupee_aux_antilles(tmp_path: Path):
    mini = _mini()
    a = mini.societe(siren(10), "ALPHAMARK SAINT BARTHELEMY", commune="SAINT BARTHELEMY")
    texte = "Alphamark Saint‑Barthélemy Saint‑Barthélemy,  \nAntilles françaises\nIG 100 %"
    (c,) = _correspondre(mini, tmp_path, texte)
    assert (c.raison, c.siren) == (UNIQUE, a)


def test_introuvable(tmp_path: Path):
    (c,) = _correspondre(_mini(), tmp_path, _vinci("Deltamark"))
    assert (c.raison, c.siren, c.nom) == (INTROUVABLE, None, None)


def test_titre_avant_la_ligne_le_nom_court_est_essaye_ensuite(tmp_path: Path):
    mini = _mini()
    a = mini.societe(siren(10), "ALPHAMARK")
    (c,) = _correspondre(mini, tmp_path, "POLE INVENTE\n" + _vinci("Alphamark"))
    assert (c.raison, c.siren, c.nom) == (UNIQUE, a, "Alphamark")


def test_nom_coupe_sur_la_ligne_de_la_ville_le_nom_long_dabord_si_le_siege_y_est(tmp_path: Path):
    mini = _mini()
    long = mini.societe(siren(10), "COMPAGNIE INVENTEE DU CHAMPAGNE", commune="EPERNAY")
    mini.societe(siren(11), "DU CHAMPAGNE")
    (c,) = _correspondre(mini, tmp_path, "Compagnie Inventée\ndu Champagne Épernay, France IG 66 %")
    assert (c.raison, c.siren) == (COMMUNE, long)


def test_nom_coupe_siege_ailleurs_limite_connue_la_fin_du_nom_gagne(tmp_path: Path):
    """Limite écrite dans `extraction` : sans le siège dans la ville, le nom recollé ne passe pas."""
    mini = _mini()
    mini.societe(siren(10), "COMPAGNIE INVENTEE DU CHAMPAGNE", commune="REIMS")
    fin = mini.societe(siren(11), "DU CHAMPAGNE")
    (c,) = _correspondre(mini, tmp_path, "Compagnie Inventée\ndu Champagne Épernay, France IG 66 %")
    assert (c.raison, c.siren) == (UNIQUE, fin)


def test_ordre_des_lignes_garde(tmp_path: Path):
    mini = _mini()
    a = mini.societe(siren(10), "ALPHAMARK")
    b = mini.societe(siren(11), "BETAMARK")
    texte = "\n".join(_vinci(n) for n in ("Betamark", "Deltamark", "Alphamark"))
    assert [c.siren for c in _correspondre(mini, tmp_path, texte)] == [b, None, a]


def test_aucune_ligne(tmp_path: Path):
    assert _correspondre(_mini(), tmp_path, "") == []


def test_entrepreneur_individuel_ecarte(tmp_path: Path):
    mini = _mini()
    mini.societe(siren(10), "ALPHAMARK", cj=1100)
    a = mini.societe(siren(11), "ALPHAMARK")
    (c,) = _correspondre(mini, tmp_path, _vinci("Alphamark"))
    assert (c.raison, c.siren, c.porteurs) == (UNIQUE, a, 1)


def test_le_registre_ne_departage_que_les_homonymes_de_la_ville(tmp_path: Path):
    mini = _mini()
    mini.societe(siren(10), "BETAMARK", commune="LYON 3")
    mini.societe(siren(11), "BETAMARK", commune="LYON 7")
    marseille = mini.societe(siren(12), "BETAMARK", commune="MARSEILLE")
    mini.lien(TETE, marseille, PRESIDENT)
    (c,) = _correspondre(mini, tmp_path, "Betamark Lyon, France IG 100 %")
    assert (c.raison, c.siren, c.porteurs) == (HOMONYMES, None, 3)


def test_titre_de_section_au_format_lvmh_ne_devient_pas_le_nom(tmp_path: Path):
    mini = _mini()
    mini.societe(siren(10), "VINS ET SPIRITUEUX", commune="LILLE")
    a = mini.societe(siren(11), "ALPHAMARK")
    (c,) = _correspondre(mini, tmp_path, "Vins et Spiritueux\nAlphamark Épernay, France IG 66 %")
    assert (c.raison, c.siren, c.nom) == (UNIQUE, a, "Alphamark")


def test_nom_raccourci_par_la_ville_exige_la_commune(tmp_path: Path):
    mini = _mini()
    mini.societe(siren(10), "ALPHAMARK", commune="PARIS 8")
    (c,) = _correspondre(mini, tmp_path, "Alphamark Parfums Cosmetiques Paris, France IG 100 %")
    assert (c.raison, c.siren) == (INTROUVABLE, None)


def test_nom_coupe_retenu_si_le_siege_est_dans_la_ville(tmp_path: Path):
    mini = _mini()
    long = mini.societe(siren(10), "COMPAGNIE INVENTEE DU CHAMPAGNE", commune="EPERNAY")
    (c,) = _correspondre(mini, tmp_path, "Compagnie Inventée du\nChampagne\nÉpernay, France IG 66 %")
    assert (c.raison, c.siren) == (COMMUNE, long)


def test_nom_coupe_refuse_si_le_siege_est_ailleurs(tmp_path: Path):
    mini = _mini()
    mini.societe(siren(10), "COMPAGNIE INVENTEE DU CHAMPAGNE", commune="REIMS")
    (c,) = _correspondre(mini, tmp_path, "Compagnie Inventée du\nChampagne\nÉpernay, France IG 66 %")
    assert (c.raison, c.siren) == (INTROUVABLE, None)


def test_une_mise_en_equivalence_ne_departage_pas(tmp_path: Path):
    mini = _mini()
    omega = mini.societe(siren(10), "OMEGAMARK")
    z1 = mini.societe(siren(11), "ZETAMARK")
    mini.societe(siren(12), "ZETAMARK")
    mini.lien(omega, z1, PRESIDENT)
    texte = "Omegamark France 40,00 Mise en équivalence\n" + _vinci("Zetamark")
    resultats = _correspondre(mini, tmp_path, texte)
    assert [(c.raison, c.siren) for c in resultats] == [(UNIQUE, omega), (HOMONYMES, None)]


def test_meme_siren_pour_deux_noms_differents_conflit():
    ligne = LignePerimetre((), "IG", 100.0, "ligne inventée")
    a = Correspondance(ligne, UNIQUE, siren(10), "Alphamark", 1)
    b = Correspondance(ligne, COMMUNE, siren(10), "Alphamark Services", 2)
    c = Correspondance(ligne, UNIQUE, siren(11), "Betamark", 1)
    assert [(x.raison, x.siren) for x in _conflits([a, b, c])] == [
        (CONFLIT, None),
        (CONFLIT, None),
        (UNIQUE, siren(11)),
    ]


def test_meme_siren_pour_le_meme_nom_garde():
    mini_lignes = [
        Correspondance(LignePerimetre((), "IG", 100.0, "x"), UNIQUE, siren(10), n, 1)
        for n in ("Alphamark SAS", "Alphamark")
    ]
    assert [c.raison for c in _conflits(mini_lignes)] == [UNIQUE, UNIQUE]
