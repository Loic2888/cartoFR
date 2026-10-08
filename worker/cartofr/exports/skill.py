"""Export d'une carto au format du skill account-mapping : 6 tables CSV dans un zip (T029, FR-010).

But : livrer au client des fichiers qu'il importe dans HubSpot ou Cargo sans
retraitement, et que `skills/account-mapping/scripts/validate_mapping.py` et
`build_hubspot_import.py` lisent tels quels. Repris de `to_skill_tables.py` (racine),
qui lisait les CSV du prototype ; ici, la source est la carto **enregistrée** dans la
base de l'app.

Usage :
    from cartofr.exports.skill import lire_carto, construire_tables, zip_des_tables
    with connecter() as conn:
        carto = lire_carto(conn, carto_id, organisation_id)
    contenu = zip_des_tables(construire_tables(carto))
Servi par la route interne `GET /export/skill/<carto>?organisation=<uuid>`
(`cartofr.api_recherche`), que la route web `export-skill` relaie.

Entrées : les lignes `cartos`, `groupes`, `reglages` (organigramme) et `carto_societes`
d'une carto terminée, lues avec son `organisation_id`. Comme le prototype, `relationships`
porte un lien par société : celui de sa maison mère dans l'arbre (les autres mandats de
`carto_liens` n'y entrent pas, ils donneraient plusieurs parents dans HubSpot).
Sortie : un zip de 6 CSV (`companies`, `relationships`, `brands`,
`entities_to_resolve`, `evidence_sources`, `coverage`) et un `LISEZMOI.txt`.
CSV en UTF-8 sans BOM, virgule, fin de ligne CRLF, guillemets RFC 4180 : le format par
défaut du skill (`references/data-model.md`), que lisent les outils d'import.

Règles tenues ici :
- aucun appel extérieur, aucune lecture du registre (principe 3) : tout vient de la
  base de l'app. Les champs que la carto enregistrée ne porte pas (SIRET et adresse du
  siège, NAF, forme juridique) restent vides, colonnes gardées ;
- aucune colonne de personne (principe 6, garde-fou 6) : on ne lit que des colonnes
  de société, et `carto_societes` n'en a aucune. `to_skill_tables.py`
  n'écrivait déjà aucun dirigeant : aucun champ n'a eu à être vidé ;
- `opposition_prospection` est porté sur chaque société (`True` / `False`), jamais
  caché, et une société opposée n'est jamais présentée comme démarchable : son
  `targetable` reste celui du moteur, la marque d'opposition est à côté, et
  `build_hubspot_import.py` la recopie ;
- une cellule qui commence par = + - @, tabulation ou retour chariot est préfixée d'une
  apostrophe (injection de formule à l'ouverture dans un tableur, comme l'export T023) ;
- une carto d'une autre organisation est introuvable : chaque lecture filtre
  `organisation_id` (le worker lit en rôle service, qui contourne RLS).
"""

from __future__ import annotations

import csv
import io
import re
import uuid
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, LiteralString

import psycopg

Connexion = psycopg.Connection[tuple[Any, ...]]

INPI = "https://data.inpi.fr/entreprises/{}"
ANNUAIRE = "https://annuaire-entreprises.data.gouv.fr/entreprise/{}"
# Séparateur posé par jobs/carto.py entre le rattachement et la règle d'entrée.
SEPARATEUR_PREUVE = " · entrée dans le groupe : "
TETE_DE_MAISON = "tête de maison"

COLONNES: dict[str, tuple[str, ...]] = {
    "companies": (
        "company_id",
        "legal_name",
        "siren",
        "siret_hq",
        "hq_address",
        "country",
        "naf_code",
        "legal_form",
        "entity_type",
        "operating_status",
        "targetable",
        "targetable_reason",
        "domain",
        "domain_scope",
        "resolution_status",
        "identity_confidence",
        "last_verified_at",
        "identity_source_url",
        "opposition_prospection",
        "non_diffusible",
        "notes",
    ),
    "relationships": (
        "parent_id",
        "child_id",
        "relationship_type",
        "ownership_pct",
        "control_pct",
        "direct_parent_verified",
        "relationship_status",
        "valid_from",
        "valid_to",
        "confidence",
        "source_url",
        "source_date",
        "notes",
    ),
    "brands": (
        "brand_id",
        "brand_name",
        "geography",
        "brand_object_type",
        "legal_entity_id",
        "legal_entity_name",
        "domain",
        "mapping_status",
        "source_url",
        "notes",
    ),
    "entities_to_resolve": (
        "candidate_id",
        "entity_name",
        "country",
        "discovery_source",
        "official_scope_type",
        "business_segment",
        "control_pct_if_known",
        "resolution_status",
        "next_action",
        "exclusion_reason",
        "notes",
    ),
    "evidence_sources": ("source_id", "source_name", "url", "source_tier", "usage", "retrieved_at"),
    "coverage": ("metric", "value"),
}
TABLES = tuple(COLONNES)

