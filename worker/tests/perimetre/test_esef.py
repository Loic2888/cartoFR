"""Périmètre publié au format ESEF (T049) : le tableau de la note de périmètre d'un DEU, lu dans un
paquet zip, puis retrouvé dans le registre, sigles de SIRENE compris.

Aucun document réel n'est copié ici (règle produit 6) : le rapport xhtml reprend seulement la forme
de la note 3 du DEU de CMAF mesurée le 2026-10-20, avec des noms et SIREN inventés.
"""

import sys
import zipfile
from pathlib import Path

import duckdb
import pytest

from cartofr.perimetre import Candidat, correspondre, extraire, passage_federations, texte_document
from cartofr.perimetre import extraction as module
from cartofr.perimetre.correspondance import HOMONYMES, INTROUVABLE, REGISTRE, UNIQUE
from cartofr.perimetre.deposer import Demande, DepotInvalide, deposer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "moteur"))
from fabrique import PRESIDENT, MiniRegistre, siren  # noqa: E402  # pyright: ignore[reportMissingImports]

TETE = siren(1)


def _cellule(texte: str) -> str:
    # Comme le rapport ESEF : chaque ligne d'une cellule dans ses propres blocs.
    return (
        "<td>"
        + "".join(f'<div><div><span class="f">{t}</span></div></div>' for t in texte.split("\n"))
        + "</td>"
    )


def _rangee(*cellules: str) -> str:
    return "<tr>" + "".join(_cellule(c) for c in cellules) + "</tr>"


def _xhtml(*rangees: str, avant: str = "") -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml"><body>'
        f"<div><p>{avant}</p></div><table>{''.join(rangees)}</table></body></html>"
    )


ENTETE = _rangee("", "Pays", "Pourcentage\nContrôle", "Pourcentage\nIntérêt", "Méthode*")
DOCUMENT = _xhtml(
    ENTETE,
    _rangee("A. RÉSEAU BANCAIRE"),
    _rangee("Banque Inventée de l'Ouest (BIO)", "France", "100", "98", "IG", "100", "98", "IG"),
    _rangee("Caisse Inventée Nord", "France", "100", "98", "IG", "100", "98", "IG"),
    _rangee("Groupe des Assurances\nInventées (GAI)", "France", "89", "88", "IG", "90", "88", "IG"),
    _rangee("Filiale Inventée GmbH", "Allemagne", "100", "98", "IG", "100", "98", "IG"),
    _rangee("Banque Inventée Monaco (succursale\nde BIO)", "France", "100", "98", "IG", "100", "98", "IG"),
    _rangee("Partenaire Inventé", "France", "50", "45", "ME", "50", "45", "ME"),
    _rangee("Ancienne Inventée", "France", "", "", "", "100", "98", "IG"),
    _rangee("Absorbée Inventée", "France", "100", "98", "FU", "100", "98", "IG"),
    _rangee("Petite Inventée", "France", "100", "60", "NC", "100", "60", "NC"),
    _rangee("Antilles Inventées", "Martinique", "100", "98", "IG", "100", "98", "IG"),
    avant=(
        "Les entités qui la composent sont : la Caisse fédérale ; les Fédérations du Crédit Mutuel"
        " Centre Inventé (FCMCI), du Sud-Est (FCMSE) et d’Antilles-Guyane (FCMAG) ; les caisses."
    ),
)


