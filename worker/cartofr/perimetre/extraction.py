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

from cartofr.perimetre.pays import OUTRE_MER, cle_pays, est_pays, est_zone, francais

METHODES_LONGUES = {
    "Intégration globale": "IG",
    "Mise en équivalence": "MEE",
    "Opération conjointe": "autre",
    "Intégration proportionnelle": "autre",
}
METHODES_COURTES = {"IG": "IG", "MEE": "MEE", "ME": "MEE", "IP": "autre", "JV": "autre"}
NON_CONSOLIDEE = "NC"
SANS_METHODE = "inconnue"  # la liste ne publie pas la méthode, seulement le taux (T054)
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
# Le taux : « 100,00 » chez VINCI, « 100 » ou « 20,89161 » chez Engie (T054).
_VINCI_FR = re.compile(rf"^(?P<avant>.+?) {_FR} (?P<taux>\d{{1,3}}(?:,\d+)?) (?P<meth>{_LONGUE})$")
_VINCI_FIN = re.compile(rf" \d{{1,3}}(?:,\d+)? (?:{_LONGUE})$")
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
    # consolidée), « inconnue » (non publiée) ou « autre »
    taux: float  # taux d'intérêt du groupe, en %
    texte: str  # la ligne de la société telle que lue, sans les lignes d'avant : la preuve

    @property
    def controlee(self) -> bool:
        """Le groupe contrôle la société : intégration globale, ou non consolidée (T053) ou de méthode
        non publiée (T054) à plus de 50 %."""
        return self.methode == "IG" or (self.methode in (NON_CONSOLIDEE, SANS_METHODE) and self.taux > 50)


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
        self._rangee = False  # dans une rangée : ses retours à la ligne ne la coupent pas (T054)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("td", "th"):
            self.morceaux.append(" | " if self._cellules else "\n")
            self._cellules += 1
            self._cellule += 1
        elif tag == "tr":
            self._cellules = 0
            self._rangee = True
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
            self._rangee = False
            self.morceaux.append("\n")
        elif self._cellule and tag in self.BLOCS:
            self.morceaux.append(" ")
        else:
            super().handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        # Un rapport indenté (TotalEnergies, Carrefour) a des retours à la ligne entre deux cellules.
        super().handle_data(data.replace("\r", " ").replace("\n", " ") if self._rangee else data)


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
    """Le texte d'un document de périmètre : PDF (pypdf), paquet ESEF (.zip ou .xhtml), page HTML
    (une ligne par rangée de tableau, cellules séparées par « | ») ou texte.

    Limites : 300 Mo pour un rapport ESEF ou son paquet (le zip d'Accor ou de Saint-Gobain dépasse
    50 Mo, T054), 50 Mo pour le reste."""
    taille = chemin.stat().st_size
    suffixe = chemin.suffix.lower()
    if suffixe in (".xhtml", ".html", ".htm"):  # rapport ESEF hors de son paquet, ou page HTML
        if taille > TAILLE_MAX_ESEF:
            raise ValueError("Rapport ESEF ou page HTML de plus de 300 Mo.")
        return _texte_esef(chemin.read_text(encoding="utf-8", errors="replace"))
    with chemin.open("rb") as f:
        debut = f.read(5)
    if debut.startswith(b"PK\x03\x04") or suffixe == ".zip":
        if taille > TAILLE_MAX_ESEF:
            raise ValueError("Paquet ESEF de plus de 300 Mo.")
        return _texte_esef(_rapport_esef(chemin))
    if taille > TAILLE_MAX:
        raise ValueError("Le document dépasse 50 Mo : ce n'est pas une liste de sociétés consolidées.")
    if debut.startswith(b"%PDF") or suffixe == ".pdf":
        from pypdf import PdfReader

        # pypdf signale chaque police qu'il décode mal : le texte reste lisible, le journal non.
        logging.getLogger("pypdf").setLevel(logging.ERROR)
        return "\n".join((page.extract_text() or "") for page in PdfReader(chemin).pages)
    texte = chemin.read_text(encoding="utf-8", errors="replace")
    return _texte_esef(texte) if texte.lstrip()[:1] == "<" else texte


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


