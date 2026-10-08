"""Travail `proposition` : faire proposer les réglages d'un groupe par l'IA (T025, FR-008, US3).

But : l'interface (bouton « Proposer », T026) insère un travail `proposition` dont
les paramètres portent `groupe_id` et `demande_par` (l'id auth.users du
consultant). Ce travail lit le groupe, interroge l'IA (cartofr.ia.proposition),
range les marques par la règle des homonymes au registre, puis enregistre une
nouvelle version de `reglages`, origine `proposition`, **sans `valide_le`**.

Usage : exécuté par la boucle du worker (`cartofr.travaux`), jamais appelé à la main.

Entrées :
    - le groupe (`groupes`, même organisation que le travail) et sa dernière version
      validée de réglages, dont les clés que l'IA ne propose pas sont reprises ;
    - `<CARTOFR_DATA>/registre.duckdb`, ouvert en lecture seule, deux fois : pour le
      contexte donné à l'IA, puis pour compter les homonymes. Il est refermé pendant
      l'appel à l'API, qui peut durer plusieurs minutes, pour ne pas bloquer la synchro ;
    - ANTHROPIC_API_KEY, CARTOFR_MODELE_IA (facultatif).
Sortie : une ligne `reglages` (version suivante du groupe) : `contenu` au schéma des
réglages (vérifié par cartofr.reglages.valider), `proposition` = modèle et éléments
(liste, valeur, source, homonymes, origine, liste déjà validée), `cree_par` = le
consultant s'il existe encore. Les éléments de la dernière version validée que l'IA ne
repropose pas y sont gardés, origine « validee » (principe 2, `garder_validees`).

Règles :
    - L'IA ne décide jamais (principe 1) : la version n'est pas validée, et la base
      refuse qu'elle le soit un jour (migration 0004). Le moteur ne tourne que sur une
      version validée (FR-005).
    - Rôle service : chaque lecture et chaque écriture filtre ou pose l'`organisation_id`
      du travail. Un groupe d'une autre organisation est introuvable.
    - Aucun nom de personne n'est envoyé à l'IA ni journalisé (garde-fou 6, R5).
    - Échec (paramètre invalide, groupe introuvable, registre absent, clé absente, API) :
      le travail échoue ; la colonne `erreur` de `travaux` ne porte que le nom de la
      classe d'exception (T008), que l'interface traduit.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any, LiteralString

import duckdb
import psycopg
from psycopg.types.json import Jsonb

from cartofr.ia.proposition import (
    ElementRange,
    client_ia,
    compter_homonymes,
    contenu_propose,
    garder_validees,
    lire_entree,
    modele,
    nettoyer,
    proposer,
    ranger,
    societes_du_groupe,
)
from cartofr.jobs import Contexte, enregistrer
from cartofr.jobs.synchro import NOM_REGISTRE, dossier_donnees
from cartofr.reglages import valider

log = logging.getLogger(__name__)

Connexion = psycopg.Connection[tuple[Any, ...]]

TYPE = "proposition"


class PropositionEnEchec(RuntimeError):
    """Le travail ne peut pas aboutir. Le message est sûr : français, sans donnée."""


class RegistreIndisponible(RuntimeError):
    """Le registre est absent ou verrouillé par la synchro."""


_GROUPE: LiteralString = """
select nom, tete_siren from public.groupes where id = %s and organisation_id = %s
"""

_BASE: LiteralString = """
select contenu from public.reglages
 where groupe_id = %s and organisation_id = %s and valide_le is not null
 order by version desc limit 1
"""

# Version suivante du groupe ; `cree_par` passe à nul si le compte a été effacé entre-temps.
_INSERER: LiteralString = """
insert into public.reglages (groupe_id, organisation_id, version, contenu, origine, proposition, cree_par)
select %(groupe)s, %(org)s, coalesce(max(r.version), 0) + 1, %(contenu)s, 'proposition', %(proposition)s,
       (select u.id from auth.users u where u.id = %(par)s)
  from public.reglages r where r.groupe_id = %(groupe)s
