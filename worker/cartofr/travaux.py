"""File de travaux du worker : prendre, exécuter, enregistrer (T008, ADR-004).

But : une boucle qui prend le plus ancien travail `en_attente` de la table
`travaux`, l'exécute selon son type (registre `cartofr.jobs.TRAVAUX`) et
enregistre son statut (`termine` ou `echec`), sa durée et son erreur.

Usage :
    python -m cartofr                     # lance boucle(), voir __main__.py
    from cartofr.travaux import boucle
    boucle(arret=threading.Event(), intervalle=5.0)

Entrée : la table `travaux` de la base de l'app (DATABASE_URL, rôle service).
Sortie : les colonnes statut, debut_le, fin_le, duree_ms, erreur de chaque travail.

Un travail à la fois, même si deux boucles tournent : la boucle prend un
verrou consultatif Postgres (`pg_try_advisory_lock`) avant de prendre un
travail et le rend après l'avoir fini. La prise elle-même passe par
`for update skip locked`, pour qu'un travail ne soit jamais pris deux fois.
Le verrou est un verrou de session : la connexion doit aller directement à
Postgres, pas à travers un pooler en mode transaction.

Chaque écriture de statut est validée dans sa propre transaction. Si le
processus meurt pendant un travail, ce travail reste `en_cours` : la reprise
des travaux bloqués n'est pas traitée ici (à faire plus tard, par exemple
repasser en `en_attente` ou en `echec` les `en_cours` trop anciens au
démarrage).

Journaux et colonne `erreur` : identifiants, types, durées et nom de la
classe d'exception seulement. Jamais les paramètres d'un travail ni le texte
d'une exception, qui peuvent contenir des données (garde-fou 6, règle 4).

Synchro nocturne (T013) : à chaque tour, la boucle appelle `planifier_synchro`,
qui insère un travail `synchro` une fois par jour, dès que l'heure de Paris
atteint CARTOFR_SYNCHRO_HEURE (`HH:MM`). Le conteneur worker n'a pas de cron :
c'est la boucle qui planifie. La planification n'est active que si
CARTOFR_SYNCHRO_HEURE est définie (ou `planifier=True`) : un test ou un outil
qui lance la boucle ne déclenche jamais de synchro, donc aucun appel INPI ou
INSEE. En production : CARTOFR_SYNCHRO_HEURE=02:00.
"""

import logging
import os
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from typing import Any, LiteralString
from zoneinfo import ZoneInfo

import psycopg
from psycopg import pq
from psycopg.types.json import Jsonb

from cartofr.db import connecter
from cartofr.jobs import TRAVAUX, Contexte

log = logging.getLogger(__name__)

Connexion = psycopg.Connection[tuple[Any, ...]]

INTERVALLE_S = 5.0

# Clé du verrou consultatif « un travail à la fois » (valeur arbitraire, propre à cartoFR).
CLE_VERROU = 7_008_000_001

# Longueur maximale d'un type recopié dans un message (le type vient de la base).
_TYPE_MAX = 80

_PRENDRE: LiteralString = """
update public.travaux
   set statut = 'en_cours', debut_le = now()
 where id = (
         select id from public.travaux
          where statut = 'en_attente'
          order by cree_le, id
          for update skip locked
          limit 1
       )
returning id, type, organisation_id, parametres
"""

# fin_le et duree_ms calculés à partir du même instant.
_FINIR: LiteralString = """
update public.travaux t
   set statut = %s,
       fin_le = f.instant,
       duree_ms = greatest(0, round(extract(epoch from f.instant - t.debut_le) * 1000))::integer,
       erreur = %s
  from (select clock_timestamp() as instant) f
 where t.id = %s and t.statut = 'en_cours'
returning t.duree_ms
"""


@dataclass(frozen=True)
class Travail:
    """Un travail pris dans la file."""

    id: int
    type: str
    organisation_id: uuid.UUID | None
    parametres: dict[str, Any] = field(default_factory=dict)


