"""Travail `synchro` et planification nocturne (T013).

Vérifie : un passage réussi publie date et volumes dans `etat_registre` (C1),
un échec y écrit sa cause sans donnée (C2), la boucle insère un travail
`synchro` chaque nuit, une seule fois par jour (C3). Plus : jours dans l'ordre,
jamais relus, plafond par passage, reprise après quota, SIRENE jamais en
avance sur le RNE, heure de Paris à minuit et aux changements d'heure.

Aucun appel réseau : le RNE passe par un faux lecteur de pages, SIRENE par un
`httpx.MockTransport`. Le registre est un DuckDB créé dans `tmp_path`, les
fiches sont celles, inventées, de `tests/fixtures/rne/` (règle produit 6).

Prérequis Postgres comme `test_travaux.py` : DATABASE_URL vers une base de
test où supabase/migrations/ est appliqué. Sans elle : tests base ignorés en
local, échec en CI. Les lignes `rne` et `sirene` d'`etat_registre` sont
remises en l'état à la fin de chaque test ; les travaux `synchro` de test
sont datés de 2099 et supprimés.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Iterator
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any, cast

import duckdb
import httpx
import psycopg
import pytest
from psycopg.types.json import Jsonb

from cartofr import travaux
from cartofr.db import VARIABLE_URL, connecter
from cartofr.jobs import TRAVAUX, Contexte, synchro
from cartofr.jobs.synchro import (
    DATE_STOCK,
    MESSAGE_REGISTRE_ABSENT,
    RNE,
    SIRENE,
    Jours,
    SynchroEnEchec,
    jours_a_lire,
    jours_max,
    synchroniser,
)
from cartofr.registre import inpi_diff, journal, synchro_sirene
from cartofr.registre.inpi_diff import Curseur, ErreurInpi, Page, QuotaAtteint
from cartofr.registre.schema import creer_tables
from cartofr.registre.synchro_rne import MESSAGE_QUOTA
from cartofr.registre.synchro_sirene import Client as ClientSirene
from cartofr.registre.synchro_sirene import Limiteur

Connexion = psycopg.Connection[tuple[Any, ...]]

FIXTURES_RNE = Path(__file__).resolve().parents[1] / "fixtures" / "rne"
J1, J2, J3 = DATE_STOCK + timedelta(days=1), DATE_STOCK + timedelta(days=2), DATE_STOCK + timedelta(days=3)
# 2026-03-08 à 02:00 heure de Paris (UTC+1 en mars avant le changement d'heure) : veille = J3.
PASSAGE = datetime(2026, 3, 8, 1, 0, tzinfo=UTC)


def fiche(nom: str) -> dict[str, Any]:
    return json.loads((FIXTURES_RNE / f"{nom}.json").read_text(encoding="utf-8"))


# --- Faux clients -------------------------------------------------------------------


class FauxRne:
    """Faux lecteur INPI : des pages (ou une exception) par jour. Garde les jours lus."""

    def __init__(
        self, par_jour: dict[date, list[list[dict[str, Any]] | BaseException]] | None = None
    ) -> None:
        self.par_jour = par_jour or {}
        self.requetes = 0
        self.jours: list[date] = []

    def lire(
        self,
        depuis: date,
        jusqua: date,
        curseur: Curseur | None = None,
        page_size: int = 100,
        chemin: Path | None = None,
    ) -> Iterator[Page]:
        assert depuis == jusqua, "un jour à la fois"
        self.jours.append(depuis)
        for numero, page in enumerate(self.par_jour.get(depuis, []), 1):
            self.requetes += 1
            if isinstance(page, BaseException):
                raise page
            yield Page(numero, [{"company": c} for c in page], None)
        self.requetes += 1  # la page vide de fin


class FauxSirene:
    """Serveur Sirene factice : aucun changement (404), garde les jours demandés."""

    def __init__(self, code: int = 404) -> None:
        self.code = code
        self.jours: list[date] = []

    def __call__(self, requete: httpx.Request) -> httpx.Response:
        if requete.url.path.endswith("/siren"):
            # q = "dateDernierTraitementUniteLegale:[AAAA-MM-JJT00:00:00 TO …"
            self.jours.append(date.fromisoformat(requete.url.params["q"].split("[")[1][:10]))
        return httpx.Response(self.code, json={"header": {"statut": self.code}})

    def client(self) -> ClientSirene:
        return ClientSirene(
            http=httpx.Client(transport=httpx.MockTransport(self)),
            cle="cle-FAKE",
            limiteur=Limiteur(horloge=lambda: 0.0, dormir=lambda _: None, maximum=10_000),
            essais=0,
            dormir=lambda _: None,
        )


# --- Fixtures -----------------------------------------------------------------------


@pytest.fixture
def conn() -> Iterator[Connexion]:
    if not os.environ.get(VARIABLE_URL):
        message = (
            f"{VARIABLE_URL} n'est pas définie : la synchro publie dans etat_registre, il faut une base. "
            "Démarrer la base locale (infra/README.md), appliquer les migrations, puis exporter DATABASE_URL."
        )
        if os.environ.get("CI"):
            pytest.fail(message)
        pytest.skip(message)
    connexion = connecter()
    if connexion.execute("select to_regclass('public.etat_registre')").fetchone() == (None,):
        connexion.close()
        pytest.fail("Table etat_registre absente : appliquer supabase/migrations/.")
    try:
        yield connexion
    finally:
        connexion.close()


@pytest.fixture
def etat(conn: Connexion) -> Iterator[None]:
    """Vide les lignes rne et sirene d'etat_registre pour le test, puis les remet."""
    colonnes = "source, date_donnees, dernier_passage, statut, volumes, erreur, maj_le"
    avant = conn.execute(
        f"select {colonnes} from public.etat_registre where source in ('rne', 'sirene')"
    ).fetchall()
    conn.execute("delete from public.etat_registre where source in ('rne', 'sirene')")
    conn.commit()
    yield
    conn.rollback()
    conn.execute("delete from public.etat_registre where source in ('rne', 'sirene')")
    with conn.cursor() as cur:
        cur.executemany(
            f"insert into public.etat_registre ({colonnes}) values (%s, %s, %s, %s, %s, %s, %s)",
            [(*ligne[:4], Jsonb(ligne[4]), *ligne[5:]) for ligne in avant],
        )
    conn.commit()


