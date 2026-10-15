"""Retrouver dans le registre les sociétés d'un périmètre publié, par une règle écrite (T042).

Règle, mesurée le 2026-10-14 sur VINCI et LVMH, puis resserrée après la revue du même jour :
1. le nom candidat, ramené à sa clé (`cle`), est la dénomination d'une seule société active,
   hors entrepreneurs individuels : retenue (`unique`) ;
2. plusieurs sociétés actives portent ce nom : celle dont le siège est dans la ville du document
   est retenue, si elle est seule (`commune`). Un candidat marqué `commune_exigee` (nom recollé
   aux lignes d'avant, ville de plusieurs mots) n'est retenu que de cette façon ;
3. sinon, parmi les homonymes de la ville du document (ou tous, sans ville), celui que le registre
   relie déjà au groupe est retenu, s'il est seul (`registre`) : liens de société ouverts,
   descendus depuis la tête et les sociétés en intégration globale retenues aux étapes 1 et 2 ;
4. sinon, la ligne n'est pas retenue : `homonymes` (avec leur nombre) ou `introuvable` ;
5. enfin, un même SIREN retenu pour des lignes de noms différents est un signe d'erreur : aucune
   de ces lignes n'est retenue (`conflit`).
Les candidats d'une ligne sont essayés dans l'ordre : le premier qui retient une société décide ;
à défaut, le premier porté par des homonymes passe à l'étape 3.

Usage :
    con = duckdb.connect(str(registre), read_only=True)
    resultats = correspondre(con, tete_siren, extraire(texte))
Entrées : une connexion au registre, le SIREN de la tête, les lignes d'`extraction`.
Sorties : une `Correspondance` par ligne, retenue ou non, avec sa raison.
Seules les dénominations des sociétés sont lues : jamais `dirigeants_personnes` (garde-fou 6).
"""

import collections
import re
from collections.abc import Iterable
from dataclasses import dataclass, replace
from typing import Any, Literal

import duckdb
import pyarrow as pa
import pyarrow.compute as _pc

from cartofr.moteur.marques import norm, norm_arrow
from cartofr.moteur.moteur import MEDIUM, STRONG
from cartofr.perimetre.extraction import LignePerimetre

pc: Any = _pc  # fonctions générées à l'exécution : inconnues du vérificateur de types

Raison = Literal["unique", "commune", "registre", "homonymes", "introuvable", "conflit"]
UNIQUE: Raison = "unique"
COMMUNE: Raison = "commune"
REGISTRE: Raison = "registre"
HOMONYMES: Raison = "homonymes"
INTROUVABLE: Raison = "introuvable"
CONFLIT: Raison = "conflit"
RETENUES: tuple[Raison, ...] = (UNIQUE, COMMUNE, REGISTRE)

# Clé d'un nom, après `norm` : formes écrites avec des points recollées (« S.A.S. » → « SAS »),
# abréviations développées, « ET » retiré, formes juridiques retirées en tête et en fin seulement
# (« SE LOGER SA » → « SE LOGER »). Mêmes expressions côté Python et côté Arrow (testé).
POINTEES = (("S A S U", "SASU"), ("S A R L", "SARL"), ("E U R L", "EURL"), ("S A S", "SAS"),
            ("S N C", "SNC"), ("S C I", "SCI"), ("S C A", "SCA"), ("S A", "SA"))  # fmt: skip
ABREVIATIONS = (("STE", "SOCIETE"), ("CIE", "COMPAGNIE"), ("ETS", "ETABLISSEMENTS"))
_FORMES = "SASU|SAS|SARL|SNC|SCI|SA|SE|EURL|SCA|GIE|SEP|SCS"
_EN_TETE = rf"^(?:(?:{_FORMES})(?: |$))+"
_EN_FIN = rf"(?:(?:^| )(?:{_FORMES}))+$"

# Rôles d'un lien de société qu'on descend pour départager des homonymes : ceux que le moteur
# compte (forts et moyens), plus directeur général (53).
ROLES_DESCENTE = sorted(set(STRONG) | set(MEDIUM) | {"53"})

_DESCENDANTS = """
with recursive groupe(siren) as (
    select unnest($depart::varchar[])
    union
    select l.enfant from liens l join groupe g on l.parent = g.siren
     where l.fin is null and list_contains($roles::varchar[], l.role)
)
select siren from groupe
"""


@dataclass(frozen=True)
class Correspondance:
    """Ce que la règle a fait d'une ligne du périmètre."""

    ligne: LignePerimetre
    raison: Raison
    siren: str | None = None  # la société retenue
    nom: str | None = None  # le nom candidat qui a décidé
    porteurs: int = 0  # sociétés actives qui portent ce nom

    @property
    def retenue(self) -> bool:
        return self.raison in RETENUES


def cle(nom: str | None) -> str:
    """La clé de correspondance d'un nom : « Sté Inventée & Cie S.A.S. » → « SOCIETE INVENTEE COMPAGNIE »."""
    s = norm(nom)
    for avec_points, forme in POINTEES:
        s = re.sub(rf"\b{avec_points}\b", forme, s)
    for court, long in ABREVIATIONS:
        s = re.sub(rf"\b{court}\b", long, s)
    s = re.sub(r"\bET\b", "", s)
    s = re.sub(r" +", " ", s).strip()
    s = re.sub(_EN_TETE, "", s)
    return re.sub(_EN_FIN, "", s).strip()


