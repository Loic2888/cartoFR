"""Proposer les réglages d'un groupe avec l'IA, par OpenRouter (T025, T037, FR-008, ARCHI « IA (P2, US3) »).

But : partir d'une page pré-remplie au lieu d'une page blanche. L'IA lit le site et
le rapport annuel du groupe (recherche et lecture web, outils serveur d'OpenRouter) et propose des marques,
des sigles, des maisons (nom légal) et des débuts de nom à exclure, chacun avec
l'URL de sa source. Une règle écrite range ensuite chaque marque : avec des
homonymes au registre, elle est ambiguë (deuxième preuve exigée par le moteur).

Usage (le travail `proposition` de cartofr.jobs.proposition enchaîne ces étapes) :
    entree = lire_entree(con, "LVMH", "775670417")         # registre, lecture seule
    bruts = proposer(entree, client_ia(), modele())         # appel à l'API
    elements = nettoyer(bruts)
    homonymes = compter_homonymes(con, [e.valeur for e in elements if e.type == "marque"],
                                  societes_du_groupe(con, "775670417"))
    ranges = ranger(elements, homonymes)

Entrées : le registre DuckDB (`societes`, `unites_legales`, `liens`), OPENROUTER_API_KEY,
CARTOFR_MODELE_IA (obligatoire, nom OpenRouter ; pas de modèle par défaut, T038).
Sorties : des `ElementRange` (liste des réglages, valeur, source, homonymes).

Règles tenues ici :
- l'IA propose, elle ne décide jamais (principe 1) : ce module ne rend qu'une
  proposition, enregistrée comme version non validée par le travail ;
- ce qui part chez OpenRouter puis le fournisseur du modèle (hors UE, R5) : le nom du groupe, la raison
  sociale, le sigle et le SIREN de la tête et des plus grosses sociétés du groupe. Que des
  données de sociétés publiques : la table des dirigeants personnes physiques
  n'est jamais lue ici (garde-fou 6, principe 6 ; test_proposition.py, C2). Le routage est
  limité aux fournisseurs sans conservation ni collecte (`provider` : zdr, data_collection) ;
- chaque élément gardé de l'IA porte une source http(s) : un élément sans source est écarté ;
- rien de validé ne se perd en silence (principe 2) : les éléments de la dernière version
  validée que l'IA ne repropose pas sont ajoutés à la revue, gardés par défaut (`garder_validees`) ;
- marque ambiguë : au moins une société active au registre, hors de la tête et
  des sociétés qu'elle dirige directement ou non, dont la dénomination, le sigle
  ou l'enseigne commence par la marque. Même normalisation (casse, accents,
  ponctuation) et mêmes formes juridiques en tête que la recherche de candidates
  du moteur (cartofr.moteur.marques) ;
- journaux : des nombres seulement (éléments, requêtes, jetons, recherches, coût), jamais une
  valeur proposée ni un texte de l'API.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass, replace
from typing import Any, Literal

import duckdb

from cartofr.moteur.marques import PREFIXES, TABLE_NOMS, norm, preparer_noms
from cartofr.reglages import MOTIF_TEXTE, TEXTE_MAX

log = logging.getLogger(__name__)

VARIABLE_MODELE = "CARTOFR_MODELE_IA"
VARIABLE_CLE_API = "OPENROUTER_API_KEY"
URL_OPENROUTER = "https://openrouter.ai/api/v1/chat/completions"
DELAI_S = 600.0  # recherche et lecture web côté serveur : la réponse peut prendre des minutes

MAX_FILIALES = 150  # sociétés du groupe données en contexte à l'IA, les plus grosses d'abord (T039)
# Sortie, raisonnement compris (T039) : une proposition exhaustive dépassait 16 000 jetons et
# l'appel de l'outil arrivait coupé. On ne paie que ce qui est produit.
MAX_TOKENS = 64000
MAX_TOURS = 6  # requêtes au plus : la première et les relances
# Budget d'outils serveur (T039) : de quoi parcourir chaque pôle d'activité du groupe. OpenRouter
# plafonne le total d'une requête à 30 (`max_tool_calls`).
RECHERCHES_MAX = 10
LECTURES_MAX = 20
OUTILS_MAX = 30
SOURCE_MAX = 500
OUTIL = "proposer_reglages"

TypeElement = Literal["marque", "sigle", "maison", "exclusion"]
TYPES: tuple[TypeElement, ...] = ("marque", "sigle", "maison", "exclusion")

# Clé de la réponse de l'outil → type d'élément.
CLES_OUTIL: dict[str, TypeElement] = {
    "marques": "marque",
    "sigles": "sigle",
    "maisons": "maison",
    "exclusions": "exclusion",
}

# Liste des réglages où va chaque type (une marque : sûre ou ambiguë selon `ranger`).
LISTE_DU_TYPE: dict[TypeElement, str] = {
    "marque": "marques_sures",
    "sigle": "marques_sigles",
    "maison": "organigramme",
    "exclusion": "exclus_noms",
}

_TEXTE = re.compile(MOTIF_TEXTE)
_URL = re.compile(r"^https?://[^\s\x00-\x1f\x7f]+$")


class PropositionImpossible(RuntimeError):
    """L'API n'a pas rendu de proposition utilisable. Le message est sûr : français, sans donnée."""


class ModeleIaManquant(RuntimeError):
    """CARTOFR_MODELE_IA n'est pas définie : aucun modèle par défaut (T038, choix de Loïc à venir)."""


