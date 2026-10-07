"""Travail `synchro` : la synchro nocturne du registre, puis la publication de son état (T013).

But : appliquer au registre DuckDB les jours RNE puis SIRENE qui manquent,
dans l'ordre, et recopier l'état de chaque source dans `etat_registre`
(Postgres) pour que l'app affiche la date de ses données.

Usage : le travail est inséré chaque nuit par `cartofr.travaux.planifier_synchro`
et exécuté par la boucle du worker. Il est global (`organisation_id` vide).

Entrées :
    - `<CARTOFR_DATA>/registre.duckdb` (CARTOFR_DATA vaut `data` par défaut),
      ouvert en écriture le temps du travail, puis fermé : entre deux synchros,
      un autre processus (la recherche) peut le lire en lecture seule ;
    - les API INPI et INSEE, par `synchro_rne` et `synchro_sirene` (identifiants
      dans l'environnement ou le fichier CARTOFR_ENV_FILE) ;
    - CARTOFR_SYNCHRO_JOURS_MAX : jours lus au plus par source et par passage
      (7 par défaut).
Sorties :
    - le registre mis à jour, et ses lignes `mises_a_jour` (une par jour et source) ;
    - `<CARTOFR_DATA>/synchro/jours.json` : le dernier jour appliqué de chaque source ;
    - une ligne par source (`rne`, `sirene`) dans `etat_registre`.

Règles :
    - Jours lus : du lendemain du dernier jour appliqué (la date du stock,
      2026-03-04, au départ) jusqu'à la veille, heure de Paris, un jour à la
      fois et dans l'ordre. Un jour appliqué n'est jamais relu : un jour RNE
      coûte environ 400 requêtes INPI (ADR-002).
    - Au plus CARTOFR_SYNCHRO_JOURS_MAX jours par source et par passage. Le
      retard depuis le stock (environ 215 jours au 2026-10-07) se résorbe en
      plusieurs nuits : 7 jours RNE, c'est environ 2 800 requêtes, sous le
      quota observé, et 6 jours de rattrapés par nuit.
    - RNE d'abord, SIRENE ensuite, et SIRENE ne dépasse jamais le dernier jour
      RNE appliqué : une société créée par SIRENE le jour J aurait sinon
      `debut = J`, et le RNE d'un jour antérieur ne pourrait plus la fermer
      (`fin >= debut`).
    - Une source s'arrête à son premier échec : les jours suivants attendent
      le passage suivant. Le quota INPI (429) donne le statut `quota` ; la
      nuit suivante reprend le même jour au curseur `searchAfter` sauvegardé.
    - `etat_registre` : `date_donnees` = dernier jour appliqué, `statut` =
      `en_cours` pendant le passage puis `succes`, `echec` ou `quota`,
      `volumes` = les comptes du passage, `erreur` = le message déjà écrit
      dans `mises_a_jour`, jamais le texte brut d'une exception.
    - Le dernier jour appliqué est gardé à côté du registre, avec l'empreinte
      de sa construction : un registre reconstruit repart de la date du stock.
      Ne jamais supprimer ce fichier d'un registre déjà synchronisé : la
      synchro repartirait de la date du stock et réappliquerait des jours
      anciens par-dessus des plus récents. `mises_a_jour` n'a pas de colonne
      de jour : c'est ce qui oblige à garder le jour ici.

Le travail échoue (statut `echec` dans `travaux`) si une source a échoué. Un
arrêt sur quota n'est pas un échec du travail. Rien n'est journalisé hors
volumes et types d'erreur.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, LiteralString
from zoneinfo import ZoneInfo

import duckdb
import psycopg
from psycopg.types.json import Jsonb

from cartofr.jobs import Contexte, enregistrer
from cartofr.registre import inpi_diff, synchro_rne, synchro_sirene
from cartofr.registre.construire import DATE_STOCK
from cartofr.registre.construire import SOURCE as SOURCE_CONSTRUCTION
from cartofr.registre.inpi_diff import ErreurInpi
from cartofr.registre.synchro_rne import MESSAGE_QUOTA, LecteurDiff
from cartofr.registre.synchro_sirene import ErreurSirene

log = logging.getLogger(__name__)

Connexion = psycopg.Connection[tuple[Any, ...]]

TYPE = "synchro"
RNE = "rne"
SIRENE = "sirene"
FUSEAU = ZoneInfo("Europe/Paris")
NOM_REGISTRE = "registre.duckdb"
VARIABLE_JOURS_MAX = "CARTOFR_SYNCHRO_JOURS_MAX"
JOURS_MAX_DEFAUT = 7

MESSAGE_REGISTRE_ABSENT = "registre introuvable : construire registre.duckdb avant la synchro"
MESSAGE_REGISTRE_OCCUPE = "registre inaccessible en écriture (ouvert par un autre processus ?)"


class SynchroEnEchec(RuntimeError):
    """Une source au moins a échoué. Le message ne porte aucune donnée."""


@dataclass
class EtatSource:
    """Issue d'une source pour un passage : ce qui est publié dans `etat_registre`."""

    source: str
    date_donnees: date
    statut: str = "succes"  # 'succes', 'echec' ou 'quota'
    volumes: dict[str, int] = field(default_factory=dict)
    erreur: str | None = None
    jours: list[date] = field(default_factory=list)  # jours appliqués, dans l'ordre