def prendre(conn: Connexion) -> Travail | None:
    """Passe le plus ancien travail en attente à `en_cours` et le rend, ou None si la file est vide."""
    try:
        ligne = conn.execute(_PRENDRE).fetchone()
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    if ligne is None:
        return None
    ident, type_travail, organisation_id, parametres = ligne
    return Travail(
        id=ident,
        type=type_travail,
        organisation_id=organisation_id,
        parametres=parametres if isinstance(parametres, dict) else {},
    )


def _finir(conn: Connexion, travail: Travail, statut: str, erreur: str | None) -> int | None:
    """Écrit le statut final, la fin et la durée, et valide. Rend la durée en ms."""
    ligne = conn.execute(_FINIR, (statut, erreur, travail.id)).fetchone()
    conn.commit()
    return None if ligne is None else ligne[0]


def _type_court(type_travail: str) -> str:
    return type_travail if len(type_travail) <= _TYPE_MAX else type_travail[:_TYPE_MAX] + "…"


def executer(conn: Connexion, travail: Travail) -> str:
    """Exécute un travail déjà pris et enregistre son issue. Rend le statut final."""
    execution = TRAVAUX.get(travail.type)
    if execution is None:
        erreur = f"type de travail inconnu : {_type_court(travail.type)}"
        _finir(conn, travail, "echec", erreur)
        log.warning("travail %s en échec : type inconnu", travail.id)
        return "echec"

    ctx = Contexte(
        travail_id=travail.id,
        type=travail.type,
        organisation_id=travail.organisation_id,
        parametres=travail.parametres,
        conn=conn,
    )
    try:
        execution(ctx)
    except Exception as exc:
        nom = type(exc).__name__
        # Annule ce que le travail a laissé en cours avant d'écrire l'échec.
        conn.rollback()
        duree = _finir(conn, travail, "echec", f"échec du travail ({nom})")
        log.warning("travail %s (%s) en échec après %s ms : %s", travail.id, travail.type, duree, nom)
        return "echec"

    if conn.info.transaction_status == pq.TransactionStatus.INERROR:
        # Le travail a avalé une erreur SQL : sa transaction est perdue, il n'a pas abouti.
        conn.rollback()
        _finir(conn, travail, "echec", "échec du travail (transaction en erreur)")
        log.warning("travail %s (%s) en échec : transaction en erreur", travail.id, travail.type)
        return "echec"

    # Valide aussi ce que le travail aurait laissé dans la transaction ouverte.
    duree = _finir(conn, travail, "termine", None)
    log.info("travail %s (%s) terminé en %s ms", travail.id, travail.type, duree)
    return "termine"


def _verrou(conn: Connexion) -> bool:
    obtenu = conn.execute("select pg_try_advisory_lock(%s)", (CLE_VERROU,)).fetchone()
    conn.commit()
    return bool(obtenu and obtenu[0])


def _rendre_verrou(conn: Connexion) -> None:
    if conn.closed or conn.broken:
        return  # Connexion perdue : Postgres a déjà rendu le verrou de session.
    conn.rollback()
    conn.execute("select pg_advisory_unlock(%s)", (CLE_VERROU,))
    conn.commit()


def traiter_un(conn: Connexion) -> bool:
    """Prend et exécute au plus un travail. Rend True si un travail a été exécuté."""
    if not _verrou(conn):
        return False  # Une autre boucle exécute déjà un travail.
    try:
        travail = prendre(conn)
        if travail is None:
            return False
        log.info("travail %s (%s) pris", travail.id, _type_court(travail.type))
        executer(conn, travail)
        return True
    finally:
        _rendre_verrou(conn)


VARIABLE_HEURE = "CARTOFR_SYNCHRO_HEURE"
HEURE_SYNCHRO = time(2, 0)
FUSEAU = ZoneInfo("Europe/Paris")

# Clé du verrou de transaction qui sérialise la planification (une seule insertion par jour).
CLE_PLANIFICATION = 7_013_000_001

# Un travail `synchro` créé depuis l'heure du jour (planifié ou lancé à la main) suffit.
_PLANIFIER: LiteralString = """
insert into public.travaux (type, parametres, cree_le)
select 'synchro', %s, %s
 where not exists (
         select 1 from public.travaux where type = 'synchro' and cree_le >= %s
       )
returning id
"""