class CleIaManquante(RuntimeError):
    """OPENROUTER_API_KEY n'est pas définie dans l'environnement du worker."""


@dataclass(frozen=True)
class SocietePublique:
    """Ce qu'on dit d'une société à l'IA : que des champs de société, jamais de personne."""

    siren: str
    nom: str
    sigle: str | None = None


@dataclass(frozen=True)
class Entree:
    """Ce que l'IA reçoit sur le groupe."""

    groupe: str
    tete: SocietePublique
    filiales: tuple[SocietePublique, ...] = ()


@dataclass(frozen=True)
class ElementBrut:
    """Un élément tel que l'IA l'a proposé."""

    type: TypeElement
    valeur: str
    source: str


@dataclass(frozen=True)
class ElementRange:
    """Un élément de la revue : la liste des réglages où il va, et d'où il vient.

    `origine` : « ia » (proposé par l'IA, avec sa source) ou « validee » (déjà dans la
    dernière version validée, que l'IA n'a pas reproposé : pas de source).
    `deja_valide_en` : la liste où la valeur était déjà validée, s'il y en a une.
    """

    liste: str
    valeur: str
    source: str | None
    homonymes: int | None = None  # marques proposées seulement : homonymes au registre
    origine: Literal["ia", "validee"] = "ia"
    deja_valide_en: str | None = None

    def en_json(self) -> dict[str, Any]:
        return {
            "liste": self.liste,
            "valeur": self.valeur,
            "source": self.source,
            "homonymes": self.homonymes,
            "origine": self.origine,
            "deja_valide_en": self.deja_valide_en,
        }


# --- Registre --------------------------------------------------------------------------------


_TETE = """
select s.siren, coalesce(u.denomination, s.denomination) as nom, u.sigle
  from societes s left join unites_legales u on u.siren = s.siren
 where s.siren = $siren
"""

