"""Client de l'API différentielle de l'INPI (`/api/companies/diff`).

But : lire les formalités RNE modifiées entre deux dates, page par page, et
pouvoir reprendre une lecture interrompue (quota atteint, panne) là où elle
s'est arrêtée.

Usage :
    client = Client()
    for page in client.lire(date(2026, 10, 5), date(2026, 10, 5)):
        ...  # page.formalites : liste de fiches JSON complètes

Entrées :
    - INPI_USERNAME, INPI_PASSWORD : identifiants, lus dans l'environnement.
      `charger_env()` les prend dans le fichier donné par CARTOFR_ENV_FILE
      (`.env` par défaut) s'ils n'y sont pas déjà.
    - CARTOFR_DATA : dossier des données (`data` par défaut).
Sorties :
    - <CARTOFR_DATA>/inpi_diff/curseur.json : où en est la lecture (dates,
      searchAfter, pages et formalités lues). Aucune formalité n'y est écrite.

Ce que dit l'API (documentation technique INPI v4.0, juin 2025, et une sonde
du 2026-10-06) :
    - `from` est exclu, `to` est inclus : lire le jour J, c'est from=J-1, to=J.
    - `pageSize` va de 1 à 100. Le corps est une liste de `{"company": ...}`.
    - La suite se demande avec `searchAfter` = l'en-tête de réponse
      `pagination-search-after` (un SIREN). Une page vide marque la fin.
    - `/diff/count` ne donne le total que s'il est sous 10 000.
    - 429 : quota journalier dépassé.

Le module ne journalise rien : ni fiche, ni identifiant, ni nom. Il compte.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx

BASE = "https://registre-national-entreprises.inpi.fr/api"
PAGE_MAX = 100
ENTETE_SUITE = "pagination-search-after"


class ErreurInpi(RuntimeError):
    """L'API INPI a refusé ou n'a pas pu servir la demande."""


class IdentifiantsManquants(ErreurInpi):
    """INPI_USERNAME ou INPI_PASSWORD absent de l'environnement."""


class QuotaAtteint(ErreurInpi):
    """L'INPI a répondu 429 : le quota du jour est épuisé.

    Le curseur sauvegardé permet de reprendre la lecture plus tard.
    """

    def __init__(self, curseur: Curseur | None) -> None:
        super().__init__("Quota INPI du jour atteint (erreur 429). Reprendre demain depuis le curseur.")
        self.curseur = curseur


def charger_env(chemin: str | Path | None = None) -> None:
    """Complète l'environnement avec un fichier `.env`, sans écraser l'existant.

    Le chemin vient de l'argument, sinon de CARTOFR_ENV_FILE, sinon `.env`.
    Un fichier absent n'est pas une erreur : l'environnement peut suffire.
    """
    fichier = Path(chemin or os.environ.get("CARTOFR_ENV_FILE", ".env"))
    if not fichier.is_file():
        return
    for ligne in fichier.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, valeur = ligne.split("=", 1)
        cle = cle.strip().removeprefix("export ").strip()
        os.environ.setdefault(cle, valeur.strip().strip('"').strip("'"))


def identifiants() -> tuple[str, str]:
    """Rend (utilisateur, mot de passe) INPI, ou une erreur claire s'il en manque."""
    manquants = [n for n in ("INPI_USERNAME", "INPI_PASSWORD") if not os.environ.get(n)]
    if manquants:
        raise IdentifiantsManquants(
            f"Identifiants INPI absents : {', '.join(manquants)}. "
            "Les mettre dans .env (ou indiquer le fichier avec CARTOFR_ENV_FILE)."
        )
    return os.environ["INPI_USERNAME"], os.environ["INPI_PASSWORD"]


def chemin_curseur() -> Path:
    """Emplacement par défaut du curseur : <CARTOFR_DATA>/inpi_diff/curseur.json."""
    return Path(os.environ.get("CARTOFR_DATA", "data")) / "inpi_diff" / "curseur.json"


@dataclass
class Curseur:
    """Où en est la lecture d'une période. `search_after` vaut None au départ."""

    depuis: date
    jusqua: date
    search_after: str | None = None
    pages: int = 0
    formalites: int = 0
    fini: bool = False

    def sauver(self, chemin: Path) -> None:
        """Écrit le curseur en JSON, d'un coup (fichier temporaire puis renommage)."""
        chemin.parent.mkdir(parents=True, exist_ok=True)
        donnees = asdict(self) | {"depuis": self.depuis.isoformat(), "jusqua": self.jusqua.isoformat()}
        tmp = chemin.with_suffix(".tmp")
        tmp.write_text(json.dumps(donnees, indent=2), encoding="utf-8")
        tmp.replace(chemin)

    @classmethod
    def charger(cls, chemin: Path) -> Curseur | None:
        """Relit un curseur sauvegardé, ou None s'il n'y en a pas."""
        if not chemin.is_file():
            return None
        d = json.loads(chemin.read_text(encoding="utf-8"))
        return cls(
            depuis=date.fromisoformat(d["depuis"]),
            jusqua=date.fromisoformat(d["jusqua"]),
            search_after=d.get("search_after"),
            pages=int(d.get("pages", 0)),
            formalites=int(d.get("formalites", 0)),
            fini=bool(d.get("fini", False)),
        )


@dataclass(frozen=True)
class Page:
    """Une page de l'API diff. `pagination` garde les en-têtes `pagination-*` (des nombres)."""

    numero: int
    formalites: list[dict[str, Any]]
    search_after: str | None
    pagination: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Compte:
    """Réponse de `/diff/count` : le total n'est connu que sous 10 000."""

    total: int | None
    plus_de_10000: bool


