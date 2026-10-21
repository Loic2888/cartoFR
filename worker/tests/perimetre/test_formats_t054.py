"""Formats de liste ajoutés le 2026-10-21 (T054) et limite de taille d'un paquet ESEF.

Lignes reprises de la forme des documents du CAC 40 (Engie, TotalEnergies, Carrefour, Société
Générale, Crédit Agricole S.A., BNP Paribas, Airbus, Eurofins, Euronext, STMicroelectronics), avec des
noms inventés (règle produit 6).
"""

import zipfile
from pathlib import Path

import pytest

from cartofr.perimetre import extraction as module
from cartofr.perimetre.extraction import LignePerimetre, extraire, texte_document
from cartofr.perimetre.pays import est_pays, francais


def _noms(lignes: list[LignePerimetre]) -> list[str]:
    return [li.candidats[0].nom for li in lignes]


# --- Pays en titre ------------------------------------------------------------------------------


def test_pays_et_zones_reconnus_tout_entiers():
    assert est_pays("Afrique Du Sud") and est_pays("ALLEMAGNE") and est_pays("Asie-Pacifique")
    assert est_pays("Emirats Arabes Unis") and est_pays("Étranger")
    assert francais("FRANCE") and francais("La Réunion") and not francais("Belgique")
    assert not est_pays("CA VERSICHERUNGSSERVICE") and not est_pays("France Inventée SAS")


# --- Engie : le format VINCI, taux sans deux décimales -----------------------------------------


def test_engie_taux_entier_ou_a_cinq_decimales():
    lignes = extraire(
        "Alpha Inventée France 100 Intégration globale\n"
        "Beta Inventée France 20,89161 Mise en équivalence\n"
        "Gamma Inventée LLC Etats-Unis d'Amérique 100 Intégration globale\n"
    )
    assert [(li.candidats[-1].nom, li.methode, li.taux) for li in lignes] == [
        ("Alpha Inventée", "IG", 100.0),
        ("Beta Inventée", "MEE", 20.89161),
    ]


# --- Tableaux : TotalEnergies, Carrefour, Bureau Veritas, STMicroelectronics ---------------------


def _cellule(texte: str) -> str:
    return f"\n  <td>\n    <div><p>\n      {texte}\n    </p></div>\n  </td>\n  "


def _rangee(*cellules: str) -> str:
    return "<tr>" + "".join(_cellule(c) for c in cellules) + "</tr>\n"


def test_rapport_indente_une_rangee_par_ligne_pays_du_siege_d_abord(tmp_path: Path):
    """TotalEnergies : secteur | nom | % | méthode | pays du siège | pays d'opération."""
    page = tmp_path / "deu.xhtml"
    page.write_text(
        "<html><body><table>"
        + _rangee("Exploration-Production")
        + _rangee("", "Alpha Inventée SAS", "100,00%", "", "France", "France")
        + _rangee("", "Beta Inventée", "40,00%", "E", "France", "France")
        + _rangee("", "Gamma Inventée GmbH", "100,00%", "", "Allemagne", "France")
        + "</table></body></html>",
        encoding="utf-8",
    )
    lignes = extraire(texte_document(page))
    assert [(n, li.methode, li.taux) for n, li in zip(_noms(lignes), lignes, strict=True)] == [
        ("Alpha Inventée SAS", "inconnue", 100.0),
        ("Beta Inventée", "MEE", 40.0),
    ]
    assert lignes[0].controlee and not lignes[1].controlee


def test_page_html_lue_en_rangees(tmp_path: Path):
    page = tmp_path / "liste.html"
    page.write_text(
        "<html><table>" + _rangee("Alpha Inventée", "France", "IG", "62") + "</table></html>",
        encoding="utf-8",
    )
    (ligne,) = extraire(texte_document(page))
    assert (ligne.candidats[0].nom, ligne.methode, ligne.taux) == ("Alpha Inventée", "IG", 62.0)


def test_titre_de_section_de_tableau_carrefour():
    lignes = extraire(
        "FRANCE | Pourcentage d'intérêts retenus en consolidation\n"
        "ALPHA INVENTEE | 100\n"
        "BETA INVENTEE | 50\n"
        "TOTAL | 3 147 | 100\n"
        "ESPAGNE | Pourcentage d'intérêts retenus en consolidation\n"
        "GAMMA INVENTEE SA | 100\n"
    )
    assert _noms(lignes) == ["ALPHA INVENTEE", "BETA INVENTEE"]
    assert lignes[0].controlee and not lignes[1].controlee  # 50 % sans méthode : pas le contrôle