# Sociétés du groupe en vigueur (liens directs ou non depuis la tête), les plus grosses d'abord
# (T039 : les filiales directes seules ne donnaient pas assez de pistes de marques). Personnes
# morales seulement : `societes` ne porte que des personnes morales, et les catégories 1xxx
# sont écartées.
_FILIALES = """
with recursive groupe(siren) as (
    select $siren
    union
    select l.enfant from liens l join groupe g on l.parent = g.siren where l.fin is null
)
select s.siren, coalesce(u.denomination, s.denomination) as nom, u.sigle,
       try_cast(u.tranche_effectifs as integer) as tranche
  from groupe g
  join societes s on s.siren = g.siren
  left join unites_legales u on u.siren = s.siren
 where s.siren <> $siren and s.fin is null
   and coalesce(u.denomination, s.denomination) is not null
   and (u.categorie_juridique is null or u.categorie_juridique not between 1000 and 1999)
 order by tranche desc nulls last, nom, s.siren
 limit $max
"""

_GROUPE = """
with recursive groupe(siren) as (
    select $siren
    union
    select l.enfant from liens l join groupe g on l.parent = g.siren where l.fin is null
)
select siren from groupe
"""


def lire_entree(
    con: duckdb.DuckDBPyConnection, groupe: str, tete_siren: str, max_filiales: int = MAX_FILIALES
) -> Entree:
    """Le contexte donné à l'IA : la tête et les plus grosses sociétés du groupe, lues au registre."""
    ligne = con.execute(_TETE, {"siren": tete_siren}).fetchone()
    tete = (
        SocietePublique(tete_siren, str(ligne[1]).strip(), _ou_rien(ligne[2]))
        if ligne is not None and ligne[1]
        else SocietePublique(tete_siren, groupe)
    )
    filiales = tuple(
        SocietePublique(str(s), str(nom).strip(), _ou_rien(sigle))
        for s, nom, sigle, _tranche in con.execute(
            _FILIALES, {"siren": tete_siren, "max": max_filiales}
        ).fetchall()
    )
    return Entree(groupe=groupe, tete=tete, filiales=filiales)


def societes_du_groupe(con: duckdb.DuckDBPyConnection, tete_siren: str) -> set[str]:
    """La tête et toutes les sociétés qu'elle dirige au registre, directement ou non (liens en vigueur)."""
    return {str(s) for (s,) in con.execute(_GROUPE, {"siren": tete_siren}).fetchall()}


def compter_homonymes(
    con: duckdb.DuckDBPyConnection, marques: Iterable[str], groupe: set[str]
) -> dict[str, int]:
    """Pour chaque marque (clé : la marque telle que donnée), le nombre de sociétés actives
    hors du groupe dont un nom commence par elle, au sens de la recherche de candidates du
    moteur : mot entier, casse, accents et ponctuation ignorés, formes juridiques admises
    devant (« SAS ALPHAMARK » compte, « ALPHAMARKET » non)."""
    a_compter = [m for m in dict.fromkeys(marques) if norm(m)]
    if not a_compter:
        return {}
    preparer_noms(con)
    prefixe = "(?:(?:" + "|".join(PREFIXES) + ") )*"
    con.register("groupe_propose", _table_sirens(groupe))
    try:
        comptes: dict[str, int] = {}
        for marque in a_compter:
            motif = "^" + prefixe + re.escape(norm(marque)) + "( |$)"
            ligne = con.execute(
                f"select count(*) from {TABLE_NOMS} n"
                " where (regexp_matches(n0, $m) or regexp_matches(n1, $m) or regexp_matches(n2, $m))"
                "   and n.siren not in (select siren from groupe_propose)",
                {"m": motif},
            ).fetchone()
            comptes[marque] = int(ligne[0]) if ligne else 0
        return comptes
    finally:
        con.unregister("groupe_propose")


def _table_sirens(sirens: set[str]) -> Any:
    import pyarrow as pa

    return pa.table({"siren": pa.array(sorted(sirens), type=pa.string())})


def _ou_rien(valeur: Any) -> str | None:
    texte = str(valeur).strip() if valeur is not None else ""
    return texte or None


# --- Règles ----------------------------------------------------------------------------------


