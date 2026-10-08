"""Travail `carto` : calculer la carto d'un groupe et enregistrer son résultat (T021, FR-005, FR-006).

But : relier l'interface au moteur par la file de travaux. L'interface insère
une ligne `cartos` (statut `en_attente`) et un travail `carto` dont les
paramètres portent `carto_id` ; ce travail lit la carto et ses réglages, lance
le moteur sur le registre local et écrit `carto_societes` et `carto_liens`.

Usage : exécuté par la boucle du worker (`cartofr.travaux`), jamais appelé à la main.

Entrées :
    - la ligne `cartos` (id dans `parametres.carto_id`, même organisation que
      le travail) et sa version de `reglages` ;
    - `<CARTOFR_DATA>/registre.duckdb`, ouvert en lecture seule ;
    - `<CARTOFR_DATA>/synchro/jours.json` (synchro T013), pour la date des données ;
    - CARTOFR_CLE_EMPREINTE, si les réglages excluent des familles.
Sorties :
    - `cartos` : statut `en_cours` puis `terminee` ou `echec`, `date_donnees`,
      `fin_le`, `duree_ms` et `avertissement` (texte français, affiché tel quel) ;
    - une ligne `carto_societes` par société retenue, une ligne `carto_liens`
      par mandat au registre entre deux sociétés retenues, toutes avec
      l'`organisation_id` du travail (C2).

Règles :
    - Refus d'une version de réglages non validée (FR-005, principe 2, C1),
      même si le déclencheur de la base a été contourné. Les réglages sont
      revérifiés par `cartofr.reglages.valider` avant d'aller au moteur.
    - Le worker écrit en rôle service, qui contourne RLS : chaque lecture et
      chaque écriture filtre ou pose l'`organisation_id` du travail. Une carto
      d'une autre organisation est introuvable pour ce travail.
    - Résultat écrit d'un coup : sociétés, liens et statut `terminee` dans une
      seule transaction. Un échec n'en laisse aucune ligne.
    - Date des données : la plus ancienne des deux dates « dernier jour
      appliqué » (RNE, SIRENE) de la synchro, lues dans `jours.json` avec les
      outils de T013 ; sans fichier, la date du stock (2026-03-04). C'est la
      date jusqu'à laquelle le registre est complet. Au-delà de 7 jours
      (SC-003), l'avertissement le dit.
    - Durée : du passage à `en_cours` à l'écriture du résultat (SC-004).
    - Tête sans aucune autre société retenue : la carto est la tête seule, avec
      un avertissement qui explique pourquoi (C4, cas limite du PRD).
    - Échec : statut `echec` et un avertissement français sûr, jamais le texte
      d'une exception ; puis le travail échoue (T008 : la colonne `erreur` de
      `travaux` ne porte que le nom de la classe).
    - Aucun nom de personne n'est écrit (garde-fou 6) : la `Carto` du moteur
      n'a aucun champ qui puisse en porter, et les preuves sont des textes du
      moteur (rôle, marque, règle). `non_diffusible` inconnu s'écrit `false`
      (la colonne est obligatoire) ; `opposition_prospection` est toujours
      écrite, jamais déduite par défaut.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, LiteralString

import duckdb
import psycopg

from cartofr.empreinte import CleManquante, cle_depuis_env
from cartofr.jobs import Contexte, enregistrer
from cartofr.jobs.synchro import FUSEAU, NOM_REGISTRE, RNE, SIRENE, Jours, dossier_donnees, empreinte_registre
from cartofr.moteur import Carto, cartographier
from cartofr.reglages import Reglages, ReglagesInvalides, valider

log = logging.getLogger(__name__)

Connexion = psycopg.Connection[tuple[Any, ...]]

TYPE = "carto"
FRAICHEUR_JOURS = 7  # SC-003

# Messages affichés à l'utilisateur (colonne `avertissement`) : français, sans donnée.
NON_VALIDEE = (
    "Les réglages de cette carto ne sont pas validés : validez une version des réglages, "
    "puis relancez la carto."
)
REGLAGES_ILLISIBLES = (
    "Les réglages validés ne sont pas lisibles par le moteur : enregistrez et validez une "
    "nouvelle version des réglages, puis relancez la carto."
)
REGISTRE_ABSENT = "Le registre n'est pas disponible sur le serveur. Prévenez l'administrateur."
REGISTRE_OCCUPE = (
    "Le registre est indisponible pour le moment (mise à jour en cours ?). Relancez la carto plus tard."
)
CLE_MANQUANTE = (
    "Le serveur n'a pas de clé d'empreinte : les familles exclues ne peuvent pas être appliquées. "
    "Prévenez l'administrateur."
)
ECHEC = "La carto a échoué. Relancez-la ; si l'échec se répète, prévenez l'administrateur."
TETE_SEULE = (
    "Aucune filiale trouvée : la tête ne dirige aucune société au registre, et aucune autre "
    "société ne remplit les règles du groupe. La carto est réduite à la tête."
)


class CartoEnEchec(RuntimeError):
    """La carto n'a pas abouti. Le message est sûr : français, sans donnée."""


