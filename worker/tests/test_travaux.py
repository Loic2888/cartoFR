"""File de travaux du worker (T008, ADR-004).

Vérifie : un travail passe de `en_attente` à `termine` ou `echec` (C1), deux
boucles n'exécutent jamais deux travaux en même temps et chaque travail une
seule fois (C2), la durée est enregistrée (C3). Plus : type inconnu, erreur
sans texte d'exception, ordre de prise, boucle qui survit à une exception.

Prérequis : supabase/migrations/ appliqué, DATABASE_URL vers la base (rôle
postgres). Les travaux de test sont validés pour de vrai (la concurrence a
besoin de vraies transactions) : ils portent un marqueur dans `parametres`
et sont supprimés à la fin de chaque test. Les boucles peuvent aussi traiter
d'autres travaux en attente : à lancer sur une base de test, jamais de prod.

Sans DATABASE_URL : tests base ignorés en local, échec en CI (variable CI).
"""

import os
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import psycopg
import pytest
from psycopg.types.json import Jsonb

from cartofr import jobs, travaux
from cartofr.db import VARIABLE_URL, connecter
from cartofr.jobs import TRAVAUX, Contexte, enregistrer

Connexion = psycopg.Connection[tuple[Any, ...]]

CLE = "test_t008"


@pytest.fixture
def conn() -> Iterator[Connexion]:
    if not os.environ.get(VARIABLE_URL):
        message = (
            f"{VARIABLE_URL} n'est pas définie : la file de travaux a besoin d'une base. "
            "Démarrer la base locale (infra/README.md), appliquer les migrations, puis exporter DATABASE_URL."
        )
        if os.environ.get("CI"):
            pytest.fail(message)
        pytest.skip(message)
    connexion = connecter()
    if connexion.execute("select to_regclass('public.travaux')").fetchone() == (None,):
        connexion.close()
        pytest.fail("Table travaux absente : appliquer supabase/migrations/.")
    try:
        yield connexion
    finally:
        connexion.close()


@pytest.fixture
def marqueur(conn: Connexion) -> Iterator[str]:
    """Marqueur unique des travaux du test ; supprime ces travaux à la fin."""
    valeur = uuid.uuid4().hex
    yield valeur
    conn.rollback()
    conn.execute("delete from public.travaux where parametres ->> %s = %s", (CLE, valeur))
    conn.commit()


def inserer(conn: Connexion, marqueur: str, type_travail: str, cree_le: str | None = None) -> int:
    parametres = Jsonb({CLE: marqueur})
    if cree_le is None:
        ligne = conn.execute(
            "insert into public.travaux (type, parametres) values (%s, %s) returning id",
            (type_travail, parametres),
        ).fetchone()
    else:
        ligne = conn.execute(
            "insert into public.travaux (type, parametres, cree_le) values (%s, %s, %s) returning id",
            (type_travail, parametres, cree_le),
        ).fetchone()
    conn.commit()
    assert ligne is not None
    return int(ligne[0])


def lire(conn: Connexion, ident: int) -> dict[str, Any]:
    curseur = conn.execute(
        "select statut, debut_le, fin_le, duree_ms, erreur from public.travaux where id = %s", (ident,)
    )
    ligne = curseur.fetchone()
    conn.commit()
    assert ligne is not None
    return dict(zip(("statut", "debut_le", "fin_le", "duree_ms", "erreur"), ligne, strict=True))


def attendre(conn: Connexion, marqueur: str, delai: float = 30.0) -> None:
    """Attend que plus aucun travail du marqueur ne soit en attente ou en cours."""
    limite = time.monotonic() + delai
    while time.monotonic() < limite:
        reste = conn.execute(
            "select count(*) from public.travaux where parametres ->> %s = %s "
            "and statut in ('en_attente', 'en_cours')",
            (CLE, marqueur),
        ).fetchone()
        conn.commit()
        if reste == (0,):
            return
        time.sleep(0.05)
    pytest.fail("les travaux du test ne sont pas tous traités à temps")