def nettoyer(bruts: Iterable[ElementBrut]) -> list[ElementBrut]:
    """Garde les éléments utilisables : un texte valide pour les réglages (pas de retour à la
    ligne, 200 caractères au plus) et une source http(s). Doublons (même type, même valeur
    normalisée) retirés, le premier gardé. Rien n'est réécrit, sauf les blancs des bords."""
    vus: set[tuple[str, str]] = set()
    gardes: list[ElementBrut] = []
    for e in bruts:
        valeur, source = e.valeur.strip(), e.source.strip()
        if e.type not in TYPES or len(valeur) > TEXTE_MAX or not _TEXTE.match(valeur) or not norm(valeur):
            continue
        if len(source) > SOURCE_MAX or not _URL.match(source):
            continue
        cle = (e.type, norm(valeur))
        if cle in vus:
            continue
        vus.add(cle)
        gardes.append(ElementBrut(e.type, valeur, source))
    return gardes


def ranger(elements: Iterable[ElementBrut], homonymes: dict[str, int]) -> list[ElementRange]:
    """La règle écrite (US3, scénario 2) : une marque qui a au moins un homonyme au registre va
    dans `marques_ambigues`, sinon dans `marques_sures`. Une marque dont le compte manque est
    rangée ambiguë : dans le doute, la deuxième preuve est exigée. Les autres types vont dans
    leur liste (LISTE_DU_TYPE), sans compte."""
    ranges: list[ElementRange] = []
    for e in elements:
        if e.type == "marque":
            n = homonymes.get(e.valeur)
            liste = "marques_sures" if n == 0 else "marques_ambigues"
            ranges.append(ElementRange(liste, e.valeur, e.source, n))
        else:
            ranges.append(ElementRange(LISTE_DU_TYPE[e.type], e.valeur, e.source))
    return ranges


# Listes que la proposition remplit ; les autres clés viennent de la dernière version validée.
LISTES_PROPOSEES = ("marques_sures", "marques_ambigues", "marques_sigles", "organigramme", "exclus_noms")


def garder_validees(ranges: Iterable[ElementRange], base: dict[str, Any] | None) -> list[ElementRange]:
    """Principe 2 : une proposition ne fait jamais perdre en silence un élément validé par un
    humain. Chaque valeur des listes proposées de la dernière version validée (`base`) :
    - reproposée par l'IA (même valeur normalisée : casse, accents, ponctuation ignorés, dans
      n'importe quelle liste) : l'élément de l'IA reste seul, marqué `deja_valide_en` avec la
      liste validée. Une liste différente se voit donc à la revue ;
    - non reproposée : ajoutée à la fin, origine « validee », dans sa liste, sans source.
      Elle entre dans le contenu proposé : gardée tant que le consultant ne la rejette pas.
    Sans version validée, les éléments de l'IA sont rendus tels quels."""
    ia = list(ranges)
    validees: dict[str, str] = {}  # valeur normalisée → première liste validée
    ordre: list[tuple[str, str]] = []  # chaque (liste, valeur) validée, une fois
    vues: set[tuple[str, str]] = set()
    for liste in LISTES_PROPOSEES:
        valeurs = (base or {}).get(liste)
        if not isinstance(valeurs, list):
            continue
        for v in valeurs:  # pyright: ignore[reportUnknownVariableType]
            if not isinstance(v, str) or not norm(v) or (liste, norm(v)) in vues:
                continue
            vues.add((liste, norm(v)))
            validees.setdefault(norm(v), liste)
            ordre.append((liste, v))
    reproposees = {norm(r.valeur) for r in ia}
    sortie = [
        replace(r, deja_valide_en=validees.get(norm(r.valeur))) if norm(r.valeur) in validees else r
        for r in ia
    ]
    sortie.extend(
        ElementRange(liste, valeur, None, origine="validee", deja_valide_en=liste)
        for liste, valeur in ordre
        if norm(valeur) not in reproposees
    )
    return sortie