# --- Dates ------------------------------------------------------------------------


VARIABLE_DECALAGE = "CARTOFR_SYNCHRO_DECALAGE"


def decalage() -> int:
    """Jours d'écart avec aujourd'hui pour le dernier jour lu (CARTOFR_SYNCHRO_DECALAGE, 1 par défaut).

    Un jour appliqué n'est jamais relu : si l'INPI ou l'INSEE publient tard, lire
    la veille dès 2 h perdrait ces publications. La production lit J-2 (compose).
    """
    brut = os.environ.get(VARIABLE_DECALAGE, "").strip()
    try:
        valeur = int(brut) if brut else 1
    except ValueError:
        valeur = 1
    return max(valeur, 1)


def veille_a_paris(maintenant: datetime) -> date:
    """Le dernier jour complet à lire, à Paris : la veille, ou plus tôt selon le décalage."""
    return maintenant.astimezone(FUSEAU).date() - timedelta(days=decalage())


def jours_a_lire(dernier: date, jusqua: date, maximum: int) -> list[date]:
    """Les jours après `dernier`, jusqu'à `jusqua` inclus, au plus `maximum`, dans l'ordre."""
    if maximum < 1:
        return []
    nombre = min((jusqua - dernier).days, maximum)
    return [dernier + timedelta(days=i) for i in range(1, nombre + 1)]


def jours_max() -> int:
    """CARTOFR_SYNCHRO_JOURS_MAX, ou 7 si elle est absente ou n'est pas un entier positif."""
    brut = os.environ.get(VARIABLE_JOURS_MAX, "").strip()
    if not brut:
        return JOURS_MAX_DEFAUT
    try:
        valeur = int(brut)
    except ValueError:
        valeur = 0
    if valeur < 1:
        log.warning("%s invalide : %s jours par défaut", VARIABLE_JOURS_MAX, JOURS_MAX_DEFAUT)
        return JOURS_MAX_DEFAUT
    return valeur


def dossier_donnees() -> Path:
    return Path(os.environ.get("CARTOFR_DATA", "data"))


# --- Dernier jour appliqué, gardé à côté du registre --------------------------------


def empreinte_registre(registre: duckdb.DuckDBPyConnection) -> str:
    """Identifie la construction du registre : change quand il est reconstruit."""
    ligne = registre.execute(
        "select id, cast(debut_le as varchar) from mises_a_jour where source = ? order by id limit 1",
        [SOURCE_CONSTRUCTION],
    ).fetchone()
    return "" if ligne is None else f"{ligne[0]}|{ligne[1]}"


class Jours:
    """Le dernier jour appliqué par source, dans un fichier JSON écrit d'un coup."""

    def __init__(self, chemin: Path, empreinte: str) -> None:
        self.chemin = chemin
        self.empreinte = empreinte
        self.derniers: dict[str, date] = {}
        if chemin.is_file():
            donnees = json.loads(chemin.read_text(encoding="utf-8"))
            if donnees.get("registre") == empreinte:
                self.derniers = {s: date.fromisoformat(d) for s, d in donnees.get("jours", {}).items()}

    def dernier(self, source: str) -> date:
        """Le dernier jour appliqué, jamais avant la date du stock."""
        return max(self.derniers.get(source, DATE_STOCK), DATE_STOCK)

    def noter(self, source: str, jour: date) -> None:
        self.derniers[source] = jour
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        donnees = {
            "registre": self.empreinte,
            "jours": {s: d.isoformat() for s, d in sorted(self.derniers.items())},
        }
        tmp = self.chemin.with_suffix(".tmp")
        tmp.write_text(json.dumps(donnees, indent=2), encoding="utf-8")
        tmp.replace(self.chemin)


# --- Publication dans etat_registre -------------------------------------------------