def lancer_boucles(
    n: int, connecteur: Callable[[], Connexion] = connecter
) -> tuple[threading.Event, list[threading.Thread]]:
    arret = threading.Event()
    fils = [
        threading.Thread(target=travaux.boucle, args=(arret, 0.01, connecteur), daemon=True) for _ in range(n)
    ]
    for f in fils:
        f.start()
    return arret, fils


def arreter(arret: threading.Event, fils: list[threading.Thread]) -> None:
    arret.set()
    for f in fils:
        f.join(timeout=10)
        assert not f.is_alive(), "la boucle ne s'arrête pas"


# --- Sans base -------------------------------------------------------------


def test_ping_enregistre() -> None:
    assert TRAVAUX["ping"] is jobs.ping


def test_type_enregistre_deux_fois_refuse() -> None:
    with pytest.raises(ValueError):
        enregistrer("ping")(lambda ctx: None)


# --- Avec base -------------------------------------------------------------


def test_ping_passe_a_termine_avec_duree(conn: Connexion, marqueur: str) -> None:
    """C1 et C3."""
    ident = inserer(conn, marqueur, "ping")
    assert lire(conn, ident)["statut"] == "en_attente"

    assert travaux.traiter_un(conn) is True

    t = lire(conn, ident)
    assert t["statut"] == "termine"
    assert t["erreur"] is None
    assert t["duree_ms"] is not None and t["duree_ms"] >= 0
    assert t["debut_le"] is not None and t["fin_le"] is not None
    assert t["fin_le"] >= t["debut_le"]