class Client:
    """Client de l'API diff : connexion, pagination par searchAfter, reprise.

    `delai` espace les requêtes (au-delà d'une par seconde, l'INPI coupe la
    connexion). `dormir` et `http` sont remplaçables pour les tests.
    """

    def __init__(
        self,
        http: httpx.Client | None = None,
        base: str = BASE,
        delai: float = 1.0,
        essais: int = 3,
        attente: float = 10.0,
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        self.http = http or httpx.Client(timeout=httpx.Timeout(120.0, connect=30.0))
        self.base = base.rstrip("/")
        self.delai = delai
        self.essais = essais
        self.attente = attente
        self.dormir = dormir
        self.requetes = 0
        self._jeton: str | None = None
        self._derniere = 0.0

    def _connecter(self) -> str:
        utilisateur, mot_de_passe = identifiants()
        r = self.http.post(f"{self.base}/sso/login", json={"username": utilisateur, "password": mot_de_passe})
        if r.status_code in (401, 403):
            raise ErreurInpi(f"Connexion INPI refusée (code {r.status_code}) : vérifier les identifiants.")
        r.raise_for_status()
        self._jeton = str(r.json()["token"])
        return self._jeton

    def _get(self, chemin: str, params: dict[str, str | int]) -> httpx.Response:
        """GET avec jeton : reconnexion une fois sur 401, essais limités sur 5xx et coupures."""
        reconnecte = False
        echecs = 0
        while True:
            jeton = self._jeton or self._connecter()
            attente = self._derniere + self.delai - time.monotonic()
            if attente > 0:
                self.dormir(attente)
            self._derniere = time.monotonic()
            self.requetes += 1
            try:
                r = self.http.get(
                    f"{self.base}{chemin}", params=params, headers={"Authorization": f"Bearer {jeton}"}
                )
            except httpx.TransportError as e:
                echecs += 1
                if echecs > self.essais:
                    raise ErreurInpi(f"INPI injoignable après {self.essais} essais.") from e
                self.dormir(self.attente * echecs)
                continue
            if r.status_code == 401 and not reconnecte:
                # Le jeton a expiré : une seule reconnexion, sinon c'est un vrai refus.
                reconnecte = True
                self._jeton = None
                continue
            if r.status_code == 429:
                raise QuotaAtteint(None)
            if r.status_code >= 500:
                echecs += 1
                if echecs > self.essais:
                    raise ErreurInpi(f"Erreur INPI {r.status_code} après {self.essais} essais.")
                self.dormir(self.attente * echecs)
                continue
            if r.status_code >= 400:
                raise ErreurInpi(f"Requête INPI refusée (code {r.status_code}).")
            return r

    @staticmethod
    def _periode(depuis: date, jusqua: date) -> dict[str, str | int]:
        # `from` est exclu par l'API : on part de la veille pour inclure `depuis`.
        return {"from": (depuis - timedelta(days=1)).isoformat(), "to": jusqua.isoformat()}

    def compter(self, depuis: date, jusqua: date) -> Compte:
        """Nombre de formalités de la période (dates incluses), s'il est sous 10 000."""
        d = self._get("/companies/diff/count", self._periode(depuis, jusqua)).json()
        total = d.get("nbResults")
        return Compte(
            total=int(total) if total is not None else None, plus_de_10000=bool(d.get("isNbResultsOver10000"))
        )

    def lire(
        self,
        depuis: date,
        jusqua: date,
        curseur: Curseur | None = None,
        page_size: int = PAGE_MAX,
        chemin: Path | None = None,
    ) -> Iterator[Page]:
        """Rend les pages de la période `depuis`..`jusqua` (dates incluses).

        Le curseur avance et se sauvegarde quand la page suivante est demandée,
        donc après que l'appelant a traité la précédente. Sur un 429, il est
        sauvegardé tel quel et `QuotaAtteint` est levée : la page refusée sera
        relue à la reprise, aucune n'est perdue ni lue deux fois.
        """
        if not 1 <= page_size <= PAGE_MAX:
            raise ValueError(f"page_size doit aller de 1 à {PAGE_MAX}.")
        chemin = chemin or chemin_curseur()
        if curseur is None:
            curseur = Curseur(depuis, jusqua)
        elif (curseur.depuis, curseur.jusqua) != (depuis, jusqua):
            raise ValueError("Le curseur sauvegardé porte sur une autre période.")
        while not curseur.fini:
            params = self._periode(depuis, jusqua) | {"pageSize": page_size}
            if curseur.search_after:
                params["searchAfter"] = curseur.search_after
            try:
                r = self._get("/companies/diff", params)
            except QuotaAtteint:
                curseur.sauver(chemin)
                raise QuotaAtteint(curseur) from None
            formalites = r.json()
            if not isinstance(formalites, list):
                raise ErreurInpi("Réponse INPI inattendue : une liste de formalités était attendue.")
            suite = r.headers.get(ENTETE_SUITE) or None
            pagination = {
                k: v for k, v in r.headers.items() if k.startswith("pagination-") and k != ENTETE_SUITE
            }
            if formalites:
                yield Page(curseur.pages + 1, formalites, suite, pagination)
                curseur.pages += 1
                curseur.formalites += len(formalites)
            # Fin : page vide, pas de suite, ou une suite qui n'avance plus.
            curseur.fini = not formalites or suite is None or suite == curseur.search_after
            curseur.search_after = suite or curseur.search_after
            curseur.sauver(chemin)
