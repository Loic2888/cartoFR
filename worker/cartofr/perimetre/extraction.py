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
  Ajouts du 2026-10-19 (T053), essayés après les autres, et seulement si aucun candidat d'avant,
  hors ces ajouts, n'a d'homonymes à départager par le registre (`secours`) :
  4. la ligne entière, ville comprise, si le siège est dans cette ville : « Hôtel Inventé
     Courchevel » est le nom d'une société de Courchevel ;
  5. chaque côté d'un nom double « MH Inventé – Moët Inventé » (tiret long), de deux mots au moins, pour les
     seuls candidats qui n'exigent pas la commune (la ligne seule, ville d'un mot).
  Une ligne qui finit par une virgule (« <nom> <ville>, ») attend la suite de la ligne : le pays
  et la méthode viennent sur les une ou deux lignes suivantes. La ligne recollée n'est gardée que
  si sa virgule est celle d'avant le pays ; une ligne qui se lit seule passe toujours d'abord, et
  ce qui attendait redevient du texte d'avant. Une ligne coupée en fin de texte est perdue.

Troisième format, ajouté le 2026-10-20 (T049) : le tableau de périmètre d'un document
d'enregistrement universel au format ESEF (paquet .zip de l'AMF, ou son .xhtml), ex. la note 3 de
CMAF. `texte_document` y rend une ligne par rangée, cellules séparées par « | » :
« CIC Nord Ouest | France | 100 | 98 | IG | 100 | 98 | IG » : nom, pays, % de contrôle, % d'intérêt
et méthode de l'exercice, puis ceux de l'exercice d'avant, ignorés. Une société sortie, fusionnée
(« FU ») ou une succursale n'est pas lue. Candidats, dans l'ordre :
  1. le nom ; 2. le nom sans son sigle final entre parenthèses (« Banque Transatlantique (BT) ») ;
  3. de secours, cherchés parmi les sigles de SIRENE et non les dénominations (`sigle`) : le nom
     sans parenthèses (« CIC Est », sigle de BANQUE CIC EST), puis le sigle entre parenthèses, s'il
     a 3 caractères au moins (`SIGLE_MIN`).

Usage :
    lignes = extraire(texte_document(Path("out/perimetre/vinci.pdf")))
