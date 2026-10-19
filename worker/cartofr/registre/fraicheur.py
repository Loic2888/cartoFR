"""Contrôle de fraîcheur du registre (T015, SC-003) : 10 changements récents, retrouvés ou non.

But : prouver que le registre a au plus 7 jours de retard. On tire au hasard des changements
publiés par les sources pendant les 7 derniers jours (hier compris, aujourd'hui exclu : la
synchro tourne la nuit), puis on regarde si le registre les porte déjà.

Règle « retrouvé » : rejouer le changement avec les règles mêmes de la synchro ne modifie rien.
Le rejeu se fait dans une transaction annulée (`synchro_rne.simuler`,
`synchro_sirene.simuler_unites`) : le registre n'est jamais modifié. Un changement manquant
ou partiel (lien non ouvert, société non fermée, dénomination ancienne…) modifie au moins une
ligne : il n'est pas retrouvé, et le bilan dit quelles tables auraient bougé.

Tirage :
- RNE (API diff INPI) : un jour au hasard de la fenêtre, une lecture qui part d'un SIREN tiré
  au hasard (`searchAfter`), une fiche de personne morale au hasard dans la page. Coût : une
  page de `TAILLE_PAGE_RNE` fiches du quota INPI par tirage. Le curseur de la synchro
  (`<CARTOFR_DATA>/inpi_diff/curseur.json`) n'est jamais touché ;
- SIRENE (API Sirene) : un jour au hasard, la première unité légale traitée ce jour-là (hors
  entrepreneurs individuels) à partir d'un SIREN tiré au hasard.
Un même SIREN n'est vérifié qu'une fois par contrôle : un doublon est tiré de nouveau.

Limite connue : la source rend l'état actuel de la société. Si elle a encore changé après la
dernière synchro (aujourd'hui, par exemple), le contrôle la compte manquante à tort. Le SIREN
d'un écart est affiché pour qu'on le vérifie à la main.

Carto du pays (T052, SC-009) : `fraicheur_pays` lit la date des données de `pays.duckdb`
(la date du registre au moment du calcul de nuit, T048). Plus de 7 jours de retard, ou aucune
carto du pays, est un retard au même titre qu'un changement du registre manquant.

Journal : SIREN de personnes morales et volumes seulement, jamais un nom ni une clé de personne.
"""

from __future__ import annotations

import random
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, fields
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal, Protocol

import duckdb

from cartofr.registre import synchro_rne, synchro_sirene
from cartofr.registre.formalite import Fiche, FormaliteInvalide, lire_fiche
from cartofr.registre.inpi_diff import Curseur
from cartofr.registre.synchro_rne import LecteurDiff
from cartofr.registre.synchro_sirene import lignes_unites

FENETRE_JOURS = 7  # SC-003 : 7 jours de retard au plus
TAILLE_PAGE_RNE = 20
ESSAIS_PAR_TIRAGE = 5  # jour sans changement, page vide : on retire, pas plus

# Champs des bilans qui disent qu'une ligne du registre aurait changé.
CHANGEMENTS_RNE = (
    "societes_maj",
    "societes_creees",
    "societes_fermees",
    "societes_rouvertes",
    "liens_ouverts",
    "liens_fermes",
    "personnes_ouvertes",
    "personnes_fermees",
)
CHANGEMENTS_SIRENE = (
    "societes_modifiees",
    "societes_ajoutees",
    "societes_cessees",
    "societes_reactivees",
    "unites_legales_modifiees",
    "unites_legales_ajoutees",
)

Source = Literal["rne", "sirene"]


class LecteurSirene(Protocol):
    """Ce que le tirage SIRENE attend du client (`synchro_sirene.Client`, remplaçable en test)."""

    def premiere_unite_depuis(self, jour: date, siren_min: str) -> dict[str, Any] | None: ...


@dataclass(frozen=True)
class Tirage:
    """Un changement tiré : sa source, le jour de sa publication, la société, et son contenu brut."""

    source: Source
    jour: date
    siren: str
    contenu: Any  # une `Fiche` (RNE) ou une unité légale brute de l'API (SIRENE)


@dataclass(frozen=True)
class Verdict:
    tirage: Tirage
    ecarts: dict[str, int]  # champ du bilan → lignes qui auraient changé ; vide = retrouvé

    @property
    def retrouve(self) -> bool:
        return not self.ecarts


def fenetre(aujourdhui: date, jours: int = FENETRE_JOURS) -> list[date]:
    """Les jours contrôlés : de J-`jours` à J-1. Aujourd'hui n'est pas encore synchronisé."""
    return [aujourdhui - timedelta(days=n) for n in range(jours, 0, -1)]


def _ecarts(bilan: object, champs: tuple[str, ...]) -> dict[str, int]:
    noms = {f.name for f in fields(bilan)}  # pyright: ignore[reportArgumentType]
    return {c: int(getattr(bilan, c)) for c in champs if c in noms and getattr(bilan, c)}


