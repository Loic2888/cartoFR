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
à défaut, le premier porté par des homonymes passe à l'étape 3. Un candidat de secours (ville
comprise dans le nom, côté d'un nom double, T053) n'est essayé que si aucun candidat d'avant, hors
secours, n'a d'homonymes.

Usage :
    con = duckdb.connect(str(registre), read_only=True)
    resultats = correspondre(con, tete_siren, extraire(texte))
    par_document = correspondre_plusieurs(con, [(tete_a, lignes_a), (tete_b, lignes_b)])
Entrées : une connexion au registre, le SIREN de la tête, les lignes d'`extraction`.
Sorties : une `Correspondance` par ligne, retenue ou non, avec sa raison.
`correspondre_plusieurs` lit les noms de SIRENE une seule fois pour tous les documents (T046) :
c'est cette lecture qui coûte, 25 s environ, plus 7 s pour l'étape 6 (mesuré le 2026-10-21) ; le
résultat est celui de `correspondre` document par document.
Un candidat marqué `sigle` (format ESEF, T049) est cherché parmi les sigles de SIRENE et non les
dénominations, par la même règle. Les formats de T054 en ont aussi, de secours, depuis T055 (le nom
sans sigle final, parmi les sigles : « PREDICA », « UBAF »). Les formats VINCI et LVMH n'en ont
jamais : leurs résultats ne changent pas.

Étape 6 (T055, 2026-10-21), pour les seules lignes encore introuvables : une ligne déjà retenue ou
à homonymes ne change jamais, et une société déjà retenue aux étapes 1 à 5 n'est pas reprise par
l'étape 6. Seuls les candidats sûrs y sont essayés : ni ceux qui exigent la commune, ni ceux de
secours. Dans l'ordre :
- une ligne de fonds (FCP, FCT, compartiment…) n'est pas une société : `fonds`, refusée ;
- le nom est la raison sociale de sociétés fermées seulement : `fermee`, refusée (fusionnée depuis
  la liste). Elle passe avant les règles suivantes : une enseigne ne vaut pas une raison sociale ;
