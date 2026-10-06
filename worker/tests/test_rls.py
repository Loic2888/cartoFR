"""Cloisonnement RLS de la base de l'app (T006, règle produit 7).

Deux organisations A et B, un membre chacune : un membre de A ne lit aucune
ligne de B, et inversement ; anon ne lit rien. Plus la vérification qu'aucune
colonne de personne physique n'existe dans le schéma (principe 6).

Prérequis : la migration supabase/migrations/0001_socle.sql appliquée, et
DATABASE_URL pointant sur la base avec le rôle postgres (qui crée les
fixtures, puis endosse authenticated ou anon). Tout est fait dans une
transaction annulée à la fin : la base n'est pas modifiée.

Sans DATABASE_URL : test ignoré en local, échec en CI (variable CI définie),
pour qu'un test non lancé ne passe jamais pour un test vert.
"""

import json
import os
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, LiteralString

import psycopg
import pytest
from psycopg import sql

from cartofr.db import VARIABLE_URL, connecter

TABLES = ("organisations", "membres", "travaux", "etat_registre")

Connexion = psycopg.Connection[tuple[Any, ...]]


@dataclass(frozen=True)
class Monde:
    """Les fixtures créées pour un test."""

    org_a: uuid.UUID
    org_b: uuid.UUID
    user_a: uuid.UUID
    user_b: uuid.UUID
    user_sans_org: uuid.UUID


@pytest.fixture
def conn() -> Iterator[Connexion]:
    if not os.environ.get(VARIABLE_URL):
        message = (
            f"{VARIABLE_URL} n'est pas définie : le test RLS a besoin d'une base. "
            "Démarrer la base locale (infra/README.md), appliquer les migrations "
            "(bash infra/appliquer-migrations.sh), puis exporter DATABASE_URL."
        )
        if os.environ.get("CI"):
            pytest.fail(message)
        pytest.skip(message)
    connexion = connecter()
    try:
        manquantes = [
            t
            for t in TABLES
            if connexion.execute("select to_regclass(%s)", (f"public.{t}",)).fetchone() == (None,)
        ]
        if manquantes:
            pytest.fail(f"Tables absentes ({', '.join(manquantes)}) : appliquer supabase/migrations/.")
        yield connexion
    finally:
        connexion.rollback()
        connexion.close()


@pytest.fixture
def monde(conn: Connexion) -> Monde:
    """Deux organisations, un membre chacune, un utilisateur sans organisation, des travaux."""
    user_a, user_b, user_sans_org = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    for uid, email in ((user_a, "a"), (user_b, "b"), (user_sans_org, "c")):
        conn.execute(
            "insert into auth.users (id, email) values (%s, %s)",
            (uid, f"{email}-{uid}@example.test"),
        )
    orgs: list[uuid.UUID] = []
    for nom in ("Organisation A (test)", "Organisation B (test)"):
        ligne = conn.execute(
            "insert into public.organisations (nom) values (%s) returning id", (nom,)
        ).fetchone()
        assert ligne is not None
        orgs.append(ligne[0])
    org_a, org_b = orgs
    for org, uid in ((org_a, user_a), (org_b, user_b)):
        conn.execute("insert into public.membres (organisation_id, user_id) values (%s, %s)", (org, uid))
        conn.execute(
            "insert into public.travaux (type, organisation_id, parametres) values ('carto', %s, %s)",
            (org, json.dumps({"test": str(org)})),
        )
    # Un travail global (synchro), sans organisation.
    conn.execute("insert into public.travaux (type) values ('synchro')")
    return Monde(org_a, org_b, user_a, user_b, user_sans_org)


def _en_tant_que(conn: Connexion, user_id: uuid.UUID) -> None:
    """Endosse authenticated avec le JWT de user_id, pour la transaction en cours.

    Pose les deux formes lues par auth.uid() : request.jwt.claims (PostgREST
    récent) et request.jwt.claim.sub (forme historique, seule lue par l'image
    supabase/postgres nue, sans les migrations GoTrue).
    """
    conn.execute("set local role authenticated")
    claims = json.dumps({"sub": str(user_id), "role": "authenticated"})
    conn.execute(
        "select set_config('request.jwt.claims', %s, true), set_config('request.jwt.claim.sub', %s, true)",
        (claims, str(user_id)),
    )