def verifier(con: duckdb.DuckDBPyConnection, tirage: Tirage, aujourdhui: date) -> Verdict:
    """Le changement est-il dans le registre ? Rejeu annulé, avec les règles de la synchro."""
    if tirage.source == "rne":
        bilan = synchro_rne.simuler(con, [tirage.contenu], aujourdhui)
        return Verdict(tirage, _ecarts(bilan, CHANGEMENTS_RNE))
    bilan = synchro_sirene.simuler_unites(con, [tirage.contenu], aujourdhui)
    return Verdict(tirage, _ecarts(bilan, CHANGEMENTS_SIRENE))


def _siren_au_hasard(hasard: random.Random) -> str:
    return f"{hasard.randrange(10**9):09d}"


def tirer_rne(client: LecteurDiff, jours: list[date], hasard: random.Random) -> Tirage | None:
    """Une fiche de personne morale publiée un des `jours`, au hasard. None après trop d'essais."""
    with tempfile.TemporaryDirectory() as dossier:
        chemin = Path(dossier) / "curseur.json"  # jamais celui de la synchro
        for _ in range(ESSAIS_PAR_TIRAGE):
            jour = hasard.choice(jours)
            curseur = Curseur(jour, jour, search_after=_siren_au_hasard(hasard))
            page = next(iter(client.lire(jour, jour, curseur, TAILLE_PAGE_RNE, chemin)), None)
            if page is None:
                continue
            fiches: list[Fiche] = []
            for formalite in page.formalites:
                try:
                    fiche = lire_fiche(formalite)
                except FormaliteInvalide:
                    continue
                if fiche is not None:
                    fiches.append(fiche)
            if fiches:
                fiche = hasard.choice(fiches)
                return Tirage("rne", jour, fiche.siren, fiche)
    return None


def tirer_sirene(client: LecteurSirene, jours: list[date], hasard: random.Random) -> Tirage | None:
    """Une unité légale (hors EI) traitée un des `jours`, au hasard : la première à partir d'un
    SIREN tiré au hasard. None après trop d'essais."""
    for _ in range(ESSAIS_PAR_TIRAGE):
        jour = hasard.choice(jours)
        brute = client.premiere_unite_depuis(jour, _siren_au_hasard(hasard))
        lignes = lignes_unites([brute]) if brute is not None else []
        if lignes:
            return Tirage("sirene", jour, str(lignes[0]["siren"]), brute)
    return None


@dataclass
class Controle:
    verdicts: list[Verdict]
    non_tires: int  # tirages impossibles (aucun changement trouvé après plusieurs essais)

    @property
    def retrouves(self) -> int:
        return sum(v.retrouve for v in self.verdicts)

    @property
    def demandes(self) -> int:
        return len(self.verdicts) + self.non_tires


def controler(
    con: duckdb.DuckDBPyConnection,
    aujourdhui: date,
    tirer: dict[Source, Callable[[list[date]], Tirage | None]],
    combien: dict[Source, int],
) -> Controle:
    """Tire `combien[source]` changements de chaque source et vérifie chacun."""
    jours = fenetre(aujourdhui)
    verdicts: list[Verdict] = []
    non_tires = 0
    vus: set[str] = set()
    for source, n in combien.items():
        for _ in range(n):
            tirage = None
            for _ in range(ESSAIS_PAR_TIRAGE):
                tirage = tirer[source](jours)
                if tirage is None or tirage.siren not in vus:
                    break
                tirage = None  # déjà vérifié : on retire
            if tirage is None:
                non_tires += 1
                continue
            vus.add(tirage.siren)
            verdicts.append(verifier(con, tirage, aujourdhui))
    return Controle(verdicts, non_tires)


@dataclass(frozen=True)
class FraicheurPays:
    """La date des données de la carto du pays et son retard. Vide : pas de carto du pays."""

    date_donnees: date | None
    retard_jours: int | None

    @property
    def a_jour(self) -> bool:
        # Une date dans le futur n'est pas une carto fraîche : une ligne du registre est fausse.
        return self.retard_jours is not None and 0 <= self.retard_jours <= FENETRE_JOURS


def fraicheur_pays(chemin: Path, aujourdhui: date) -> FraicheurPays:
    """Le retard de la carto du pays au jour `aujourdhui` : la date des données du dernier calcul
    (`pays_bilan`), lue en lecture seule. Sans fichier ou sans date : pas à jour."""
    if not chemin.is_file():
        return FraicheurPays(None, None)
    con = duckdb.connect(str(chemin), read_only=True)
    try:
        ligne = con.execute("select date_donnees from pays_bilan order by calcule_le desc limit 1").fetchone()
    finally:
        con.close()
    if ligne is None or ligne[0] is None:
        return FraicheurPays(None, None)
    jour: date = ligne[0]
    return FraicheurPays(jour, (aujourdhui - jour).days)