_PUBLIER: LiteralString = """
insert into public.etat_registre as e (source, date_donnees, dernier_passage, statut, volumes, erreur, maj_le)
values (%s, %s, %s, %s, %s, %s, now())
on conflict (source) do update
   set date_donnees = excluded.date_donnees,
       dernier_passage = excluded.dernier_passage,
       statut = excluded.statut,
       volumes = excluded.volumes,
       erreur = excluded.erreur,
       maj_le = now()
"""


def publier(conn: Connexion, etat: EtatSource, passage: datetime, statut: str | None = None) -> None:
    """Écrit l'état d'une source dans `etat_registre` et valide."""
    conn.execute(
        _PUBLIER,
        (
            etat.source,
            etat.date_donnees,
            passage,
            statut or etat.statut,
            Jsonb(etat.volumes),
            etat.erreur,
        ),
    )
    conn.commit()


# --- Erreurs : le message du journal, jamais le texte brut ----------------------------


def _dernier_id(registre: duckdb.DuckDBPyConnection) -> int:
    ligne = registre.execute("select coalesce(max(id), 0) from mises_a_jour").fetchone()
    return int(ligne[0]) if ligne else 0


def _erreur(registre: duckdb.DuckDBPyConnection, source_journal: str, depuis_id: int, exc: Exception) -> str:
    """Le message écrit dans `mises_a_jour` par la synchro ; sinon un message sans donnée."""
    try:
        ligne = registre.execute(
            "select erreur from mises_a_jour where source = ? and id > ? and erreur is not null"
            " order by id desc limit 1",
            [source_journal, depuis_id],
        ).fetchone()
    except duckdb.Error:
        ligne = None
    if ligne is not None:
        return str(ligne[0])
    if isinstance(exc, ErreurInpi | ErreurSirene):
        return str(exc)  # nos messages : ni nom, ni identifiant, ni clé
    return f"{type(exc).__name__} pendant la synchro"


# --- Les deux sources ----------------------------------------------------------------


def synchro_rne_jours(
    conn: Connexion,
    registre: duckdb.DuckDBPyConnection,
    jours: Jours,
    jusqua: date,
    maximum: int,
    passage: datetime,
    fabrique: Callable[[], LecteurDiff],
    chemin_curseur: Path | None = None,
) -> EtatSource:
    """Applique les jours RNE manquants, un par un. S'arrête au premier échec ou au quota."""
    etat = EtatSource(RNE, jours.dernier(RNE))
    a_lire = jours_a_lire(etat.date_donnees, jusqua, maximum)
    total = synchro_rne.Bilan()
    pages = 0
    client: LecteurDiff | None = None
    for jour in a_lire:
        depuis_id = _dernier_id(registre)
        try:
            client = client or fabrique()
            resultat = synchro_rne.synchroniser(registre, jour, jour, client=client, chemin=chemin_curseur)
        except Exception as exc:
            etat.statut, etat.erreur = "echec", _erreur(registre, synchro_rne.SOURCE, depuis_id, exc)
            log.warning("synchro RNE du %s en échec : %s", jour, type(exc).__name__)
            break
        total.ajouter(resultat.bilan)
        pages += resultat.pages
        if resultat.statut != "succes":
            etat.statut = "quota" if resultat.erreur == MESSAGE_QUOTA else "echec"
            etat.erreur = resultat.erreur
            log.warning("synchro RNE du %s arrêtée : %s", jour, etat.statut)
            break
        jours.noter(RNE, jour)
        etat.date_donnees = jour
        etat.jours.append(jour)
        etat.volumes = _volumes_rne(etat, total, pages, client)
        publier(conn, etat, passage, statut="en_cours")
    etat.volumes = _volumes_rne(etat, total, pages, client)
    return etat


def _volumes_rne(
    etat: EtatSource, total: synchro_rne.Bilan, pages: int, client: LecteurDiff | None
) -> dict[str, int]:
    requetes = client.requetes if client is not None else 0
    return {"jours": len(etat.jours), "pages": pages, "requetes": requetes, **asdict(total)}