def test_duree_mesuree(conn: Connexion, marqueur: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """C3 : la durée reflète le temps réel du travail."""
    monkeypatch.setitem(TRAVAUX, "test_t008_lent", lambda ctx: time.sleep(0.2))
    ident = inserer(conn, marqueur, "test_t008_lent")
    travaux.traiter_un(conn)
    t = lire(conn, ident)
    assert t["statut"] == "termine"
    assert 200 <= t["duree_ms"] < 5000


def test_exception_passe_a_echec_sans_texte(
    conn: Connexion, marqueur: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C1 (échec) : l'erreur porte le type d'exception, jamais son texte."""

    def echoue(ctx: Contexte) -> None:
        raise ValueError("Jeanne Exemple, donnée à ne pas recopier")

    monkeypatch.setitem(TRAVAUX, "test_t008_echec", echoue)
    ident = inserer(conn, marqueur, "test_t008_echec")

    assert travaux.traiter_un(conn) is True

    t = lire(conn, ident)
    assert t["statut"] == "echec"
    assert t["erreur"] == "échec du travail (ValueError)"
    assert "Jeanne" not in t["erreur"]
    assert t["duree_ms"] is not None and t["fin_le"] >= t["debut_le"]


def test_type_inconnu_passe_a_echec_avec_message_clair(conn: Connexion, marqueur: str) -> None:
    ident = inserer(conn, marqueur, "test_t008_inexistant")
    travaux.traiter_un(conn)
    t = lire(conn, ident)
    assert t["statut"] == "echec"
    assert t["erreur"] == "type de travail inconnu : test_t008_inexistant"
    assert t["duree_ms"] is not None


def test_echec_annule_les_ecritures_du_travail(
    conn: Connexion, marqueur: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un travail qui échoue après avoir écrit ne laisse rien en base."""

    def ecrit_puis_echoue(ctx: Contexte) -> None:
        assert ctx.conn is not None
        ctx.conn.execute(
            "update public.travaux set parametres = parametres || '{\"ecrit\": true}' where id = %s",
            (ctx.travail_id,),
        )
        raise RuntimeError("boum")

    monkeypatch.setitem(TRAVAUX, "test_t008_ecrit", ecrit_puis_echoue)
    ident = inserer(conn, marqueur, "test_t008_ecrit")
    travaux.traiter_un(conn)
    ligne = conn.execute("select parametres from public.travaux where id = %s", (ident,)).fetchone()
    conn.commit()
    assert ligne is not None and "ecrit" not in ligne[0]
    assert lire(conn, ident)["statut"] == "echec"


def test_erreur_sql_avalee_passe_a_echec(
    conn: Connexion, marqueur: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un travail qui avale une erreur SQL n'est pas compté comme terminé."""

    def avale(ctx: Contexte) -> None:
        assert ctx.conn is not None
        try:
            ctx.conn.execute("select 1 / 0")
        except psycopg.Error:
            pass

    monkeypatch.setitem(TRAVAUX, "test_t008_avale", avale)
    ident = inserer(conn, marqueur, "test_t008_avale")
    assert travaux.traiter_un(conn) is True
    t = lire(conn, ident)
    assert t["statut"] == "echec"
    assert t["erreur"] == "échec du travail (transaction en erreur)"


def test_le_plus_ancien_est_pris_en_premier(conn: Connexion, marqueur: str) -> None:
    recent = inserer(conn, marqueur, "ping", "1970-01-02T00:00:00Z")
    ancien = inserer(conn, marqueur, "ping", "1970-01-01T00:00:00Z")

    premier = travaux.prendre(conn)
    second = travaux.prendre(conn)

    assert premier is not None and second is not None
    assert (premier.id, second.id) == (ancien, recent)
    assert premier.parametres == {CLE: marqueur}
    assert lire(conn, ancien)["statut"] == "en_cours"


def test_deux_boucles_jamais_en_meme_temps(
    conn: Connexion, marqueur: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C2 : deux boucles, chaque travail exécuté une fois, jamais deux à la fois."""
    en_cours = threading.Lock()
    chevauchements: list[int] = []
    executions: list[int] = []
    fils_vus: set[int] = set()

    def lent(ctx: Contexte) -> None:
        if not en_cours.acquire(blocking=False):
            chevauchements.append(ctx.travail_id)
            return
        try:
            fils_vus.add(threading.get_ident())
            time.sleep(0.03)
            executions.append(ctx.travail_id)
        finally:
            en_cours.release()

    monkeypatch.setitem(TRAVAUX, "test_t008_concurrence", lent)
    idents = [inserer(conn, marqueur, "test_t008_concurrence") for _ in range(12)]

    arret, fils = lancer_boucles(2)
    try:
        attendre(conn, marqueur)
    finally:
        arreter(arret, fils)

    assert chevauchements == []
    assert sorted(executions) == sorted(idents)  # chacun une fois, aucun oublié
    lignes = conn.execute(
        "select debut_le, fin_le, statut from public.travaux where id = any(%s) order by debut_le",
        (idents,),
    ).fetchall()
    conn.commit()
    assert all(statut == "termine" for _, _, statut in lignes)
    # Les intervalles enregistrés en base ne se chevauchent pas non plus.
    for (_, fin, _), (debut_suivant, _, _) in zip(lignes, lignes[1:], strict=False):
        assert fin <= debut_suivant


def test_boucle_survit_aux_exceptions(
    conn: Connexion, marqueur: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Connexion impossible, erreur dans la prise, travail en échec : la boucle continue."""
    appels = {"connexion": 0, "prise": 0}

    def connecteur() -> Connexion:
        appels["connexion"] += 1
        if appels["connexion"] == 1:
            raise psycopg.OperationalError("base injoignable (simulé)")
        return connecter()

    prendre_vrai = travaux.prendre

    def prendre_capricieux(c: Connexion) -> travaux.Travail | None:
        appels["prise"] += 1
        if appels["prise"] == 1:
            raise RuntimeError("panne simulée")
        return prendre_vrai(c)

    def echoue(ctx: Contexte) -> None:
        raise KeyError("x")

    monkeypatch.setattr(travaux, "prendre", prendre_capricieux)
    monkeypatch.setitem(TRAVAUX, "test_t008_echec", echoue)
    en_echec = inserer(conn, marqueur, "test_t008_echec", "1970-01-01T00:00:00Z")
    apres = inserer(conn, marqueur, "ping", "1970-01-01T00:00:01Z")

    arret, fils = lancer_boucles(1, connecteur)
    try:
        attendre(conn, marqueur)
    finally:
        arreter(arret, fils)

    assert appels["connexion"] >= 2 and appels["prise"] >= 2
    assert lire(conn, en_echec)["statut"] == "echec"
    assert lire(conn, apres)["statut"] == "termine"
