"""Connexion à la base de l'app (Postgres Supabase), en SQL direct (ADR-005).

But : donner au worker une connexion psycopg avec le rôle service, qui
contourne RLS (file de travaux, écriture des cartos).

Usage :
    from cartofr.db import connecter
    with connecter() as conn:
        conn.execute("select 1")

Entrée : la variable d'environnement DATABASE_URL (URL postgresql://…).
Sortie : une connexion psycopg, hors autocommit.

L'URL contient un mot de passe : elle n'est jamais écrite dans un log ni dans
un message d'erreur (garde-fou 5).
"""

import os
from typing import Any

import psycopg

VARIABLE_URL = "DATABASE_URL"


class ConfigurationManquante(RuntimeError):
    """La variable d'environnement de connexion n'est pas définie."""


def url_base() -> str:
    """Rend l'URL de la base lue dans l'environnement, ou lève ConfigurationManquante."""
    url = os.environ.get(VARIABLE_URL, "").strip()
    if not url:
        raise ConfigurationManquante(
            f"La variable {VARIABLE_URL} n'est pas définie : impossible de joindre la base de l'app. "
            "Renseignez-la dans l'environnement du worker (voir infra/README.md)."
        )
    return url


def connecter() -> psycopg.Connection[tuple[Any, ...]]:
    """Ouvre une connexion à la base de l'app."""
    return psycopg.connect(url_base())
