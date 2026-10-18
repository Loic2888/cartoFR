"""Planification du travail `pays` (T048, C2) : après chaque synchro terminée, et au plus tard 7 jours
après le dernier calcul réussi, même sans synchro.

Prérequis : supabase/migrations/ appliqué, DATABASE_URL vers une base de test (rôle postgres). Les
travaux de test sont datés de 2099 et supprimés avant et après chaque test.
Sans DATABASE_URL : tests ignorés en local, échec en CI (variable CI).
"""

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import pytest

from cartofr import travaux
from cartofr.db import VARIABLE_URL, connecter

Connexion = psycopg.Connection[tuple[Any, ...]]


@pytest.fixture
def conn() -> Iterator[Connexion]:
    if not os.environ.get(VARIABLE_URL):
        message = f"{VARIABLE_URL} n'est pas définie : la planification a besoin d'une base."
        if os.environ.get("CI"):
            pytest.fail(message)
        pytest.skip(message)
    connexion = connecter()
    if connexion.execute("select to_regclass('public.travaux')").fetchone() == (None,):
        connexion.close()
        pytest.fail("Table travaux absente : appliquer supabase/migrations/.")

    def nettoyer() -> None:
        connexion.rollback()
        connexion.execute(
            "delete from public.travaux where type in ('pays', 'synchro') and cree_le >= '2099-01-01'"
        )
        connexion.commit()

    nettoyer()
    try:
        yield connexion
    finally:
        nettoyer()
        connexion.close()


def utc(jour: int, heure: int = 0, minute: int = 0) -> datetime:
    return datetime(2099, 1, jour, heure, minute, tzinfo=UTC)


def travail(
    conn: Connexion, type_travail: str, statut: str, cree_le: datetime, fin_le: datetime | None
) -> None:
    conn.execute(
        "insert into public.travaux (type, statut, cree_le, fin_le) values (%s, %s, %s, %s)",
        (type_travail, statut, cree_le, fin_le),
    )
    conn.commit()


def pays(conn: Connexion) -> list[tuple[Any, ...]]:
    lignes = conn.execute(
        "select statut, cree_le from public.travaux where type = 'pays' and cree_le >= '2099-01-01'"
        " order by cree_le"
    ).fetchall()
    conn.commit()
    return lignes


def terminer_pays(conn: Connexion, fin_le: datetime, statut: str = "termine") -> None:
    conn.execute(
        "update public.travaux set statut = %s, fin_le = %s"
        " where type = 'pays' and statut = 'en_attente' and cree_le >= '2099-01-01'",
        (statut, fin_le),
    )
    conn.commit()


def test_c2_un_seul_travail_en_attente(conn: Connexion) -> None:
    """Sans calcul réussi depuis 7 jours, un travail est inséré ; jamais un second tant qu'il attend."""
    travail(conn, "pays", "termine", utc(1), utc(1, 1))
    assert travaux.planifier_pays(conn, utc(10)) is not None
    assert travaux.planifier_pays(conn, utc(10, 0, 1)) is None
    assert travaux.planifier_pays(conn, utc(20)) is None
    assert [s for s, _ in pays(conn)] == ["termine", "en_attente"]


def test_c2_apres_chaque_synchro_terminee(conn: Connexion) -> None:
    travail(conn, "pays", "termine", utc(10, 3), utc(10, 4))
    assert travaux.planifier_pays(conn, utc(11)) is None  # calcul récent, pas de synchro depuis
    travail(conn, "synchro", "echec", utc(11, 2), utc(11, 3))
    assert travaux.planifier_pays(conn, utc(11, 4)) is None  # une synchro en échec ne compte pas
    travail(conn, "synchro", "termine", utc(12, 2), utc(12, 3))
    assert travaux.planifier_pays(conn, utc(12, 4)) is not None
    terminer_pays(conn, utc(12, 5))
    assert travaux.planifier_pays(conn, utc(12, 6)) is None  # la synchro a déjà son calcul


def test_c2_synchro_terminee_pendant_un_calcul(conn: Connexion) -> None:
    """Une synchro finie après la création du dernier calcul en demande un nouveau, une fois le
    précédent fini."""
    travail(conn, "pays", "en_cours", utc(10, 1), None)
    travail(conn, "synchro", "termine", utc(10, 2), utc(10, 3))
    assert travaux.planifier_pays(conn, utc(10, 4)) is None  # un calcul tourne déjà
    conn.execute("update public.travaux set statut = 'termine', fin_le = %s where type = 'pays'"
                 " and cree_le >= '2099-01-01'", (utc(10, 5),))  # fmt: skip
    conn.commit()
    assert travaux.planifier_pays(conn, utc(10, 6)) is not None


def test_c2_au_plus_tard_sept_jours_sans_synchro(conn: Connexion) -> None:
    travail(conn, "pays", "termine", utc(1), utc(1, 1))
    assert travaux.planifier_pays(conn, utc(8, 0, 59)) is None
    assert travaux.planifier_pays(conn, utc(8, 1, 1)) is not None


def test_c2_un_calcul_en_echec_est_reessaye_une_fois_par_jour(conn: Connexion) -> None:
    travail(conn, "pays", "termine", utc(1), utc(1, 1))
    assert travaux.planifier_pays(conn, utc(9)) is not None
    terminer_pays(conn, utc(9, 1), "echec")
    assert travaux.planifier_pays(conn, utc(9, 12)) is None
    assert travaux.planifier_pays(conn, utc(9) + timedelta(days=1, minutes=1)) is not None


def test_c2_un_travail_orphelin_ne_bloque_pas_pour_toujours(conn: Connexion) -> None:
    """Un processus mort pendant le calcul laisse un travail `en_cours` : après 6 h, il ne bloque plus."""
    conn.execute(
        "insert into public.travaux (type, statut, cree_le, debut_le) values ('pays', 'en_cours', %s, %s)",
        (utc(1), utc(1)),
    )
    conn.commit()
    travail(conn, "synchro", "termine", utc(1, 2), utc(1, 3))
    assert travaux.planifier_pays(conn, utc(1, 5, 59)) is None
    assert travaux.planifier_pays(conn, utc(1, 6, 1)) is not None