def _ids(conn: Connexion, requete: LiteralString) -> set[Any]:
    return {ligne[0] for ligne in conn.execute(requete).fetchall()}


@pytest.mark.parametrize("cote", ["a", "b"])
def test_un_membre_ne_voit_que_son_organisation(conn: Connexion, monde: Monde, cote: str) -> None:
    moi, autre = (monde.org_a, monde.org_b) if cote == "a" else (monde.org_b, monde.org_a)
    user = monde.user_a if cote == "a" else monde.user_b
    _en_tant_que(conn, user)

    assert _ids(conn, "select id from public.organisations") == {moi}
    assert _ids(conn, "select organisation_id from public.membres") == {moi}
    assert _ids(conn, "select user_id from public.membres") == {user}
    assert _ids(conn, "select organisation_id from public.travaux") == {moi}
    # Aucune ligne de l'autre organisation, même demandée explicitement.
    for table, colonne in (
        ("organisations", "id"),
        ("membres", "organisation_id"),
        ("travaux", "organisation_id"),
    ):
        requete = sql.SQL("select count(*) from public.{} where {} = %s").format(
            sql.Identifier(table), sql.Identifier(colonne)
        )
        assert conn.execute(requete, (autre,)).fetchone() == (0,), table


def test_un_utilisateur_sans_organisation_ne_voit_rien(conn: Connexion, monde: Monde) -> None:
    _en_tant_que(conn, monde.user_sans_org)
    for table in ("organisations", "membres", "travaux"):
        requete = sql.SQL("select count(*) from public.{}").format(sql.Identifier(table))
        assert conn.execute(requete).fetchone() == (0,), table


def test_les_travaux_globaux_sont_invisibles_aux_membres(conn: Connexion, monde: Monde) -> None:
    _en_tant_que(conn, monde.user_a)
    globaux = conn.execute("select count(*) from public.travaux where organisation_id is null").fetchone()
    assert globaux == (0,)


def test_un_membre_ne_peut_pas_ecrire(conn: Connexion, monde: Monde) -> None:
    _en_tant_que(conn, monde.user_a)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(
            "insert into public.travaux (type, organisation_id) values ('carto', %s)",
            (monde.org_b,),
        )


@pytest.mark.parametrize("table", TABLES)
def test_anon_ne_lit_rien(conn: Connexion, monde: Monde, table: str) -> None:
    conn.execute("set local role anon")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(sql.SQL("select * from public.{}").format(sql.Identifier(table)))


def test_rls_active_sur_chaque_table(conn: Connexion) -> None:
    lignes = conn.execute(
        "select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace "
        "where n.nspname = 'public' and c.relname = any(%s) and c.relrowsecurity",
        (list(TABLES),),
    ).fetchall()
    assert {ligne[0] for ligne in lignes} == set(TABLES)


# Colonnes autorisées malgré un nom qui ressemble à une personne : le nom d'une
# organisation cliente n'est pas celui d'une personne physique.
COLONNES_AUTORISEES = {("organisations", "nom")}
MOTS_PERSONNE = ("nom", "prenom", "email", "mail", "personne", "dirigeant", "telephone", "naissance")


def test_aucune_colonne_de_personne_physique(conn: Connexion) -> None:
    lignes = conn.execute(
        "select table_name, column_name from information_schema.columns "
        "where table_schema = 'public' and table_name = any(%s)",
        (list(TABLES),),
    ).fetchall()
    assert lignes, "aucune colonne lue : schéma absent ?"
    suspectes = [
        (table, colonne)
        for table, colonne in lignes
        if any(mot in colonne for mot in MOTS_PERSONNE) and (table, colonne) not in COLONNES_AUTORISEES
    ]
    assert suspectes == []
