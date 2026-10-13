"""Rôle en lecture seule du service recherche (T041, migration 0006 ; règle produit 7).

Vérifie : `cartofr_recherche` n'a aucun privilège dangereux et ouvre ses transactions en
lecture seule ; sans organisation déclarée il ne voit rien ; avec une organisation déclarée
il ne voit qu'elle, même si la requête demande une autre organisation ; il ne lit que les
quatre tables de l'export et n'écrit nulle part ; la route d'export marche avec lui.

Le test prend le rôle par `set role` depuis la connexion postgres : aucun mot de passe n'est
posé ni changé. Données fabriquées (règle produit 6). Demande DATABASE_URL (migrations
appliquées) : ignoré en local sans elle, échec en CI.
"""

import io
import json
import os
import threading
import uuid
import zipfile
from collections.abc import Iterator
from datetime import date
from typing import Any, LiteralString
from urllib.error import HTTPError
from urllib.request import urlopen

import psycopg
import pytest
from psycopg import sql
from psycopg.types.json import Jsonb

from cartofr.api_recherche import Serveur
from cartofr.db import VARIABLE_URL, connecter

Connexion = psycopg.Connection[tuple[Any, ...]]
ROLE = "cartofr_recherche"
TABLES_LUES = ("groupes", "reglages", "cartos", "carto_societes")
TABLES_INTERDITES = (
    "organisations",
    "membres",
    "travaux",
    "carto_liens",
    "carto_cas",
    "decisions",
    "etat_registre",
)
TETE, FILIALE = "100000001", "100000002"


@pytest.fixture
def conn() -> Iterator[Connexion]:
    if not os.environ.get(VARIABLE_URL):
        message = f"{VARIABLE_URL} n'est pas définie : le rôle de la recherche se vérifie dans la base."
        if os.environ.get("CI"):
            pytest.fail(message)
        pytest.skip(message)
    connexion = connecter()
    try:
        yield connexion
    finally:
        connexion.close()


def _un(conn: Connexion, requete: Any, params: tuple[Any, ...]) -> Any:
    ligne = conn.execute(requete, params).fetchone()
    assert ligne is not None
    return ligne[0]


@pytest.fixture
def deux_organisations(conn: Connexion) -> Iterator[dict[str, uuid.UUID]]:
    """A et B ont chacune un groupe, des réglages validés et une carto terminée à deux sociétés."""
    marque = f"test_t041 {uuid.uuid4().hex}"
    ids: dict[str, uuid.UUID] = {}
    try:
        for cle in ("a", "b"):
            org = _un(
                conn, "insert into public.organisations (nom) values (%s) returning id", (f"{marque} {cle}",)
            )
            ids[cle] = org
            groupe = _un(
                conn,
                "insert into public.groupes (organisation_id, tete_siren, nom)"
                " values (%s, %s, %s) returning id",
                (org, TETE, f"GROUPE {cle.upper()}"),
            )
            reglages = _un(
                conn,
                "insert into public.reglages (groupe_id, organisation_id, version, contenu, valide_le)"
                " values (%s, %s, 1, %s, now()) returning id",
                (groupe, org, Jsonb({"groupe": cle.upper(), "tete": TETE})),
            )
            carto = _un(
                conn,
                "insert into public.cartos (organisation_id, groupe_id, reglages_id, statut, date_donnees)"
                " values (%s, %s, %s, 'terminee', %s) returning id",
                (org, groupe, reglages, date(2026, 10, 1)),
            )
            ids[f"carto_{cle}"] = carto
            for siren, niveau, mere in ((TETE, 0, None), (FILIALE, 1, TETE)):
                conn.execute(
                    "insert into public.carto_societes (carto_id, organisation_id, siren, nom, niveau,"
                    " maison_mere_siren, confiance, preuve, ciblable, raison_ciblable,"
                    " opposition_prospection, non_diffusible)"
                    " values (%s, %s, %s, %s, %s, %s, %s, 'Preuve', true, 'Raison', false, false)",
                    (carto, org, siren, f"SOCIETE {siren}", niveau, mere, None if mere is None else "A"),
                )
        conn.commit()
        yield ids
    finally:
        conn.rollback()
        conn.execute("reset role")
        conn.execute("delete from public.organisations where nom like %s", (f"{marque}%",))
        conn.commit()


def prendre_le_role(conn: Connexion) -> None:
    """La connexion agit désormais comme le service recherche (jusqu'à `reset role`)."""
    conn.execute(f"set role {ROLE}")
    conn.commit()