- le nom sans ses espaces (« CRFP22 » pour « CRFP 22 »), 6 caractères au moins : `compacte` ;
- le nom est la dénomination usuelle SIRENE d'une société : `usuelle` ;
  pour ces deux règles, la société est retenue si elle est la seule à porter le nom parmi les
  sociétés que le registre relie au groupe, ou dans la ville du document. Être seule en France ne
  suffit pas : une dénomination usuelle est souvent une enseigne (« Franck & Fils », dénomination
  usuelle d'une société de travaux de Menton, revue T055). Seule exception, un nom-code sans
  espaces (un chiffre, ou 10 caractères au moins : « SOLAIREGREOUX1 ») seul en France ;
- le nom, de trois mots au moins, est le début de la raison sociale d'une seule société active que
  le registre relie au groupe, tête exclue : `debut`.
Puis la règle des conflits, entre les seules lignes de l'étape 6.
Seuls les dénominations et sigles des sociétés sont lus : jamais `dirigeants_personnes` (garde-fou 6).
"""

import collections
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from typing import Any, Literal

import duckdb
import pyarrow as pa
import pyarrow.compute as _pc

from cartofr.moteur.marques import norm, norm_arrow
from cartofr.moteur.moteur import MEDIUM, STRONG
from cartofr.perimetre.extraction import MOTIF_FONDS, LignePerimetre

pc: Any = _pc  # fonctions générées à l'exécution : inconnues du vérificateur de types

Raison = Literal[
    "unique", "commune", "registre", "compacte", "usuelle", "debut",
    "homonymes", "introuvable", "conflit", "fonds", "fermee",
]  # fmt: skip
UNIQUE: Raison = "unique"
COMMUNE: Raison = "commune"
REGISTRE: Raison = "registre"
HOMONYMES: Raison = "homonymes"
INTROUVABLE: Raison = "introuvable"
CONFLIT: Raison = "conflit"
COMPACTE: Raison = "compacte"
USUELLE: Raison = "usuelle"
DEBUT: Raison = "debut"
FONDS: Raison = "fonds"
FERMEE: Raison = "fermee"
RETENUES: tuple[Raison, ...] = (UNIQUE, COMMUNE, REGISTRE, COMPACTE, USUELLE, DEBUT)
# Une clé sans espaces plus courte rejoint trop de noms sans rapport (« CPR AM », « C'PRAM »).
COMPACTE_MIN = 6
CODE_MIN = 10  # un nom sans espaces de cette longueur, ou avec un chiffre, est un nom-code
DEBUT_MOTS = 3  # « Société Générale » est le début de trop de raisons sociales
COMPACT = "\x03"  # préfixe des clés sans espaces dans la table des porteurs
USUEL = "\x04"  # préfixe des clés de dénomination usuelle
FERME = "\x05"  # préfixe des clés des sociétés fermées
SIGLE = "\x02"  # préfixe des clés de sigle dans la table des porteurs

# Clé d'un nom, après `norm` : sigles espacés recollés, formes écrites avec des points comprises
# (« S.A.S. » → « SAS », « M H C S » → « MHCS », T053), abréviations développées (« ST » →
# « SAINT », T053), « ET » retiré, formes juridiques retirées en tête et en fin seulement
# (« SE LOGER SA » → « SE LOGER »). Mêmes expressions côté Python et côté Arrow (testé).
ABREVIATIONS = (("STE", "SOCIETE"), ("CIE", "COMPAGNIE"), ("ETS", "ETABLISSEMENTS"), ("ST", "SAINT"))
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
    # Sigle espacé, sans lookahead (Arrow n'en a pas) : chaque espace est doublée, une lettre seule
    # est encadrée de \x01 ; deux lettres seules voisines se touchent par « \x01\x01 », retiré.
    # Une lettre seule dans un nom (« D ART ») reste seule. Le sigle entier est recollé avant de
    # reconnaître une forme juridique : « S.N.C.F. » donne « SNCF », pas « SNC F » (revue T053).
    # Limite : une forme collée à un sigle (« M H C S S A ») reste dans le sigle, « MHCSSA ».
    s = re.sub(r" ([A-Z]) ", "\x01\\1\x01", " " + norm(nom).replace(" ", "  ") + " ")
    s = s.replace("\x01\x01", "").replace("\x01", " ")
    for court, long in ABREVIATIONS:
        s = re.sub(rf"\b{court}\b", long, s)
    s = re.sub(r"\bET\b", "", s)
    s = re.sub(r" +", " ", s).strip()
    s = re.sub(_EN_TETE, "", s)
    return re.sub(_EN_FIN, "", s).strip()


def cle_arrow(noms: pa.Array) -> pa.Array:
    """`cle` sur toute une colonne d'un coup, même résultat."""
    s = norm_arrow(noms)
    s = pc.binary_join_element_wise(" ", pc.replace_substring(s, " ", "  "), " ", "")
    s = pc.replace_substring_regex(s, r" ([A-Z]) ", "\x01\\1\x01")
    s = pc.replace_substring(pc.replace_substring(s, "\x01\x01", ""), "\x01", " ")
    for court, long in ABREVIATIONS:
        s = pc.replace_substring_regex(s, rf"\b{court}\b", long)
    s = pc.replace_substring_regex(s, r"\bET\b", "")
    s = pc.utf8_trim(pc.replace_substring_regex(s, r" +", " "), " ")
    s = pc.replace_substring_regex(s, _EN_TETE, "")
    return pc.utf8_trim(pc.replace_substring_regex(s, _EN_FIN, ""), " ")


def _porteurs(
    con: duckdb.DuckDBPyConnection, cles: set[str], colonne: str = "denomination", prefixe: str = ""
) -> dict[str, list[tuple[str, str]]]:
    """Pour chaque clé voulue, les sociétés actives qui la portent : (SIREN, commune normalisée).
    `colonne` : `denomination`, ou `sigle` (clés rendues avec `prefixe`)."""
    if colonne not in ("denomination", "sigle"):
        raise ValueError(colonne)
    table = con.execute(f"""
        select u.siren, u.{colonne} nom, coalesce(s.commune, '') commune
        from unites_legales u left join sieges s using (siren)
        where u.etat_administratif = 'A' and u.fin is null and u.{colonne} is not null
          and (u.categorie_juridique is null or u.categorie_juridique not between 1000 and 1999)
    """).to_arrow_table()
    return _garder(table, cle_arrow(table.column("nom").combine_chunks()), cles, prefixe)


def _garder(
    table: pa.Table, cles_noms: pa.Array, cles: set[str], prefixe: str
) -> dict[str, list[tuple[str, str]]]:
    """Les lignes de `table` dont la clé est voulue, rangées par clé (avec `prefixe`)."""
    garde = pc.is_in(cles_noms, value_set=pa.array(sorted(cles), pa.string()))
    sortie: dict[str, list[tuple[str, str]]] = {}
    for k, siren, commune in zip(
        pc.filter(cles_noms, garde).to_pylist(),
        pc.filter(table.column("siren"), garde).to_pylist(),
        pc.filter(table.column("commune"), garde).to_pylist(),
        strict=True,
    ):
        sortie.setdefault(prefixe + k, []).append((siren, norm(commune)))
    return sortie


def compacte(k: str) -> str:
    """La clé sans ses espaces : « CRFP 22 » et « CRFP22 » se rejoignent (T055)."""
    return k.replace(" ", "")


@dataclass(frozen=True)
class _Actives:
    """Les dénominations des sociétés actives et leurs clés, lues une fois pour les étapes 1 et 6."""

    table: pa.Table  # siren, nom, commune
    cles: pa.Array


def _lire_actives(con: duckdb.DuckDBPyConnection) -> _Actives:
    table = con.execute("""
        select u.siren, u.denomination nom, coalesce(s.commune, '') commune
        from unites_legales u left join sieges s using (siren)
        where u.etat_administratif = 'A' and u.fin is null and u.denomination is not null
          and (u.categorie_juridique is null or u.categorie_juridique not between 1000 and 1999)
    """).to_arrow_table()
    return _Actives(table, cle_arrow(table.column("nom").combine_chunks()))


def _porteurs_etape_6(
    con: duckdb.DuckDBPyConnection, cles: set[str], actives: _Actives
) -> dict[str, list[tuple[str, str]]]:
    """Les porteurs de l'étape 6 : clés sans espaces des actives (`COMPACT`, sur les clés déjà
    calculées), dénominations usuelles des actives (`USUEL`), dénominations des fermées (`FERME`).
    Les fermées sont d'abord filtrées par DuckDB sur le mot le plus long de chaque clé : on ne
    calcule la clé que de quelques milliers de noms, pas de 4 millions."""
    sortie = _garder(
        actives.table, pc.replace_substring(actives.cles, " ", ""), {compacte(k) for k in cles}, COMPACT
    )
    usuelles = con.execute("""
        select u.siren, u.denomination_usuelle_1 u1, u.denomination_usuelle_2 u2, u.denomination_usuelle_3 u3,
               coalesce(s.commune, '') commune
        from unites_legales u left join sieges s using (siren)
        where u.etat_administratif = 'A' and u.fin is null
          and coalesce(u.denomination_usuelle_1, u.denomination_usuelle_2,
                       u.denomination_usuelle_3) is not null
          and (u.categorie_juridique is null or u.categorie_juridique not between 1000 and 1999)
    """).to_arrow_table()
    for colonne in ("u1", "u2", "u3"):
        avec = usuelles.filter(pc.is_valid(usuelles.column(colonne)))
        for k, porteurs in _garder(
            avec, cle_arrow(avec.column(colonne).combine_chunks()), cles, USUEL
        ).items():
            deja = sortie.setdefault(k, [])
            deja.extend(p for p in porteurs if p not in deja)
    mots = sorted({max(k.split(), key=len) for k in cles})
    fermees = con.execute(
        """
        select u.siren, u.denomination nom, '' commune from unites_legales u
        where u.etat_administratif <> 'A' and u.fin is null and u.denomination is not null
          and (u.categorie_juridique is null or u.categorie_juridique not between 1000 and 1999)
          and regexp_matches(upper(strip_accents(u.denomination)), $motif)
        """,
        # Une seule expression (RE2, sans retour arrière) : `list_has_any` sur `string_split` a levé
        # une erreur interne de DuckDB 1.5, par intermittence (2026-10-21).
        {"motif": "(^|[^A-Z0-9])(" + "|".join(re.escape(m) for m in mots) + ")([^A-Z0-9]|$)"},
    ).to_arrow_table()
    return sortie | _garder(fermees, cle_arrow(fermees.column("nom").combine_chunks()), cles, FERME)


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
    attente_sure = False  # les homonymes en attente viennent d'un candidat qui n'est pas de secours
    for candidat in ligne.candidats:
        if candidat.secours and attente_sure:
            break  # les homonymes d'un nom plus sûr passent avant : le registre les départage
        societes = porteurs.get((SIGLE if candidat.sigle else "") + cle(candidat.nom))
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
            attente_sure = not candidat.secours
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
    return correspondre_plusieurs(con, [(tete, lignes)])[0]


def correspondre_plusieurs(
    con: duckdb.DuckDBPyConnection, documents: Sequence[tuple[str, list[LignePerimetre]]]
) -> list[list[Correspondance]]:
    """`correspondre` pour plusieurs documents (tête, lignes), avec une seule lecture des noms."""
    candidats = [c for _, lignes in documents for ligne in lignes for c in ligne.candidats]
    voulues = {k for c in candidats if not c.sigle and (k := cle(c.nom))}
    sigles = {k for c in candidats if c.sigle and (k := cle(c.nom))}
    actives = _lire_actives(con)
    porteurs = _garder(actives.table, actives.cles, voulues, "") if voulues else {}
    if sigles:
        porteurs |= _porteurs(con, sigles, "sigle", SIGLE)
    resultats = [_document(con, tete, lignes, porteurs) for tete, lignes in documents]
    # Étape 6 : les noms des lignes encore introuvables seulement.
    restantes = {
        k for res in resultats for c in res if c.raison == INTROUVABLE
        for cand in c.ligne.candidats
        if not (cand.sigle or cand.commune_exigee or cand.secours) and (k := cle(cand.nom))
    }  # fmt: skip
    if not restantes:
        return resultats
    porteurs |= _porteurs_etape_6(con, restantes, actives)
    return [_etape_6(con, tete, res, porteurs) for (tete, _), res in zip(documents, resultats, strict=True)]


def _document(
    con: duckdb.DuckDBPyConnection,
    tete: str,
    lignes: list[LignePerimetre],
    porteurs: dict[str, list[tuple[str, str]]],
) -> list[Correspondance]:
    """Les étapes 1 à 5 pour un document, sur les porteurs déjà lus."""
    sortie: list[Correspondance] = []
    en_attente: dict[int, list[str]] = {}  # rang de la ligne -> SIREN des homonymes
    for ligne in lignes:
        resultat, homonymes = _une_ligne(ligne, porteurs)
        if homonymes:
            en_attente[len(sortie)] = homonymes
        sortie.append(resultat)
    sortie = _conflits(sortie)

    if en_attente:
        groupe = _groupe(con, tete, sortie)
        for rang, sirens in en_attente.items():
            dedans = [s for s in sirens if s in groupe]
            if len(dedans) == 1:
                sortie[rang] = replace(sortie[rang], raison=REGISTRE, siren=dedans[0])
        sortie = _conflits(sortie)
    return sortie


def _groupe(con: duckdb.DuckDBPyConnection, tete: str, sortie: Sequence[Correspondance]) -> set[str]:
    """Les sociétés que le registre relie au groupe : sous la tête et les sociétés contrôlées déjà
    retenues. Une société mise en équivalence n'est pas contrôlée : ses filiales ne sont pas du groupe."""
    return descendants(con, {tete} | {c.siren for c in sortie if c.siren and c.ligne.controlee})


_DENOMINATIONS = """
select u.siren, u.denomination from unites_legales u
 where u.siren in (select unnest($s::varchar[])) and u.fin is null and u.denomination is not null
   and u.etat_administratif = 'A'
"""


def _etape_6(
    con: duckdb.DuckDBPyConnection,
    tete: str,
    sortie: list[Correspondance],
    porteurs: dict[str, list[tuple[str, str]]],
) -> list[Correspondance]:
    """L'étape 6 pour un document : les lignes introuvables, règle par règle (voir le docstring du module)."""
    rangs = [i for i, c in enumerate(sortie) if c.raison == INTROUVABLE]
    if not rangs:
        return sortie
    groupe = _groupe(con, tete, sortie)
    debuts = [(cle(n), s) for s, n in con.execute(_DENOMINATIONS, {"s": sorted(groupe - {tete})}).fetchall()]
    deja = {c.siren for c in sortie if c.retenue}
    nouvelles = {}
    for i in rangs:
        c6 = _une_ligne_6(sortie[i], porteurs, groupe, debuts)
        # Une société déjà retenue aux étapes 1 à 5 n'est pas reprise : la règle la moins sûre ne
        # met jamais en conflit une ligne plus sûre (revue T055).
        nouvelles[i] = sortie[i] if c6.siren in deja else c6
    resolues = _conflits(list(nouvelles.values()))
    sortie = list(sortie)
    for i, c6 in zip(nouvelles, resolues, strict=True):
        sortie[i] = c6
    return sortie


def _une_ligne_6(
    c: Correspondance,
    porteurs: dict[str, list[tuple[str, str]]],
    groupe: set[str],
    debuts: list[tuple[str, str]],
) -> Correspondance:
    ligne = c.ligne
    if ligne.candidats and MOTIF_FONDS.search(ligne.candidats[0].nom):
        return replace(c, raison=FONDS)
    # Les candidats sûrs seulement : un nom qui exige la commune, ou de secours, est déjà une hypothèse.
    candidats = [
        (cand.nom, k, norm(cand.ville))
        for cand in ligne.candidats
        if not (cand.sigle or cand.commune_exigee or cand.secours) and (k := cle(cand.nom))
    ]
    if any(FERME + k in porteurs for _, k, _ in candidats):
        return replace(c, raison=FERMEE)
    for prefixe, raison in ((COMPACT, COMPACTE), (USUEL, USUELLE)):
        for nom, k, ville in candidats:
            cle_cherchee = compacte(k) if prefixe == COMPACT else k
            if prefixe == COMPACT and len(cle_cherchee) < COMPACTE_MIN:
                continue  # « CPR AM » n'est pas « C'PRAM »
            societes = porteurs.get(prefixe + cle_cherchee, [])
            sirens = {s for s, _ in societes}
            dedans = sirens & groupe
            ici = {s for s, commune in societes if _meme_commune(commune, ville)}
            code = prefixe == COMPACT and (
                len(cle_cherchee) >= CODE_MIN or any(ch.isdigit() for ch in cle_cherchee)
            )
            if len(dedans) == 1:
                choisie = next(iter(dedans))
            elif len(ici) == 1:
                choisie = next(iter(ici))
            elif code and len(sirens) == 1:
                choisie = next(iter(sirens))
            else:
                continue
            return replace(c, raison=raison, siren=choisie, nom=nom, porteurs=len(sirens))
    for nom, k, _ in candidats:
        if len(k.split()) < DEBUT_MOTS:
            continue
        trouvees = {s for d, s in debuts if d.startswith(k + " ")}
        if len(trouvees) == 1:
            return replace(c, raison=DEBUT, siren=trouvees.pop(), nom=nom, porteurs=1)
    return c