Entrée : un PDF, une page HTML ou un texte.
Sortie : une `LignePerimetre` par société située en France ou en outre-mer.
"""

import logging
import re
import zipfile
import zlib
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

# Outre-mer présent dans SIRENE. La Nouvelle-Calédonie et la Polynésie ont leurs propres registres.
OUTRE_MER = (
    "Guadeloupe", "Martinique", "Guyane", "La Réunion", "Réunion", "Mayotte",
    "Saint-Martin", "Saint-Barthélemy", "Saint-Pierre-et-Miquelon", "Antilles françaises",
)  # fmt: skip
METHODES_LONGUES = {
    "Intégration globale": "IG",
    "Mise en équivalence": "MEE",
    "Opération conjointe": "autre",
    "Intégration proportionnelle": "autre",
}
METHODES_COURTES = {"IG": "IG", "MEE": "MEE", "ME": "MEE", "IP": "autre", "JV": "autre"}
NON_CONSOLIDEE = "NC"
LIGNES_AVANT = 2  # lignes non terminées gardées pour recoller un nom coupé
LIGNES_SUITE = 2  # lignes lues au plus pour finir une ligne coupée après la virgule
# « MH Inventé – Moët Inventé » : deux noms de la même société. Le tiret long seul : « Hôtel -
# Restaurant Inventé » est un seul nom, son côté « Restaurant Inventé » serait trop vague (revue T053).
_DOUBLE = re.compile(r" – ")
TAILLE_MAX = 50 * 1024 * 1024  # un document de périmètre fait quelques Mo : au-delà, on refuse
# Le rapport d'un paquet ESEF, une fois décompressé : 96 Mo pour le DEU 2025 de CMAF. Au-delà, on
# refuse : un zip de quelques Mo peut se décompresser en plusieurs Go.
TAILLE_MAX_ESEF = 300 * 1024 * 1024

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
# Liste des sociétés non incluses dans la consolidation (LVMH) : « <nom> <ville>, <pays> <taux> % »,
# sans méthode. Lue seulement après son titre : ailleurs, ce format serait trop proche du texte courant.
_NC = re.compile(r"^(?P<avant>.+), (?P<pays>[^,]+) (?P<taux>\d{1,3}(?:[.,]\d+)?) ?%$")
_TITRE_NC = re.compile(r"(?i)non (?:incluses dans la|comprises dans la) consolidation|non consolidées")
_INVISIBLES = dict.fromkeys(map(ord, "​‌‍⁠﻿"))
# Format ESEF : « <nom> | <pays> | <contrôle> | <intérêt> | <méthode> », puis l'exercice d'avant.
_NOMBRE = r"\d{1,3}(?:[,.]\d+)?"
_TABLEAU = re.compile(
    rf"^(?P<nom>[^|]+?) \| (?P<pays>[^|]+?) \| {_NOMBRE} \| (?P<taux>{_NOMBRE}) \| (?P<meth>IG|MEE|ME|IP|NC)"
    r"(?: \|.*)?$"
)
# « ACM Vie, Société d'Assurance Mutuelle » : une forme juridique écrite en toutes lettres après une
# virgule, et sa forme abrégée, telle que SIRENE l'écrit dans les sigles (« ACM VIE SAM »).
_FORMES_EN_LETTRES = {
    "SOCIETE D ASSURANCE MUTUELLE": "SAM",
    "SOCIETE ANONYME": "SA",
    "SOCIETE PAR ACTIONS SIMPLIFIEE": "SAS",
    "SOCIETE CIVILE IMMOBILIERE": "SCI",
    "SOCIETE EN NOM COLLECTIF": "SNC",
}
_FORME_EN_LETTRES = re.compile(
    r"(?i)^(?P<nom>[^,]+), (?P<forme>soci[ée]t[ée] (?:d['’ ]assurance mutuelle|anonyme"
    r"|par actions simplifi[ée]e|civile immobili[èe]re|en nom collectif))$"
)


def _cle_forme(forme: str) -> str:
    sans = forme.upper().replace("’", " ").replace("'", " ")
    for accent, lettre in (("É", "E"), ("È", "E")):
        sans = sans.replace(accent, lettre)
    return " ".join(sans.split())


# Un sigle entre parenthèses plus court (« LB », « BT ») est porté par trop de sociétés : le registre
# finirait par en retenir une au hasard dans le groupe.
SIGLE_MIN = 3
_SIGLE_FINAL = re.compile(r"^(?P<nom>.+?) \((?P<sigle>[^()]+)\)$")


@dataclass(frozen=True)
class Candidat:
    """Un nom possible pour la société d'une ligne, et la ville que le document lui donne."""

    nom: str
    ville: str | None  # None : le document ne donne pas la ville (format VINCI)
    commune_exigee: bool = False  # retenu seulement si le siège SIRENE est dans `ville`
    secours: bool = False  # essayé seulement si aucun candidat d'avant n'a d'homonymes
    sigle: bool = False  # cherché parmi les sigles de SIRENE, pas parmi les dénominations (ESEF)


@dataclass(frozen=True)
class LignePerimetre:
    """Une société du périmètre, située en France. `candidats` : du plus probable au moins probable."""

    candidats: tuple[Candidat, ...]
    methode: str  # « IG » (intégration globale), « MEE » (mise en équivalence), « NC » (non
    # consolidée) ou « autre »
    taux: float  # taux d'intérêt du groupe, en %
    texte: str  # la ligne de la société telle que lue, sans les lignes d'avant : la preuve

    @property
    def controlee(self) -> bool:
        """Le groupe contrôle la société : intégration globale, ou non consolidée à plus de 50 % (T053)."""
        return self.methode == "IG" or (self.methode == NON_CONSOLIDEE and self.taux > 50)


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


class _Rangees(_Texte):
    """Le texte d'un rapport ESEF : une ligne par rangée de tableau, cellules séparées par « | ». Les
    blocs d'une cellule (un nom sur deux lignes) y sont recollés par une espace."""

    def __init__(self) -> None:
        super().__init__()
        self._cellule = 0  # profondeur dans une cellule
        self._cellules = 0  # cellules déjà ouvertes dans la rangée

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("td", "th"):
            self.morceaux.append(" | " if self._cellules else "\n")
            self._cellules += 1
            self._cellule += 1
        elif tag == "tr":
            self._cellules = 0
            self.morceaux.append("\n")
        elif self._cellule and tag in self.BLOCS:
            self.morceaux.append(" ")
        else:
            super().handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th"):
            self._cellule = max(0, self._cellule - 1)
        elif tag == "tr":
            self._cellules = 0
            self.morceaux.append("\n")
        elif self._cellule and tag in self.BLOCS:
            self.morceaux.append(" ")
        else:
            super().handle_endtag(tag)


