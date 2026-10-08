"""Registre des types de travaux du worker (T008, ADR-004).

But : associer chaque `travaux.type` à la fonction qui l'exécute. Les tâches
suivantes (synchro T013, carto T021, IA T025) écrivent leur module dans ce
paquet et y enregistrent leur type avec le décorateur `enregistrer`, puis
importent ce module en bas de ce fichier.

Usage :
    from cartofr.jobs import Contexte, enregistrer

    @enregistrer("synchro")
    def synchro(ctx: Contexte) -> None: ...

Entrée d'un travail : un `Contexte` (id, organisation, paramètres, connexion).
Sortie : rien. Une exception fait passer le travail en échec.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import psycopg


@dataclass(frozen=True)
class Contexte:
    """Ce qu'un travail reçoit pour s'exécuter."""

    travail_id: int
    type: str
    organisation_id: uuid.UUID | None
    parametres: dict[str, Any] = field(default_factory=dict)
    # Connexion du worker (rôle service). Le travail gère ses propres transactions.
    conn: psycopg.Connection[tuple[Any, ...]] | None = None


Execution = Callable[[Contexte], None]

TRAVAUX: dict[str, Execution] = {}


def enregistrer(type_travail: str) -> Callable[[Execution], Execution]:
    """Décorateur : enregistre une fonction comme exécution du type donné."""

    def decorer(fonction: Execution) -> Execution:
        if type_travail in TRAVAUX:
            raise ValueError(f"type de travail déjà enregistré : {type_travail}")
        TRAVAUX[type_travail] = fonction
        return fonction

    return decorer


@enregistrer("ping")
def ping(ctx: Contexte) -> None:
    """Travail vide : sert aux tests et à vérifier que la boucle tourne."""


# Types de travaux enregistrés par leur module (import en bas : ils importent ce module).
from cartofr.jobs import carto as carto  # noqa: E402
from cartofr.jobs import proposition as proposition  # noqa: E402
from cartofr.jobs import synchro as synchro  # noqa: E402