def _candidats_tableau(nom: str, sigle_seul: bool = True) -> tuple[Candidat, ...]:
    """Format ESEF : le nom, le nom sans son sigle final ou sans sa forme juridique en toutes lettres,
    puis, de secours, parmi les sigles de SIRENE : le nom sans sigle, le nom suivi de sa forme
    abrégée, et le sigle seul (sauf `sigle_seul=False` : « (FMU) » chez Crédit Agricole S.A. est un
    type de fonds, pas le sigle de la société)."""
    m = _SIGLE_FINAL.match(nom)
    court = m["nom"] if m else nom
    candidats = [Candidat(nom, None), Candidat(court, None)]
    secours = [Candidat(court, None, secours=True, sigle=True)]
    if f := _FORME_EN_LETTRES.match(court):
        abregee = _FORMES_EN_LETTRES[_cle_forme(f["forme"])]
        candidats.append(Candidat(f["nom"], None))
        secours.append(Candidat(f"{f['nom']} {abregee}", None, secours=True, sigle=True))
    if sigle_seul and m and len(m["sigle"].replace(" ", "")) >= SIGLE_MIN:
        secours.append(Candidat(m["sigle"], None, secours=True, sigle=True))
    return _unique(candidats + secours + _cotes_du_tiret(court))


# « GENECAR - SOCIETE GENERALE DE COURTAGE… », « SOCIETE D'INGENIERIE… - SIME » : un nom et son sigle
# séparés par un tiret entouré d'espaces (T055).
_TIRET = re.compile(r" [-–] ")
_SIGLE_SEUL = re.compile(r"^[A-Z0-9.& ]{3,12}$")
# Une ligne de fonds n'est pas une société (T055) : un fonds n'a pas de SIREN. Une SICAV ou une
# SPPICAV en ont un (ce sont des sociétés) : elles ne sont pas dans la liste.
MOTIF_FONDS = re.compile(
    r"(?i:\b(?:FCP|FCPE|FCPR|FCPI|FCT|FPCI|FPS|FIP|OPC|OPCVM|compartiment)\b|^fonds\b|\bfund$)"
    # Une part de fonds : « CAP SANTE 3 PART A ». La lettre est en capitale : « part de » n'en est pas une.
    r"|\b(?:PARTS?|[Pp]arts?) [A-Z0-9]{1,2}\b"
)
_FORMES_MOTS = {
    "SA",
    "SAS",
    "SASU",
    "SARL",
    "SNC",
    "SCI",
    "SE",
    "EURL",
    "SCA",
    "GIE",
    "SCS",
    "SAS.",
    "S.A.",
    "S.A.S.",
}


def _mots_du_nom(cote: str) -> int:
    """Les mots d'un nom hors formes juridiques : « SNC Viparis » n'en a qu'un."""
    return sum(m.upper() not in _FORMES_MOTS for m in cote.split())


_PETITS_MOTS = {"DE", "DU", "DES", "D", "L", "LA", "LE", "LES", "ET", "EN", "A", "AU", "AUX"}


def _initiales(sigle: str, nom: str) -> bool:
    """`sigle` (3 caractères au moins) se lit, dans l'ordre, dans les initiales des mots de `nom`,
    petits mots retirés, et commence par la première : « SPIF » dans « Soc Participation Île de France »."""
    if not _SIGLE_SEUL.match(sigle):
        return False
    lettres = [c for c in sigle if c.isalnum()]
    initiales = [m[0] for m in cle_pays(nom).split() if m not in _PETITS_MOTS]
    if len(lettres) < SIGLE_MIN or not initiales or lettres[0] != initiales[0]:
        return False
    reste = iter(initiales)
    return all(lettre in reste for lettre in lettres)


