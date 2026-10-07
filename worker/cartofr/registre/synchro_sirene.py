"""Applique au registre les changements SIRENE d'une journée (API Sirene de l'INSEE).

But : tenir `societes`, `unites_legales` et `sieges` à jour avec les unités
légales et les établissements sièges que l'INSEE a traités un jour donné.

Usage, depuis la racine du dépôt :
    .venv/bin/python -m cartofr.registre.synchro_sirene --jour 2026-10-05 [--registre data/registre.duckdb]

Entrées :
    - INSEE_API_KEY : clé de l'API Sirene, lue dans l'environnement ;
      `charger_env()` la prend dans le fichier CARTOFR_ENV_FILE (`.env` par défaut).
    - le registre `<CARTOFR_DATA>/registre.duckdb` (ou `--registre`).
Sorties :
    - `societes`, `unites_legales` et `sieges` mis à jour, une ligne `sirene`
      dans `mises_a_jour` ;
    - sur la sortie standard, des volumes seulement.

Ce que dit l'API (Sirene 3.11, sonde du 2026-10-07) :
    - `GET /siren?q=…` et `GET /siret?q=…`, en-tête `X-INSEE-Api-Key-Integration`.
    - Jour J : `dateDernierTraitementUniteLegale:[J T00:00:00 TO J T23:59:59]`
      (idem `dateDernierTraitementEtablissement`). Le 2026-10-05 : 21 864 unités
      légales, 8 062 hors entrepreneurs individuels ; 6 204 sièges hors EI.
    - Les entrepreneurs individuels (catégorie 1000) sont exclus dans la requête :
      `-periode(categorieJuridiqueUniteLegale:1000)` sur /siren,
      `-categorieJuridiqueUniteLegale:1000` sur /siret. Leur nom est celui d'une personne.
    - `champs` limite les champs rendus ; les champs historisés (état, dénomination,
      catégorie, activité) arrivent dans `periodesUniteLegale` / `periodesEtablissement`,
      la période en cours ayant `dateFin` vide.
    - Pagination : `curseur=*` puis `curseurSuivant`, jusqu'à ce qu'il égale le
      curseur envoyé. `nombre` va jusqu'à 1 000.
    - 404 : aucun résultat. 429 : plus de 30 requêtes par minute (`Retry-After`).

Règles d'application :
    - Minimisation (règle produit 4) : seuls les champs de `CHAMPS_UNITES` et
      `CHAMPS_ETABLISSEMENTS` sont demandés. Aucun prénom, nom de naissance ou
      d'usage, pseudonyme ni sexe. Une valeur masquée (`[ND]`) vaut vide.
    - `societes` : `non_diffusible`, `etat_administratif` et `date_creation` suivent
      SIRENE. La cessation observée (état qui passe à 'C') ferme la société :
      `fin` = début de la période cessée, jamais avant `debut`. Une réactivation
      ('C' qui repasse à 'A') rouvre `fin`. Rien n'est supprimé (principe 4). Les
      sociétés déjà cessées au chargement initial gardent `fin` vide, comme lui.
    - Une unité légale active absente de `societes` y entre, avec `debut` = le jour.
      `diffusion_commerciale` reste vide : c'est une donnée RNE.
    - `unites_legales` (T013, sert la recherche des marques) : personnes morales
      seulement, catégorie juridique connue et jamais 1000, aucune colonne de
      personne. Une unité connue est mise à jour ; une inconnue y entre avec
      `debut` = le jour, cessée ou non, comme au chargement initial (la
      cessation se lit dans `etat_administratif`, `fin` reste vide). Unité non
      diffusible : une valeur masquée ou vide ne remplace pas la valeur connue.
      Unité diffusible : la fiche fait foi (un sigle retiré est vidé).
      Dénomination, catégorie et état ne sont jamais vidés.
    - `sieges` : le siège actif d'une unité active (règles de `build_sieges.py`,
      dont `adresse_cle`) est mis à jour ou ajouté, clé SIREN. Un siège fermé ou
      une unité cessée n'y change rien : la table n'a ni `debut` ni `fin`, et la
      synchro ne fait jamais de DELETE. Un siège non diffusible est ignoré.
    - Tout est lu avant d'écrire, puis appliqué dans une seule transaction : un
      échec, réseau ou base, laisse le registre tel qu'il était, et le journal
      dit `echec` (message sans donnée personnelle).

Le module ne journalise ni nom ni identifiant, et jamais la clé d'API. Il compte.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections import deque
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
import httpx
import pyarrow as pa

from cartofr.registre import journal
from cartofr.registre.inpi_diff import charger_env

BASE = "https://api.insee.fr/api-sirene/3.11"
ENTETE_CLE = "X-INSEE-Api-Key-Integration"
SOURCE = "sirene"
NOMBRE_MAX = 1000
REQUETES_PAR_MINUTE = 30
MASQUE = "[ND]"
CJ_ENTREPRENEUR_INDIVIDUEL = "1000"

# Les seuls champs demandés à l'API. Aucun champ de personne physique.
CHAMPS_UNITES = (
    "siren",
    "statutDiffusionUniteLegale",
    "dateCreationUniteLegale",
    "dateDebut",
    "etatAdministratifUniteLegale",
    "denominationUniteLegale",
    "categorieJuridiqueUniteLegale",
    # Pour `unites_legales` (T013) : sigle, enseignes, activité, effectif. Aucune personne.
    "sigleUniteLegale",
    "denominationUsuelle1UniteLegale",
    "denominationUsuelle2UniteLegale",
    "denominationUsuelle3UniteLegale",
    "activitePrincipaleUniteLegale",
    "trancheEffectifsUniteLegale",
)
CHAMPS_ETABLISSEMENTS = (
    "siren",
    "siret",
    "etablissementSiege",
    "statutDiffusionEtablissement",
    "etatAdministratifEtablissement",
    "numeroVoieEtablissement",
    "indiceRepetitionDernierNumeroVoieEtablissement",
    "typeVoieEtablissement",
    "libelleVoieEtablissement",
    "codePostalEtablissement",
    "libelleCommuneEtablissement",
    "denominationUniteLegale",
    "categorieJuridiqueUniteLegale",
    "activitePrincipaleUniteLegale",
    "trancheEffectifsUniteLegale",
    "etatAdministratifUniteLegale",
)


class ErreurSirene(RuntimeError):
    """L'API Sirene a refusé ou n'a pas pu servir la demande. Message sans donnée."""


class CleManquante(ErreurSirene):
    """INSEE_API_KEY absente de l'environnement."""