def _paquet(
    chemin: Path, xhtml: str, nom: str = "groupe-2025-12-31-fr/reports/groupe-2025-12-31-fr.xhtml"
) -> Path:
    with zipfile.ZipFile(chemin, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(nom, xhtml)
        z.writestr("groupe-2025-12-31-fr/META-INF/reportPackage.json", "{}")
    return chemin


# --- Lecture du paquet --------------------------------------------------------------------------


def test_une_ligne_par_rangee_cellules_separees(tmp_path: Path):
    texte = texte_document(_paquet(tmp_path / "deu.zip", DOCUMENT))
    lignes = {" ".join(ligne.split()) for ligne in texte.splitlines()}
    assert "Banque Inventée de l'Ouest (BIO) | France | 100 | 98 | IG | 100 | 98 | IG" in lignes
    # Un nom sur deux blocs d'une même cellule est recollé.
    assert "Groupe des Assurances Inventées (GAI) | France | 89 | 88 | IG | 90 | 88 | IG" in lignes


def test_xhtml_seul_lu_comme_un_paquet(tmp_path: Path):
    chemin = tmp_path / "deu.xhtml"
    chemin.write_text(DOCUMENT, encoding="utf-8")
    assert len(extraire(texte_document(chemin))) == 6


def test_lignes_du_tableau(tmp_path: Path):
    lignes = extraire(texte_document(_paquet(tmp_path / "deu.zip", DOCUMENT)))
    noms = [li.candidats[0].nom for li in lignes]
    # Étrangère, succursale, sortie (exercice vide) et fusionnée ne sont pas lues ; l'outre-mer l'est.
    assert noms == [
        "Banque Inventée de l'Ouest (BIO)", "Caisse Inventée Nord", "Groupe des Assurances Inventées (GAI)",
        "Partenaire Inventé", "Petite Inventée", "Antilles Inventées",
    ]  # fmt: skip
    par_nom = dict(zip(noms, lignes, strict=True))
    # Le taux est celui d'intérêt, la méthode celle de l'exercice, pas celle d'avant.
    assert (
        par_nom["Groupe des Assurances Inventées (GAI)"].taux,
        par_nom["Groupe des Assurances Inventées (GAI)"].methode,
    ) == (88.0, "IG")
    assert par_nom["Partenaire Inventé"].methode == "MEE" and not par_nom["Partenaire Inventé"].controlee
    assert par_nom["Petite Inventée"].methode == "NC" and par_nom["Petite Inventée"].controlee  # 60 % > 50 %
    assert (
        par_nom["Caisse Inventée Nord"].texte
        == "Caisse Inventée Nord | France | 100 | 98 | IG | 100 | 98 | IG"
    )


def test_candidats_sans_sigle_puis_sigles_de_secours(tmp_path: Path):
    (bio, nord, *_) = extraire(texte_document(_paquet(tmp_path / "deu.zip", DOCUMENT)))
    assert bio.candidats == (
        Candidat("Banque Inventée de l'Ouest (BIO)", None),
        Candidat("Banque Inventée de l'Ouest", None),
        Candidat("Banque Inventée de l'Ouest", None, secours=True, sigle=True),
        Candidat("BIO", None, secours=True, sigle=True),
    )
    assert nord.candidats == (
        Candidat("Caisse Inventée Nord", None),
        Candidat("Caisse Inventée Nord", None, secours=True, sigle=True),
    )


def test_forme_juridique_en_toutes_lettres():
    (ligne,) = extraire("Inventée Vie, Société d’Assurance Mutuelle | France | 100 | 100 | IG")
    assert ligne.candidats == (
        Candidat("Inventée Vie, Société d’Assurance Mutuelle", None),
        Candidat("Inventée Vie", None),
        Candidat("Inventée Vie, Société d’Assurance Mutuelle", None, secours=True, sigle=True),
        Candidat("Inventée Vie SAM", None, secours=True, sigle=True),
    )


def test_forme_en_toutes_lettres_retrouvee_par_le_sigle(tmp_path: Path):
    mini = _mini()
    mini.societe(siren(9), "ASSURANCES INVENTEES VIE", sigle="INVENTEE VIE SAM")
    (c,) = _correspondre(mini, tmp_path, _ig("Inventée Vie, Société d'Assurance Mutuelle"))
    assert (c.raison, c.siren) == (UNIQUE, siren(9))


def test_rangee_avec_cellule_vide_en_tete_appel_de_note_et_pourcentage():
    (ligne,) = extraire("| Société Inventée | France | 100 % | 98 % | IG (1) | 100 | 98 | IG")
    assert (ligne.candidats[0].nom, ligne.taux, ligne.methode) == ("Société Inventée", 98.0, "IG")
    # La preuve garde la ligne telle que lue.
    assert ligne.texte == "| Société Inventée | France | 100 % | 98 % | IG (1) | 100 | 98 | IG"


def test_societe_sortie_colonnes_vides_au_milieu_non_lue():
    assert extraire("Sortie Inventée | France |  |  |  | 100 | 98 | IG") == []


def test_xhtml_seul_au_dela_de_50_mo_accepte_jusqu_a_la_limite_esef(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    chemin = tmp_path / "deu.xhtml"
    chemin.write_text(DOCUMENT, encoding="utf-8")
    monkeypatch.setattr(module, "TAILLE_MAX", 10)
    assert len(extraire(texte_document(chemin))) == 6
    monkeypatch.setattr(module, "TAILLE_MAX_ESEF", 10)
    with pytest.raises(ValueError, match="300 Mo"):
        texte_document(chemin)


def test_methode_de_compression_inconnue_refusee_en_francais(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    def inconnue(*_: object, **__: object) -> None:
        raise NotImplementedError("compression type 9 (deflate64)")

    paquet = _paquet(tmp_path / "deu.zip", DOCUMENT)
    monkeypatch.setattr(module.zipfile.ZipFile, "open", inconnue)
    with pytest.raises(ValueError, match="compressée d'une façon inconnue"):
        texte_document(paquet)


def test_sigle_trop_court_jamais_essaye():
    (ligne,) = extraire("CIC Lyonnaise Inventée (LB) | France | 100 | 98 | IG")
    assert [c.nom for c in ligne.candidats if c.sigle] == ["CIC Lyonnaise Inventée"]


def test_passage_des_federations(tmp_path: Path):
    texte = texte_document(_paquet(tmp_path / "deu.zip", DOCUMENT))
    assert (
        passage_federations(texte)
        == "Centre Inventé (FCMCI), du Sud-Est (FCMSE) et d’Antilles-Guyane (FCMAG)"
    )
    assert passage_federations("Aucune liste ici.") == ""


def test_formats_vinci_et_lvmh_inchanges():
    # Une ligne VINCI ou LVMH n'a jamais de candidat cherché parmi les sigles.
    lignes = extraire("Alphamark (AM) France 100,00 Intégration globale\nMHCS Épernay, France IG 66 %")
    assert lignes and not any(c.sigle for li in lignes for c in li.candidats)


def test_paquet_sans_rapport_ou_abime_refuse(tmp_path: Path):
    with pytest.raises(ValueError, match="rapport unique"):
        texte_document(_paquet(tmp_path / "vide.zip", DOCUMENT, nom="groupe/autre/x.xhtml"))
    abime = tmp_path / "abime.zip"
    abime.write_bytes(b"PK\x03\x04pas un zip")
    with pytest.raises(ValueError, match="abîmée"):
        texte_document(abime)


def test_rapport_trop_gros_une_fois_decompresse(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(module, "TAILLE_MAX_ESEF", 1000)
    with pytest.raises(ValueError, match="300 Mo"):
        texte_document(_paquet(tmp_path / "gros.zip", DOCUMENT + " " * 2000))


# --- Correspondance par les sigles --------------------------------------------------------------


def _mini() -> MiniRegistre:
    mini = MiniRegistre()
    mini.societe(TETE, "CAISSE FEDERALE INVENTEE")
    return mini


def _correspondre(mini: MiniRegistre, tmp_path: Path, *rangees: str):
    chemin = mini.ecrire(tmp_path / "r.duckdb")
    con = duckdb.connect(str(chemin), read_only=True)
    try:
        return correspondre(
            con, TETE, extraire(texte_document(_paquet(tmp_path / "d.zip", _xhtml(*rangees))))
        )
    finally:
        con.close()


def _ig(nom: str) -> str:
    return _rangee(nom, "France", "100", "98", "IG", "100", "98", "IG")


def test_nom_sans_son_sigle_entre_parentheses(tmp_path: Path):
    mini = _mini()
    mini.societe(siren(2), "BANQUE INVENTEE DE L'OUEST")
    (c,) = _correspondre(mini, tmp_path, _ig("Banque Inventée de l'Ouest (BIO)"))
    assert (c.raison, c.siren) == (UNIQUE, siren(2))


def test_nom_d_usage_retrouve_par_le_sigle_sirene(tmp_path: Path):
    mini = _mini()
    mini.societe(siren(3), "BANQUE INVENTEE NORD", sigle="CAISSE INVENTEE NORD")
    (c,) = _correspondre(mini, tmp_path, _ig("Caisse Inventée Nord"))
    assert (c.raison, c.siren, c.nom) == (UNIQUE, siren(3), "Caisse Inventée Nord")


def test_sigle_entre_parentheses_departage_par_le_registre(tmp_path: Path):
    mini = _mini()
    mini.societe(siren(4), "ASSURANCES INVENTEES DU GROUPE", sigle="GAI")
    mini.societe(siren(5), "AUTRE SOCIETE INVENTEE", sigle="GAI")
    mini.lien(TETE, siren(4), PRESIDENT)
    (c,) = _correspondre(mini, tmp_path, _ig("Groupe des Assurances Inventées (GAI)"))
    assert (c.raison, c.siren) == (REGISTRE, siren(4))


def test_sigle_d_homonymes_hors_du_groupe_non_retenu(tmp_path: Path):
    mini = _mini()
    mini.societe(siren(4), "ASSURANCES INVENTEES UNE", sigle="GAI")
    mini.societe(siren(5), "ASSURANCES INVENTEES DEUX", sigle="GAI")
    (c,) = _correspondre(mini, tmp_path, _ig("Groupe des Assurances Inventées (GAI)"))
    assert c.raison == HOMONYMES and c.siren is None


def test_denomination_avant_le_sigle(tmp_path: Path):
    # La dénomination unique décide ; le sigle d'une autre société n'est pas essayé.
    mini = _mini()
    mini.societe(siren(6), "CAISSE INVENTEE NORD")
    mini.societe(siren(7), "AUTRE INVENTEE", sigle="CAISSE INVENTEE NORD")
    (c,) = _correspondre(mini, tmp_path, _ig("Caisse Inventée Nord"))
    assert (c.raison, c.siren) == (UNIQUE, siren(6))


def test_sigle_d_une_ligne_vinci_jamais_lu(tmp_path: Path):
    mini = _mini()
    mini.societe(siren(8), "BANQUE INVENTEE", sigle="ALPHAMARK")
    chemin = mini.ecrire(tmp_path / "r.duckdb")
    con = duckdb.connect(str(chemin), read_only=True)
    try:
        (c,) = correspondre(con, TETE, extraire("Alphamark France 100,00 Intégration globale"))
    finally:
        con.close()
    assert c.raison == INTROUVABLE


# --- Dépôt --------------------------------------------------------------------------------------


def test_depot_d_un_paquet_esef(tmp_path: Path):
    data = tmp_path / "data"
    data.mkdir()
    mini = _mini()
    mini.societe(siren(2), "BANQUE INVENTEE DE L'OUEST")
    mini.ecrire(data / "registre.duckdb")
    (depot,) = deposer([Demande(TETE, _paquet(tmp_path / "deu.zip", DOCUMENT))], data)
    assert depot.fichier and depot.fichier.endswith(".zip") and (data / "perimetre" / depot.fichier).is_file()
    assert depot.retenues == 1


def test_depot_d_un_zip_abime_refuse(tmp_path: Path):
    data = tmp_path / "data"
    data.mkdir()
    _mini().ecrire(data / "registre.duckdb")
    abime = tmp_path / "abime.zip"
    abime.write_bytes(b"PK\x03\x04pas un zip")
    with pytest.raises(DepotInvalide, match="illisible"):
        deposer([Demande(TETE, abime)], data)
