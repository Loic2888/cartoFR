"""Cloisonnement RLS de la base de l'app (T006, T018, règle produit 7).

Deux organisations A et B, un membre chacune : un membre de A ne lit aucune
ligne de B, et inversement ; anon ne lit rien. Plus la vérification qu'aucune
colonne de personne physique n'existe dans le schéma (principe 6), les
garde-fous des réglages et des cartos (FR-005 : une carto ne part que sur une
version validée, une version validée est figée, aucune ligne ne pointe vers
une autre organisation), et le chargement des réglages de départ (T018, C4).

Prérequis : les migrations de supabase/migrations/ appliquées, et
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
from pathlib import Path
from typing import Any, LiteralString

import psycopg
import pytest
from psycopg import sql
from psycopg.types.json import Jsonb

from cartofr.db import VARIABLE_URL, connecter

RACINE = Path(__file__).resolve().parents[2]
SEED = RACINE / "supabase" / "seed" / "reglages_depart.sql"

TABLES_SOCLE = ("organisations", "membres", "travaux", "etat_registre")
# Tables de T018 : toutes portent organisation_id.
TABLES_CARTOS = ("groupes", "reglages", "cartos", "carto_societes", "carto_liens")
TABLES = TABLES_SOCLE + TABLES_CARTOS

# Les réglages de départ : fichier de config → tête du groupe.
CONFIGS_DEPART = {"lvmh": "775670417", "vinci": "552037806", "cmaf": "588505354"}

Connexion = psycopg.Connection[tuple[Any, ...]]


@dataclass(frozen=True)
class Monde:
    """Les fixtures créées pour un test."""

    org_a: uuid.UUID
    org_b: uuid.UUID
    user_a: uuid.UUID
    user_b: uuid.UUID
    user_sans_org: uuid.UUID
    # Par organisation : un groupe, une version validée, une non validée, une carto, un travail.
    groupes: dict[uuid.UUID, uuid.UUID]
    reglages_valides: dict[uuid.UUID, uuid.UUID]
    reglages_brouillon: dict[uuid.UUID, uuid.UUID]
    cartos: dict[uuid.UUID, uuid.UUID]
    travaux: dict[uuid.UUID, int]


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


def _un(conn: Connexion, requete: LiteralString, params: tuple[Any, ...]) -> Any:
    """Exécute une requête qui rend une ligne, et rend sa première colonne."""
    ligne = conn.execute(requete, params).fetchone()
    assert ligne is not None
    return ligne[0]


def _remplir_cartos(conn: Connexion, org: uuid.UUID, user: uuid.UUID, tete: str) -> dict[str, Any]:
    """Un groupe, deux versions de réglages (validée, brouillon), une carto et son résultat."""
    groupe = _un(
        conn,
        "insert into public.groupes (organisation_id, tete_siren, nom, cree_par) "
        "values (%s, %s, 'Société de tête (test)', %s) returning id",
        (org, tete, user),
    )
    valide = _un(
        conn,
        "insert into public.reglages (groupe_id, organisation_id, version, contenu, cree_par, "
        "valide_le, valide_par) values (%s, %s, 1, %s, %s, now(), %s) returning id",
        (groupe, org, Jsonb({"marques_sures": ["Test"]}), user, user),
    )
    brouillon = _un(
        conn,
        "insert into public.reglages (groupe_id, organisation_id, version, contenu, cree_par) "
        "values (%s, %s, 2, %s, %s) returning id",
        (groupe, org, Jsonb({"marques_sures": ["Test", "Autre"]}), user),
    )
    travail = _un(
        conn,
        "select id from public.travaux where organisation_id = %s order by id limit 1",
        (org,),
    )
    carto = _un(
        conn,
        "insert into public.cartos (organisation_id, groupe_id, reglages_id, travail_id, statut, "
        "date_donnees, duree_ms) values (%s, %s, %s, %s, 'terminee', current_date, 1000) returning id",
        (org, groupe, valide, travail),
    )
    filiale = tete[:-1] + ("1" if tete[-1] != "1" else "2")
    conn.execute(
        "insert into public.carto_societes (carto_id, organisation_id, siren, nom, niveau, "
        "maison_mere_siren, confiance, preuve, ciblable, raison_ciblable, opposition_prospection, "
        "non_diffusible) values "
        "(%s, %s, %s, 'Société de tête (test)', 0, null, null, null, true, null, false, false), "
        "(%s, %s, %s, 'Filiale (test)', 1, %s, 'A', 'présidée par la tête', false, "
        "'opposition à la prospection', true, false)",
        (carto, org, tete, carto, org, filiale, tete),
    )
    conn.execute(
        "insert into public.carto_liens (carto_id, organisation_id, parent_siren, enfant_siren, role, "
        "preuve, confiance) values (%s, %s, %s, %s, 'président', 'présidée par la tête', 'A')",
        (carto, org, tete, filiale),
    )
    return {"groupe": groupe, "valide": valide, "brouillon": brouillon, "carto": carto, "travail": travail}


@pytest.fixture
def monde(conn: Connexion) -> Monde:
    """Deux organisations, un membre chacune, un utilisateur sans organisation, des travaux et des cartos."""
    user_a, user_b, user_sans_org = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    for uid, email in ((user_a, "a"), (user_b, "b"), (user_sans_org, "c")):
        conn.execute(
            "insert into auth.users (id, email) values (%s, %s)",
            (uid, f"{email}-{uid}@example.test"),
        )
    orgs: list[uuid.UUID] = []
    for nom in ("Organisation A (test)", "Organisation B (test)"):
        orgs.append(_un(conn, "insert into public.organisations (nom) values (%s) returning id", (nom,)))
    org_a, org_b = orgs
    for org, uid in ((org_a, user_a), (org_b, user_b)):
        conn.execute("insert into public.membres (organisation_id, user_id) values (%s, %s)", (org, uid))
        conn.execute(
            "insert into public.travaux (type, organisation_id, parametres) values ('carto', %s, %s)",
            (org, json.dumps({"test": str(org)})),
        )
    # Un travail global (synchro), sans organisation.
    conn.execute("insert into public.travaux (type) values ('synchro')")
    # SIREN de test (fictifs), une tête différente par organisation.
    remplis = {
        org_a: _remplir_cartos(conn, org_a, user_a, "900000001"),
        org_b: _remplir_cartos(conn, org_b, user_b, "900000002"),
    }
    return Monde(
        org_a,
        org_b,
        user_a,
        user_b,
        user_sans_org,
        groupes={o: r["groupe"] for o, r in remplis.items()},
        reglages_valides={o: r["valide"] for o, r in remplis.items()},
        reglages_brouillon={o: r["brouillon"] for o, r in remplis.items()},
        cartos={o: r["carto"] for o, r in remplis.items()},
        travaux={o: r["travail"] for o, r in remplis.items()},
    )


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
    for table in TABLES_CARTOS:
        requete = sql.SQL("select distinct organisation_id from public.{}").format(sql.Identifier(table))
        assert {ligne[0] for ligne in conn.execute(requete).fetchall()} == {moi}, table
    # Aucune ligne de l'autre organisation, même demandée explicitement.
    for table, colonne in (
        ("organisations", "id"),
        ("membres", "organisation_id"),
        ("travaux", "organisation_id"),
        *((t, "organisation_id") for t in TABLES_CARTOS),
    ):
        requete = sql.SQL("select count(*) from public.{} where {} = %s").format(
            sql.Identifier(table), sql.Identifier(colonne)
        )
        assert conn.execute(requete, (autre,)).fetchone() == (0,), table


@pytest.mark.parametrize("cote", ["a", "b"])
def test_un_membre_ne_voit_ni_les_cartos_ni_les_reglages_de_l_autre(
    conn: Connexion, monde: Monde, cote: str
) -> None:
    """T018, C2 : par identifiant, la carto et les réglages de l'autre organisation sont introuvables."""
    moi, autre = (monde.org_a, monde.org_b) if cote == "a" else (monde.org_b, monde.org_a)
    _en_tant_que(conn, monde.user_a if cote == "a" else monde.user_b)

    assert _ids(conn, "select id from public.cartos") == {monde.cartos[moi]}
    assert _ids(conn, "select id from public.reglages") == {
        monde.reglages_valides[moi],
        monde.reglages_brouillon[moi],
    }
    lectures: tuple[tuple[LiteralString, Any], ...] = (
        ("select count(*) from public.cartos where id = %s", monde.cartos[autre]),
        ("select count(*) from public.reglages where id = %s", monde.reglages_valides[autre]),
        ("select count(*) from public.reglages where groupe_id = %s", monde.groupes[autre]),
        ("select count(*) from public.groupes where id = %s", monde.groupes[autre]),
        ("select count(*) from public.carto_societes where carto_id = %s", monde.cartos[autre]),
        ("select count(*) from public.carto_liens where carto_id = %s", monde.cartos[autre]),
    )
    for requete, valeur in lectures:
        assert conn.execute(requete, (valeur,)).fetchone() == (0,), requete


