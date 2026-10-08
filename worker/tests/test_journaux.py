"""Journaux du worker : aucune adresse e-mail, aucun nom de personne (T031, C3 ; règle produit 4).

But : faire passer le worker par un parcours représentatif, journaux au niveau DEBUG, puis
chercher dans tout ce qui a été journalisé (et écrit sur la sortie standard) une adresse
e-mail, l'adresse du compte qui a créé le groupe, et le nom d'un dirigeant personne du
registre de test.

Parcours :
- sans base : la route de recherche (saisie qui est une adresse e-mail, saisie qui est le nom
  d'une personne, saisie trop courte, registre absent), et le démarrage du worker sans
  DATABASE_URL ;
- avec base : une carto réussie sur un mini-registre où des dirigeants personnes font entrer
  une société, une carto refusée (réglages non validés), une carto en échec (registre absent),
  un travail dont le paramètre est une adresse e-mail, un travail de type inconnu. Le groupe et
  les réglages sont créés par un compte auth.users à adresse example.test.

Données inventées (règle produit 6) : noms de fabrique.py, adresses en example.test.
Sans DATABASE_URL : la partie base est ignorée en local, en échec en CI (variable CI).
"""

import json
import logging
import os
import re
import sys
import threading
import uuid
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import urlopen

import duckdb
import psycopg
import pytest
from psycopg.types.json import Jsonb

sys.path.insert(0, str(Path(__file__).resolve().parent / "moteur"))
from fabrique import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    PRESIDENT,
    MiniRegistre,
    personne,
    siren,
)

from cartofr import __main__ as principal  # noqa: E402
from cartofr import travaux  # noqa: E402
from cartofr.api_recherche import Serveur  # noqa: E402
from cartofr.db import VARIABLE_URL, connecter  # noqa: E402
from cartofr.empreinte import VARIABLE_CLE  # noqa: E402
from cartofr.registre.schema import creer_tables  # noqa: E402
from cartofr.travaux import Travail  # noqa: E402

Connexion = psycopg.Connection[tuple[Any, ...]]

# Une adresse e-mail, quelle qu'elle soit (pas seulement celles du test).
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")

# Les personnes du registre de test : clés au format du registre, « NOM|PRÉNOMS|AAAA-MM ».
FAMILLE = "FAMILLEJOURNAL"
PERSONNES = [personne(i, famille=FAMILLE) for i in (1, 2)] + [personne(3), personne(4)]

TETE, FILIALE, HOLDING = siren(1), siren(10), siren(50)
ADRESSE_GROUPE = "1 PLACE DU GROUPE INVENTE 75008"
CONTENU: dict[str, Any] = {"groupe": "TEST T031", "tete": TETE, "marques_sures": []}


def morceaux_de_noms() -> set[str]:
    """Ce qui ne doit jamais apparaître : chaque clé entière, son nom de famille, son prénom,
    et le nom complet dans les deux ordres."""
    morceaux: set[str] = set()
    for cle in PERSONNES:
        nom, prenoms, _ = cle.split("|")
        morceaux |= {cle, nom, prenoms, f"{nom} {prenoms}", f"{prenoms} {nom}"}
    return morceaux


def verifier_sans_donnee_personnelle(texte: str, *emails: str) -> None:
    """Échoue en citant le seul genre de fuite : l'assertion ne recopie pas le journal."""
    assert texte.strip(), "aucun journal capturé : le parcours ne vérifie rien"
    assert EMAIL.search(texte) is None, "une adresse e-mail apparaît dans les journaux"
    for email in emails:
        assert email.lower() not in texte.lower(), "l'adresse d'un compte apparaît dans les journaux"
    trouves = sum(1 for m in morceaux_de_noms() if m.lower() in texte.lower())
    assert trouves == 0, f"{trouves} morceau(x) de nom de personne dans les journaux"


@pytest.mark.parametrize(
    "fuite",
    [
        pytest.param("travail 12 pris par quelqu.un@exemple.fr", id="email_quelconque"),
        pytest.param(f"carto refusée pour {PERSONNES[0]}", id="cle_brute"),
        pytest.param("dirigeant prenom2 familleJournal", id="nom_complet_casse_melangee"),
    ],
)
def test_le_controle_detecte_une_fuite(fuite: str) -> None:
    with pytest.raises(AssertionError):
        verifier_sans_donnee_personnelle(f"INFO cartofr : démarrage\n{fuite}\n")