def cle_api() -> str:
    """Rend la clé INSEE_API_KEY, ou une erreur claire qui ne la cite jamais."""
    cle = os.environ.get("INSEE_API_KEY")
    if not cle:
        raise CleManquante(
            "Clé INSEE absente : INSEE_API_KEY. La mettre dans .env "
            "(ou indiquer le fichier avec CARTOFR_ENV_FILE)."
        )
    return cle


class Limiteur:
    """Au plus `maximum` requêtes sur toute fenêtre glissante de `fenetre` secondes.

    `horloge` et `dormir` sont remplaçables pour les tests (horloge simulée).
    """

    def __init__(
        self,
        maximum: int = REQUETES_PAR_MINUTE,
        fenetre: float = 60.0,
        horloge: Callable[[], float] = time.monotonic,
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        self.maximum = maximum
        self.fenetre = fenetre
        self.horloge = horloge
        self.dormir = dormir
        self._passees: deque[float] = deque()

    def attendre(self) -> None:
        """Bloque jusqu'à ce qu'une requête de plus tienne dans la fenêtre, puis la compte."""
        while True:
            maintenant = self.horloge()
            while self._passees and self._passees[0] <= maintenant - self.fenetre:
                self._passees.popleft()
            if len(self._passees) < self.maximum:
                self._passees.append(maintenant)
                return
            self.dormir(self._passees[0] + self.fenetre - maintenant)


class Client:
    """Client de l'API Sirene : clé, limite de 30 requêtes par minute, pagination par curseur."""

    def __init__(
        self,
        http: httpx.Client | None = None,
        base: str = BASE,
        cle: str | None = None,
        limiteur: Limiteur | None = None,
        essais: int = 3,
        attente: float = 10.0,
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        self.http = http or httpx.Client(timeout=httpx.Timeout(120.0, connect=30.0))
        self.base = base.rstrip("/")
        self._cle = cle
        self.limiteur = limiteur or Limiteur(dormir=dormir)
        self.essais = essais
        self.attente = attente
        self.dormir = dormir
        self.requetes = 0

    def _get(self, chemin: str, params: dict[str, str | int]) -> dict[str, Any] | None:
        """GET limité. Rend le JSON, ou None sur 404 (aucun résultat).

        429 : attend `Retry-After` (60 s sinon), 5xx et coupures : attente croissante,
        au plus `essais` reprises chacun.
        """
        entetes = {ENTETE_CLE: self._cle or cle_api(), "Accept": "application/json"}
        echecs = 0
        refus = 0
        while True:
            self.limiteur.attendre()
            self.requetes += 1
            try:
                r = self.http.get(f"{self.base}{chemin}", params=params, headers=entetes)
            except httpx.TransportError as e:
                echecs += 1
                if echecs > self.essais:
                    raise ErreurSirene(f"API Sirene injoignable après {self.essais} essais.") from e
                self.dormir(self.attente * echecs)
                continue
            if r.status_code == 404:
                return None
            if r.status_code == 429:
                refus += 1
                if refus > self.essais:
                    raise ErreurSirene(f"API Sirene : trop de requêtes (429) après {self.essais} essais.")
                self.dormir(_retry_after(r))
                continue
            if r.status_code >= 500:
                echecs += 1
                if echecs > self.essais:
                    raise ErreurSirene(f"Erreur Sirene {r.status_code} après {self.essais} essais.")
                self.dormir(self.attente * echecs)
                continue
            if r.status_code in (401, 403):
                raise ErreurSirene(f"Clé INSEE refusée (code {r.status_code}) : vérifier INSEE_API_KEY.")
            if r.status_code >= 400:
                raise ErreurSirene(f"Requête Sirene refusée (code {r.status_code}).")
            corps = r.json()
            if not isinstance(corps, dict):
                raise ErreurSirene("Réponse Sirene inattendue : un objet JSON était attendu.")
            return corps

    def pages(
        self, chemin: str, cle_liste: str, q: str, champs: tuple[str, ...], nombre: int = NOMBRE_MAX
    ) -> Iterator[list[dict[str, Any]]]:
        """Rend les pages de `q`, du curseur `*` jusqu'à ce que `curseurSuivant` n'avance plus."""
        if not 1 <= nombre <= NOMBRE_MAX:
            raise ValueError(f"nombre doit aller de 1 à {NOMBRE_MAX}.")
        curseur = "*"
        while True:
            params: dict[str, str | int] = {
                "q": q,
                "nombre": nombre,
                "curseur": curseur,
                "champs": ",".join(champs),
            }
            corps = self._get(chemin, params)
            if corps is None:
                return
            elements = corps.get(cle_liste) or []
            if not isinstance(elements, list):
                raise ErreurSirene(f"Réponse Sirene inattendue : `{cle_liste}` n'est pas une liste.")
            if elements:
                yield elements
            suivant = (corps.get("header") or {}).get("curseurSuivant")
            if not elements or not suivant or suivant == curseur:
                return
            curseur = str(suivant)

    def unites_du_jour(self, jour: date) -> Iterator[list[dict[str, Any]]]:
        """Unités légales traitées le `jour`, hors entrepreneurs individuels."""
        q = (
            f"dateDernierTraitementUniteLegale:{_plage(jour)}"
            f" AND -periode(categorieJuridiqueUniteLegale:{CJ_ENTREPRENEUR_INDIVIDUEL})"
        )
        return self.pages("/siren", "unitesLegales", q, CHAMPS_UNITES)

    def sieges_du_jour(self, jour: date) -> Iterator[list[dict[str, Any]]]:
        """Établissements sièges traités le `jour`, hors entrepreneurs individuels."""
        q = (
            f"dateDernierTraitementEtablissement:{_plage(jour)} AND etablissementSiege:true"
            f" AND -categorieJuridiqueUniteLegale:{CJ_ENTREPRENEUR_INDIVIDUEL}"
        )
        return self.pages("/siret", "etablissements", q, CHAMPS_ETABLISSEMENTS)


def _plage(jour: date) -> str:
    j = jour.isoformat()
    return f"[{j}T00:00:00 TO {j}T23:59:59]"


def _retry_after(r: httpx.Response) -> float:
    try:
        return max(1.0, float(r.headers.get("Retry-After", "60")))
    except ValueError:
        return 60.0


# --- Mise en forme des réponses -------------------------------------------------


def _v(valeur: Any) -> Any:
    """Une valeur masquée par l'INSEE (`[ND]`) ou une chaîne vide vaut vide."""
    if valeur is None or valeur == MASQUE or valeur == "":
        return None
    return valeur


def _date(valeur: Any) -> date | None:
    v = _v(valeur)
    return date.fromisoformat(str(v)) if v is not None else None


def _entier(valeur: Any) -> int | None:
    v = _v(valeur)
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _periode_en_cours(periodes: Any) -> dict[str, Any]:
    """La période sans `dateFin`, sinon la première (l'API rend la plus récente d'abord)."""
    if not isinstance(periodes, list) or not periodes:
        return {}
    for p in periodes:
        if isinstance(p, dict) and p.get("dateFin") is None:
            return p
    return periodes[0] if isinstance(periodes[0], dict) else {}


SCHEMA_UNITES = pa.schema(
    [
        ("siren", pa.string()),
        ("denomination", pa.string()),
        ("non_diffusible", pa.bool_()),
        ("etat", pa.string()),
        ("date_etat", pa.date32()),
        ("date_creation", pa.date32()),
        ("sigle", pa.string()),
        ("denomination_usuelle_1", pa.string()),
        ("denomination_usuelle_2", pa.string()),
        ("denomination_usuelle_3", pa.string()),
        ("cj", pa.int64()),
        ("naf", pa.string()),
        ("tranche", pa.string()),
    ]
)

SCHEMA_SIEGES = pa.schema(
    [
        ("siren", pa.string()),
        ("siret_siege", pa.string()),
        ("num", pa.string()),
        ("type_voie", pa.string()),
        ("voie", pa.string()),
        ("cp", pa.string()),
        ("commune", pa.string()),
        ("adresse_cle", pa.string()),
        ("nom", pa.string()),
        ("cj", pa.int64()),
        ("naf", pa.string()),
        ("tranche", pa.string()),
        ("actif", pa.bool_()),
    ]
)


def lignes_unites(unites: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Une ligne par SIREN (la dernière lue gagne), entrepreneurs individuels écartés."""
    lignes: dict[str, dict[str, Any]] = {}
    for u in unites:
        p = _periode_en_cours(u.get("periodesUniteLegale"))
        if _v(p.get("categorieJuridiqueUniteLegale")) == CJ_ENTREPRENEUR_INDIVIDUEL:
            continue
        siren = _v(u.get("siren"))
        if siren is None:
            continue
        statut = _v(u.get("statutDiffusionUniteLegale"))
        lignes[siren] = {
            "siren": siren,
            "denomination": _v(p.get("denominationUniteLegale")),
            "non_diffusible": None if statut is None else statut != "O",
            "etat": _v(p.get("etatAdministratifUniteLegale")),
            "date_etat": _date(p.get("dateDebut")),
            "date_creation": _date(u.get("dateCreationUniteLegale")),
            "sigle": _v(u.get("sigleUniteLegale")),
            "denomination_usuelle_1": _v(p.get("denominationUsuelle1UniteLegale")),
            "denomination_usuelle_2": _v(p.get("denominationUsuelle2UniteLegale")),
            "denomination_usuelle_3": _v(p.get("denominationUsuelle3UniteLegale")),
            "cj": _entier(p.get("categorieJuridiqueUniteLegale")),
            "naf": _v(p.get("activitePrincipaleUniteLegale")),
            "tranche": _v(u.get("trancheEffectifsUniteLegale")),
        }
    return list(lignes.values())


def _maj(valeur: Any) -> str:
    return "" if valeur is None else str(valeur).upper()


def lignes_sieges(etablissements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Une ligne par SIREN pour les sièges diffusibles, colonnes de `build_sieges.py`.

    `actif` : établissement et unité légale actifs. Seuls ceux-là s'écrivent.
    """
    lignes: dict[str, dict[str, Any]] = {}
    for e in etablissements:
        if e.get("etablissementSiege") is not True or e.get("statutDiffusionEtablissement") != "O":
            continue
        ul = e.get("uniteLegale") or {}
        cj = _v(ul.get("categorieJuridiqueUniteLegale"))
        siren = _v(e.get("siren"))
        if cj == CJ_ENTREPRENEUR_INDIVIDUEL or siren is None:
            continue
        a = e.get("adresseEtablissement") or {}
        numero = _v(a.get("numeroVoieEtablissement"))
        indice = _v(a.get("indiceRepetitionDernierNumeroVoieEtablissement"))
        type_voie = _v(a.get("typeVoieEtablissement"))
        voie = _v(a.get("libelleVoieEtablissement"))
        cp = _v(a.get("codePostalEtablissement"))
        periode = _periode_en_cours(e.get("periodesEtablissement"))
        # Mêmes expressions que build_sieges.py : coalesce à '', trim des espaces, majuscules.
        lignes[siren] = {
            "siren": siren,
            "siret_siege": _v(e.get("siret")),
            "num": _maj(f"{numero or ''}{indice or ''}".strip(" ")),
            "type_voie": _maj(type_voie),
            "voie": _maj(voie),
            "cp": cp,
            "commune": _v(a.get("libelleCommuneEtablissement")),
            "adresse_cle": _maj(f"{numero or ''} {type_voie or ''} {voie or ''} {cp or ''}".strip(" ")),
            "nom": _v(ul.get("denominationUniteLegale")),
            "cj": int(cj) if cj is not None else None,
            "naf": _v(ul.get("activitePrincipaleUniteLegale")),
            "tranche": _v(ul.get("trancheEffectifsUniteLegale")),
            "actif": periode.get("etatAdministratifEtablissement") == "A"
            and ul.get("etatAdministratifUniteLegale") == "A",
        }
    return list(lignes.values())


# --- Application au registre ------------------------------------------------------


@dataclass
class Bilan:
    """Volumes d'une synchro : ce qui a été lu, changé, ajouté, fermé. Aucun nom."""

    requetes: int = 0
    unites_lues: int = 0
    societes_modifiees: int = 0
    societes_ajoutees: int = 0
    societes_cessees: int = 0
    societes_reactivees: int = 0
    passages_non_diffusible: int = 0
    unites_legales_modifiees: int = 0
    unites_legales_ajoutees: int = 0
    sieges_lus: int = 0
    sieges_modifies: int = 0
    sieges_ajoutes: int = 0
    sieges_inactifs_ignores: int = 0


def _compte(con: duckdb.DuckDBPyConnection, sql: str, params: dict[str, Any] | None = None) -> int:
    ligne = con.execute(sql, params or {}).fetchone()
    return int(ligne[0]) if ligne else 0


def appliquer_unites(
    con: duckdb.DuckDBPyConnection, unites: list[dict[str, Any]], jour: date, bilan: Bilan
) -> None:
    """Met `societes` et `unites_legales` à jour depuis des unités légales brutes. Sans transaction propre."""
    table = pa.Table.from_pylist(lignes_unites(unites), schema=SCHEMA_UNITES)
    bilan.unites_lues += table.num_rows
    con.register("sirene_unites", table)
    try:
        params = {"jour": jour}
        # Compter avant de modifier : les transitions se lisent sur l'état d'avant.
        bilan.passages_non_diffusible += _compte(
            con,
            "select count(*) from societes s join sirene_unites u using (siren)"
            " where u.non_diffusible and s.non_diffusible is distinct from true",
        )
        bilan.societes_cessees += _compte(
            con,
            "update societes s set fin = greatest(s.debut, coalesce(u.date_etat, $jour))"
            " from sirene_unites u where s.siren = u.siren and u.etat = 'C'"
            " and s.etat_administratif is distinct from 'C' and s.fin is null",
            params,
        )
        bilan.societes_reactivees += _compte(
            con,
            "update societes s set fin = null from sirene_unites u"
            " where s.siren = u.siren and u.etat = 'A' and s.etat_administratif = 'C' and s.fin is not null",
        )
        bilan.societes_modifiees += _compte(
            con,
            "update societes s set non_diffusible = coalesce(u.non_diffusible, s.non_diffusible),"
            " etat_administratif = coalesce(u.etat, s.etat_administratif),"
            " date_creation = coalesce(u.date_creation, s.date_creation)"
            " from sirene_unites u where s.siren = u.siren and ("
            " s.non_diffusible is distinct from coalesce(u.non_diffusible, s.non_diffusible)"
            " or s.etat_administratif is distinct from coalesce(u.etat, s.etat_administratif)"
            " or s.date_creation is distinct from coalesce(u.date_creation, s.date_creation))",
        )
        bilan.societes_ajoutees += _compte(
            con,
            "insert into societes (siren, denomination, non_diffusible, etat_administratif,"
            " date_creation, debut)"
            " select u.siren, u.denomination, u.non_diffusible, u.etat, u.date_creation, $jour"
            " from sirene_unites u where u.etat = 'A'"
            " and not exists (select 1 from societes s where s.siren = u.siren)",
            params,
        )
        _appliquer_unites_legales(con, jour, bilan)
    finally:
        con.unregister("sirene_unites")


# (colonne de `unites_legales`, colonne de `sirene_unites`). Pour une unité non diffusible,
# une valeur vide ou masquée garde la valeur connue ; sinon la fiche fait foi.
_UNITES_LEGALES_FICHE = (
    ("sigle", "sigle"),
    ("denomination_usuelle_1", "denomination_usuelle_1"),
    ("denomination_usuelle_2", "denomination_usuelle_2"),
    ("denomination_usuelle_3", "denomination_usuelle_3"),
    ("naf", "naf"),
    ("tranche_effectifs", "tranche"),
)
# Jamais vidées : une personne morale garde un nom, une catégorie et un état.
_UNITES_LEGALES_GARDEES = (
    ("denomination", "denomination"),
    ("categorie_juridique", "cj"),
    ("etat_administratif", "etat"),
)


def _appliquer_unites_legales(con: duckdb.DuckDBPyConnection, jour: date, bilan: Bilan) -> None:
    """Met `unites_legales` à jour depuis la vue `sirene_unites`. Jamais de catégorie 1000 ni vide."""
    valeurs = [
        (c, f"case when u.non_diffusible then coalesce(u.{v}, l.{c}) else u.{v} end")
        for c, v in _UNITES_LEGALES_FICHE
    ] + [(c, f"coalesce(u.{v}, l.{c})") for c, v in _UNITES_LEGALES_GARDEES]
    affectations = ", ".join(f"{c} = {v}" for c, v in valeurs)
    differences = " or ".join(f"l.{c} is distinct from {v}" for c, v in valeurs)
    bilan.unites_legales_modifiees += _compte(
        con,
        f"update unites_legales l set {affectations} from sirene_unites u"
        f" where l.siren = u.siren and ({differences})",
    )
    bilan.unites_legales_ajoutees += _compte(
        con,
        "insert into unites_legales (siren, denomination, sigle, denomination_usuelle_1,"
        " denomination_usuelle_2, denomination_usuelle_3, categorie_juridique, naf, tranche_effectifs,"
        " etat_administratif, debut)"
        " select u.siren, u.denomination, u.sigle, u.denomination_usuelle_1, u.denomination_usuelle_2,"
        " u.denomination_usuelle_3, u.cj, u.naf, u.tranche, u.etat, $jour"
        f" from sirene_unites u where u.cj is not null and u.cj <> {CJ_ENTREPRENEUR_INDIVIDUEL}"
        " and not exists (select 1 from unites_legales l where l.siren = u.siren)",
        {"jour": jour},
    )


COLONNES_SIEGE = (
    "siret_siege",
    "num",
    "type_voie",
    "voie",
    "cp",
    "commune",
    "adresse_cle",
    "nom",
    "cj",
    "naf",
    "tranche",
)


def appliquer_sieges(
    con: duckdb.DuckDBPyConnection, etablissements: list[dict[str, Any]], bilan: Bilan
) -> None:
    """Met `sieges` à jour (clé SIREN) depuis des établissements sièges bruts de l'API."""
    table = pa.Table.from_pylist(lignes_sieges(etablissements), schema=SCHEMA_SIEGES)
    bilan.sieges_lus += table.num_rows
    con.register("sirene_sieges", table)
    try:
        bilan.sieges_inactifs_ignores += _compte(con, "select count(*) from sirene_sieges where not actif")
        affectations = ", ".join(f"{c} = e.{c}" for c in COLONNES_SIEGE)
        differences = " or ".join(f"s.{c} is distinct from e.{c}" for c in COLONNES_SIEGE)
        bilan.sieges_modifies += _compte(
            con,
            f"update sieges s set {affectations} from sirene_sieges e"
            f" where s.siren = e.siren and e.actif and ({differences})",
        )
        colonnes = ", ".join(("siren", *COLONNES_SIEGE))
        bilan.sieges_ajoutes += _compte(
            con,
            f"insert into sieges ({colonnes}) select {colonnes} from sirene_sieges e"
            " where e.actif and not exists (select 1 from sieges s where s.siren = e.siren)",
        )
    finally:
        con.unregister("sirene_sieges")


def _message(erreur: BaseException) -> str:
    """Le nôtre en entier (sans donnée), sinon le type seul : un message DuckDB peut citer une valeur."""
    if isinstance(erreur, ErreurSirene):
        return str(erreur)
    return f"{type(erreur).__name__} pendant la synchro SIRENE"


def synchroniser(con: duckdb.DuckDBPyConnection, jour: date, client: Client | None = None) -> Bilan:
    """Lit les changements SIRENE du `jour`, puis les applique au registre d'un seul coup."""
    client = client or Client()
    id_maj = journal.ouvrir(con, SOURCE)
    bilan = Bilan()
    try:
        unites = [u for page in client.unites_du_jour(jour) for u in page]
        etablissements = [e for page in client.sieges_du_jour(jour) for e in page]
        bilan.requetes = client.requetes
        con.execute("begin transaction")
        try:
            appliquer_unites(con, unites, jour, bilan)
            appliquer_sieges(con, etablissements, bilan)
            con.execute("commit")
        except BaseException:
            con.execute("rollback")
            raise
    except BaseException as erreur:
        journal.echouer(con, id_maj, _message(erreur))
        raise
    journal.terminer(
        con,
        id_maj,
        ajoutes=bilan.societes_ajoutees + bilan.sieges_ajoutes,
        fermes=bilan.societes_cessees,
    )
    return bilan


def main(arguments: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description="Applique au registre les changements SIRENE d'un jour.")
    parseur.add_argument("--jour", required=True, type=date.fromisoformat, help="date AAAA-MM-JJ")
    parseur.add_argument(
        "--registre", type=Path, help="chemin du registre (défaut : <CARTOFR_DATA>/registre.duckdb)"
    )
    options = parseur.parse_args(arguments)
    chemin = options.registre or Path(os.environ.get("CARTOFR_DATA", "data")) / "registre.duckdb"
    if not chemin.is_file():
        print(f"Échec : registre introuvable : {chemin}", file=sys.stderr)
        return 1
    charger_env()
    debut = time.monotonic()
    con = duckdb.connect(str(chemin))
    try:
        bilan = synchroniser(con, options.jour)
    except ErreurSirene as erreur:
        print(f"Échec : {erreur}", file=sys.stderr)
        return 1
    finally:
        con.close()
    for nom, valeur in asdict(bilan).items():
        print(f"{nom} : {valeur}")
    print(f"duree_s : {time.monotonic() - debut:.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