def test_un_utilisateur_sans_organisation_ne_voit_rien(conn: Connexion, monde: Monde) -> None:
    _en_tant_que(conn, monde.user_sans_org)
    for table in ("organisations", "membres", "travaux", *TABLES_CARTOS):
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


# Une écriture par table de T018, même dans sa propre organisation : refusée.
ECRITURES_REFUSEES: tuple[LiteralString, ...] = (
    "insert into public.groupes (organisation_id, tete_siren, nom) values (%(org)s, '900000009', 'X')",
    "insert into public.reglages (groupe_id, organisation_id, version, contenu) "
    "values (%(groupe)s, %(org)s, 9, '{}')",
    "update public.reglages set valide_le = now() where id = %(brouillon)s",
    "insert into public.cartos (organisation_id, groupe_id, reglages_id) "
    "values (%(org)s, %(groupe)s, %(valide)s)",
    "delete from public.carto_societes where carto_id = %(carto)s",
    "delete from public.carto_liens where carto_id = %(carto)s",
)


@pytest.mark.parametrize("requete", ECRITURES_REFUSEES)
def test_un_membre_ne_peut_pas_ecrire_les_cartos(
    conn: Connexion, monde: Monde, requete: LiteralString
) -> None:
    org = monde.org_a
    _en_tant_que(conn, monde.user_a)
    params = {
        "org": org,
        "groupe": monde.groupes[org],
        "valide": monde.reglages_valides[org],
        "brouillon": monde.reglages_brouillon[org],
        "carto": monde.cartos[org],
    }
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(requete, params)