def _cotes_du_tiret(nom: str) -> list[Candidat]:
    """De secours, chaque côté d'un nom coupé par un seul tiret entre un nom et son sigle : le nom, de
    deux mots au moins hors formes juridiques, parmi les dénominations ; le sigle (« SIME »,
    « V S P U ») parmi les sigles de SIRENE."""
    cotes = _TIRET.split(nom)
    # « Bureau Veritas SA – Nouvelle Calédonie » : une succursale, le côté est un lieu. Un fonds
    # (« SOGECAP - DIVERSIFIED LOANS FUND ») n'est pas une société : aucun de ses côtés n'en est une.
    if len(cotes) != 2 or MOTIF_FONDS.search(nom) or any(est_pays(c) for c in cotes):
        return []
    # Un nom et son sigle seulement, le sigle tiré des initiales du nom (« SIME », Société
    # d'Ingénierie Maintenance Exploitation) : « SNC VIPARIS - PORTE DE VERSAILLES » est un nom et un
    # lieu, « HOTEL INVENTE - LYON » une ville, et « LYON » est le sigle d'une autre société (revue T055).
    if not (_initiales(cotes[1], cotes[0]) or _initiales(cotes[0], cotes[1])):
        return []
    sortie = []
    for cote in cotes:
        if _SIGLE_SEUL.match(cote) and len(cote.replace(" ", "").replace(".", "")) >= SIGLE_MIN:
            sortie.append(Candidat(cote, None, secours=True, sigle=True))
        elif _mots_du_nom(cote) > 1:
            sortie.append(Candidat(cote, None, secours=True))
    return sortie


def _unique(candidats: list[Candidat]) -> tuple[Candidat, ...]:
    return tuple(dict.fromkeys(c for c in candidats if c.nom))


def extraire(texte: str) -> list[LignePerimetre]:
    """Les sociétés situées en France ou en outre-mer, dans l'ordre du document. Les formats de
    T054 ne sont essayés que si les formats VINCI, LVMH et ESEF ne lisent rien : un document déjà
    lu l'est toujours de la même façon."""
    return _extraire_vinci_lvmh_esef(texte) or _extraire_sections(texte)


def _extraire_vinci_lvmh_esef(texte: str) -> list[LignePerimetre]:
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
        if "|" in ligne:  # une page HTML au format VINCI ou LVMH : la rangée se lit sans ses cellules
            ligne = " ".join(c.strip() for c in ligne.split("|") if c.strip())
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