def cle_arrow(noms: pa.Array) -> pa.Array:
    """`cle` sur toute une colonne d'un coup, même résultat."""
    s = norm_arrow(noms)
    for avec_points, forme in POINTEES:
        s = pc.replace_substring_regex(s, rf"\b{avec_points}\b", forme)
    for court, long in ABREVIATIONS:
        s = pc.replace_substring_regex(s, rf"\b{court}\b", long)
    s = pc.replace_substring_regex(s, r"\bET\b", "")
    s = pc.utf8_trim(pc.replace_substring_regex(s, r" +", " "), " ")
    s = pc.replace_substring_regex(s, _EN_TETE, "")
    return pc.utf8_trim(pc.replace_substring_regex(s, _EN_FIN, ""), " ")


def _porteurs(con: duckdb.DuckDBPyConnection, cles: set[str]) -> dict[str, list[tuple[str, str]]]:
    """Pour chaque clé voulue, les sociétés actives qui la portent : (SIREN, commune normalisée)."""
    table = con.execute("""
        select u.siren, u.denomination, coalesce(s.commune, '') commune
        from unites_legales u left join sieges s using (siren)
        where u.etat_administratif = 'A' and u.fin is null and u.denomination is not null
          and (u.categorie_juridique is null or u.categorie_juridique not between 1000 and 1999)
    """).to_arrow_table()
    cles_noms = cle_arrow(table.column("denomination").combine_chunks())
    garde = pc.is_in(cles_noms, value_set=pa.array(sorted(cles), pa.string()))
    sortie: dict[str, list[tuple[str, str]]] = {}
    for k, siren, commune in zip(
        pc.filter(cles_noms, garde).to_pylist(),
        pc.filter(table.column("siren"), garde).to_pylist(),
        pc.filter(table.column("commune"), garde).to_pylist(),
        strict=True,
    ):
        sortie.setdefault(k, []).append((siren, norm(commune)))
    return sortie


def _meme_commune(commune: str, ville: str) -> bool:
    """Même commune, ou un arrondissement de la ville : « PARIS 8 » est à « PARIS » ; « SAINT DENIS »
    n'est pas à « SAINT »."""
    if not ville:
        return False
    reste = commune.removeprefix(ville + " ")
    return commune == ville or (reste != commune and reste.split(" ")[0].isdigit())


def descendants(con: duckdb.DuckDBPyConnection, depart: Iterable[str]) -> set[str]:
    """Les sociétés que les liens de société ouverts relient sous `depart`, `depart` compris."""
    lignes = con.execute(_DESCENDANTS, {"depart": sorted(set(depart)), "roles": ROLES_DESCENTE}).fetchall()
    return {s for (s,) in lignes}


def _une_ligne(
    ligne: LignePerimetre, porteurs: dict[str, list[tuple[str, str]]]
) -> tuple[Correspondance, list[str]]:
    """Étapes 1 et 2 pour une ligne ; rend aussi les homonymes à départager par le registre."""
    attente: tuple[Correspondance, list[str]] | None = None
    for candidat in ligne.candidats:
        societes = porteurs.get(cle(candidat.nom))
        if not societes:
            continue
        if len(societes) == 1 and not candidat.commune_exigee:
            return Correspondance(ligne, UNIQUE, societes[0][0], candidat.nom, 1), []
        v = norm(candidat.ville)
        memes = [s for s, commune in societes if _meme_commune(commune, v)]
        if len(memes) == 1:
            return Correspondance(ligne, COMMUNE, memes[0], candidat.nom, len(societes)), []
        if candidat.commune_exigee:
            continue
        if attente is None:
            homonymes = memes or [s for s, _ in societes]
            attente = Correspondance(ligne, HOMONYMES, None, candidat.nom, len(societes)), homonymes
    return attente or (Correspondance(ligne, INTROUVABLE), [])


def _conflits(sortie: list[Correspondance]) -> list[Correspondance]:
    """Étape 5 : un SIREN retenu pour des lignes de noms différents n'est retenu pour aucune."""
    noms: dict[str, set[str]] = collections.defaultdict(set)
    for c in sortie:
        if c.siren:
            noms[c.siren].add(cle(c.nom))
    return [
        replace(c, raison=CONFLIT, siren=None) if c.siren and len(noms[c.siren]) > 1 else c for c in sortie
    ]


def correspondre(
    con: duckdb.DuckDBPyConnection, tete: str, lignes: list[LignePerimetre]
) -> list[Correspondance]:
    """Applique la règle à chaque ligne du périmètre ; rend une `Correspondance` par ligne, dans l'ordre."""
    voulues = {k for ligne in lignes for c in ligne.candidats if (k := cle(c.nom))}
    porteurs = _porteurs(con, voulues) if voulues else {}

    sortie: list[Correspondance] = []
    en_attente: dict[int, list[str]] = {}  # rang de la ligne -> SIREN des homonymes
    for ligne in lignes:
        resultat, homonymes = _une_ligne(ligne, porteurs)
        if homonymes:
            en_attente[len(sortie)] = homonymes
        sortie.append(resultat)
    sortie = _conflits(sortie)

    if en_attente:
        # Une société mise en équivalence n'est pas contrôlée : ses filiales ne sont pas du groupe.
        depart = {tete} | {c.siren for c in sortie if c.siren and c.ligne.methode == "IG"}
        groupe = descendants(con, depart)
        for rang, sirens in en_attente.items():
            dedans = [s for s in sirens if s in groupe]
            if len(dedans) == 1:
                sortie[rang] = replace(sortie[rang], raison=REGISTRE, siren=dedans[0])
        sortie = _conflits(sortie)
    return sortie