@pytest.mark.parametrize("table", TABLES)
def test_anon_ne_lit_rien(conn: Connexion, monde: Monde, table: str) -> None:
    conn.execute("set local role anon")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(sql.SQL("select * from public.{}").format(sql.Identifier(table)))


def test_rls_active_sur_chaque_table(conn: Connexion) -> None:
    """T006 et T018, C1 : RLS active sur chaque table, dont les cinq de 0002_cartos.sql."""
    lignes = conn.execute(
        "select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace "
        "where n.nspname = 'public' and c.relname = any(%s) and c.relrowsecurity",
        (list(TABLES),),
    ).fetchall()
    assert {ligne[0] for ligne in lignes} == set(TABLES)


def test_anon_et_authenticated_n_ont_que_le_necessaire(conn: Connexion) -> None:
    """Les privilèges par défaut de Supabase sont retirés : authenticated lit, anon rien (MEMORY.md)."""
    lignes = conn.execute(
        "select table_name, grantee, privilege_type from information_schema.role_table_grants "
        "where table_schema = 'public' and table_name = any(%s) and grantee in ('anon', 'authenticated')",
        (list(TABLES),),
    ).fetchall()
    assert set(lignes) == {(t, "authenticated", "SELECT") for t in TABLES}


# Colonnes autorisées malgré un nom qui ressemble à une personne : ce sont des
# noms d'organisation cliente ou de société, pas de personne physique.
COLONNES_AUTORISEES = {
    ("organisations", "nom"),  # organisation cliente (Youno)
    ("groupes", "nom"),  # nom du groupe ou de sa société de tête
    ("carto_societes", "nom"),  # dénomination de la société au registre
}
MOTS_PERSONNE = ("nom", "prenom", "email", "mail", "personne", "dirigeant", "telephone", "naissance")