# --- Formats ajoutés le 2026-10-21 (T054) ------------------------------------------------------
# Méthodes écrites dans une cellule ou en fin de ligne, ramenées par `cle_pays` (majuscules, sans
# accents) : « E » chez TotalEnergies, « MEP », « MEI », « MES » à la Société Générale.
_METHODES_T054 = {
    "IG": "IG", "INTEGRATION GLOBALE": "IG", "FC": "IG",
    "MEE": "MEE", "ME": "MEE", "E": "MEE", "MEP": "MEE", "MEI": "MEE", "MES": "MEE",
    "MISE EN EQUIVALENCE": "MEE", "EM": "MEE",
    "IP": "autre", "JV": "autre", "INTEGRATION PROPORTIONNELLE": "autre", "OPERATION CONJOINTE": "autre",
    "NC": NON_CONSOLIDEE,
}  # fmt: skip
_POURCENT = re.compile(r"^\d{1,3}(?:[,.]\d+)?$")
_MONTANT = re.compile(r"^\(?-?\d[\d  ]*(?:[,.]\d+)?\)?$")  # « 1 995 », « (1 693) » : un montant
_SIREN_CELLULE = re.compile(r"^\d{3} ?\d{3} ?\d{3}$")  # Hermès donne le SIREN de ses filiales
_VIDE = {"", "-", "–", "—", "n.a."}
# Succursale, établissement d'une société étrangère : jamais une société française à retrouver.
_SUCCURSALE = re.compile(r"(?i)\b(?:succursale|succ\.|branch|niederlassung|sucursal)")
_NOTES_TETE = re.compile(r"^(?:\(\d+\)\s*)+")  # « (1)(6) TREEZOR SAS »
_NOTES_FIN = re.compile(r"(?:\s*\(\d+\))+$")  # « ACTICCIA VIE 3 (1) »
_TAUX_T054 = r"\d{1,3}(?:,\d+)?"
# Société Générale : « <NOM> <Activité> <méthode> <% intérêt> <% contrôle> », pays en titre.
_SG = re.compile(rf"^(?P<corps>.+?) (?P<meth>IG|MEP|MEI|MES|MEE|ME) (?P<taux>{_TAUX_T054}) {_TAUX_T054}$")
# Crédit Agricole S.A. : « <nom> <symbole> <variation> <type> <pôle> <% contrôle 2025> <2024>
# <% intérêt 2025> <2024> », pays en titre. ■ intégration globale, ▲ équivalence, ● mère, X juste valeur.
_CASA_VALEUR = r"(?:\d{1,3},\d|-)"
_CASA = re.compile(
    rf"^(?P<corps>.+?) (?P<sym>[■▲●X]) \S+ \S+ \S+ {_CASA_VALEUR} {_CASA_VALEUR}"
    rf" (?P<taux>{_CASA_VALEUR}) {_CASA_VALEUR}$"
)
_CASA_METHODES = {"■": "IG", "●": "IG", "▲": "MEE", "X": "autre"}
# BNP Paribas : « <nom> France <méthode>(<note>) <% contrôle> <% intérêt> », puis l'exercice d'avant.
_BNP = re.compile(
    r"^(?P<corps>.+?) France (?P<meth>IG|ME|MEE)(?:\(\d+\))? (?:\d{1,3},\d%) (?P<taux>\d{1,3},\d)%(?: .*)?$"
)
# Une rangée BNP, quel que soit le pays : « … Belgique IG 100,0% 100,0% ». Hors de France, elle
# n'est pas lue, mais elle termine le nom en cours (T055 : avant, elle se collait au nom suivant).
_BNP_RANGEE = re.compile(r" (?:IG|ME|MEE)(?:\(\d+\))? (?:\d{1,3},\d%|-) (?:\d{1,3},\d%|-)(?: |$)")
# Airbus : « <F|E|P> <% intérêt> <nom> France » (F intégration globale, E équivalence, P proportionnelle).
_AIRBUS = re.compile(r"^(?P<meth>[FEP]) (?P<taux>\d{1,3}\.\d+) (?P<corps>.+) France$")
_AIRBUS_METHODES = {"F": "IG", "E": "MEE", "P": "autre"}
# Eurofins : « <nom> FR <mère directe> <% détenu> <mois/année d'entrée> ».
# Longueurs bornées : sans elles, une longue ligne pleine de « FR » prend un temps quadratique.
_EUROFINS = re.compile(
    r"^(?P<corps>[^%]{1,200}?) FR (?P<mere>[^%]{1,200}?) (?P<taux>\d{1,3}[.,]\d+)% \d{2}/\d{2}$"
)
# Euronext : « <nom> France <% 2025> <% 2024> ». Le nom finit par sa forme juridique : sans elle,
# « Effectifs France 62,3% 60,1% » se lirait comme une société.
_FORME = r"(?:S\.?A\.?S?\.?U?|SARL|SNC|SCI|SE|GIE|N\.V\.|B\.V\.|Ltd\.?|S\.p\.A\.|S\.r\.l\.|GmbH)"
_POURCENTS = re.compile(
    rf"^(?P<corps>.{{1,200}}? {_FORME}) France (?P<taux>\d{{1,3}}[.,]\d+)% (?:\d{{1,3}}[.,]\d+%|—|-)$"
)
# Les formats où le pays est sur la ligne : ils se lisent hors d'une section « France ».
_PAYS_SUR_LA_LIGNE = (_BNP, _AIRBUS, _EUROFINS, _POURCENTS)
_PARAGRAPHE = 80  # une ligne sans « | » plus longue est du texte courant : elle ferme une section de tableau
_LIGNE_MAX = 1000  # une rangée de liste tient en moins ; au-delà, du texte : pas de motif à essayer
# Titre d'une section de tableau : le pays, puis l'intitulé d'une colonne de détention (Carrefour :
# « FRANCE | Pourcentage d'intérêts retenus en consolidation »).
_TITRE_DETENTION = re.compile(r"(?i)pourcentage|%|int[ée]r[êe]t|contr[ôo]le|d[ée]tention|interest|ownership")
# « Sortie Inventée | France |  |  |  | 100 | 98 | IG » : trois cellules vides de suite avant le premier
# taux, ce sont les colonnes de l'exercice ; les suivantes sont celles d'avant. Stellantis laisse
# des colonnes vides de mise en page, une à la fois.
_VIDES_SORTIE = 3