DIRECT = {"A": "yes", "B": "no", "C": "no"}
STATUT_LIEN = {"A": "confirmed", "B": "confirmed", "C": "to_verify"}
CONFIANCE = {"A": "high", "B": "medium", "C": "low"}

DEBUT_DE_FORMULE = re.compile(r"^[=+\-@\t\r]")

LISEZMOI = """\
Export cartoFR au format du skill account-mapping
=================================================

Groupe : {groupe}
Date des données du registre : {date}

Six tables CSV (UTF-8, séparateur virgule), à importer dans HubSpot ou Cargo :
- companies.csv : une ligne par société du groupe ;
- relationships.csv : une ligne par lien société mère -> filiale retenu ;
- brands.csv : les marques de l'organigramme public du groupe ;
- entities_to_resolve.csv : sociétés à examiner (vide dans cet export) ;
- evidence_sources.csv : les sources des données ;
- coverage.csv : les indicateurs de couverture de la carto.

Confiance d'un lien : high = lu au registre (A), medium = au moins deux indices (B),
low = un seul indice, à vérifier (C).

opposition_prospection = True : la société s'oppose à la réutilisation de ses
données du registre (INPI) pour la prospection commerciale. Elle reste dans la
carto, mais ne doit pas être démarchée.
non_diffusible = True : la société a demandé la diffusion partielle de ses données
(INSEE).

Aucun nom de personne n'est exporté. Aucune donnée n'est envoyée à un outil tiers :
l'import se fait par vous.
"""


@dataclass(frozen=True)
class SocieteEnregistree:
    """Une ligne `carto_societes`. Que des colonnes de société."""

    siren: str
    nom: str | None
    niveau: int
    maison_mere_siren: str | None
    confiance: str | None
    preuve: str | None
    ciblable: bool
    raison_ciblable: str | None
    opposition_prospection: bool
    non_diffusible: bool


@dataclass(frozen=True)
class CartoEnregistree:
    """Une carto terminée, telle que la base de l'app la garde."""

    groupe: str
    tete_siren: str
    date_donnees: date | None
    organigramme: tuple[str, ...]
    societes: tuple[SocieteEnregistree, ...]


@dataclass(frozen=True)
class Table:
    nom: str
    colonnes: tuple[str, ...]
    lignes: tuple[tuple[str, ...], ...]


class CartoNonTerminee(RuntimeError):
    """La carto existe pour cette organisation mais n'est pas terminée : rien à exporter."""


# --- Construction des tables, sans base -------------------------------------------------------


def _texte(valeur: Any) -> str:
    return "" if valeur is None else str(valeur)


def _vrai_faux(valeur: bool) -> str:
    return "True" if valeur else "False"


def type_entite(s: SocieteEnregistree, tete: str) -> str:
    """Le type d'entité du skill, comme `to_skill_tables.py` : lu dans la raison « ciblable »."""
    raison = s.raison_ciblable or ""
    if s.siren == tete:
        return "holding_operating_group"
    if "civile" in raison:
        return "sci"
    if "GIE" in raison:
        return "shared_service"
    if "Holding" in raison:
        return "holding"
    return "operating_company"


def rattachement(preuve: str | None) -> str:
    """La preuve du rattachement à la maison mère, sans la règle d'entrée (le `type_lien` du prototype)."""
    return (preuve or "").split(SEPARATEUR_PREUVE, 1)[0]


def _table(nom: str, lignes: Sequence[dict[str, Any]]) -> Table:
    colonnes = COLONNES[nom]
    return Table(nom, colonnes, tuple(tuple(_texte(ligne.get(c)) for c in colonnes) for ligne in lignes))