def contenu_propose(
    groupe: str, tete: str, ranges: Iterable[ElementRange], base: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Le contenu des réglages proposés : groupe et tête du groupe, les listes proposées, et les
    autres clés (exclusions par SIREN, empreintes de familles, priorités…) reprises telles
    quelles de `base`, la dernière version validée s'il y en a une."""
    contenu: dict[str, Any] = {
        cle: valeur
        for cle, valeur in (base or {}).items()
        if cle not in ("groupe", "tete", *LISTES_PROPOSEES)
    }
    contenu["groupe"] = groupe
    contenu["tete"] = tete
    for cle in LISTES_PROPOSEES:
        contenu[cle] = []
    for r in ranges:
        contenu[r.liste].append(r.valeur)
    return contenu


# --- API -------------------------------------------------------------------------------------


SYSTEME = """Tu aides un consultant à écrire les réglages d'un moteur qui cartographie un groupe \
de sociétés françaises à partir du registre du commerce. Tu proposes ; un humain relit et décide.

Le moteur trouve lui-même les filiales au registre (mandats entre sociétés) : ne cherche pas \
la liste des filiales, ni l'annexe des comptes consolidés. Ce qui lui manque, ce sont les noms \
de marques et de maisons, pour retrouver les sociétés que le registre ne relie pas au groupe. \
Le but est d'être exhaustif : le consultant retire un élément en un clic, mais il ne pense pas \
à ajouter ce qui manque.

Méthode :
1. Trouve la page du site officiel qui liste les pôles d'activité, les marques ou les maisons \
du groupe (« nos marques », « nos maisons », « nos métiers », « nos activités »).
2. Ouvre la page de chaque pôle ou de chaque activité, et relève toutes les marques et \
maisons qu'elle cite, pas seulement les plus connues. Fais de même pour les filiales \
importantes qui ont leur propre site.
3. Sers-toi des sociétés du groupe données plus bas : leurs noms sont des pistes de marques \
et de maisons à vérifier sur le site.
4. N'ouvre un rapport annuel que si le site ne donne pas ces listes, et jamais en entier.

Ce que tu proposes :
- marques : les noms commerciaux sous lesquels les filiales françaises du groupe sont \
immatriculées ou connues (une marque par élément, telle qu'elle s'écrit) ;
- sigles : les sigles du groupe ou de ses maisons (ex. un acronyme du nom du groupe) ;
- maisons : le nom légal exact des principales sociétés ou maisons du groupe en France ;
- exclusions : des débuts de nom de sociétés qui ressemblent au groupe sans en faire partie \
(groupe homonyme, actionnaire familial, ancienne filiale cédée).

Règles :
- Chaque élément porte l'URL exacte de la page que tu as consultée et qui le justifie. \
Pas d'URL inventée : si tu n'as pas de source, n'ajoute pas l'élément.
- Uniquement des noms de sociétés, de marques ou de sigles. Jamais le nom d'une personne \
physique (dirigeant, fondateur, actionnaire), même si une marque le contient : dans ce cas \
écris la marque seule si elle est une marque déposée de société, sinon omets-la.
- Exhaustif sur ce que tes sources citent, mais rien d'inventé : chaque élément vient d'une page lue.
- Termine en appelant l'outil proposer_reglages une seule fois, avec toute ta proposition."""

RELANCE = "Appelle maintenant l'outil proposer_reglages avec ta proposition, sources comprises."


def _schema_liste(description: str) -> dict[str, Any]:
    return {
        "type": "array",
        "description": description,
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["nom", "source"],
            "properties": {
                "nom": {"type": "string", "description": "Le nom, tel qu'il s'écrit."},
                "source": {"type": "string", "description": "URL http(s) de la page qui le justifie."},
            },
        },
    }