@dataclass(frozen=True)
class CartoLue:
    """Une carto à calculer et sa version de réglages, lues en base."""

    id: uuid.UUID
    organisation_id: uuid.UUID
    statut: str
    travail_id: int | None
    contenu: Any
    valide_le: datetime | None


_LIRE: LiteralString = """
select c.id, c.organisation_id, c.statut, c.travail_id, r.contenu, r.valide_le
  from public.cartos c
  join public.reglages r
    on r.id = c.reglages_id and r.groupe_id = c.groupe_id and r.organisation_id = c.organisation_id
 where c.id = %s and c.organisation_id = %s
"""

# Prise de la carto : seulement si elle attend encore, et pour ce travail.
_PRENDRE: LiteralString = """
update public.cartos
   set statut = 'en_cours', travail_id = %s
 where id = %s and organisation_id = %s and statut = 'en_attente'
   and (travail_id is null or travail_id = %s)
returning id
"""

_TERMINER: LiteralString = """
update public.cartos
   set statut = 'terminee', date_donnees = %s, fin_le = now(), duree_ms = %s, avertissement = %s
 where id = %s and organisation_id = %s and statut = 'en_cours'
returning id
"""

# Échec : seulement une carto qui n'est pas finie et qui n'appartient pas à un autre travail.
_ECHOUER: LiteralString = """
update public.cartos
   set statut = 'echec', fin_le = now(), avertissement = %s, duree_ms = %s,
       travail_id = coalesce(travail_id, %s)
 where id = %s and organisation_id = %s and statut in ('en_attente', 'en_cours')
   and (travail_id is null or travail_id = %s)
"""

_SOCIETE: LiteralString = """
insert into public.carto_societes (carto_id, organisation_id, siren, nom, niveau, maison_mere_siren,
  confiance, preuve, ciblable, raison_ciblable, opposition_prospection, non_diffusible)
values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

_LIEN: LiteralString = """
insert into public.carto_liens (carto_id, organisation_id, parent_siren, enfant_siren, role, preuve,
  confiance)