def construire_tables(carto: CartoEnregistree) -> list[Table]:
    """Les 6 tables du skill, dans l'ordre de `TABLES`."""
    jour = carto.date_donnees.isoformat() if carto.date_donnees else ""
    societes = sorted(carto.societes, key=lambda s: (s.niveau, s.siren))
    noms = {s.siren: s.nom or "" for s in societes}

    companies = [
        {
            "company_id": s.siren,
            "legal_name": s.nom,
            "siren": s.siren,
            "country": "FR",
            "entity_type": type_entite(s, carto.tete_siren),
            "operating_status": "active",
            "targetable": "yes" if s.ciblable else "no",
            "targetable_reason": s.raison_ciblable,
            "resolution_status": "resolved",
            "identity_confidence": "high",
            "last_verified_at": jour,
            "identity_source_url": ANNUAIRE.format(s.siren),
            "opposition_prospection": _vrai_faux(s.opposition_prospection),
            "non_diffusible": _vrai_faux(s.non_diffusible),
            "notes": f"Preuve : {s.preuve}" if s.preuve else "",
        }
        for s in societes
    ]

    # Une ligne par lien maison mère retenu. A = lu au registre ; B = au moins deux indices ; C = à vérifier.
    rattachees = [s for s in societes if s.maison_mere_siren and s.siren != carto.tete_siren]
    relationships = [
        {
            "parent_id": s.maison_mere_siren,
            "child_id": s.siren,
            "relationship_type": "control",
            "direct_parent_verified": DIRECT.get(s.confiance or "", "no"),
            "relationship_status": STATUT_LIEN.get(s.confiance or "", "to_verify"),
            "confidence": CONFIANCE.get(s.confiance or "", "low"),
            "source_url": (INPI if s.confiance == "A" else ANNUAIRE).format(s.siren),
            "source_date": jour,
            "notes": rattachement(s.preuve),
        }
        for s in rattachees
    ]

    tetes = {noms[s.siren]: s.siren for s in societes if TETE_DE_MAISON in (s.preuve or "")}

    def entite_de(marque: str) -> str:
        cle = marque.upper().replace("'", " ")
        return next((siren for nom, siren in tetes.items() if cle in nom.upper().replace("'", " ")), "")

    brands = []
    for i, marque in enumerate(carto.organigramme):
        siren = entite_de(marque)
        brands.append(
            {
                "brand_id": f"B{i + 1}",
                "brand_name": marque,
                "geography": "FR",
                "brand_object_type": "brand",
                "legal_entity_id": siren,
                "legal_entity_name": noms.get(siren, ""),
                "mapping_status": "mapped" if siren else "unresolved",
                "notes": "organigramme public (réglages validés)",
            }
        )

    # Participations et sociétés étrangères ne sont pas enregistrées dans la base de l'app :
    # la file de recherche reste vide (colonnes gardées).
    entities_to_resolve: list[dict[str, Any]] = []

    evidence_sources = [
        {
            "source_id": "S1",
            "source_name": "Registre national des entreprises (INPI), stock complet",
            "url": "https://data.inpi.fr",
            "source_tier": "A",
            "usage": "mandats entre sociétés",
            "retrieved_at": jour,
        },
        {
            "source_id": "S2",
            "source_name": "Base SIRENE (INSEE)",
            "url": "https://www.data.gouv.fr/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret/",
            "source_tier": "A",
            "usage": "identité, effectif",
            "retrieved_at": jour,
        },
        {
            "source_id": "S3",
            "source_name": "Organigramme public du groupe (réglages validés)",
            "url": "",
            "source_tier": "B",
            "usage": "têtes de maison",
            "retrieved_at": jour,
        },
    ]

    n = len(companies)
    lus = sum(1 for s in rattachees if s.confiance == "A")
    part_lue = round(100 * lus / len(rattachees), 1) if rattachees else 0
    metriques: dict[str, Any] = {
        "root_company_id": carto.tete_siren,
        "mapping_status": "substantially_complete" if n else "not_started",
        "recursive_expansion_complete": "yes" if n else "no",
        "companies_resolved": n,
        "entities_to_resolve_count": len(entities_to_resolve),
        "brands_detected": len(brands),
        "brands_mapped": sum(1 for b in brands if b["mapping_status"] == "mapped"),
        "direct_parent_verified_pct": part_lue,
        "source_primary_pct": part_lue,
        "orphan_count": max(0, n - len(rattachees) - (1 if carto.tete_siren in noms else 0)),
        "targetable_count": sum(1 for s in societes if s.ciblable),
        "opposition_prospection_count": sum(1 for s in societes if s.opposition_prospection),
        "data_date": jour,
    }
    coverage = [{"metric": k, "value": v} for k, v in metriques.items()]

    return [
        _table("companies", companies),
        _table("relationships", relationships),
        _table("brands", brands),
        _table("entities_to_resolve", entities_to_resolve),
        _table("evidence_sources", evidence_sources),
        _table("coverage", coverage),
    ]