OUTIL_PROPOSITION: dict[str, Any] = {
    "name": OUTIL,
    "description": "Enregistre la proposition de réglages du groupe, chaque élément avec sa source.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": list(CLES_OUTIL),
        "properties": {
            "marques": _schema_liste("Marques des filiales françaises du groupe."),
            "sigles": _schema_liste("Sigles du groupe ou de ses maisons."),
            "maisons": _schema_liste("Nom légal exact des principales sociétés ou maisons en France."),
            "exclusions": _schema_liste("Débuts de nom de sociétés à exclure (homonymes, actionnaires)."),
        },
    },
}


def message_utilisateur(entree: Entree) -> str:
    """Le texte envoyé à l'IA : que des données de sociétés (nom, sigle, SIREN)."""
    lignes = [
        f"Groupe : {entree.groupe}",
        f"Société de tête : {_decrire(entree.tete)}",
    ]
    if entree.filiales:
        lignes.append("Sociétés du groupe au registre (les plus grosses d'abord) :")
        lignes.extend(f"- {_decrire(f)}" for f in entree.filiales)
    lignes.append("")
    lignes.append("Propose les réglages de ce groupe pour la France, avec une source pour chaque élément.")
    return "\n".join(lignes)


def _decrire(s: SocietePublique) -> str:
    sigle = f" ({s.sigle})" if s.sigle else ""
    return f"{s.nom}{sigle}, SIREN {s.siren}"


def construire_requete(entree: Entree, modele: str) -> dict[str, Any]:
    """Le corps de la requête OpenRouter (POST /chat/completions, format OpenAI).

    La recherche et la lecture web sont des outils serveur d'OpenRouter : il les exécute
    lui-même et ne rend au worker que l'appel de l'outil de proposition. `provider` limite le
    routage aux fournisseurs sans conservation ni collecte des données (R5, T037)."""
    return {
        "model": modele,
        "max_tokens": MAX_TOKENS,
        "messages": [
            {"role": "system", "content": SYSTEME},
            {"role": "user", "content": message_utilisateur(entree)},
        ],
        "tools": [
            {"type": "openrouter:web_search", "parameters": {"max_uses": RECHERCHES_MAX}},
            {"type": "openrouter:web_fetch", "parameters": {"max_uses": LECTURES_MAX}},
            {
                "type": "function",
                "function": {
                    "name": OUTIL_PROPOSITION["name"],
                    "description": OUTIL_PROPOSITION["description"],
                    "parameters": OUTIL_PROPOSITION["input_schema"],
                    "strict": True,
                },
            },
        ],
        "tool_choice": "auto",
        "max_tool_calls": OUTILS_MAX,
        "provider": {"data_collection": "deny", "zdr": True},
    }


def modele() -> str:
    """Le modèle (nom OpenRouter, ex. « fournisseur/modele ») : CARTOFR_MODELE_IA, obligatoire.
    Pas de modèle par défaut : le choix se fait sur l'essai comparatif (T038 C4)."""
    nom = os.environ.get(VARIABLE_MODELE, "").strip()
    if not nom:
        raise ModeleIaManquant(
            f"La variable {VARIABLE_MODELE} n'est pas définie : choisissez le modèle de l'IA "
            "(nom OpenRouter)."
        )
    return nom