@pytest.fixture
def registre(tmp_path: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    """Un registre vide, comme juste après la construction initiale."""
    con = duckdb.connect(str(tmp_path / "registre.duckdb"))
    creer_tables(con)
    journal.terminer(con, journal.ouvrir(con, "construction_initiale"), ajoutes=0, fermes=0)
    yield con
    con.close()


def lire_etat(conn: Connexion) -> dict[str, dict[str, Any]]:
    cur = conn.execute(
        "select source, date_donnees, dernier_passage, statut, volumes, erreur from public.etat_registre"
        " where source in ('rne', 'sirene')"
    )
    noms = [d.name for d in cur.description or []]
    lignes = {r[0]: dict(zip(noms, r, strict=True)) for r in cur.fetchall()}
    conn.commit()
    return lignes


def passer(
    conn: Connexion,
    registre: duckdb.DuckDBPyConnection,
    tmp_path: Path,
    rne: FauxRne,
    sirene: FauxSirene | None = None,
    passage: datetime = PASSAGE,
    maximum: int = 7,
) -> list[synchro.EtatSource]:
    sirene = sirene or FauxSirene()
    return synchroniser(
        conn,
        registre,
        passage,
        maximum,
        lambda: rne,
        sirene.client,
        tmp_path / "synchro" / "jours.json",
        tmp_path / "inpi_diff" / "curseur.json",
    )


# --- C1 : un passage réussi publie la date et les volumes -----------------------------


@pytest.mark.usefixtures("etat")
def test_c1_passage_reussi_publie_date_et_volumes(
    conn: Connexion, registre: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    rne = FauxRne({J1: [[fiche("societe_a_v1"), fiche("entreprise_individuelle")]]})
    sirene = FauxSirene()
    etats = passer(conn, registre, tmp_path, rne, sirene)

    assert [e.statut for e in etats] == ["succes", "succes"]
    assert rne.jours == [J1, J2, J3]  # dans l'ordre, jusqu'à la veille (Paris)
    assert sirene.jours == [J1, J2, J3]
    publie = lire_etat(conn)
    assert publie[RNE]["date_donnees"] == J3 and publie[SIRENE]["date_donnees"] == J3
    assert publie[RNE]["statut"] == publie[SIRENE]["statut"] == "succes"
    assert publie[RNE]["dernier_passage"] == PASSAGE
    assert publie[RNE]["erreur"] is None
    volumes = publie[RNE]["volumes"]
    assert {k: volumes[k] for k in ("jours", "fiches", "ignorees", "societes_creees", "liens_ouverts")} == {
        "jours": 3,
        "fiches": 1,
        "ignorees": 1,
        "societes_creees": 1,
        "liens_ouverts": 2,
    }
    assert volumes["requetes"] == rne.requetes
    assert publie[SIRENE]["volumes"]["jours"] == 3
    assert publie[SIRENE]["volumes"]["requetes"] == 6  # /siren et /siret, trois jours
    # Le registre a reçu les changements, et le journal une ligne par jour et source.
    assert registre.execute("select count(*) from societes").fetchone() == (1,)
    assert registre.execute(
        "select source, count(*) from mises_a_jour where statut = 'succes' group by source order by source"
    ).fetchall() == [("construction_initiale", 1), ("rne_diff", 3), ("sirene", 3)]


@pytest.mark.usefixtures("etat")
def test_rien_a_lire_publie_quand_meme_le_passage(
    conn: Connexion, registre: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    passage = datetime(2026, 3, 4, 12, 0, tzinfo=UTC)  # veille = 03-03, avant le stock
    rne = FauxRne()
    etats = passer(conn, registre, tmp_path, rne, passage=passage)
    assert rne.jours == [] and [e.statut for e in etats] == ["succes", "succes"]
    publie = lire_etat(conn)
    assert publie[RNE]["date_donnees"] == DATE_STOCK and publie[RNE]["dernier_passage"] == passage
    assert publie[RNE]["volumes"]["jours"] == 0


# --- Jours : dans l'ordre, jamais relus, plafonnés ----------------------------------------


@pytest.mark.usefixtures("etat")
def test_un_jour_applique_n_est_jamais_relu(
    conn: Connexion, registre: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    passer(conn, registre, tmp_path, FauxRne())
    deuxieme, sirene = FauxRne(), FauxSirene()
    passer(conn, registre, tmp_path, deuxieme, sirene)  # même nuit, relancé
    assert deuxieme.jours == [] and sirene.jours == []
    lendemain, sirene = FauxRne(), FauxSirene()
    passer(conn, registre, tmp_path, lendemain, sirene, passage=PASSAGE + timedelta(days=1))
    assert lendemain.jours == [J3 + timedelta(days=1)] and sirene.jours == [J3 + timedelta(days=1)]


@pytest.mark.usefixtures("etat")
def test_plafond_de_jours_par_passage(
    conn: Connexion, registre: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    """Le retard depuis le stock (217 jours ici) n'est jamais lu d'un coup : 7 jours par nuit."""
    passage = datetime(2026, 10, 7, 0, 30, tzinfo=UTC)
    rne, sirene = FauxRne(), FauxSirene()
    passer(conn, registre, tmp_path, rne, sirene, passage=passage, maximum=7)
    attendus = [DATE_STOCK + timedelta(days=i) for i in range(1, 8)]
    assert rne.jours == attendus and sirene.jours == attendus
    assert lire_etat(conn)[RNE]["date_donnees"] == attendus[-1]
    suivant = FauxRne()
    passer(conn, registre, tmp_path, suivant, passage=passage, maximum=7)
    assert suivant.jours == [DATE_STOCK + timedelta(days=i) for i in range(8, 15)]


@pytest.mark.parametrize("ecart", [0, 1, 6, 7, 8, 215])
@pytest.mark.parametrize("maximum", [0, 1, 7])
def test_jours_a_lire_jamais_plus_que_le_plafond(ecart: int, maximum: int) -> None:
    jours = jours_a_lire(DATE_STOCK, DATE_STOCK + timedelta(days=ecart), maximum)
    assert len(jours) == min(ecart, maximum)
    assert jours == sorted(jours) and all(j > DATE_STOCK for j in jours)
    assert jours == [DATE_STOCK + timedelta(days=i) for i in range(1, len(jours) + 1)]  # sans trou
    assert jours_a_lire(DATE_STOCK, DATE_STOCK - timedelta(days=3), maximum) == []


def test_plafond_lu_dans_l_environnement(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CARTOFR_SYNCHRO_JOURS_MAX", raising=False)
    assert jours_max() == 7
    monkeypatch.setenv("CARTOFR_SYNCHRO_JOURS_MAX", "3")
    assert jours_max() == 3
    for invalide in ("0", "-2", "beaucoup"):
        monkeypatch.setenv("CARTOFR_SYNCHRO_JOURS_MAX", invalide)
        assert jours_max() == 7


# --- C2 : un échec écrit sa cause ---------------------------------------------------------


@pytest.mark.usefixtures("etat")
def test_c2_echec_rne_ecrit_sa_cause_sans_donnee(
    conn: Connexion, registre: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    # Un message d'exception qui citerait une société : il ne doit sortir nulle part.
    rne = FauxRne({J2: [RuntimeError("SOCIETE FICTIVE A 000000001")]})
    sirene = FauxSirene()
    etats = passer(conn, registre, tmp_path, rne, sirene)

    assert [e.statut for e in etats] == ["echec", "succes"]
    assert rne.jours == [J1, J2]  # arrêt au premier échec, J3 attend le passage suivant
    publie = lire_etat(conn)
    assert publie[RNE]["statut"] == "echec"
    assert publie[RNE]["erreur"] == "RuntimeError pendant la synchro RNE, page 1"  # celui du journal
    assert publie[RNE]["date_donnees"] == J1  # le dernier jour appliqué
    # SIRENE ne dépasse jamais le dernier jour RNE appliqué.
    assert sirene.jours == [J1] and publie[SIRENE]["date_donnees"] == J1
    assert "FICTIVE" not in json.dumps(publie, default=str)
    # Le passage suivant reprend au jour en échec.
    reprise = FauxRne()
    passer(conn, registre, tmp_path, reprise)
    assert reprise.jours == [J2, J3]


@pytest.mark.usefixtures("etat")
def test_c2_identifiants_refuses(
    conn: Connexion, registre: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    """Vérification manuelle du ticket, automatisée : identifiants faux → cause lisible."""
    refus = ErreurInpi("Connexion INPI refusée (code 401) : vérifier les identifiants.")
    passer(conn, registre, tmp_path, FauxRne({J1: [refus]}))
    publie = lire_etat(conn)[RNE]
    assert (publie["statut"], publie["date_donnees"]) == ("echec", DATE_STOCK)
    assert publie["erreur"] == "ErreurInpi pendant la synchro RNE, page 1"


@pytest.mark.usefixtures("etat")
def test_c2_echec_sirene(conn: Connexion, registre: duckdb.DuckDBPyConnection, tmp_path: Path) -> None:
    etats = passer(conn, registre, tmp_path, FauxRne(), FauxSirene(code=401))
    assert [e.statut for e in etats] == ["succes", "echec"]
    publie = lire_etat(conn)[SIRENE]
    assert (publie["statut"], publie["date_donnees"]) == ("echec", DATE_STOCK)
    assert publie["erreur"] == "Clé INSEE refusée (code 401) : vérifier INSEE_API_KEY."
    assert "cle-FAKE" not in publie["erreur"]


@pytest.mark.usefixtures("etat")
def test_quota_puis_reprise_le_lendemain(
    conn: Connexion, registre: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    rne = FauxRne({J2: [[fiche("societe_a_v1")], QuotaAtteint(None)]})
    sirene = FauxSirene()
    etats = passer(conn, registre, tmp_path, rne, sirene)
    assert [e.statut for e in etats] == ["quota", "succes"]
    assert rne.jours == [J1, J2]
    publie = lire_etat(conn)
    assert (publie[RNE]["statut"], publie[RNE]["erreur"]) == ("quota", MESSAGE_QUOTA)
    assert publie[RNE]["date_donnees"] == J1 and publie[RNE]["volumes"]["fiches"] == 1
    assert sirene.jours == [J1]  # SIRENE passe quand même, sans dépasser le RNE
    # La nuit suivante reprend J2 (la page déjà lue sera reprise au curseur par synchro_rne).
    nuit_suivante = FauxRne()
    passer(conn, registre, tmp_path, nuit_suivante, passage=PASSAGE + timedelta(days=1))
    assert nuit_suivante.jours == [J2, J3, J3 + timedelta(days=1)]
    assert lire_etat(conn)[RNE]["statut"] == "succes"


def test_registre_reconstruit_repart_du_stock(tmp_path: Path) -> None:
    chemin = tmp_path / "jours.json"
    Jours(chemin, "1|2026-10-06").noter(RNE, J3)
    assert Jours(chemin, "1|2026-10-06").dernier(RNE) == J3
    assert Jours(chemin, "2|2026-11-01").dernier(RNE) == DATE_STOCK  # autre construction
    assert Jours(chemin, "1|2026-10-06").dernier(SIRENE) == DATE_STOCK


# --- Le travail dans la file ------------------------------------------------------------


@pytest.fixture
def sans_reseau(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    """Le travail réel, branché sur les faux clients et un dossier de données temporaire."""
    faux: dict[str, Any] = {"rne": FauxRne(), "sirene": FauxSirene()}
    monkeypatch.setenv("CARTOFR_DATA", str(tmp_path))
    monkeypatch.setattr(inpi_diff, "charger_env", lambda *_: None)
    monkeypatch.setattr(inpi_diff, "Client", lambda: faux["rne"])
    monkeypatch.setattr(synchro_sirene, "Client", lambda: faux["sirene"].client())
    return faux


def lancer_travail(conn: Connexion) -> dict[str, Any]:
    """Insère un travail synchro de test (daté de 2099), l'exécute, rend sa ligne."""
    ligne = conn.execute(
        "insert into public.travaux (type, parametres, cree_le) values ('synchro', '{}', '2099-12-31')"
        " returning id"
    ).fetchone()
    assert ligne is not None
    conn.commit()
    travail = travaux.Travail(id=ligne[0], type="synchro", organisation_id=None)
    conn.execute("update public.travaux set statut = 'en_cours', debut_le = now() where id = %s", (ligne[0],))
    conn.commit()
    try:
        travaux.executer(conn, travail)
        cur = conn.execute("select statut, erreur from public.travaux where id = %s", (ligne[0],))
        statut, erreur = cast(tuple[str, str | None], cur.fetchone())
        conn.commit()
    finally:
        conn.execute("delete from public.travaux where id = %s", (ligne[0],))
        conn.commit()
    return {"statut": statut, "erreur": erreur}


@pytest.mark.usefixtures("etat")
def test_travail_synchro_dans_la_file(conn: Connexion, tmp_path: Path, sans_reseau: dict[str, Any]) -> None:
    assert "synchro" in TRAVAUX
    con = duckdb.connect(str(tmp_path / "registre.duckdb"))
    creer_tables(con)
    journal.terminer(con, journal.ouvrir(con, "construction_initiale"), ajoutes=0, fermes=0)
    con.close()

    assert lancer_travail(conn) == {"statut": "termine", "erreur": None}
    assert lire_etat(conn)[RNE]["statut"] == "succes"
    # Le registre est refermé : un autre processus peut l'ouvrir.
    duckdb.connect(str(tmp_path / "registre.duckdb"), read_only=True).close()

    # Repartir du stock (registre vide, rien à défaire) avec un refus INPI dès le premier jour.
    (tmp_path / "synchro" / "jours.json").unlink()
    sans_reseau["rne"] = FauxRne({J1: [ErreurInpi("refus")]})
    assert lancer_travail(conn) == {"statut": "echec", "erreur": "échec du travail (SynchroEnEchec)"}
    assert lire_etat(conn)[RNE]["erreur"] == "ErreurInpi pendant la synchro RNE, page 1"


@pytest.mark.usefixtures("etat", "sans_reseau")
def test_c2_registre_absent(conn: Connexion) -> None:
    assert lancer_travail(conn) == {"statut": "echec", "erreur": "échec du travail (SynchroEnEchec)"}
    publie = lire_etat(conn)
    assert publie[RNE]["statut"] == publie[SIRENE]["statut"] == "echec"
    assert publie[RNE]["erreur"] == MESSAGE_REGISTRE_ABSENT


def test_travail_sans_connexion() -> None:
    with pytest.raises(SynchroEnEchec):
        synchro.travail_synchro(Contexte(travail_id=1, type="synchro", organisation_id=None))


# --- C3 : un travail synchro chaque nuit, une seule fois ------------------------------------


@pytest.fixture
def planifies(conn: Connexion) -> Iterator[None]:
    """Supprime les travaux synchro de test (tous datés de 2099)."""

    def nettoyer() -> None:
        conn.rollback()
        conn.execute("delete from public.travaux where type = 'synchro' and cree_le >= '2099-01-01'")
        conn.commit()

    nettoyer()
    yield
    nettoyer()


def synchros(conn: Connexion) -> list[tuple[Any, ...]]:
    lignes = conn.execute(
        "select cree_le, parametres from public.travaux where type = 'synchro' and cree_le >= '2099-01-01'"
        " order by cree_le"
    ).fetchall()
    conn.commit()
    return lignes


def utc(annee: int, mois: int, jour: int, heure: int, minute: int) -> datetime:
    return datetime(annee, mois, jour, heure, minute, tzinfo=UTC)


@pytest.mark.usefixtures("planifies")
def test_c3_un_travail_par_nuit(conn: Connexion) -> None:
    # Hiver : Paris = UTC+1.
    assert travaux.planifier_synchro(conn, utc(2099, 1, 15, 0, 59)) is None  # 01:59 à Paris
    assert synchros(conn) == []
    premier = travaux.planifier_synchro(conn, utc(2099, 1, 15, 1, 0))  # 02:00 à Paris
    assert premier is not None
    assert travaux.planifier_synchro(conn, utc(2099, 1, 15, 1, 0)) is None
    assert travaux.planifier_synchro(conn, utc(2099, 1, 15, 22, 59)) is None  # 23:59 à Paris
    assert travaux.planifier_synchro(conn, utc(2099, 1, 16, 1, 0)) is not None  # la nuit suivante
    lignes = synchros(conn)
    assert [ligne[0] for ligne in lignes] == [utc(2099, 1, 15, 1, 0), utc(2099, 1, 16, 1, 0)]
    assert lignes[0][1] == {"planifie_le": "2099-01-15"}


@pytest.mark.usefixtures("planifies")
def test_c3_deux_appels_simultanes_un_seul_travail(conn: Connexion) -> None:
    for jour in range(1, 6):
        maintenant = utc(2099, 2, jour, 3, 0)
        barriere = threading.Barrier(4)
        ids: list[int | None] = []

        def appeler(
            moment: datetime = maintenant,
            sortie: list[int | None] = ids,
            depart: threading.Barrier = barriere,
        ) -> None:
            with connecter() as autre:
                depart.wait()
                sortie.append(travaux.planifier_synchro(autre, moment))

        fils = [threading.Thread(target=appeler) for _ in range(4)]
        for f in fils:
            f.start()
        for f in fils:
            f.join(timeout=10)
        assert len(ids) == 4 and len([i for i in ids if i is not None]) == 1
    assert len(synchros(conn)) == 5


@pytest.mark.usefixtures("planifies")
def test_c3_minuit_heure_de_paris(conn: Connexion) -> None:
    # Été : Paris = UTC+2. 22:30 UTC le 15 = 00:30 à Paris le 16 : pas encore l'heure.
    assert travaux.planifier_synchro(conn, utc(2099, 7, 15, 22, 30)) is None
    assert travaux.planifier_synchro(conn, utc(2099, 7, 16, 0, 0)) is not None  # 02:00 à Paris
    assert synchros(conn)[0][1] == {"planifie_le": "2099-07-16"}


@pytest.mark.usefixtures("planifies")
def test_c3_changements_d_heure(conn: Connexion) -> None:
    # 2099-03-29 : 02:00 n'existe pas à Paris, 01:59 CET est suivi de 03:00 CEST.
    assert travaux.planifier_synchro(conn, utc(2099, 3, 29, 0, 59)) is None
    assert travaux.planifier_synchro(conn, utc(2099, 3, 29, 1, 0)) is not None
    # 2099-10-25 : 02:00 arrive deux fois (CEST puis CET). Un seul travail.
    assert travaux.planifier_synchro(conn, utc(2099, 10, 25, 0, 0)) is not None  # 02:00 CEST
    assert travaux.planifier_synchro(conn, utc(2099, 10, 25, 1, 0)) is None  # 02:00 CET
    assert len(synchros(conn)) == 2


@pytest.mark.usefixtures("planifies")
def test_c3_heure_reglable(conn: Connexion) -> None:
    heure = travaux.heure_synchro("04:30")
    assert heure == time(4, 30)
    assert travaux.planifier_synchro(conn, utc(2099, 1, 20, 3, 0), heure) is None  # 04:00 à Paris
    assert travaux.planifier_synchro(conn, utc(2099, 1, 20, 3, 30), heure) is not None


def test_heure_synchro_format(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CARTOFR_SYNCHRO_HEURE", raising=False)
    assert travaux.heure_synchro() == time(2, 0)
    monkeypatch.setenv("CARTOFR_SYNCHRO_HEURE", "03:15")
    assert travaux.heure_synchro() == time(3, 15)
    for invalide in ("3h", "25:00", "02:00:00"):
        with pytest.raises(ValueError, match="HH:MM"):
            travaux.heure_synchro(invalide)


class FausseConnexion:
    closed = False
    broken = False

    def close(self) -> None:
        pass

    def rollback(self) -> None:
        pass


@pytest.mark.parametrize(("heure", "attendu"), [(None, 0), ("00:00", 1)])
def test_boucle_planifie_seulement_si_l_heure_est_reglee(
    monkeypatch: pytest.MonkeyPatch, heure: str | None, attendu: int
) -> None:
    """Sans CARTOFR_SYNCHRO_HEURE, la boucle ne planifie rien ; avec, une fois par jour."""
    if heure is None:
        monkeypatch.delenv("CARTOFR_SYNCHRO_HEURE", raising=False)
    else:
        monkeypatch.setenv("CARTOFR_SYNCHRO_HEURE", heure)
    appels: list[datetime] = []
    tours = {"n": 0}
    arret = threading.Event()

    def traiter(_: Any) -> bool:
        tours["n"] += 1
        if tours["n"] >= 5:
            arret.set()
        return False

    monkeypatch.setattr(travaux, "planifier_synchro", lambda _c, m, _h: appels.append(m))
    monkeypatch.setattr(travaux, "traiter_un", traiter)
    travaux.boucle(arret, 0.0, connecteur=lambda: cast(Connexion, FausseConnexion()))
    assert tours["n"] == 5 and len(appels) == attendu  # une seule vérification pour le jour en cours


@pytest.mark.parametrize(("brut", "attendu"), [("", 1), ("2", 2), ("0", 1), ("x", 1)])
def test_decalage_reglable(monkeypatch: pytest.MonkeyPatch, brut: str, attendu: int) -> None:
    """Le dernier jour lu recule de CARTOFR_SYNCHRO_DECALAGE jours (1 par défaut, jamais moins)."""
    from cartofr.jobs import synchro

    monkeypatch.setenv(synchro.VARIABLE_DECALAGE, brut)
    midi = datetime(2026, 10, 7, 12, 0, tzinfo=synchro.FUSEAU)
    assert synchro.veille_a_paris(midi) == date(2026, 10, 7) - timedelta(days=attendu)


def test_ouverture_reessaie_tant_qu_un_lecteur_tient_le_registre(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Un lecteur bref (recherche T019) ne fait pas échouer la synchro : on réessaie."""
    import duckdb

    from cartofr.jobs import synchro

    chemin = tmp_path / "registre.duckdb"
    duckdb.connect(str(chemin)).close()
    vrai = duckdb.connect
    appels = {"n": 0}

    def connect_occupe(*args: object, **kwargs: object) -> duckdb.DuckDBPyConnection:
        appels["n"] += 1
        if appels["n"] < 3:
            raise duckdb.IOException("Could not set lock on file")
        return vrai(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(synchro.duckdb, "connect", connect_occupe)
    con = synchro.ouvrir_en_ecriture(chemin, essais=5, pause=0)
    con.close()
    assert appels["n"] == 3

    appels["n"] = -100
    with pytest.raises(duckdb.IOException):
        synchro.ouvrir_en_ecriture(chemin, essais=3, pause=0)
