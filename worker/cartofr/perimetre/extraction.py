"""Lire un document de périmètre et en tirer les sociétés situées en France (T042).

Deux formats de liste mesurés le 2026-10-14 :
- VINCI : « <nom> <pays> <taux> <méthode> », ex. « Cofiroute France 100,00 Intégration globale » ;
- LVMH : « <nom> <ville>, <pays> <méthode> <taux> % », ex. « MHCS Épernay, France IG 66 % ».

Le texte extrait d'un PDF coupe parfois un nom sur plusieurs lignes, et laisse des titres de pôle
ou de page juste avant une ligne. On ne sait pas trancher à coup sûr : une ligne rend donc plusieurs
noms candidats, et c'est la correspondance avec le registre qui choisit. Ordre des candidats :
- format VINCI : les lignes d'avant recollées d'abord, la ligne seule ensuite. Le nom contient
  toujours la ligne courante : un titre seul n'est jamais candidat ;
- format LVMH, où nom et ville ne sont pas séparés :
  1. les noms recollés aux lignes d'avant (la fin d'un nom coupé, ou un titre de section) ;
  2. la ligne seule, avec une ville d'un mot ;
  3. la ligne seule, avec une ville de 2 ou 3 mots.
  Les candidats 1 et 3 ne sont retenus que si le siège SIRENE est dans la ville du document
  (`commune_exigee`) : un titre de section ne passe donc pas, et « Alphamark Parfums Paris » ne
  finit pas en « Alphamark », le nom d'une autre société (revue du 2026-10-14). Limite : un nom
  coupé dont le siège n'est pas dans la ville du document se rabat sur la fin du nom, s'il
  existe seul dans SIRENE.

Usage :
    lignes = extraire(texte_document(Path("out/perimetre/vinci.pdf")))
Entrée : un PDF, une page HTML ou un texte.
Sortie : une `LignePerimetre` par société située en France ou en outre-mer.
"""

import logging
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

# Outre-mer présent dans SIRENE. La Nouvelle-Calédonie et la Polynésie ont leurs propres registres.
OUTRE_MER = (
    "Guadeloupe", "Martinique", "Guyane", "La Réunion", "Réunion", "Mayotte",
    "Saint-Martin", "Saint-Barthélemy", "Saint-Pierre-et-Miquelon",
)  # fmt: skip
METHODES_LONGUES = {
    "Intégration globale": "IG",
    "Mise en équivalence": "MEE",
    "Opération conjointe": "autre",
    "Intégration proportionnelle": "autre",
}
METHODES_COURTES = {"IG": "IG", "MEE": "MEE", "ME": "MEE", "IP": "autre", "JV": "autre"}
LIGNES_AVANT = 2  # lignes non terminées gardées pour recoller un nom coupé
TAILLE_MAX = 50 * 1024 * 1024  # un document de périmètre fait quelques Mo : au-delà, on refuse

_FR = r"(?:(?:" + "|".join(re.escape(o) for o in OUTRE_MER) + r"), )?France"
# Format VINCI. Seule la France est lue en détail : le nom d'un pays étranger peut avoir plusieurs mots.
_LONGUE = "|".join(METHODES_LONGUES)
_VINCI_FR = re.compile(rf"^(?P<avant>.+?) {_FR} (?P<taux>\d{{1,3}},\d{{2}}) (?P<meth>{_LONGUE})$")
_VINCI_FIN = re.compile(rf" \d{{1,3}},\d{{2}} (?:{_LONGUE})$")
# Format LVMH : « <nom> <ville>, <pays> <méthode> <taux> % ».
_COURTE = "|".join(METHODES_COURTES)
_LVMH = re.compile(
    rf"^(?P<avant>.+), (?P<pays>[^,]+) (?P<meth>{_COURTE}) (?P<taux>\d{{1,3}}(?:[.,]\d+)?) ?%$"
)
_INVISIBLES = dict.fromkeys(map(ord, "​‌‍⁠﻿"))


@dataclass(frozen=True)
class Candidat:
    """Un nom possible pour la société d'une ligne, et la ville que le document lui donne."""

    nom: str
    ville: str | None  # None : le document ne donne pas la ville (format VINCI)
    commune_exigee: bool = False  # retenu seulement si le siège SIRENE est dans `ville`


@dataclass(frozen=True)
class LignePerimetre:
    """Une société du périmètre, située en France. `candidats` : du plus probable au moins probable."""

    candidats: tuple[Candidat, ...]
    methode: str  # « IG » (intégration globale), « MEE » (mise en équivalence) ou « autre »
    taux: float  # taux d'intérêt du groupe, en %
    texte: str  # la ligne de la société telle que lue, sans les lignes d'avant : la preuve