def _texte_esef(xhtml: str) -> str:
    lecteur = _Rangees()
    lecteur.feed(xhtml)
    lecteur.close()
    return "".join(lecteur.morceaux)


def _rapport_esef(chemin: Path) -> str:
    """Le rapport xhtml d'un paquet ESEF (zip déposé à l'AMF), dans `reports/`."""
    try:
        with zipfile.ZipFile(chemin) as paquet:
            rapports = [i for i in paquet.infolist() if "/reports/" in f"/{i.filename}"
                        and i.filename.lower().endswith((".xhtml", ".html"))]  # fmt: skip
            if len(rapports) != 1:
                raise ValueError("Paquet ESEF sans rapport unique dans « reports/ ».")
            if rapports[0].file_size > TAILLE_MAX_ESEF:
                raise ValueError("Rapport ESEF de plus de 300 Mo une fois décompressé.")
            with paquet.open(rapports[0]) as f:
                donnees = f.read(TAILLE_MAX_ESEF + 1)  # la taille annoncée peut mentir
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError, EOFError, zlib.error) as erreur:
        # NotImplementedError : méthode de compression inconnue ; RuntimeError : archive chiffrée.
        raise ValueError("Archive zip abîmée, chiffrée ou compressée d'une façon inconnue.") from erreur
    if len(donnees) > TAILLE_MAX_ESEF:
        raise ValueError("Rapport ESEF de plus de 300 Mo une fois décompressé.")
    return donnees.decode("utf-8", errors="replace")


def texte_document(chemin: Path) -> str:
    """Le texte d'un document de périmètre : PDF (pypdf), paquet ESEF (.zip ou .xhtml, une ligne par
    rangée de tableau), page HTML (balises retirées) ou texte."""
    taille = chemin.stat().st_size
    if chemin.suffix.lower() == ".xhtml":  # rapport ESEF hors de son paquet
        if taille > TAILLE_MAX_ESEF:
            raise ValueError("Rapport ESEF de plus de 300 Mo.")
        return _texte_esef(chemin.read_text(encoding="utf-8", errors="replace"))
    if taille > TAILLE_MAX:
        raise ValueError("Le document dépasse 50 Mo : ce n'est pas une liste de sociétés consolidées.")
    with chemin.open("rb") as f:
        debut = f.read(5)
    if debut.startswith(b"PK\x03\x04") or chemin.suffix.lower() == ".zip":
        return _texte_esef(_rapport_esef(chemin))
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
    if len(mots) > 1:
        sortie.append(Candidat(debut, mots[-1], True, secours=True))
    return sortie


def _noms_doubles(candidats: list[Candidat]) -> list[Candidat]:
    """Les candidats, puis chaque côté de leurs noms doubles, de deux mots au moins. Un candidat qui
    exige la commune n'est pas coupé : son nom est déjà une hypothèse."""
    cotes = [
        Candidat(cote, c.ville, secours=True)
        for c in candidats
        if not c.commune_exigee and _DOUBLE.search(c.nom)
        for cote in _DOUBLE.split(c.nom)
        if len(cote.split()) > 1
    ]
    return candidats + cotes


_FEDERATIONS = re.compile(
    r"(?is)\bles\s+F[ée]d[ée]rations\s+du\s+Cr[ée]dit\s+Mutuel\b(?P<liste>[^;]{1,2000});"
)


_NOTE = re.compile(r"\s*(?:\(\d+\)|\*+|%)$")


def _rangee(ligne: str) -> str:
    """Une rangée ESEF sans cellules vides en tête ni en fin, ni appel de note (« IG (1) », « 98* »)
    ni « % ». Une cellule vide au milieu reste : les colonnes vides d'une société sortie ne doivent
    pas faire lire l'exercice d'avant à leur place."""
    if "|" not in ligne:
        return ligne
    cellules = [_NOTE.sub("", c.strip()).strip() for c in ligne.split("|")]
    while cellules and not cellules[0]:
        cellules.pop(0)
    while cellules and not cellules[-1]:
        cellules.pop()
    return " | ".join(cellules)


def passage_federations(texte: str) -> str:
    """Le passage d'un document de groupe mutualiste qui liste ses fédérations (« les Fédérations du
    Crédit Mutuel Centre Est Europe (FCMCEE), du Sud-Est… ; », note 3a du DEU de CMAF), espaces
    recollées ; vide si le document n'en a pas (T049)."""
    m = _FEDERATIONS.search(texte)
    return " ".join(m["liste"].split()) if m else ""