@pytest.fixture
def journaux(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    """Tous les journaux, de tous les modules (psycopg compris), dès le niveau DEBUG."""
    caplog.set_level(logging.DEBUG)
    return caplog


# --- Sans base ------------------------------------------------------------------------------


def registre_recherche(chemin: Path) -> Path:
    """Une société, et un entrepreneur individuel dont la dénomination est le nom d'une personne,
    qui dirige aussi la société."""
    nom, prenom, _ = PERSONNES[0].split("|")
    con = duckdb.connect(str(chemin))
    try:
        creer_tables(con)
        con.execute(
            "insert into societes (siren, denomination, etat_administratif, debut) values (?, ?, 'A', ?)",
            [TETE, "FROMAGERIE JOURNAL", date(2026, 3, 4)],
        )
        con.execute(
            "insert into sieges (siren, commune, nom, cj, tranche) values"
            " (?, 'VILLEFICTIVE', 'FROMAGERIE JOURNAL', 5710, '11'),"
            " (?, 'VILLEFICTIVE', ?, 1000, '00')",
            [TETE, siren(2), f"{nom} {prenom}"],
        )
        con.execute(
            "insert into dirigeants_personnes (siren, personne, role, debut) values (?, ?, ?, ?)",
            [TETE, PERSONNES[0], PRESIDENT, date(2026, 3, 4)],
        )
    finally:
        con.close()
    return chemin


def interroger(base: str, q: str) -> int:
    try:
        with urlopen(f"{base}/recherche?q={quote(q)}", timeout=10) as reponse:
            json.loads(reponse.read())
            return reponse.status
    except HTTPError as exc:
        return exc.code


@pytest.fixture
def recherche(tmp_path: Path) -> Iterator[tuple[str, Serveur]]:
    srv = Serveur(("127.0.0.1", 0), registre_recherche(tmp_path / "registre.duckdb"))
    fil = threading.Thread(target=srv.serve_forever, daemon=True)
    fil.start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}", srv
    finally:
        srv.shutdown()
        srv.server_close()