def test_section_de_tableau_fermee_par_un_paragraphe_ou_un_autre_tableau():
    paragraphe = (
        "Le chiffre d'affaires du groupe progresse en France, porté par l'alimentaire et la proximité"
    )
    assert extraire(f"FRANCE | Pourcentage\nALPHA INVENTEE | 100\n{paragraphe}\nEffectif | 45\n") == extraire(
        "FRANCE | Pourcentage\nALPHA INVENTEE | 100\n"
    )
    # Un tableau d'une autre largeur ne se lit pas sous le titre.
    assert _noms(extraire("FRANCE | Pourcentage\nEffectif | 45 | 50 | 12\n")) == []


def test_tableau_de_sites_sans_methode_ni_decimales_non_lu():
    """Hermès : « Cristallerie | France | 2 » est un nombre de sites, pas un taux."""
    assert extraire("Cristallerie | France | 2\nVerrerie | Italie | 3\n") == []
    assert _noms(extraire("Alpha Inventée | France | 100 | 100\nZeta Inventée | Italie | 100 | 100\n")) == [
        "Alpha Inventée"
    ]
    assert _noms(extraire("Beta Inventée | France | 99,98\nZeta Inventée | Italie | 99,98\n")) == [
        "Beta Inventée"
    ]


def test_pays_avant_le_nom_et_pays_avec_la_ville():
    lignes = extraire(
        "France | Alpha Inventée SAS | F | 100,0 | 100,0\n"
        "Belgique | Delta Inventée SA | F | 100,0 | 100,0\n"
        "France, Crolles | Beta Inventée (Crolles 2) SAS | 100\n"
        "Italie, Agrate | Gamma Inventée Srl | 100\n"
    )
    assert _noms(lignes) == ["Alpha Inventée SAS", "Beta Inventée (Crolles 2) SAS"]


def test_rangee_financiere_succursale_et_nom_vide_non_lus():
    assert extraire("Alpha Inventée | France | 1 995 | 99,6\n") == []  # un montant
    assert extraire("Alpha Inventée | France | 10 | 20 | 30 | 40 | 50\n") == []  # plus de 4 taux
    assert extraire("Alpha Inventée succursale de Milan | France | IG | 100\n") == []
    assert extraire("# | France | IG | 57,80\n") == []
    assert _noms(extraire("AS 24 | 100,00 |  | France | France\nZZ 9 | 100,00 |  | Italie | Italie\n")) == [
        "AS 24"
    ]


def test_societe_sortie_colonnes_de_l_exercice_vides():
    assert extraire("Sortie Inventée | France |  |  |  | 100 | 98 | IG") == []
    # Stellantis : des colonnes vides de mise en page, une à la fois.
    stellantis = (
        "Alpha Inventée S.A.S. |  | France |  | 100.00\nZeta Inventée S.p.A. |  | Italie |  | 100.00\n"
    )
    assert _noms(extraire(stellantis)) == ["Alpha Inventée S.A.S."]


def test_rangee_d_un_tableau_esef_d_avant_inchangee():
    (ligne,) = extraire("Alpha Inventée | France | 100 | 98 | IG | 100 | 98 | IG")
    assert (ligne.taux, ligne.methode) == (98.0, "IG")  # le % d'intérêt, pas le % de contrôle


# --- Société Générale : pays en titre, activité en minuscules ------------------------------------

SG = """Pays Activités Méthode*
Allemagne
  ALPHA INVENTEE GMBH Services de mobilité et leasing IG 54,81 100
France
  29 BETA INVENTEE EQUILIBRE Assurances IG 87,1 87,1
  908 GAMMA INVENTEE Banque de détail en France et Banque
privée MEP 50 50
(1)(6) DELTA INVENTEE SAS Financement et Conseil IG 100 100
(1)  EPSILON INVENTEE SUCCURSALE EN ESPANA Banque de détail en France et Banque
privée IG 96,24 100
Italie
  ZETA INVENTEE SPA Financement et Conseil IG 100 100
"""


def test_societe_generale():
    lignes = extraire(SG)
    assert [(n, li.methode, li.taux) for n, li in zip(_noms(lignes), lignes, strict=True)] == [
        ("29 BETA INVENTEE EQUILIBRE", "IG", 87.1),
        ("908 GAMMA INVENTEE", "MEE", 50.0),
        ("DELTA INVENTEE SAS", "IG", 100.0),
    ]
    # La preuve : la rangée qui porte le nom, sans ligne d'avant de trop.
    assert lignes[1].texte == "908 GAMMA INVENTEE Banque de détail en France et Banque privée MEP 50 50"


