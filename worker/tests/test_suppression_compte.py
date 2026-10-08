"""Suppression d'un compte (T031, règle produit 4, migration 0005).

Vérifie, en base, ce que devient l'organisation quand un compte est effacé de
auth.users (c'est ce que fait la page /compte, par l'API d'administration de
GoTrue) :

- ses appartenances disparaissent ; ses groupes, réglages et cartos restent à
  l'organisation, sans référence au compte (cree_par, valide_par à nul) ;
- son adresse e-mail ne reste dans aucune colonne du schéma public ;
- règle du dernier administrateur : s'il n'en reste aucun dans une
  organisation qui a encore des membres, le membre le plus ancien est promu ;
  sans membre restant, l'organisation et ses cartos sont gardées.

Prérequis : supabase/migrations/ appliqué, DATABASE_URL vers la base (rôle
postgres). Tout se passe dans une transaction annulée à la fin. Adresses en
example.test, jamais réelles.

Sans DATABASE_URL : tests ignorés en local, échec en CI (variable CI).
"""

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, LiteralString

import psycopg
import pytest
from psycopg import sql
from psycopg.types.json import Jsonb

from cartofr.db import VARIABLE_URL, connecter

Connexion = psycopg.Connection[tuple[Any, ...]]

TETE = "900000001"
DEBUT = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def conn() -> Iterator[Connexion]:
    if not os.environ.get(VARIABLE_URL):
        message = (
            f"{VARIABLE_URL} n'est pas définie : la suppression d'un compte se vérifie en base. "
            "Démarrer la base locale (infra/README.md), appliquer les migrations, puis exporter DATABASE_URL."
        )
        if os.environ.get("CI"):
            pytest.fail(message)
        pytest.skip(message)
    connexion = connecter()
    try:
        if connexion.execute("select to_regproc('public.membres_garder_un_admin')").fetchone() == (None,):
            pytest.fail("Fonction membres_garder_un_admin absente : appliquer supabase/migrations/.")
        yield connexion
    finally:
        connexion.rollback()
        connexion.close()


def _un(conn: Connexion, requete: LiteralString | sql.Composed, params: tuple[Any, ...]) -> Any:
    ligne = conn.execute(requete, params).fetchone()
    assert ligne is not None
    return ligne[0]


def compte(conn: Connexion) -> tuple[uuid.UUID, str]:
    """Un compte auth.users de test, avec une adresse unique en example.test."""
    ident = uuid.uuid4()
    email = f"membre-{ident.hex[:12]}@example.test"
    conn.execute("insert into auth.users (id, email) values (%s, %s)", (ident, email))
    return ident, email


def organisation(conn: Connexion) -> uuid.UUID:
    return _un(
        conn, "insert into public.organisations (nom) values ('Organisation de test T031') returning id", ()
    )


def adherer(conn: Connexion, org: uuid.UUID, user: uuid.UUID, role: str, jours: int) -> None:
    """Appartenance créée `jours` jours après DEBUT : l'ordre d'ancienneté est maîtrisé."""
    conn.execute(
        "insert into public.membres (organisation_id, user_id, role, cree_le) values (%s, %s, %s, %s)",
        (org, user, role, DEBUT + timedelta(days=jours)),
    )


def effacer(conn: Connexion, *users: uuid.UUID) -> None:
    """Ce que fait GoTrue (deleteUser) : une suppression dans auth.users, en une instruction."""
    conn.execute("delete from auth.users where id = any(%s)", (list(users),))


def roles(conn: Connexion, org: uuid.UUID) -> dict[uuid.UUID, str]:
    lignes = conn.execute(
        "select user_id, role from public.membres where organisation_id = %s", (org,)
    ).fetchall()
    return {u: r for u, r in lignes}


def remplir(conn: Connexion, org: uuid.UUID, auteur: uuid.UUID) -> dict[str, Any]:
    """Un groupe, une version validée de réglages et une carto terminée, créés par `auteur`."""
    groupe = _un(
        conn,
        "insert into public.groupes (organisation_id, tete_siren, nom, cree_par)"
        " values (%s, %s, 'Société de tête (test)', %s) returning id",
        (org, TETE, auteur),
    )
    reglages = _un(
        conn,
        "insert into public.reglages (groupe_id, organisation_id, version, contenu, cree_par,"
        " valide_le, valide_par)"
        " values (%s, %s, 1, %s, %s, now(), %s) returning id",
        (groupe, org, Jsonb({"marques_sures": ["Test"]}), auteur, auteur),
    )
    carto = _un(
        conn,
        "insert into public.cartos (organisation_id, groupe_id, reglages_id, statut, date_donnees)"
        " values (%s, %s, %s, 'terminee', current_date) returning id",
        (org, groupe, reglages),
    )
    conn.execute(
        "insert into public.carto_societes (carto_id, organisation_id, siren, nom, niveau, ciblable,"
        " opposition_prospection, non_diffusible) values (%s, %s, %s, 'Société de tête (test)', 0, true,"
        " false, false)",
        (carto, org, TETE),
    )
    return {"groupe": groupe, "reglages": reglages, "carto": carto}