def declarer(conn: Connexion, organisation: uuid.UUID) -> None:
    conn.execute("select set_config('cartofr.organisation', %s, true)", (str(organisation),))


def compter(conn: Connexion, table: str, filtre: LiteralString = "", params: tuple[Any, ...] = ()) -> int:
    requete = sql.SQL("select count(*) from public.{} " + filtre).format(sql.Identifier(table))
    return int(_un(conn, requete, params))


def test_role_sans_privilege_dangereux(conn: Connexion) -> None:
    ligne = conn.execute(
        "select rolsuper, rolbypassrls, rolcreaterole, rolcreatedb, rolinherit, rolconfig"
        " from pg_roles where rolname = %s",
        (ROLE,),
    ).fetchone()
    conn.commit()
    assert ligne is not None, "migration 0006 non appliquée"
    super_, bypass, createrole, createdb, inherit, config = ligne
    assert (super_, bypass, createrole, createdb, inherit) == (False, False, False, False, False)
    assert "default_transaction_read_only=on" in (config or [])


def test_sans_organisation_declaree_rien_n_est_visible(
    conn: Connexion, deux_organisations: dict[str, uuid.UUID]
) -> None:
    prendre_le_role(conn)
    for table in TABLES_LUES:
        assert compter(conn, table) == 0, table
    conn.rollback()


def test_ne_voit_que_l_organisation_declaree(
    conn: Connexion, deux_organisations: dict[str, uuid.UUID]
) -> None:
    ids = deux_organisations
    prendre_le_role(conn)
    declarer(conn, ids["a"])
    attendu = {"groupes": 1, "reglages": 1, "cartos": 1, "carto_societes": 2}
    for table, n in attendu.items():
        assert compter(conn, table, "where organisation_id in (%s, %s)", (ids["a"], ids["b"])) == n, table
        # Même une requête qui demande B ne voit rien de B : la base refuse, pas le code.
        assert compter(conn, table, "where organisation_id = %s", (ids["b"],)) == 0, table
    assert compter(conn, "cartos", "where id = %s", (ids["carto_b"],)) == 0
    conn.rollback()
    # La déclaration ne vaut que pour sa transaction.
    assert compter(conn, "cartos") == 0
    conn.rollback()


@pytest.mark.parametrize("table", TABLES_INTERDITES)
def test_aucune_autre_table(conn: Connexion, deux_organisations: dict[str, uuid.UUID], table: str) -> None:
    prendre_le_role(conn)
    declarer(conn, deux_organisations["a"])
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        compter(conn, table)
    conn.rollback()


def test_aucune_ecriture(conn: Connexion, deux_organisations: dict[str, uuid.UUID]) -> None:
    ids = deux_organisations
    prendre_le_role(conn)
    ecritures: list[tuple[LiteralString, tuple[Any, ...]]] = [
        ("update public.cartos set statut = 'echec' where id = %s", (ids["carto_a"],)),
        ("delete from public.carto_societes where carto_id = %s", (ids["carto_a"],)),
        (
            "insert into public.groupes (organisation_id, tete_siren, nom) values (%s, %s, 'X')",
            (ids["a"], FILIALE),
        ),
    ]
    for requete, params in ecritures:
        declarer(conn, ids["a"])
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(requete, params)
        conn.rollback()


# --- la route d'export avec ce rôle ---


def appeler(url: str) -> tuple[int, bytes]:
    try:
        with urlopen(url, timeout=10) as r:
            return r.status, r.read()
    except HTTPError as e:
        return e.code, e.read()


def connexion_recherche() -> Connexion:
    c = connecter()
    prendre_le_role(c)
    return c


def test_route_export_avec_le_role(conn: Connexion, deux_organisations: dict[str, uuid.UUID]) -> None:
    ids = deux_organisations
    serveur = Serveur(("127.0.0.1", 0), connecter=connexion_recherche)
    fil = threading.Thread(target=serveur.serve_forever, daemon=True)
    fil.start()
    base = f"http://127.0.0.1:{serveur.server_address[1]}/export/skill"
    try:
        statut, corps = appeler(f"{base}/{ids['carto_a']}?organisation={ids['a']}")
        assert statut == 200
        assert zipfile.ZipFile(io.BytesIO(corps)).testzip() is None
        # La carto de A demandée pour B : introuvable.
        statut, corps = appeler(f"{base}/{ids['carto_a']}?organisation={ids['b']}")
        assert (statut, json.loads(corps)) == (404, {"erreur": "carto_introuvable"})
    finally:
        serveur.shutdown()
        serveur.server_close()