def test_societe_generale_suite_de_ligne_jamais_candidate_seule():
    (ligne,) = extraire("France\nOMEGA INVENTEE Banque de détail en France et Banque\nprivée IG 55 80\n")
    assert [c.nom for c in ligne.candidats] == ["OMEGA INVENTEE"]


def test_ligne_de_societe_hors_d_une_section_france_non_lue():
    assert extraire("ALPHA INVENTEE Assurances IG 100 100\n") == []


# --- Crédit Agricole S.A. : symbole de méthode, fin de rangée coupée ----------------------------

CASA = """ALLEMAGNE
ALPHA INVENTEE GMBH ■ - F SFS 100,0 100,0 100,0 100,0
FRANCE
BETA INVENTEE ■ - ESC GEA 100,0 100,0 66,9 67,2
GAMMA INVENTEE 3DEC (1) ■ -
ESC GEA 99,6 99,5 99,6 99,5
DELTA INVENTEE
(FMU) (1) ■ E3
ESC GEA 46,3 - 46,3 -
EPSILON INVENTEE ▲ S4 Co-E AHM - 50,0 - 35,2
ZETA PARTICIPATIONS INVENTEES X - EA GEA 24,5 24,5 24,5 24,5
"""


def test_credit_agricole_sa():
    lignes = extraire(CASA)
    assert [(n, li.methode, li.taux) for n, li in zip(_noms(lignes), lignes, strict=True)] == [
        ("BETA INVENTEE", "IG", 66.9),
        ("GAMMA INVENTEE 3DEC", "IG", 99.6),
        ("DELTA INVENTEE (FMU)", "IG", 46.3),
        ("ZETA PARTICIPATIONS INVENTEES", "autre", 24.5),
    ]
    # « (FMU) » seul, la fin d'un nom coupé, n'est jamais candidat. EPSILON est sortie (« - »).
    assert [c.nom for c in lignes[2].candidats] == ["DELTA INVENTEE (FMU)"]


# --- Pays sur la ligne : BNP Paribas, Airbus, Eurofins, Euronext ---------------------------------


def test_bnp_paribas():
    lignes = extraire(
        " Alpha Inventée Finance France IG(1) 100,0% 100,0%  IG(1) 100,0% 100,0%\n"
        " Beta Inventée  France ME 22,4% 22,4% V4 ME 22,0% 22,0%\n"
        " Gamma Fonds Inventés France IG(4) - -  IG(4) - -\n"
        " Delta Inventée (succ. Allemagne) Allemagne IG 100,0% 100,0%  IG 100,0% 100,0%\n"
    )
    assert [(n, li.methode, li.taux) for n, li in zip(_noms(lignes), lignes, strict=True)] == [
        ("Alpha Inventée Finance", "IG", 100.0),
        ("Beta Inventée", "MEE", 22.4),
    ]


def test_airbus():
    lignes = extraire("E 38.69 Alpha Inventée Holding France\nF 100.00 Beta Inventée SAS France\n"
                      "F 100.00 Gamma Inventée GmbH Germany\n")  # fmt: skip
    assert [(n, li.methode, li.taux) for n, li in zip(_noms(lignes), lignes, strict=True)] == [
        ("Alpha Inventée Holding", "MEE", 38.69),
        ("Beta Inventée SAS", "IG", 100.0),
    ]


def test_eurofins_mere_directe_coupee_sur_deux_lignes():
    lignes = extraire(
        "Alpha Inventée SAS FR Eurofins Inventée Holding France SAS 100.0% 09/25\n"
        "Beta Inventée SASU FR Eurofins Inventée Prélèvement France\n"
        "Holding SAS 100,0% 09/25\n"
        "Gamma Inventée GmbH DE Eurofins Inventée GmbH 100.0% 09/25\n"
    )
    assert _noms(lignes) == ["Alpha Inventée SAS", "Beta Inventée SASU"]
    assert lignes[1].controlee  # méthode non publiée, 100 % : le contrôle


def test_euronext():
    lignes = extraire("Alpha Inventée S.A. France 100.00% 100.00%\nBeta Inventée Srl Italy 100.00% 100.00%\n")
    assert _noms(lignes) == ["Alpha Inventée S.A."]


# --- Ordre des formats --------------------------------------------------------------------------