def _candidats_tableau(nom: str) -> tuple[Candidat, ...]:
    """Format ESEF : le nom, le nom sans son sigle final ou sans sa forme juridique en toutes lettres,
    puis, de secours, parmi les sigles de SIRENE : le nom sans sigle, le nom suivi de sa forme
    abrégée, et le sigle seul."""
    m = _SIGLE_FINAL.match(nom)
    court = m["nom"] if m else nom
    candidats = [Candidat(nom, None), Candidat(court, None)]
    secours = [Candidat(court, None, secours=True, sigle=True)]
    if f := _FORME_EN_LETTRES.match(court):
        abregee = _FORMES_EN_LETTRES[_cle_forme(f["forme"])]
        candidats.append(Candidat(f["nom"], None))
        secours.append(Candidat(f"{f['nom']} {abregee}", None, secours=True, sigle=True))
    if m and len(m["sigle"].replace(" ", "")) >= SIGLE_MIN:
        secours.append(Candidat(m["sigle"], None, secours=True, sigle=True))
    return _unique(candidats + secours)


def _unique(candidats: list[Candidat]) -> tuple[Candidat, ...]:
    return tuple(dict.fromkeys(c for c in candidats if c.nom))


def extraire(texte: str) -> list[LignePerimetre]:
    """Les sociétés situées en France ou en outre-mer, dans l'ordre du document."""
    sortie: list[LignePerimetre] = []
    avant: list[str] = []
    coupee: list[str] = []  # une ligne finie par une virgule, et ce qui l'a suivie
    non_consolidees = False  # le titre de la liste des sociétés non consolidées est passé
    for brute in texte.splitlines():
        ligne = _propre(brute)
        if not ligne or ligne.isdigit():  # ligne vide ou numéro de page
            continue
        if m := _TABLEAU.match(_rangee(ligne)):  # format ESEF : une rangée se lit seule
            nom = m["nom"].strip()
            if (m["pays"] == "France" or m["pays"] in OUTRE_MER) and "succursale" not in nom.lower():
                meth = METHODES_COURTES.get(m["meth"], NON_CONSOLIDEE)
                sortie.append(LignePerimetre(_candidats_tableau(nom), meth, _taux(m["taux"]), ligne))
            avant, coupee = [], []
            continue
        if coupee:
            seule = _VINCI_FR.match(ligne) or _LVMH.match(ligne) or _VINCI_FIN.search(ligne)
            recollee = None if seule else _LVMH.match(" ".join([*coupee, ligne]))
            if recollee and recollee["avant"] == coupee[0][:-1]:
                ligne = " ".join([*coupee, ligne])
                coupee = []
            elif seule or len(coupee) >= LIGNES_SUITE:
                avant = (avant + coupee)[-LIGNES_AVANT:]  # pas une ligne coupée : du texte
                coupee = []
                if not seule:
                    avant = (avant + [ligne])[-LIGNES_AVANT:]
                    continue
            else:
                coupee.append(ligne)
                continue
        elif ligne.endswith(","):
            coupee = [ligne]
            continue
        if not non_consolidees and _TITRE_NC.search(ligne):
            non_consolidees = True
        if m := _VINCI_FR.match(ligne):
            candidats = _candidats_vinci(avant, m["avant"])
            sortie.append(
                LignePerimetre(_unique(candidats), METHODES_LONGUES[m["meth"]], _taux(m["taux"]), ligne)
            )
        elif m := _LVMH.match(ligne):
            if m["pays"] == "France" or m["pays"] in OUTRE_MER:
                candidats = _noms_doubles(_candidats_lvmh(avant, m["avant"]))
                sortie.append(
                    LignePerimetre(_unique(candidats), METHODES_COURTES[m["meth"]], _taux(m["taux"]), ligne)
                )
        elif non_consolidees and (m := _NC.match(ligne)):
            if m["pays"] == "France" or m["pays"] in OUTRE_MER:
                candidats = _noms_doubles(_candidats_lvmh(avant, m["avant"]))
                sortie.append(LignePerimetre(_unique(candidats), NON_CONSOLIDEE, _taux(m["taux"]), ligne))
        elif not _VINCI_FIN.search(ligne):
            avant = (avant + [ligne])[-LIGNES_AVANT:]
            continue
        avant = []  # une ligne de société, en France ou non, termine le nom en cours
    return sortie