def _nom_t054(corps: str, majuscules: bool = False) -> str:
    """Le nom d'une ligne : sans appels de note, et pour la Société Générale sans la colonne
    d'activité, écrite en minuscules (« SODEPROM Banque de détail en France ») : on garde les mots
    du début qui n'ont aucune minuscule."""
    nom = _NOTES_FIN.sub("", _NOTES_TETE.sub("", corps)).strip()
    if majuscules:
        mots = []
        for mot in nom.split():
            if any(c.islower() for c in mot):
                break
            mots.append(mot)
        nom = " ".join(mots)
    return nom


def _nom_plausible(nom: str) -> bool:
    """Deux lettres au moins (« AS 24 », pas « # »), et pas la fin d'un nom coupé (« (FMU) », « privée »)."""
    return sum(c.isalpha() for c in nom) >= 2 and not nom.startswith("(") and not nom[:1].islower()


@dataclass(frozen=True)
class _Rangee:
    """Une rangée de tableau lue par `_cellules_t054`."""

    nom: str
    en_france: bool
    methode: str
    taux: float
    pays_etranger: bool  # la rangée porte un pays étranger (pas une zone) : un tableau de sociétés
    avec_methode: bool
    forme: tuple[int, int]  # (cellules, place de la cellule du pays) : la forme du tableau


def _cellules_t054(ligne: str, section: tuple[bool, int] | None) -> _Rangee | None:
    """Une rangée de tableau : (nom, en France, méthode, taux), ou None. Le pays est la première
    cellule qui est un nom de pays (TotalEnergies : le pays du siège avant le pays d'opération), à
    défaut celui du titre de la section de tableau, si la rangée a autant de cellules que lui. Une
    rangée qui porte un montant (« 1 995 ») ou plus de 4 taux est un tableau financier ; sans
    méthode ni titre de section, une rangée doit porter deux taux, ou un taux à décimales."""
    cellules = [c.strip() for c in ligne.split("|")]
    nom = pays = meth = None
    place = -1  # place de la cellule du pays
    taux: list[float] = []
    vides = 0  # cellules vides de suite après le nom, avant le premier taux
    decimal = False  # un taux écrit avec ses décimales (« 15,00 ») : une colonne de pourcentages
    for c in cellules:
        if c in _VIDE:
            if nom is not None and not taux:
                vides += 1
                if vides >= _VIDES_SORTIE:  # l'exercice est vide : société sortie, pas l'exercice d'avant
                    return None
            continue
        vides = 0
        if _SIREN_CELLULE.match(c):
            continue
        if _POURCENT.match(c):
            if float(c.replace(",", ".")) > 100:
                return None
            if nom is not None:
                taux.append(_taux(c))
                decimal = decimal or not c.isdigit()
            continue
        if _MONTANT.match(c):
            return None
        if (m := _METHODES_T054.get(cle_pays(c))) is not None:
            meth = meth or m
        elif est_pays(c):
            if pays is None:
                pays, place = c, cellules.index(c)
        elif "," in c and est_pays(debut := c.split(",", 1)[0]):  # « France, Crolles » (STMicro)
            if pays is None:
                pays, place = debut, cellules.index(c)
            decimal = True  # une colonne d'adresse : un tableau de sociétés, pas de sites
        elif nom is None:
            nom = c
    if (
        nom is None
        or not taux
        or len(taux) > 4
        or _SUCCURSALE.search(nom)
        or sum(c.isalpha() for c in nom) < 2
    ):
        return None
    if pays is not None:
        # « Cristallerie | France | 2 » (un tableau de sites, Hermès) : sans méthode, il faut deux taux
        # ou un taux à décimales pour croire à une liste de sociétés.
        if meth is None and len(taux) == 1 and not decimal:
            return None
        en_france = francais(pays)
    elif section is not None and section[1] == len(cellules):
        en_france = section[0]
    else:
        return None
    etranger = pays is not None and not en_france and not est_zone(pays)
    return _Rangee(
        nom, en_france, meth or SANS_METHODE, taux[0], etranger, meth is not None, (len(cellules), place)
    )