def test_aucune_colonne_de_personne_physique(conn: Connexion) -> None:
    """Principe 6 et T018, C3 : aucune colonne de personne, nouvelles tables comprises."""
    lignes = conn.execute(
        "select table_name, column_name from information_schema.columns "
        "where table_schema = 'public' and table_name = any(%s)",
        (list(TABLES),),
    ).fetchall()
    assert {ligne[0] for ligne in lignes} == set(TABLES), "schéma absent ?"
    suspectes = [
        (table, colonne)
        for table, colonne in lignes
        if any(mot in colonne for mot in MOTS_PERSONNE) and (table, colonne) not in COLONNES_AUTORISEES
    ]
    assert suspectes == []


def test_une_carto_refuse_des_reglages_non_valides(conn: Connexion, monde: Monde) -> None:
    """FR-005 : le moteur ne tourne que sur une version validée, même en service_role."""
    org = monde.org_a
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(
            "insert into public.cartos (organisation_id, groupe_id, reglages_id) values (%s, %s, %s)",
            (org, monde.groupes[org], monde.reglages_brouillon[org]),
        )


def test_une_carto_ne_peut_pas_passer_sur_des_reglages_non_valides(conn: Connexion, monde: Monde) -> None:
    org = monde.org_a
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(
            "update public.cartos set reglages_id = %s where id = %s",
            (monde.reglages_brouillon[org], monde.cartos[org]),
        )


def test_une_version_validee_est_figee(conn: Connexion, monde: Monde) -> None:
    org = monde.org_a
    valide = monde.reglages_valides[org]
    modifications: tuple[tuple[LiteralString, tuple[Any, ...]], ...] = (
        ("update public.reglages set contenu = '{}' where id = %s", (valide,)),
        ("update public.reglages set version = 5 where id = %s", (valide,)),
        ("update public.reglages set valide_le = null, valide_par = null where id = %s", (valide,)),
        ("update public.reglages set valide_par = %s where id = %s", (monde.user_b, valide)),
    )
    for requete, params in modifications:
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute(requete, params)
    # Effacer le compte du validateur reste possible (RGPD) : valide_par passe à nul.
    conn.execute("delete from auth.users where id = %s", (monde.user_a,))
    ligne = conn.execute(
        "select valide_le is not null, valide_par from public.reglages where id = %s", (valide,)
    )
    assert ligne.fetchone() == (True, None)
    # Une version brouillon, elle, se valide.
    brouillon = monde.reglages_brouillon[monde.org_b]
    conn.execute(
        "update public.reglages set valide_le = now(), valide_par = %s where id = %s",
        (monde.user_b, brouillon),
    )


def test_pas_de_validateur_sans_date(conn: Connexion, monde: Monde) -> None:
    org = monde.org_a
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(
            "update public.reglages set valide_par = %s where id = %s",
            (monde.user_a, monde.reglages_brouillon[org]),
        )