def heure_synchro(valeur: str | None = None) -> time:
    """L'heure de la synchro, `HH:MM` (CARTOFR_SYNCHRO_HEURE), 02:00 si vide."""
    brut = (valeur if valeur is not None else os.environ.get(VARIABLE_HEURE, "")).strip()
    if not brut:
        return HEURE_SYNCHRO
    try:
        heures, minutes = brut.split(":")
        return time(int(heures), int(minutes))
    except ValueError:
        raise ValueError(f"{VARIABLE_HEURE} doit être au format HH:MM, par exemple 02:00.") from None


def planifier_synchro(conn: Connexion, maintenant: datetime, heure: time = HEURE_SYNCHRO) -> int | None:
    """Insère le travail `synchro` du jour s'il est l'heure et qu'il n'existe pas encore.

    Le jour et l'heure sont ceux de Paris (changements d'heure compris). Un
    travail `synchro` créé depuis l'heure du jour, quel que soit son statut,
    suffit : aucun second n'est inséré. Deux appels simultanés sont sérialisés
    par un verrou de transaction ; le second voit la ligne du premier. `cree_le`
    vaut `maintenant`. Rend l'id inséré, ou None.
    """
    local = maintenant.astimezone(FUSEAU)
    if local.time() < heure:
        return None
    seuil = datetime.combine(local.date(), heure, tzinfo=FUSEAU)
    try:
        conn.execute("select pg_advisory_xact_lock(%s)", (CLE_PLANIFICATION,))
        # Requête distincte : sa photo est prise après le verrou, elle voit l'insertion d'un concurrent.
        ligne = conn.execute(
            _PLANIFIER, (Jsonb({"planifie_le": local.date().isoformat()}), maintenant, seuil)
        ).fetchone()
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    if ligne is None:
        return None
    log.info("travail %s (synchro) planifié", ligne[0])
    return int(ligne[0])


def _fermer(conn: Connexion | None) -> None:
    if conn is None or conn.closed:
        return
    try:
        conn.close()
    except Exception:  # fermeture au mieux
        pass


def boucle(
    arret: threading.Event | None = None,
    intervalle: float = INTERVALLE_S,
    connecteur: Callable[[], Connexion] = connecter,
    planifier: bool | None = None,
) -> None:
    """Traite la file jusqu'à ce que `arret` soit levé.

    File vide : attend `intervalle` secondes. Toute exception est journalisée
    (nom de classe seulement) et la boucle continue ; une connexion perdue
    est rouverte au tour suivant.

    `planifier` : insérer le travail `synchro` de chaque nuit. None (défaut) :
    seulement si CARTOFR_SYNCHRO_HEURE est définie.
    """
    arret = arret or threading.Event()
    if planifier is None:
        planifier = bool(os.environ.get(VARIABLE_HEURE, "").strip())
    heure = heure_synchro() if planifier else HEURE_SYNCHRO
    planifie_pour: date | None = None  # jour (Paris) déjà vérifié : pas de requête à chaque tour
    conn: Connexion | None = None
    log.info("file de travaux : démarrage (intervalle %s s)", intervalle)
    if planifier:
        log.info("synchro planifiée chaque jour à %s, heure de Paris", heure.strftime("%H:%M"))
    try:
        while not arret.is_set():
            try:
                if conn is None or conn.closed or conn.broken:
                    _fermer(conn)
                    conn = connecteur()
                if planifier:
                    maintenant = datetime.now(UTC)
                    local = maintenant.astimezone(FUSEAU)
                    if local.date() != planifie_pour and local.time() >= heure:
                        planifier_synchro(conn, maintenant, heure)
                        planifie_pour = local.date()
                if not traiter_un(conn):
                    arret.wait(intervalle)
            except Exception as exc:
                log.error("file de travaux : erreur %s, reprise dans %s s", type(exc).__name__, intervalle)
                if conn is not None and not (conn.closed or conn.broken):
                    try:
                        conn.rollback()
                    except Exception:  # la connexion sera rouverte
                        _fermer(conn)
                arret.wait(intervalle)
    finally:
        _fermer(conn)
        log.info("file de travaux : arrêt")