def _extraire_sections(texte: str) -> list[LignePerimetre]:
    """Les formats de T054 :
    - une rangée de tableau dont une cellule est le pays (TotalEnergies, Bureau Veritas, Hermès), ou
      sous un titre de section de tableau « FRANCE | Pourcentage d'intérêts » (Carrefour) ;
    - une ligne de la Société Générale ou du Crédit Agricole S.A., sous un titre « France » ;
    - une ligne de BNP Paribas (« <nom> France IG 100,0% 100,0% »), d'Airbus, d'Eurofins ou
      d'Euronext, où le pays est sur la ligne ;
    - une rangée « France, <ville> | <nom> | <taux> » (STMicroelectronics).
    Le nom d'une ligne de texte peut être coupé sur les deux lignes d'avant : les noms recollés sont
    essayés d'abord, la ligne seule ensuite, si son nom est plausible.

    Une rangée de tableau sans méthode n'est gardée que si le document a, de la même forme (nombre
    de cellules, place du pays), une rangée d'un pays étranger : une liste de filiales couvre
    plusieurs pays, parfois en blocs par région (Renault) ; un tableau de chiffres sur la France
    (« Répartition des effectifs | France | 55 | 54 ») non. Sous un titre de section de détention
    (Carrefour), le titre suffit. La lecture se fait donc en deux temps : rangées, puis formes."""
    sortie: list[LignePerimetre] = []
    avant: list[str] = []
    section_texte = False  # sous un titre « France » d'une liste en texte
    section_tableau: tuple[bool, int] | None = None  # (France ?, cellules) du titre de tableau
    # Dans l'ordre du document : une ligne de texte déjà lue, ou une rangée de tableau à trancher.
    lues: list[LignePerimetre | tuple[_Rangee, str, bool]] = []

    for brute in texte.splitlines():
        ligne = _rangee(_propre(brute))
        if not ligne or ligne.isdigit() or len(ligne) > _LIGNE_MAX:
            continue
        if "|" in ligne:
            cellules = ligne.split(" | ")
            if (
                est_pays(cellules[0])
                and len(cellules) > 1
                and all(_TITRE_DETENTION.search(c) for c in cellules[1:])
            ):
                section_tableau = (francais(cellules[0]), len(cellules))
            elif r := _cellules_t054(ligne, section_tableau):
                lues.append((r, ligne, section_tableau is not None and section_tableau[1] == len(cellules)))
            avant = []
            continue
        if est_pays(ligne):
            section_texte = francais(ligne)
            section_tableau = None
            avant = []
            continue
        if len(ligne) > _PARAGRAPHE:
            section_tableau = None
        lue = _ligne_texte_t054(avant, ligne, section_texte)
        if lue is None and _BNP_RANGEE.search(ligne):  # rangée BNP d'un autre pays : pas un début de nom
            avant = []
            continue
        if lue is None:
            avant = (avant + [ligne])[-LIGNES_AVANT:]
            continue
        if lue.candidats:
            lues.append(lue)
        avant = []
    listes = {x[0].forme for x in lues if isinstance(x, tuple) and x[0].pays_etranger}
    for x in lues:
        if isinstance(x, LignePerimetre):
            sortie.append(x)
            continue
        r, texte, par_titre = x
        if r.en_france and (r.avec_methode or par_titre or r.forme in listes):
            sortie.append(LignePerimetre(_candidats_tableau(r.nom), r.methode, r.taux, texte))
    return sortie