class ClientOpenRouter:
    """Envoie une requête à OpenRouter et rend la réponse JSON. La clé est lue dans
    OPENROUTER_API_KEY et ne sort que dans l'en-tête Authorization. Une erreur HTTP devient
    PropositionImpossible ; le journal n'en garde que le statut, jamais le corps."""

    def __init__(self, cle: str, url: str = URL_OPENROUTER, delai: float = DELAI_S) -> None:
        self._cle = cle
        self._url = url
        self._delai = delai

    def envoyer(self, corps: dict[str, Any]) -> dict[str, Any]:
        import httpx

        try:
            reponse = httpx.post(
                self._url,
                json=corps,
                headers={"Authorization": f"Bearer {self._cle}", "X-Title": "cartoFR"},
                timeout=self._delai,
            )
        except httpx.HTTPError as e:
            log.warning("proposition IA : OpenRouter injoignable (%s)", type(e).__name__)
            raise PropositionImpossible("Le service d'IA est injoignable. Réessayez plus tard.") from None
        if reponse.status_code in (401, 403):
            log.warning("proposition IA : OpenRouter refuse la clé (HTTP %s)", reponse.status_code)
            raise PropositionImpossible("La clé du service d'IA est refusée : prévenez l'administrateur.")
        if reponse.status_code == 402:
            log.warning("proposition IA : crédit OpenRouter épuisé (HTTP 402)")
            raise PropositionImpossible("Le crédit du service d'IA est épuisé : prévenez l'administrateur.")
        if reponse.status_code >= 400:
            log.warning("proposition IA : OpenRouter répond HTTP %s", reponse.status_code)
            raise PropositionImpossible("Le service d'IA a renvoyé une erreur. Réessayez plus tard.")
        try:
            donnees = reponse.json()
        except ValueError:
            raise PropositionImpossible("La réponse du service d'IA est illisible.") from None
        if not isinstance(donnees, dict):
            raise PropositionImpossible("La réponse du service d'IA est illisible.")
        return donnees  # pyright: ignore[reportUnknownVariableType]


def client_ia() -> ClientOpenRouter:
    """Un client OpenRouter, la clé lue dans OPENROUTER_API_KEY (jamais écrite ailleurs)."""
    cle = os.environ.get(VARIABLE_CLE_API, "").strip()
    if not cle:
        raise CleIaManquante(
            f"La variable {VARIABLE_CLE_API} n'est pas définie : le worker ne peut pas appeler l'IA."
        )
    return ClientOpenRouter(cle)