values (%s, %s, %s, %s, %s, %s, %s)
"""


# --- Règles sans base, testées seules ----------------------------------------------------


def verifier_reglages(valide_le: datetime | None, contenu: Any) -> Reglages:
    """Les réglages d'une carto, s'ils sont validés et lisibles. Lève CartoEnEchec sinon (C1)."""
    if valide_le is None:
        raise CartoEnEchec(NON_VALIDEE)
    try:
        return valider(contenu)
    except ReglagesInvalides:
        # Le détail n'est pas recopié : il peut citer une valeur saisie.
        raise CartoEnEchec(REGLAGES_ILLISIBLES) from None


def date_des_donnees(registre: Path) -> date:
    """Jusqu'à quand le registre est complet : le plus ancien dernier jour appliqué (RNE, SIRENE).

    Lu dans `<dossier du registre>/synchro/jours.json` (T013) ; sans fichier, ou
    pour un registre reconstruit depuis, la date du stock.
    """
    con = duckdb.connect(str(registre), read_only=True)
    try:
        construction = empreinte_registre(con)
    finally:
        con.close()
    jours = Jours(registre.parent / "synchro" / "jours.json", construction)
    return min(jours.dernier(RNE), jours.dernier(SIRENE))


def avertissement(carto: Carto, date_donnees: date, aujourdhui: date) -> str | None:
    """Ce que l'utilisateur doit savoir de cette carto : avertissements du moteur (garde de la
    boucle atteinte), tête seule, données anciennes. None sinon."""
    messages = list(carto.avertissements)
    if all(s.siren == carto.tete for s in carto.societes):
        messages.append(TETE_SEULE)
    if (aujourdhui - date_donnees).days > FRAICHEUR_JOURS:
        messages.append(
            f"Données du registre au {date_donnees.strftime('%d/%m/%Y')} : plus de "
            f"{FRAICHEUR_JOURS} jours de retard, des changements récents peuvent manquer."
        )
    return " ".join(messages) or None


def lignes_societes(carto: Carto, carto_id: uuid.UUID, organisation_id: uuid.UUID) -> list[tuple[Any, ...]]:
    """Les lignes `carto_societes`, avec l'organisation du travail.

    Preuve : le rattachement à la maison mère, puis la règle qui a fait entrer
    la société. La tête n'a ni confiance ni maison mère.
    """
    lignes = []
    for s in carto.societes:
        tete = s.siren == carto.tete
        preuve = s.preuve if tete else f"{s.preuve} · entrée dans le groupe : {s.pourquoi_dans_le_groupe}"
        lignes.append(
            (
                carto_id,
                organisation_id,
                s.siren,
                s.nom,
                s.niveau,
                None if tete else s.maison_mere_siren,
                None if tete else s.confiance,
                preuve,
                s.ciblable,
                s.raison_ciblable,
                bool(s.opposition_prospection),
                bool(s.non_diffusible),
            )
        )
    return lignes


def lignes_liens(carto: Carto, carto_id: uuid.UUID, organisation_id: uuid.UUID) -> list[tuple[Any, ...]]:
    """Les lignes `carto_liens` : chaque mandat au registre entre deux sociétés retenues."""
    return [
        (carto_id, organisation_id, lien.parent, lien.enfant, lien.role, lien.preuve, lien.confiance)
        for lien in carto.liens
    ]


# --- Base -----------------------------------------------------------------------------------


def lire(conn: Connexion, carto_id: uuid.UUID, organisation_id: uuid.UUID) -> CartoLue | None:
    ligne = conn.execute(_LIRE, (carto_id, organisation_id)).fetchone()
    conn.commit()
    if ligne is None:
        return None
    return CartoLue(*ligne)


def echouer(
    conn: Connexion,
    carto_id: uuid.UUID,
    organisation_id: uuid.UUID,
    travail_id: int,
    message: str,
    duree_ms: int | None = None,
) -> None:
    """Passe la carto en échec avec un message sûr, dans sa propre transaction."""
    conn.rollback()
    conn.execute(_ECHOUER, (message, duree_ms, travail_id, carto_id, organisation_id, travail_id))
    conn.commit()


def enregistrer_resultat(
    conn: Connexion,
    carto: Carto,
    carto_id: uuid.UUID,
    organisation_id: uuid.UUID,
    date_donnees: date,
    duree_ms: int,
    message: str | None,
) -> None:
    """Sociétés, liens et statut `terminee`, en une seule transaction."""
    try:
        with conn.cursor() as cur:
            cur.executemany(_SOCIETE, lignes_societes(carto, carto_id, organisation_id))
            cur.executemany(_LIEN, lignes_liens(carto, carto_id, organisation_id))
            cur.execute(_TERMINER, (date_donnees, duree_ms, message, carto_id, organisation_id))
            if cur.fetchone() is None:
                raise CartoEnEchec(ECHEC)  # la carto n'est plus en cours : rien n'est écrit
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


def _parametre_carto(parametres: dict[str, Any]) -> uuid.UUID:
    try:
        return uuid.UUID(str(parametres["carto_id"]))
    except (KeyError, ValueError):
        raise CartoEnEchec("paramètre carto_id absent ou invalide") from None


def _message(exc: BaseException) -> str:
    """Le message affiché pour une exception : jamais son texte, sauf nos propres messages."""
    if isinstance(exc, CartoEnEchec):
        return str(exc)
    if isinstance(exc, CleManquante):
        return CLE_MANQUANTE
    if isinstance(exc, duckdb.IOException):
        return REGISTRE_OCCUPE
    return ECHEC


@enregistrer(TYPE)
def travail_carto(ctx: Contexte) -> None:
    """Le travail `carto` de la file : lit, vérifie, calcule, enregistre."""
    conn = ctx.conn
    if conn is None:
        raise CartoEnEchec("le travail carto a besoin de la connexion du worker")
    if ctx.organisation_id is None:
        raise CartoEnEchec("le travail carto doit porter une organisation")
    carto_id = _parametre_carto(ctx.parametres)
    organisation_id = ctx.organisation_id

    lue = lire(conn, carto_id, organisation_id)
    if lue is None:
        raise CartoEnEchec("carto introuvable pour l'organisation du travail")
    if lue.statut != "en_attente" or lue.travail_id not in (None, ctx.travail_id):
        raise CartoEnEchec("carto déjà prise par un autre travail")

    try:
        reglages = verifier_reglages(lue.valide_le, lue.contenu)
    except CartoEnEchec as exc:
        echouer(conn, carto_id, organisation_id, ctx.travail_id, str(exc))
        log.warning("carto %s refusée : réglages non validés ou illisibles", carto_id)
        raise
    prise = conn.execute(_PRENDRE, (ctx.travail_id, carto_id, organisation_id, ctx.travail_id)).fetchone()
    conn.commit()
    if prise is None:  # prise entre-temps : on ne touche pas à la carto d'un autre travail
        raise CartoEnEchec("carto déjà prise par un autre travail")

    debut = time.monotonic()
    try:
        registre = dossier_donnees() / NOM_REGISTRE
        if not registre.is_file():
            raise CartoEnEchec(REGISTRE_ABSENT)
        donnees = date_des_donnees(registre)
        contenu = reglages.model_dump()
        cle = cle_depuis_env() if contenu["familles_exclues_empreintes"] else None
        carto = cartographier(contenu, registre, cle_empreinte=cle)
        duree_ms = round((time.monotonic() - debut) * 1000)
        message = avertissement(carto, donnees, datetime.now(FUSEAU).date())
        enregistrer_resultat(conn, carto, carto_id, organisation_id, donnees, duree_ms, message)
    except Exception as exc:
        duree_ms = round((time.monotonic() - debut) * 1000)
        try:
            echouer(conn, carto_id, organisation_id, ctx.travail_id, _message(exc), duree_ms)
        except Exception as erreur:  # la base elle-même est en cause : le travail échoue quand même
            log.warning("carto %s : statut d'échec non écrit (%s)", carto_id, type(erreur).__name__)
        log.warning("carto %s en échec : %s", carto_id, type(exc).__name__)
        if isinstance(exc, CartoEnEchec):
            raise
        raise CartoEnEchec(_message(exc)) from exc
    log.info(
        "carto %s terminée : %s sociétés, %s liens, %s ms",
        carto_id,
        len(carto.societes),
        len(carto.liens),
        duree_ms,
    )