def synchro_sirene_jours(
    conn: Connexion,
    registre: duckdb.DuckDBPyConnection,
    jours: Jours,
    jusqua: date,
    maximum: int,
    passage: datetime,
    fabrique: Callable[[], synchro_sirene.Client],
) -> EtatSource:
    """Applique les jours SIRENE manquants, un par un, jusqu'à `jusqua`. S'arrête au premier échec."""
    etat = EtatSource(SIRENE, jours.dernier(SIRENE))
    a_lire = jours_a_lire(etat.date_donnees, jusqua, maximum)
    total: dict[str, int] = {}
    client: synchro_sirene.Client | None = None
    for jour in a_lire:
        depuis_id = _dernier_id(registre)
        try:
            client = client or fabrique()
            bilan = synchro_sirene.synchroniser(registre, jour, client)
        except Exception as exc:
            etat.statut, etat.erreur = "echec", _erreur(registre, synchro_sirene.SOURCE, depuis_id, exc)
            log.warning("synchro SIRENE du %s en échec : %s", jour, type(exc).__name__)
            break
        for nom, valeur in asdict(bilan).items():
            total[nom] = total.get(nom, 0) + int(valeur)
        jours.noter(SIRENE, jour)
        etat.date_donnees = jour
        etat.jours.append(jour)
        etat.volumes = _volumes_sirene(etat, total, client)
        publier(conn, etat, passage, statut="en_cours")
    etat.volumes = _volumes_sirene(etat, total, client)
    return etat


def _volumes_sirene(
    etat: EtatSource, total: dict[str, int], client: synchro_sirene.Client | None
) -> dict[str, int]:
    # `requetes` du bilan cumule le compteur du client : on garde le compteur, pas la somme.
    return {"jours": len(etat.jours), **total, "requetes": client.requetes if client is not None else 0}


def synchroniser(
    conn: Connexion,
    registre: duckdb.DuckDBPyConnection,
    passage: datetime,
    maximum: int,
    fabrique_rne: Callable[[], LecteurDiff],
    fabrique_sirene: Callable[[], synchro_sirene.Client],
    chemin_jours: Path,
    chemin_curseur: Path | None = None,
) -> list[EtatSource]:
    """Un passage complet : RNE puis SIRENE, publiés dans `etat_registre`. Rend l'état des deux."""
    jours = Jours(chemin_jours, empreinte_registre(registre))
    veille = veille_a_paris(passage)
    rne = synchro_rne_jours(conn, registre, jours, veille, maximum, passage, fabrique_rne, chemin_curseur)
    publier(conn, rne, passage)
    # SIRENE jamais après le dernier jour RNE appliqué (voir l'en-tête).
    sirene = synchro_sirene_jours(
        conn, registre, jours, min(veille, rne.date_donnees), maximum, passage, fabrique_sirene
    )
    publier(conn, sirene, passage)
    for etat in (rne, sirene):
        log.info(
            "synchro %s : %s, %s jour(s) appliqué(s), données au %s",
            etat.source,
            etat.statut,
            len(etat.jours),
            etat.date_donnees,
        )
    return [rne, sirene]


def _publier_echec(conn: Connexion, passage: datetime, message: str) -> None:
    """Le registre n'a pas pu s'ouvrir : les deux sources passent en échec, date inchangée."""
    for source in (RNE, SIRENE):
        conn.execute(
            "insert into public.etat_registre (source, dernier_passage, statut, volumes, erreur)"
            " values (%s, %s, 'echec', '{}'::jsonb, %s)"
            " on conflict (source) do update set dernier_passage = excluded.dernier_passage,"
            " statut = 'echec', volumes = '{}'::jsonb, erreur = excluded.erreur, maj_le = now()",
            (source, passage, message),
        )
    conn.commit()


@enregistrer(TYPE)
def travail_synchro(ctx: Contexte) -> None:
    """Le travail `synchro` de la file : ouvre le registre, synchronise, publie, ferme."""
    conn = ctx.conn
    if conn is None:
        raise SynchroEnEchec("le travail synchro a besoin de la connexion du worker")
    passage = datetime.now(UTC)
    dossier = dossier_donnees()
    chemin = dossier / NOM_REGISTRE
    if not chemin.is_file():
        _publier_echec(conn, passage, MESSAGE_REGISTRE_ABSENT)
        raise SynchroEnEchec(MESSAGE_REGISTRE_ABSENT)
    try:
        registre = duckdb.connect(str(chemin))
    except duckdb.Error as exc:
        _publier_echec(conn, passage, MESSAGE_REGISTRE_OCCUPE)
        raise SynchroEnEchec(MESSAGE_REGISTRE_OCCUPE) from exc
    inpi_diff.charger_env()
    try:
        etats = synchroniser(
            conn,
            registre,
            passage,
            jours_max(),
            inpi_diff.Client,
            synchro_sirene.Client,
            dossier / "synchro" / "jours.json",
        )
        registre.execute("checkpoint")
    finally:
        registre.close()
    en_echec = [e.source for e in etats if e.statut == "echec"]
    if en_echec:
        raise SynchroEnEchec(f"synchro en échec : {', '.join(en_echec)} (voir etat_registre)")