_MOTIFS_TEXTE = (
    (_SG, True), (_CASA, False), (_BNP, False), (_AIRBUS, False), (_EUROFINS, False), (_POURCENTS, False),
)  # fmt: skip


def _ligne_texte_t054(avant: list[str], ligne: str, section_fr: bool) -> LignePerimetre | None:
    """Une ligne de société (Société Générale, Crédit Agricole S.A., BNP Paribas, Airbus, Eurofins,
    Euronext), recollée aux lignes d'avant si sa fin y commence. None : pas une ligne de société.
    Une ligne de société hors de France, ou sans nom plausible, rend une ligne sans candidat.

    Méthode et taux : ceux de la rangée la plus courte qui se lit (Airbus les écrit en tête de
    ligne : une rangée plus longue les prendrait sur la ligne d'avant, une autre société). Noms :
    le plus long d'abord ; les plus courts, des bouts possibles d'un nom coupé, ne sont que de
    secours, et jamais un mot seul (« BONDS », la fin d'un nom de fonds, est une autre société).
    Preuve : la rangée la plus courte qui porte un nom plausible."""
    for motif, majuscules in _MOTIFS_TEXTE:
        jointes = []  # (texte, correspondance), de la ligne seule à la plus longue
        # Airbus commence sa rangée par la méthode : elle n'est jamais la suite d'une ligne d'avant.
        for k in range(len(avant), len(avant) - 1 if motif is _AIRBUS else -1, -1):
            texte = " ".join([*avant[k:], ligne])
            if mk := motif.match(texte):
                jointes.append((texte, mk))
        if not jointes:
            continue
        m = jointes[0][1]
        if motif is _CASA and m["taux"] == "-":  # sortie du périmètre dans l'exercice
            return LignePerimetre((), "", 0.0, ligne)
        if motif not in _PAYS_SUR_LA_LIGNE and not section_fr:
            return LignePerimetre((), "", 0.0, ligne)
        if motif is _CASA:
            meth = _CASA_METHODES[m["sym"]]
        elif motif is _AIRBUS:
            meth = _AIRBUS_METHODES[m["meth"]]
        elif motif in (_EUROFINS, _POURCENTS):
            meth = SANS_METHODE
        else:
            meth = _METHODES_T054[m["meth"]]
        noms = [
            (nom, texte) for texte, mk in jointes if _nom_plausible(nom := _nom_t054(mk["corps"], majuscules))
        ]
        if not noms or _SUCCURSALE.search(noms[0][0]):
            return LignePerimetre((), "", 0.0, ligne)
        long, *courts = reversed(noms)
        # Le nom, sans son sigle final (« Crédit Agricole Assurances (CAA) »), ses côtés du tiret,
        # puis les bouts plus courts, de secours.
        candidats = list(_candidats_tableau(long[0], sigle_seul=False)) + [
            Candidat(n, None, secours=True) for n, _ in courts if len(n.split()) > 1
        ]
        return LignePerimetre(_unique(candidats), meth, _taux(m["taux"]), noms[0][1])
    return None
