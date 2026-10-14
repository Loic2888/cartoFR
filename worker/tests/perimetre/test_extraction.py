"""Extraction d'un périmètre publié (T042 C1) : formats VINCI et LVMH, sur des textes inventés.

Aucun document réel n'est copié ici (règle produit 6) : les lignes reprennent seulement la forme
des listes mesurées le 2026-10-14, avec des noms inventés.
"""

import time
from pathlib import Path

import pytest

from cartofr.perimetre import Candidat, extraction, extraire, texte_document


def test_format_vinci_france():
    (ligne,) = extraire("Alphamark Services France 100,00 Intégration globale")
    assert ligne.candidats == (Candidat("Alphamark Services", None),)
    assert ligne.methode == "IG"
    assert ligne.taux == 100.0
    assert ligne.texte == "Alphamark Services France 100,00 Intégration globale"


def test_format_vinci_mise_en_equivalence_et_taux_decimal():
    (ligne,) = extraire("Deltamark France 49,50 Mise en équivalence")
    assert ligne.methode == "MEE"
    assert ligne.taux == 49.5


def test_format_vinci_etranger_ignore():
    assert extraire("Alphamark GmbH Allemagne 100,00 Intégration globale") == []
    assert extraire("Alphamark Holding, S.A. République Dominicaine 100,00 Intégration globale") == []


def test_format_vinci_outre_mer_garde_et_nom_qui_contient_le_territoire():
    (ligne,) = extraire("Betamark Guadeloupe Guadeloupe, France 100,00 Intégration globale")
    assert ligne.candidats == (Candidat("Betamark Guadeloupe", None),)


def test_format_vinci_titre_avant_la_ligne_le_nom_recolle_dabord():
    (ligne,) = extraire("POLE INVENTE\nGammamark France 100,00 Intégration globale")
    assert ligne.candidats == (Candidat("POLE INVENTE Gammamark", None), Candidat("Gammamark", None))


def test_au_plus_deux_lignes_davant_et_numero_de_page_ignore():
    texte = "Comptes inventés\nNote inventée\n67\nTITRE INVENTE\nGammamark France 100,00 Intégration globale"
    (ligne,) = extraire(texte)
    assert [c.nom for c in ligne.candidats] == [
        "Note inventée TITRE INVENTE Gammamark",
        "TITRE INVENTE Gammamark",
        "Gammamark",
    ]


def test_une_ligne_etrangere_termine_le_nom_en_cours():
    texte = (
        "TITRE INVENTE\n"
        "Alphamark GmbH Allemagne 100,00 Intégration globale\n"
        "Betamark France 100,00 Intégration globale"
    )
    (ligne,) = extraire(texte)
    assert ligne.candidats == (Candidat("Betamark", None),)


def test_format_lvmh_ville_de_plusieurs_mots_exige_la_commune():
    (ligne,) = extraire("Alphamark Vins Épernay, France IG 66 %")
    assert ligne.candidats == (
        Candidat("Alphamark Vins", "Épernay"),
        Candidat("Alphamark", "Vins Épernay", commune_exigee=True),
    )
    assert ligne.methode == "IG"
    assert ligne.taux == 66.0


def test_format_lvmh_titre_de_section_exige_la_commune():
    (ligne,) = extraire("Vins et Spiritueux\nAlphamark Épernay, France IG 66 %")
    assert ligne.candidats == (
        Candidat("Vins et Spiritueux Alphamark", "Épernay", commune_exigee=True),
        Candidat("Vins et Spiritueux", "Alphamark Épernay", commune_exigee=True),
        Candidat("Alphamark", "Épernay"),
    )


def test_format_lvmh_nom_coupe_sur_deux_lignes():
    texte = "Compagnie Inventée \ndu Champagne Fictif\nÉpernay, France IG 66 %"
    (ligne,) = extraire(texte)
    assert ligne.candidats[0] == Candidat(
        "Compagnie Inventée du Champagne Fictif", "Épernay", commune_exigee=True
    )
    assert ligne.texte == "Épernay, France IG 66 %"


def test_format_lvmh_etranger_ignore_et_termine_le_nom():
    texte = "TITRE INVENTE\nAlphamark UK Londres, Royaume-Uni IG 66 %\nBetamark Paris, France MEE 40 %"
    (ligne,) = extraire(texte)
    assert ligne.candidats == (Candidat("Betamark", "Paris"),)
    assert ligne.methode == "MEE"


def test_format_lvmh_outre_mer():
    (ligne,) = extraire("Deltamark Antilles Fort-de-France, Martinique IG 100 %")
    assert ligne.candidats[0] == Candidat("Deltamark Antilles", "Fort-de-France")


def test_tiret_espace_insecables_et_caracteres_invisibles():
    (ligne,) = extraire("Epsilonmark Gyé‑sur‑Seine, France IG 66 %​")
    assert ligne.candidats[0] == Candidat("Epsilonmark", "Gyé-sur-Seine")


def test_texte_sans_societe():
    assert extraire("") == []
    assert extraire("LISTE DES SOCIÉTÉS CONSOLIDÉES\nSociétés Siège social Méthode") == []


def test_texte_document_html(tmp_path: Path):
    page = tmp_path / "perimetre.html"
    page.write_text(
        "<html><style>p{}</style><table><tr><td>Alphamark</td><td>France</td><td>100,00</td>"
        "<td>Intégration globale</td></tr><tr><td>B&eacute;tamark</td><td>France</td><td>100,00</td>"
        "<td>Intégration globale</td></tr></table></html>",
        encoding="utf-8",
    )
    lignes = extraire(texte_document(page))
    assert [li.candidats[-1].nom for li in lignes] == ["Alphamark", "Bétamark"]


def test_texte_document_html_mal_forme_reste_rapide(tmp_path: Path):
    page = tmp_path / "perimetre.html"
    page.write_text("<html>" + "<script>" * 50_000 + "fin", encoding="utf-8")
    debut = time.monotonic()
    assert extraire(texte_document(page)) == []
    assert time.monotonic() - debut < 2


def test_texte_document_texte(tmp_path: Path):
    fichier = tmp_path / "perimetre.txt"
    fichier.write_text("Alphamark France 100,00 Intégration globale\n", encoding="utf-8")
    assert len(extraire(texte_document(fichier))) == 1


def test_texte_document_trop_gros(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fichier = tmp_path / "perimetre.txt"
    fichier.write_text("Alphamark France 100,00 Intégration globale\n", encoding="utf-8")
    monkeypatch.setattr(extraction, "TAILLE_MAX", 10)
    with pytest.raises(ValueError, match="dépasse 50 Mo"):
        texte_document(fichier)