def colonnes_texte_public(conn: Connexion) -> list[tuple[str, str]]:
    """Toutes les colonnes texte ou JSON des tables du schéma public."""
    return conn.execute(
        "select table_name, column_name from information_schema.columns"
        " where table_schema = 'public'"
        " and data_type in ('text', 'character varying', 'character', 'jsonb', 'json')"
        " and table_name in (select tablename from pg_tables where schemaname = 'public')"
    ).fetchall()


def occurrences(conn: Connexion, texte: str) -> list[str]:
    """Les colonnes du schéma public dont une ligne contient `texte`."""
    trouvees = []
    for table, colonne in colonnes_texte_public(conn):
        requete = sql.SQL("select exists (select 1 from public.{} where {}::text ilike %s)").format(
            sql.Identifier(table), sql.Identifier(colonne)
        )
        if _un(conn, requete, (f"%{texte}%",)):
            trouvees.append(f"{table}.{colonne}")
    return trouvees


# --- Ce qui reste à l'organisation ----------------------------------------------------------------


def test_les_cartos_restent_a_l_organisation_sans_reference_au_compte(conn: Connexion) -> None:
    org = organisation(conn)
    admin, _ = compte(conn)
    auteur, email = compte(conn)
    adherer(conn, org, admin, "admin", 0)
    adherer(conn, org, auteur, "membre", 1)
    ids = remplir(conn, org, auteur)

    effacer(conn, auteur)

    assert roles(conn, org) == {admin: "admin"}
    assert _un(conn, "select cree_par from public.groupes where id = %s", (ids["groupe"],)) is None
    ligne = conn.execute(
        "select cree_par, valide_par, valide_le is not null from public.reglages where id = %s",
        (ids["reglages"],),
    ).fetchone()
    assert ligne == (None, None, True)  # la version reste validée, sans validateur
    assert _un(conn, "select organisation_id from public.cartos where id = %s", (ids["carto"],)) == org
    assert _un(conn, "select count(*) from public.carto_societes where carto_id = %s", (ids["carto"],)) == 1
    assert occurrences(conn, email) == []


def test_aucune_colonne_ne_reference_auth_users_sans_regle_d_effacement(conn: Connexion) -> None:
    """Toute clé étrangère du schéma public vers auth.users cascade ou passe à nul : un compte
    s'efface toujours, et rien ne garde son identifiant."""
    regles = conn.execute(
        "select conrelid::regclass::text, confdeltype from pg_constraint"
        " where confrelid = 'auth.users'::regclass and connamespace = 'public'::regnamespace"
    ).fetchall()
    assert regles, "aucune clé étrangère vers auth.users : le test ne vérifie plus rien"
    assert {t for t, regle in regles if regle not in ("c", "n")} == set()


# --- Règle du dernier administrateur ---------------------------------------------------------------


def test_seul_admin_efface_le_membre_le_plus_ancien_est_promu(conn: Connexion) -> None:
    org = organisation(conn)
    admin, _ = compte(conn)
    ancien, _ = compte(conn)
    recent, _ = compte(conn)
    adherer(conn, org, admin, "admin", 0)
    adherer(conn, org, recent, "membre", 5)
    adherer(conn, org, ancien, "membre", 2)

    effacer(conn, admin)

    assert roles(conn, org) == {ancien: "admin", recent: "membre"}


def test_anciennete_egale_departagee_par_identifiant(conn: Connexion) -> None:
    org = organisation(conn)
    admin, _ = compte(conn)
    a, _ = compte(conn)
    b, _ = compte(conn)
    adherer(conn, org, admin, "admin", 0)
    adherer(conn, org, a, "membre", 3)
    adherer(conn, org, b, "membre", 3)

    effacer(conn, admin)

    assert roles(conn, org)[min(a, b)] == "admin"
    assert list(roles(conn, org).values()).count("admin") == 1


def test_un_autre_admin_reste_personne_n_est_promu(conn: Connexion) -> None:
    org = organisation(conn)
    admin, _ = compte(conn)
    autre_admin, _ = compte(conn)
    membre, _ = compte(conn)
    adherer(conn, org, admin, "admin", 0)
    adherer(conn, org, membre, "membre", 1)
    adherer(conn, org, autre_admin, "admin", 2)

    effacer(conn, admin)

    assert roles(conn, org) == {autre_admin: "admin", membre: "membre"}