returning id, version
"""


def _uuid(parametres: dict[str, Any], cle: str, obligatoire: bool = True) -> uuid.UUID | None:
    valeur = parametres.get(cle)
    if valeur is None and not obligatoire:
        return None
    try:
        return uuid.UUID(str(valeur))
    except ValueError:
        raise PropositionEnEchec(f"paramètre {cle} absent ou invalide") from None


def _ouvrir(registre: Path) -> duckdb.DuckDBPyConnection:
    if not registre.is_file():
        raise RegistreIndisponible("registre absent")
    try:
        return duckdb.connect(str(registre), read_only=True)
    except (duckdb.IOException, duckdb.ConnectionException):
        # Message DuckDB non recopié : il contient le chemin et le PID du verrou.
        raise RegistreIndisponible("registre occupé") from None


def enregistrer_proposition(
    conn: Connexion,
    groupe_id: uuid.UUID,
    organisation_id: uuid.UUID,
    contenu: dict[str, Any],
    ranges: list[ElementRange],
    nom_modele: str,
    demande_par: uuid.UUID | None,
) -> tuple[uuid.UUID, int]:
    """Insère la version proposée, non validée. Une course sur le numéro : une seconde tentative."""
    proposition = {"modele": nom_modele, "elements": [r.en_json() for r in ranges]}
    for essai in (1, 2):
        try:
            ligne = conn.execute(
                _INSERER,
                {
                    "groupe": groupe_id,
                    "org": organisation_id,
                    "contenu": Jsonb(contenu),
                    "proposition": Jsonb(proposition),
                    "par": demande_par,
                },
            ).fetchone()
            conn.commit()
        except psycopg.errors.UniqueViolation:
            conn.rollback()
            if essai == 2:
                raise
            continue
        assert ligne is not None
        return ligne[0], int(ligne[1])
    raise AssertionError("inatteignable")


@enregistrer(TYPE)
def travail_proposition(ctx: Contexte) -> None:
    """Lit le groupe, interroge l'IA, range, enregistre la version proposée non validée."""
    conn = ctx.conn
    if conn is None or ctx.organisation_id is None:
        raise PropositionEnEchec("travail sans connexion ou sans organisation")
    groupe_id = _uuid(ctx.parametres, "groupe_id")
    demande_par = _uuid(ctx.parametres, "demande_par", obligatoire=False)
    assert groupe_id is not None

    ligne = conn.execute(_GROUPE, (groupe_id, ctx.organisation_id)).fetchone()
    base_ligne = conn.execute(_BASE, (groupe_id, ctx.organisation_id)).fetchone()
    conn.commit()
    if ligne is None:
        raise PropositionEnEchec("groupe introuvable dans l'organisation du travail")
    nom_groupe, tete = str(ligne[0]), str(ligne[1])
    base = base_ligne[0] if base_ligne is not None and isinstance(base_ligne[0], dict) else None

    registre = dossier_donnees() / NOM_REGISTRE
    con = _ouvrir(registre)
    try:
        entree = lire_entree(con, nom_groupe, tete)
    finally:
        con.close()

    nom_modele = modele()
    elements = nettoyer(proposer(entree, client_ia(), nom_modele))

    con = _ouvrir(registre)
    try:
        marques = [e.valeur for e in elements if e.type == "marque"]
        homonymes = compter_homonymes(con, marques, societes_du_groupe(con, tete)) if marques else {}
    finally:
        con.close()

    ranges = garder_validees(ranger(elements, homonymes), base)
    contenu = valider(contenu_propose(nom_groupe, tete, ranges, base)).model_dump()
    _, version = enregistrer_proposition(
        conn, groupe_id, ctx.organisation_id, contenu, ranges, nom_modele, demande_par
    )
    log.info(
        "travail %s : proposition enregistrée (version %s, %s éléments dont %s déjà validés"
        " non reproposés, %s marques ambiguës)",
        ctx.travail_id,
        version,
        len(ranges),
        sum(1 for r in ranges if r.origine == "validee"),
        sum(1 for r in ranges if r.liste == "marques_ambigues"),
    )