@dataclass(frozen=True)
class PerimetrePublie:
    """Un document de périmètre déjà lu, tel que le moteur le reçoit (T043)."""

    source: str  # le document, nommé pour la preuve : « Liste des sociétés consolidées 2025 »
    lignes: tuple[LignePerimetre, ...]


class _Texte(HTMLParser):
    """Le texte d'une page HTML : une ligne par bloc, sans scripts ni styles. Pas d'expression
    régulière ici : sur une page mal formée, elle prendrait un temps quadratique."""

    BLOCS = {"p", "tr", "li", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6", "table"}

    def __init__(self) -> None:
        super().__init__()
        self.morceaux: list[str] = []
        self._cache = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self._cache += 1
        elif tag in self.BLOCS:
            self.morceaux.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._cache = max(0, self._cache - 1)
        elif tag in self.BLOCS:
            self.morceaux.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._cache:
            self.morceaux.append(" " + data)


def texte_document(chemin: Path) -> str:
    """Le texte d'un document de périmètre : PDF (pypdf), page HTML (balises retirées) ou texte."""
    if chemin.stat().st_size > TAILLE_MAX:
        raise ValueError("Le document dépasse 50 Mo : ce n'est pas une liste de sociétés consolidées.")
    with chemin.open("rb") as f:
        debut = f.read(5)
    if debut.startswith(b"%PDF") or chemin.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        # pypdf signale chaque police qu'il décode mal : le texte reste lisible, le journal non.
        logging.getLogger("pypdf").setLevel(logging.ERROR)
        return "\n".join((page.extract_text() or "") for page in PdfReader(chemin).pages)
    texte = chemin.read_text(encoding="utf-8", errors="replace")
    if chemin.suffix.lower() in (".html", ".htm") or texte.lstrip()[:1] == "<":
        lecteur = _Texte()
        lecteur.feed(texte)
        lecteur.close()
        texte = "".join(lecteur.morceaux)
    return texte


def _propre(ligne: str) -> str:
    ligne = ligne.translate(_INVISIBLES).replace("‑", "-").replace(" ", " ").replace(" ", " ")
    return re.sub(r"\s+", " ", ligne).strip()


def _taux(texte: str) -> float:
    return float(texte.replace(",", "."))


def _candidats_vinci(avant: list[str], nom: str) -> list[Candidat]:
    prefixes = [" ".join(avant[i:]) for i in range(len(avant))] + [""]
    return [Candidat((p + " " + nom).strip(), None) for p in prefixes]


def _candidats_lvmh(avant: list[str], debut: str) -> list[Candidat]:
    mots = debut.split()
    sortie: list[Candidat] = []
    for i in range(len(avant)):  # le plus long d'abord
        prefixe = " ".join(avant[i:]).split()
        for k in range(1, min(3, len(mots)) + 1):
            sortie.append(Candidat(" ".join(prefixe + mots[:-k]), " ".join(mots[-k:]), True))
    if len(mots) > 1:
        sortie.append(Candidat(" ".join(mots[:-1]), mots[-1]))
    for k in (2, 3):
        if len(mots) > k:
            sortie.append(Candidat(" ".join(mots[:-k]), " ".join(mots[-k:]), True))
    return sortie


def _unique(candidats: list[Candidat]) -> tuple[Candidat, ...]:
    return tuple(dict.fromkeys(c for c in candidats if c.nom))


def extraire(texte: str) -> list[LignePerimetre]:
    """Les sociétés situées en France ou en outre-mer, dans l'ordre du document."""
    sortie: list[LignePerimetre] = []
    avant: list[str] = []
    for brute in texte.splitlines():
        ligne = _propre(brute)
        if not ligne or ligne.isdigit():  # ligne vide ou numéro de page
            continue
        if m := _VINCI_FR.match(ligne):
            candidats = _candidats_vinci(avant, m["avant"])
            sortie.append(
                LignePerimetre(_unique(candidats), METHODES_LONGUES[m["meth"]], _taux(m["taux"]), ligne)
            )
        elif m := _LVMH.match(ligne):
            if m["pays"] == "France" or m["pays"] in OUTRE_MER:
                candidats = _candidats_lvmh(avant, m["avant"])
                sortie.append(
                    LignePerimetre(_unique(candidats), METHODES_COURTES[m["meth"]], _taux(m["taux"]), ligne)
                )
        elif not _VINCI_FIN.search(ligne):
            avant = (avant + [ligne])[-LIGNES_AVANT:]
            continue
        avant = []  # une ligne de société, en France ou non, termine le nom en cours
    return sortie