# Lignes qui pointeraient vers une autre organisation : refusées par les clés
# étrangères composées, même écrites en service_role (qui contourne RLS).
LIENS_CROISES: tuple[LiteralString, ...] = (
    # Réglages rangés dans B pour un groupe de A.
    "insert into public.reglages (groupe_id, organisation_id, version, contenu) "
    "values (%(groupe_a)s, %(org_b)s, 9, '{}')",
    # Carto de B sur le groupe et les réglages de A.
    "insert into public.cartos (organisation_id, groupe_id, reglages_id) "
    "values (%(org_b)s, %(groupe_a)s, %(valide_a)s)",
    # Carto de A sur les réglages validés de B.
    "insert into public.cartos (organisation_id, groupe_id, reglages_id) "
    "values (%(org_a)s, %(groupe_a)s, %(valide_b)s)",
    # Carto de A rattachée au travail de B.
    "insert into public.cartos (organisation_id, groupe_id, reglages_id, travail_id) "
    "values (%(org_a)s, %(groupe_a)s, %(valide_a)s, %(travail_b)s)",
    # Résultat rangé dans B pour la carto de A.
    "insert into public.carto_societes (carto_id, organisation_id, siren, niveau, ciblable, "
    "opposition_prospection, non_diffusible) "
    "values (%(carto_a)s, %(org_b)s, '900000003', 1, true, false, false)",
    "insert into public.carto_liens (carto_id, organisation_id, parent_siren, enfant_siren, preuve, "
    "confiance) values (%(carto_a)s, %(org_b)s, '900000001', '900000003', 'test', 'B')",
)


@pytest.mark.parametrize("requete", LIENS_CROISES)
def test_aucune_ligne_ne_pointe_vers_une_autre_organisation(
    conn: Connexion, monde: Monde, requete: LiteralString
) -> None:
    a, b = monde.org_a, monde.org_b
    params = {
        "org_a": a,
        "org_b": b,
        "groupe_a": monde.groupes[a],
        "valide_a": monde.reglages_valides[a],
        "valide_b": monde.reglages_valides[b],
        "carto_a": monde.cartos[a],
        "travail_b": monde.travaux[b],
    }
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        conn.execute(requete, params)


def test_le_seed_charge_les_reglages_de_depart_valides(conn: Connexion) -> None:
    """T018, C4 : LVMH, VINCI et CMAF en version 1 validée, contenu identique à config/<g>.json.

    Le seed est joué deux fois dans la transaction du test (annulée à la fin) :
    il est idempotent, et le test passe que la base l'ait déjà reçu (CI) ou non.
    """
    script = SEED.read_text(encoding="utf-8")
    conn.execute(script.encode())
    conn.execute(script.encode())

    orgs = conn.execute(
        "select id from public.organisations where nom = 'Youno' order by cree_le, id"
    ).fetchall()
    assert len(orgs) >= 1
    youno = orgs[0][0]
    lignes = conn.execute(
        "select g.tete_siren, r.version, r.origine, r.valide_le is not null, r.contenu "
        "from public.groupes g join public.reglages r on r.groupe_id = g.id "
        "where g.organisation_id = %s and r.organisation_id = %s and r.version = 1",
        (youno, youno),
    ).fetchall()
    par_tete = {ligne[0]: ligne[1:] for ligne in lignes}
    assert len(lignes) == len(par_tete), "une seule version 1 par groupe"
    assert set(par_tete) == set(CONFIGS_DEPART.values())
    for fichier, tete in CONFIGS_DEPART.items():
        attendu = json.loads((RACINE / "config" / f"{fichier}.json").read_text(encoding="utf-8"))
        version, origine, validee, contenu = par_tete[tete]
        assert (version, origine, validee) == (1, "depart", True), fichier
        assert contenu == attendu, fichier

    # Une carto peut partir sur ces réglages (validés).
    conn.execute(
        "insert into public.cartos (organisation_id, groupe_id, reglages_id) "
        "select r.organisation_id, r.groupe_id, r.id from public.reglages r "
        "where r.organisation_id = %s and r.version = 1",
        (youno,),
    )