def _message(reponse: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """Le message de l'assistant et la raison de fin du premier choix ; illisible : erreur."""
    if isinstance(reponse.get("error"), dict):
        raise PropositionImpossible("Le service d'IA a renvoyé une erreur. Réessayez plus tard.")
    choix = reponse.get("choices")
    if not isinstance(choix, list) or not choix or not isinstance(choix[0], dict):
        raise PropositionImpossible("La réponse du service d'IA est illisible.")
    premier: dict[str, Any] = choix[0]  # pyright: ignore[reportUnknownVariableType]
    message = premier.get("message")
    if not isinstance(message, dict):
        raise PropositionImpossible("La réponse du service d'IA est illisible.")
    fin = premier.get("finish_reason")
    return message, fin if isinstance(fin, str) else None  # pyright: ignore[reportUnknownVariableType]


@dataclass
class Consommation:
    """Ce qu'a coûté une proposition, additionné sur les requêtes (champ `usage` d'OpenRouter).
    `cout` : en dollars, quand OpenRouter le donne. Des nombres seulement, jamais un texte."""

    requetes: int = 0
    jetons_entree: int = 0
    jetons_sortie: int = 0
    recherches_web: int = 0
    cout: float | None = None

    def ajouter(self, reponse: dict[str, Any]) -> None:
        self.requetes += 1
        usage = reponse.get("usage")
        if not isinstance(usage, dict):
            return
        self.jetons_entree += _entier(usage.get("prompt_tokens"))  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        self.jetons_sortie += _entier(usage.get("completion_tokens"))  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        # Champ d'OpenRouter : `server_tool_use_details` (relevé le 2026-10-10) ; l'ancien nom reste lu.
        outils = usage.get("server_tool_use_details") or usage.get("server_tool_use")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if isinstance(outils, dict):
            self.recherches_web += _entier(outils.get("web_search_requests"))  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        cout = usage.get("cost")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if isinstance(cout, int | float) and not isinstance(cout, bool):
            self.cout = (self.cout or 0.0) + float(cout)

    def journaliser(self, modele: str) -> None:
        cout = "inconnu" if self.cout is None else f"{self.cout:.4f} $"
        log.info(
            "proposition IA : modèle %s, %s requêtes, %s jetons en entrée, %s en sortie, "
            "%s recherches web, coût %s",
            modele,
            self.requetes,
            self.jetons_entree,
            self.jetons_sortie,
            self.recherches_web,
            cout,
        )


def _entier(valeur: Any) -> int:
    return valeur if isinstance(valeur, int) and not isinstance(valeur, bool) and valeur > 0 else 0


def appeler(
    client: Any,
    requete: dict[str, Any],
    max_tours: int = MAX_TOURS,
    conso: Consommation | None = None,
) -> dict[str, Any]:
    """Interroge l'IA jusqu'à l'appel de l'outil de proposition, et rend ses arguments.

    Fin sans appel de l'outil : le message est gardé et une relance est envoyée. Refus
    (`refusal` ou filtre de contenu), réponse tronquée, arguments illisibles ou trop de
    tours : PropositionImpossible. `conso`, s'il est donné, additionne les jetons de chaque
    réponse, même quand l'appel finit en erreur.
    """
    messages = list(requete["messages"])
    for _ in range(max_tours):
        reponse = client.envoyer({**requete, "messages": messages})
        if conso is not None and isinstance(reponse, dict):
            conso.ajouter(reponse)  # pyright: ignore[reportUnknownArgumentType]
        message, fin = _message(reponse)  # pyright: ignore[reportUnknownArgumentType]
        if message.get("refusal") or fin == "content_filter":
            raise PropositionImpossible("L'IA a refusé de faire la proposition.")
        if fin == "length":  # avant les appels : leurs arguments seraient coupés
            raise PropositionImpossible("La réponse de l'IA a été tronquée.")
        appels = message.get("tool_calls")
        for appel in appels if isinstance(appels, list) else []:  # pyright: ignore[reportUnknownVariableType]
            fonction = appel.get("function") if isinstance(appel, dict) else None  # pyright: ignore[reportUnknownMemberType]
            if not isinstance(fonction, dict) or fonction.get("name") != OUTIL:  # pyright: ignore[reportUnknownMemberType]
                continue
            try:
                arguments = json.loads(fonction.get("arguments") or "")  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
            except (TypeError, ValueError):
                raise PropositionImpossible("La proposition de l'IA est illisible.") from None
            if not isinstance(arguments, dict):
                raise PropositionImpossible("La proposition de l'IA est illisible.")
            return dict(arguments)  # pyright: ignore[reportUnknownArgumentType]
        messages.append({"role": "assistant", "content": message.get("content") or ""})
        messages.append({"role": "user", "content": RELANCE})
    raise PropositionImpossible("L'IA n'a pas rendu de proposition.")


def lire_reponse(entree: dict[str, Any]) -> list[ElementBrut]:
    """Les éléments de la réponse de l'outil. Ce qui n'a pas la forme attendue est ignoré."""
    elements: list[ElementBrut] = []
    for cle, type_element in CLES_OUTIL.items():
        valeurs = entree.get(cle)
        if not isinstance(valeurs, list):
            continue
        for v in valeurs:  # pyright: ignore[reportUnknownVariableType]
            if isinstance(v, dict) and isinstance(v.get("nom"), str) and isinstance(v.get("source"), str):  # pyright: ignore[reportUnknownMemberType]
                elements.append(ElementBrut(type_element, v["nom"], v["source"]))  # pyright: ignore[reportUnknownArgumentType]
    return elements


def proposer(entree: Entree, client: Any, nom_modele: str) -> list[ElementBrut]:
    """Demande la proposition à l'IA et rend ses éléments bruts (à passer à `nettoyer`)."""
    conso = Consommation()
    try:
        bruts = lire_reponse(appeler(client, construire_requete(entree, nom_modele), conso=conso))
    finally:
        conso.journaliser(nom_modele)
    log.info("proposition IA : %s éléments reçus", len(bruts))
    return bruts