def test_un_simple_membre_efface_ne_change_aucun_role(conn: Connexion) -> None:
    org = organisation(conn)
    admin, _ = compte(conn)
    membre, _ = compte(conn)
    autre, _ = compte(conn)
    adherer(conn, org, admin, "admin", 5)
    adherer(conn, org, membre, "membre", 0)
    adherer(conn, org, autre, "membre", 1)

    effacer(conn, membre)

    assert roles(conn, org) == {admin: "admin", autre: "membre"}


def test_deux_admins_effaces_ensemble_un_seul_promu(conn: Connexion) -> None:
    org = organisation(conn)
    a1, _ = compte(conn)
    a2, _ = compte(conn)
    m1, _ = compte(conn)
    m2, _ = compte(conn)
    adherer(conn, org, a1, "admin", 0)
    adherer(conn, org, a2, "admin", 1)
    adherer(conn, org, m1, "membre", 2)
    adherer(conn, org, m2, "membre", 3)

    effacer(conn, a1, a2)

    assert roles(conn, org) == {m1: "admin", m2: "membre"}


def test_dernier_membre_efface_l_organisation_et_ses_cartos_restent(conn: Connexion) -> None:
    org = organisation(conn)
    seul, email = compte(conn)
    adherer(conn, org, seul, "admin", 0)
    ids = remplir(conn, org, seul)

    effacer(conn, seul)

    assert roles(conn, org) == {}
    assert _un(conn, "select count(*) from public.organisations where id = %s", (org,)) == 1
    assert _un(conn, "select count(*) from public.cartos where id = %s", (ids["carto"],)) == 1
    assert occurrences(conn, email) == []


def test_promotion_limitee_aux_organisations_ou_le_compte_etait_admin(conn: Connexion) -> None:
    """Admin de A, simple membre de B : seule A reçoit un nouvel administrateur."""
    org_a, org_b = organisation(conn), organisation(conn)
    double, _ = compte(conn)
    membre_a, _ = compte(conn)
    admin_b, _ = compte(conn)
    membre_b, _ = compte(conn)
    adherer(conn, org_a, double, "admin", 0)
    adherer(conn, org_a, membre_a, "membre", 1)
    adherer(conn, org_b, double, "membre", 0)
    adherer(conn, org_b, admin_b, "admin", 1)
    adherer(conn, org_b, membre_b, "membre", 2)

    effacer(conn, double)

    assert roles(conn, org_a) == {membre_a: "admin"}
    assert roles(conn, org_b) == {admin_b: "admin", membre_b: "membre"}


def test_supprimer_une_organisation_reste_possible(conn: Connexion) -> None:
    """La cascade organisations → membres ne déclenche aucune promotion ni erreur."""
    org = organisation(conn)
    admin, _ = compte(conn)
    membre, _ = compte(conn)
    adherer(conn, org, admin, "admin", 0)
    adherer(conn, org, membre, "membre", 1)
    remplir(conn, org, admin)

    conn.execute("delete from public.organisations where id = %s", (org,))

    assert _un(conn, "select count(*) from public.membres where organisation_id = %s", (org,)) == 0


# --- Droits ----------------------------------------------------------------------------------------


def test_effacement_par_le_role_de_gotrue(conn: Connexion) -> None:
    """GoTrue efface avec son propre rôle (supabase_auth_admin), sans droit d'écriture sur
    public.membres : la promotion passe quand même (fonction security definer)."""
    org = organisation(conn)
    admin, _ = compte(conn)
    membre, _ = compte(conn)
    adherer(conn, org, admin, "admin", 0)
    adherer(conn, org, membre, "membre", 1)

    conn.execute("set local role supabase_auth_admin")
    effacer(conn, admin)
    conn.execute("reset role")

    assert roles(conn, org) == {membre: "admin"}


def test_la_fonction_de_promotion_n_est_pas_appelable_par_un_membre(conn: Connexion) -> None:
    for role in ("anon", "authenticated"):
        assert (
            _un(
                conn,
                "select has_function_privilege(%s, 'public.membres_garder_un_admin()', 'execute')",
                (role,),
            )
            is False
        )


def test_un_membre_ne_peut_pas_retirer_une_appartenance(conn: Connexion) -> None:
    """RLS conservée : la suppression passe par GoTrue (service_role), jamais par un membre."""
    org = organisation(conn)
    admin, _ = compte(conn)
    adherer(conn, org, admin, "admin", 0)
    conn.execute("set local role authenticated")
    conn.execute("select set_config('request.jwt.claim.sub', %s, true)", (str(admin),))
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("delete from public.membres where user_id = %s", (admin,))