def test_recherche_ne_journalise_ni_la_saisie_ni_les_personnes(
    recherche: tuple[str, Serveur],
    journaux: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    base, srv = recherche
    nom, prenom, _ = PERSONNES[0].split("|")
    email = "consultant-t031@example.test"
    assert interroger(base, email) == 200
    assert interroger(base, f"{nom} {prenom}") == 200
    assert interroger(base, "FROMAGERIE") == 200
    assert interroger(base, "a") == 400
    srv.registre = tmp_path / "absent.duckdb"
    assert interroger(base, f"{prenom} {nom}") == 503

    sortie = capsys.readouterr()
    verifier_sans_donnee_personnelle(journaux.text + sortie.out + sortie.err, email)


def test_demarrage_sans_base_ne_journalise_aucune_donnee_personnelle(
    journaux: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(VARIABLE_URL, raising=False)
    assert principal.main() == 2
    sortie = capsys.readouterr()
    verifier_sans_donnee_personnelle(journaux.text + sortie.out + sortie.err)


# --- Avec base ------------------------------------------------------------------------------


@pytest.fixture
def conn() -> Iterator[Connexion]:
    if not os.environ.get(VARIABLE_URL):
        message = (
            f"{VARIABLE_URL} n'est pas définie : le parcours des travaux écrit dans la base. "
            "Démarrer la base locale (infra/README.md), appliquer les migrations, puis exporter DATABASE_URL."
        )
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


def registre_groupe() -> MiniRegistre:
    """Une tête, sa filiale présidée, et une holding qui n'entre que par des dirigeants
    personnes communs avec la tête : le moteur lit leurs noms pendant le calcul."""
    mini = MiniRegistre()
    mini.societe(TETE, "TETE JOURNAL", naf="70.10Z", tranche="22", adresse=ADRESSE_GROUPE)
    mini.societe(FILIALE, "FILIALE JOURNAL", adresse=ADRESSE_GROUPE)
    mini.lien(TETE, FILIALE, PRESIDENT)
    mini.societe(HOLDING, "HOLDING JOURNAL", naf="64.20Z", adresse=ADRESSE_GROUPE)
    for cle in PERSONNES[:2]:
        mini.dirigeant(TETE, cle)
        mini.dirigeant(HOLDING, cle)
    mini.dirigeants_communs(TETE, FILIALE, premier=3)
    return mini


class Monde:
    """Une organisation de test, un compte à adresse example.test, un groupe créé par ce compte.
    Tout est supprimé à la fin (la cascade emporte groupes, réglages, cartos et travaux)."""

    def __init__(self, conn: Connexion) -> None:
        self.conn = conn
        self.user = uuid.uuid4()
        self.email = f"auteur-{self.user.hex[:12]}@example.test"
        conn.execute("insert into auth.users (id, email) values (%s, %s)", (self.user, self.email))
        self.org = _un(
            conn,
            "insert into public.organisations (nom) values (%s) returning id",
            (f"test_t031 {self.user.hex}",),
        )
        conn.execute(
            "insert into public.membres (organisation_id, user_id, role) values (%s, %s, 'admin')",
            (self.org, self.user),
        )
        self.groupe = _un(
            conn,
            "insert into public.groupes (organisation_id, tete_siren, nom, cree_par)"
            " values (%s, %s, 'TEST T031', %s) returning id",
            (self.org, TETE, self.user),
        )
        conn.commit()

    def reglages(self, *, valide: bool, version: int) -> uuid.UUID:
        ident = _un(
            self.conn,
            "insert into public.reglages (groupe_id, organisation_id, version, contenu, cree_par,"
            " valide_le, valide_par) values (%s, %s, %s, %s, %s, case when %s then now() end,"
            " case when %s then %s::uuid end) returning id",
            (self.groupe, self.org, version, Jsonb(CONTENU), self.user, valide, valide, self.user),
        )
        self.conn.commit()
        return ident

    def carto(self, reglages_id: uuid.UUID, *, contourner_declencheur: bool = False) -> uuid.UUID:
        if contourner_declencheur:
            self.conn.execute("alter table public.cartos disable trigger cartos_reglages_valides")
        ident = _un(
            self.conn,
            "insert into public.cartos (organisation_id, groupe_id, reglages_id)"
            " values (%s, %s, %s) returning id",
            (self.org, self.groupe, reglages_id),
        )
        if contourner_declencheur:
            self.conn.execute("alter table public.cartos enable trigger cartos_reglages_valides")
        self.conn.commit()
        return ident

    def executer(self, type_travail: str, parametres: dict[str, Any]) -> str:
        """Un travail pris (en_cours), exécuté comme par la boucle du worker."""
        ident = _un(
            self.conn,
            "insert into public.travaux (type, organisation_id, parametres, statut, debut_le)"
            " values (%s, %s, %s, 'en_cours', now()) returning id",
            (type_travail, self.org, Jsonb(parametres)),
        )
        self.conn.commit()
        travail = Travail(id=ident, type=type_travail, organisation_id=self.org, parametres=parametres)
        return travaux.executer(self.conn, travail)

    def nettoyer(self) -> None:
        self.conn.rollback()
        self.conn.execute("delete from public.organisations where id = %s", (self.org,))
        self.conn.execute("delete from auth.users where id = %s", (self.user,))
        self.conn.commit()


@pytest.fixture
def monde(conn: Connexion) -> Iterator[Monde]:
    m = Monde(conn)
    try:
        yield m
    finally:
        m.nettoyer()


def test_parcours_des_travaux_sans_donnee_personnelle_dans_les_journaux(
    monde: Monde,
    journaux: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    donnees = tmp_path / "data"
    donnees.mkdir()
    monkeypatch.setenv("CARTOFR_DATA", str(donnees))
    monkeypatch.setenv(VARIABLE_CLE, "cle-de-test-FAKE")
    valide = monde.reglages(valide=True, version=1)
    brouillon = monde.reglages(valide=False, version=2)

    # Registre absent : la carto échoue.
    assert monde.executer("carto", {"carto_id": str(monde.carto(valide))}) == "echec"
    # Registre en place : la carto réussit, et les dirigeants personnes y font entrer la holding.
    registre_groupe().ecrire(donnees / "registre.duckdb")
    reussie = monde.carto(valide)
    assert monde.executer("carto", {"carto_id": str(reussie)}) == "termine"
    entrees = monde.conn.execute(
        "select siren from public.carto_societes where carto_id = %s", (reussie,)
    ).fetchall()
    monde.conn.commit()
    assert (HOLDING,) in entrees, "le parcours doit faire lire des dirigeants personnes au moteur"
    # Réglages non validés : refus.
    refusee = monde.carto(brouillon, contourner_declencheur=True)
    assert monde.executer("carto", {"carto_id": str(refusee)}) == "echec"
    # Paramètres hostiles : une adresse e-mail à la place de l'identifiant de carto.
    assert monde.executer("carto", {"carto_id": monde.email}) == "echec"
    # Type inconnu, dont le nom est une adresse e-mail.
    assert monde.executer(monde.email, {}) == "echec"
    # La boucle elle-même : démarrage et arrêt.
    arret = threading.Event()
    arret.set()
    travaux.boucle(arret, intervalle=0, planifier=False)

    sortie = capsys.readouterr()
    verifier_sans_donnee_personnelle(journaux.text + sortie.out + sortie.err, monde.email)