def test_formats_t054_seulement_si_les_anciens_ne_lisent_rien():
    texte = "Alpha Inventée France 100,00 Intégration globale\nFrance\nBETA INVENTEE Assurances IG 100 100\n"
    assert _noms(extraire(texte)) == ["Alpha Inventée"]


# --- Limite de taille ---------------------------------------------------------------------------


def _paquet(chemin: Path, xhtml: str) -> Path:
    with zipfile.ZipFile(chemin, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("groupe-2025-12-31-fr/reports/groupe-2025-12-31-fr.xhtml", xhtml)
    return chemin


def test_paquet_esef_de_plus_de_50_mo_accepte_jusqu_a_300(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    paquet = _paquet(tmp_path / "deu.zip", "<html><table>" + _rangee("Alpha Inventée", "France", "IG", "62"))
    monkeypatch.setattr(module, "TAILLE_MAX", 10)  # le paquet dépasse la limite d'un document ordinaire
    assert _noms(extraire(texte_document(paquet))) == ["Alpha Inventée"]
    monkeypatch.setattr(module, "TAILLE_MAX_ESEF", 10)
    with pytest.raises(ValueError, match="300 Mo"):
        texte_document(paquet)


def test_pdf_de_plus_de_50_mo_toujours_refuse(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fichier = tmp_path / "liste.pdf"
    fichier.write_bytes(b"%PDF-1.4 invente")
    monkeypatch.setattr(module, "TAILLE_MAX", 10)
    with pytest.raises(ValueError, match="dépasse 50 Mo"):
        texte_document(fichier)


# --- Revue adverse du 2026-10-21 ----------------------------------------------------------------


def test_airbus_methode_et_taux_de_la_ligne_meme():
    """La rangée la plus longue prenait « F 100.00 » sur la ligne d'avant, une autre société."""
    lignes = extraire("F 84.62 Alpha Inventée GmbH Germany\nE 38.69 Beta Inventée Holding France\n")
    assert [(li.candidats[0].nom, li.methode, li.taux) for li in lignes] == [
        ("Beta Inventée Holding", "MEE", 38.69)
    ]
    assert not lignes[0].controlee


def test_bout_de_nom_coupe_de_secours_et_jamais_un_mot_seul():
    """« BONDS » seul, la fin d'un nom de fonds coupé, retrouvait une autre société (revue T054)."""
    (fonds,) = extraire("FRANCE\nALPHA INVENTEE CREDIT GREEN\nBONDS (1) ■ - ESC GEA 100,0 100,0 84,9 84,9\n")
    assert [c.nom for c in fonds.candidats] == ["ALPHA INVENTEE CREDIT GREEN BONDS"]
    (deux,) = extraire("FRANCE\nALPHA INVENTEE\nBETA GAMMA (1) ■ - ESC GEA 100,0 100,0 84,9 84,9\n")
    assert [(c.nom, c.secours) for c in deux.candidats] == [
        ("ALPHA INVENTEE BETA GAMMA", False),
        ("BETA GAMMA", True),
    ]


@pytest.mark.parametrize(
    "texte",
    [
        "Effectifs France 62,3% 60,1%\n",
        "Répartition des effectifs | France | 55 | 54\n",
        "Répartition des effectifs | France | 55 | 54\nAutres | Europe | 45 | 46\n",
        "Indicateur | France | Europe | Asie\nTaux de satisfaction | 85 | 87 | 80\n",
        "France | 2025 | 2024\nTaux de marge brute | 75 | 74\n",
    ],
)
def test_tableaux_de_chiffres_jamais_lus_comme_des_societes(texte: str):
    assert extraire(texte) == []


def test_page_html_au_format_lvmh_toujours_lue(tmp_path: Path):
    page = tmp_path / "liste.html"
    page.write_text(
        "<html><table><tr><td>Alphamark SAS Paris, France</td><td>IG</td><td>66 %</td></tr></table></html>",
        encoding="utf-8",
    )
    (ligne,) = extraire(texte_document(page))
    assert (ligne.methode, ligne.taux) == ("IG", 66.0)


def test_longue_ligne_pleine_de_fr_reste_rapide():
    import time

    debut = time.monotonic()
    extraire(("mot FR " * 14_000 + "\n") * 3)
    assert time.monotonic() - debut < 2


def test_methode_non_publiee_en_clair_dans_la_preuve():
    from cartofr.moteur.moteur import methode

    (ligne,) = extraire("Alpha Inventée S.A. France 100.00% 100.00%\n")
    assert methode(ligne) == "méthode non publiée"