def cellule(valeur: str) -> str:
    """Neutralise une cellule qui serait lue comme une formule par un tableur."""
    return f"'{valeur}" if DEBUT_DE_FORMULE.match(valeur) else valeur


def csv_de(table: Table) -> str:
    """Une table en CSV : virgule, guillemets RFC 4180, CRLF, formules neutralisées."""
    tampon = io.StringIO()
    ecrivain = csv.writer(
        tampon, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n"
    )
    ecrivain.writerow(table.colonnes)
    for ligne in table.lignes:
        ecrivain.writerow([cellule(v) for v in ligne])
    return tampon.getvalue()


def zip_des_tables(tables: Sequence[Table], carto: CartoEnregistree) -> bytes:
    """Le zip livré : un CSV par table et un LISEZMOI.txt. Contenu reproductible (date fixe)."""
    quand = (
        (carto.date_donnees.year, carto.date_donnees.month, carto.date_donnees.day, 0, 0, 0)
        if (carto.date_donnees and carto.date_donnees.year >= 1980)
        else (1980, 1, 1, 0, 0, 0)
    )
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        fichiers = [(f"{t.nom}.csv", csv_de(t)) for t in tables]
        date_fr = carto.date_donnees.strftime("%d/%m/%Y") if carto.date_donnees else "inconnue"
        fichiers.append(
            ("LISEZMOI.txt", LISEZMOI.format(groupe=carto.groupe, date=date_fr).replace("\n", "\r\n"))
        )
        for nom, texte in fichiers:
            info = zipfile.ZipInfo(nom, date_time=quand)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, texte.encode("utf-8"))
    return tampon.getvalue()


# --- Lecture en base ---------------------------------------------------------------------------

_CARTO: LiteralString = """
select c.statut, c.date_donnees, g.nom, g.tete_siren, r.contenu
  from public.cartos c
  join public.groupes g on g.id = c.groupe_id and g.organisation_id = c.organisation_id
  join public.reglages r
    on r.id = c.reglages_id and r.groupe_id = c.groupe_id and r.organisation_id = c.organisation_id
 where c.id = %s and c.organisation_id = %s
"""

_SOCIETES: LiteralString = """
select siren, nom, niveau, maison_mere_siren, confiance, preuve, ciblable, raison_ciblable,
       opposition_prospection, non_diffusible
  from public.carto_societes
 where carto_id = %s and organisation_id = %s
 order by niveau, siren
"""


def _organigramme(contenu: Any) -> tuple[str, ...]:
    valeur = contenu.get("organigramme") if isinstance(contenu, dict) else None
    if not isinstance(valeur, list):
        return ()
    return tuple(str(m) for m in valeur if isinstance(m, str) and m.strip())


def lire_carto(conn: Connexion, carto_id: uuid.UUID, organisation_id: uuid.UUID) -> CartoEnregistree | None:
    """La carto terminée de cette organisation, ou None si elle n'existe pas pour elle.

    Lève CartoNonTerminee si la carto existe mais n'est pas terminée. Lecture seule.
    """
    try:
        ligne = conn.execute(_CARTO, (carto_id, organisation_id)).fetchone()
        if ligne is None:
            return None
        statut, date_donnees, groupe, tete, contenu = ligne
        if statut != "terminee":
            raise CartoNonTerminee(str(carto_id))
        societes = tuple(
            SocieteEnregistree(*r) for r in conn.execute(_SOCIETES, (carto_id, organisation_id)).fetchall()
        )
    finally:
        conn.rollback()  # lecture seule : rien à valider
    return CartoEnregistree(
        groupe=str(groupe),
        tete_siren=str(tete),
        date_donnees=date_donnees,
        organigramme=_organigramme(contenu),
        societes=societes,
    )


def exporter(conn: Connexion, carto_id: uuid.UUID, organisation_id: uuid.UUID) -> bytes | None:
    """Le zip de la carto, ou None si elle n'existe pas pour cette organisation."""
    carto = lire_carto(conn, carto_id, organisation_id)
    if carto is None:
        return None
    return zip_des_tables(construire_tables(carto), carto)
