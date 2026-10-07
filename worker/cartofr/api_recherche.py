"""Route HTTP interne de recherche de la tête d'un groupe (T019, ARCHI « Recherche de la tête »).

But : le seul pont entre l'interface et le registre. L'écran « Nouveau groupe »
cherche une société par nom ou par SIREN ; cette route lit `registre.duckdb`
en lecture seule et rend 20 sociétés au plus.

Usage :
    CARTOFR_DATA=data .venv/bin/python -m cartofr.api_recherche [--port 8080] [--hote 0.0.0.0]

Routes :
    GET /recherche?q=<nom ou SIREN>
        200 {"resultats": [{"siren", "nom", "sigle", "ville", "statut"}, ...]}
        400 {"erreur": "requete_trop_courte" | "requete_trop_longue"}
        503 {"erreur": "registre_occupe" | "registre_absent"}
    GET /sante  → 200 {"statut": "ok"}

Entrées : `<CARTOFR_DATA>/registre.duckdb` (`data` par défaut), ou CARTOFR_REGISTRE.
Sortie : du JSON. `statut` vaut `active`, `cessee` (SIRENE : état C) ou
`radiee` (fermée au registre : `fin` posée).

Règles tenues ici :
- aucun champ de personne (garde-fou 6, principe 6) : la réponse ne porte que
  des champs de société, `dirigeants_personnes` n'est jamais lue, et les
  entrepreneurs individuels (catégorie juridique 1xxx, dont le nom est celui
  d'une personne) sont écartés ;
- la cartographie ne fait aucun appel extérieur (principe 3) : seule la base
  locale est lue ;
- registre ouvert en lecture seule, à chaque requête. Quand la synchro tient le
  verrou d'écriture (DuckDB : un seul écrivain), la route répond 503 au lieu
  d'attendre ;
- journaux sans le texte cherché : un nom de personne peut y être tapé par
  erreur (règle produit 4). On ne journalise que le nombre de résultats, le
  statut et la durée ;
- SQL paramétré : la saisie ne touche jamais le texte de la requête.
"""

import argparse
import json
import logging
import os
import re
import signal
import time
import unicodedata
from dataclasses import asdict, dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import duckdb

log = logging.getLogger("cartofr.recherche")

MAX_RESULTATS = 20
LONGUEUR_MIN = 2
LONGUEUR_MAX = 100
SIREN = re.compile(r"^[0-9]{9}$")


class RegistreIndisponible(RuntimeError):
    """Le registre ne peut pas être ouvert : absent, ou verrouillé par la synchro."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class RequeteInvalide(ValueError):
    """La saisie est vide, trop courte ou trop longue."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Resultat:
    """Une société trouvée. Que des champs de société : jamais de personne."""

    siren: str
    nom: str
    sigle: str | None
    ville: str | None
    statut: str  # 'active', 'cessee' ou 'radiee'


def chemin_registre() -> Path:
    """Emplacement du registre : CARTOFR_REGISTRE, sinon <CARTOFR_DATA>/registre.duckdb."""
    explicite = os.environ.get("CARTOFR_REGISTRE")
    if explicite:
        return Path(explicite)
    return Path(os.environ.get("CARTOFR_DATA", "data")) / "registre.duckdb"


def normaliser(texte: str) -> str:
    """Majuscules, sans accents, espaces réduits : comme `upper(strip_accents(…))` côté SQL."""
    sans_accents = "".join(c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c))
    return " ".join(sans_accents.upper().split())


def preparer(q: str) -> str:
    """Saisie normalisée, ou RequeteInvalide. Un SIREN tapé avec des espaces est recollé."""
    texte = normaliser(q)
    compact = texte.replace(" ", "")
    if SIREN.match(compact):
        return compact
    if len(texte) < LONGUEUR_MIN:
        raise RequeteInvalide("requete_trop_courte")
    if len(texte) > LONGUEUR_MAX:
        raise RequeteInvalide("requete_trop_longue")
    return texte


def ouvrir(chemin: Path) -> duckdb.DuckDBPyConnection:
    """Connexion en lecture seule, ou RegistreIndisponible (absent, ou verrouillé en écriture)."""
    if not chemin.is_file():
        raise RegistreIndisponible("registre_absent")
    try:
        return duckdb.connect(str(chemin), read_only=True)
    except (duckdb.IOException, duckdb.ConnectionException) as exc:
        # Message DuckDB non recopié : il contient le chemin et le PID du verrou.
        raise RegistreIndisponible("registre_occupe") from exc


def _tables(con: duckdb.DuckDBPyConnection) -> set[str]:
    lignes = con.execute("select table_name from information_schema.tables").fetchall()
    return {str(ligne[0]) for ligne in lignes}


def _rang(colonne: str, famille: int) -> str:
    """Rang d'une colonne de nom pour la saisie `$q` (normalisée) : `famille` + 0 si
    la colonne est égale à la saisie, + 1 si elle commence par elle ; 30 + `famille`/10
    si elle la contient seulement. Vide sinon."""
    n = f"upper(strip_accents({colonne}))"
    return (
        f"case when {n} = $q then {famille} when starts_with({n}, $q) then {famille + 1} "
        f"when contains({n}, $q) then {30 + famille // 10} end"
    )


def _sql(tables: set[str], par_siren: bool) -> str:
    """Requête de recherche, selon les tables présentes dans ce registre.

    `societes` (RNE, personnes morales) est toujours là. `unites_legales`
    (SIRENE, si chargée) apporte le sigle et la catégorie juridique, `sieges`
    la ville et la catégorie des unités actives. Trois familles, dans cet ordre :
    SIREN, dénomination égale ou qui commence par la saisie (rangs 10-11) ; sigle
    égal ou qui commence par elle (20-21) ; nom qui la contient (31-32). Dans une
    famille : les actives d'abord, puis les plus grosses (tranche d'effectif),
    pour que la tête d'un groupe passe avant ses homonymes ; puis l'égalité
    exacte avant le début, puis le nom.
    """
    ul = "unites_legales" in tables
    cj = "coalesce(u.categorie_juridique, g.cj)" if ul else "g.cj"
    sigle = "u.sigle" if ul else "null"
    tranche = "coalesce(u.tranche_effectifs, g.tranche)" if ul else "g.tranche"
    etat = "coalesce(s.etat_administratif, u.etat_administratif)" if ul else "s.etat_administratif"
    fin = "coalesce(s.fin, u.fin)" if ul else "s.fin"
    nom = "coalesce(s.denomination, u.denomination, g.nom)" if ul else "coalesce(s.denomination, g.nom)"

    if par_siren:
        sources = ["select $q as siren, 10 as rang"]
    else:
        sources = [f"select siren, {_rang('denomination', 10)} as rang from societes"]
        if ul:
            sources.append(
                f"select siren, least({_rang('denomination', 10)}, {_rang('sigle', 20)}) as rang "
                "from unites_legales where categorie_juridique is null "
                "or categorie_juridique not between 1000 and 1999"
            )
        else:
            # Sans unites_legales : les sièges SIRENE (personnes morales actives) portent le nom.
            sources.append(f"select siren, {_rang('nom', 10)} as rang from sieges")

    candidats = " union all ".join(f"({s})" for s in sources)
    jointure_ul = "left join unites_legales u on u.siren = m.siren" if ul else ""
    return f"""
        with candidats as ({candidats}),
        meilleurs as (
            select siren, min(rang) as rang from candidats where rang is not null group by siren
        )
        select m.siren, {nom} as nom, {sigle} as sigle, g.commune as ville,
               case when {fin} is not null then 'radiee'
                    when {etat} = 'C' then 'cessee'
                    else 'active' end as statut
        from meilleurs m
        left join societes s on s.siren = m.siren
        {jointure_ul}
        left join sieges g on g.siren = m.siren
        where {nom} is not null
          and ({cj} is null or {cj} not between 1000 and 1999)
        order by m.rang // 10,
                 ({fin} is null and coalesce({etat}, 'A') <> 'C') desc,
                 try_cast({tranche} as integer) desc nulls last,
                 m.rang, nom, m.siren
        limit {MAX_RESULTATS}
    """


def rechercher(q: str, chemin: Path | None = None) -> list[Resultat]:
    """Les sociétés qui correspondent à `q` (nom, sigle ou SIREN), 20 au plus."""
    saisie = preparer(q)
    con = ouvrir(chemin or chemin_registre())
    try:
        con.execute("set enable_progress_bar = false")
        sql = _sql(_tables(con), par_siren=bool(SIREN.match(saisie)))
        lignes: list[tuple[Any, ...]] = con.execute(sql, {"q": saisie}).fetchall()
    finally:
        con.close()
    return [
        Resultat(
            siren=str(siren),
            nom=str(nom).strip(),
            sigle=str(sigle) if sigle else None,
            ville=str(ville) if ville else None,
            statut=str(statut),
        )
        for siren, nom, sigle, ville, statut in lignes
    ]


class Gestionnaire(BaseHTTPRequestHandler):
    """Deux routes en GET. Tout le reste : 404 ou 405."""

    server_version = "cartofr-recherche"
    sys_version = ""

    def _repondre(self, statut: HTTPStatus, corps: dict[str, Any]) -> None:
        donnees = json.dumps(corps, ensure_ascii=False).encode("utf-8")
        self.send_response(statut)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(donnees)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(donnees)

    def do_GET(self) -> None:  # noqa: N802 (nom imposé par http.server)
        url = urlsplit(self.path)
        if url.path == "/sante":
            self._repondre(HTTPStatus.OK, {"statut": "ok"})
            return
        if url.path != "/recherche":
            self._repondre(HTTPStatus.NOT_FOUND, {"erreur": "route_inconnue"})
            return
        debut = time.monotonic()
        q = parse_qs(url.query).get("q", [""])[0]
        try:
            resultats = rechercher(q, self.server.registre)  # type: ignore[attr-defined]
        except RequeteInvalide as exc:
            log.info("recherche : 400 %s", exc.code)
            self._repondre(HTTPStatus.BAD_REQUEST, {"erreur": exc.code})
            return
        except RegistreIndisponible as exc:
            log.warning("recherche : 503 %s", exc.code)
            self._repondre(HTTPStatus.SERVICE_UNAVAILABLE, {"erreur": exc.code})
            return
        except Exception as exc:  # noqa: BLE001 : jamais de trace avec la saisie dans le journal
            log.error("recherche : 500 %s", type(exc).__name__)
            self._repondre(HTTPStatus.INTERNAL_SERVER_ERROR, {"erreur": "erreur_interne"})
            return
        duree = int((time.monotonic() - debut) * 1000)
        log.info("recherche : 200, %d résultat(s) en %d ms", len(resultats), duree)
        self._repondre(HTTPStatus.OK, {"resultats": [asdict(r) for r in resultats]})

    def do_POST(self) -> None:  # noqa: N802
        self._repondre(HTTPStatus.METHOD_NOT_ALLOWED, {"erreur": "methode_refusee"})

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        # Le journal par défaut recopie la ligne de requête, donc la saisie : coupé.
        return


class Serveur(ThreadingHTTPServer):
    """Serveur HTTP qui connaît l'emplacement du registre."""

    daemon_threads = True

    def __init__(self, adresse: tuple[str, int], registre: Path | None = None) -> None:
        super().__init__(adresse, Gestionnaire)
        self.registre = registre


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Route interne de recherche dans le registre.")
    parser.add_argument("--hote", default=os.environ.get("CARTOFR_RECHERCHE_HOTE", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("CARTOFR_RECHERCHE_PORT", "8080")))
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=os.environ.get("CARTOFR_LOG", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s : %(message)s",
    )
    serveur = Serveur((args.hote, args.port))

    def arreter(signum: int, _frame: object) -> None:
        # PID 1 dans le conteneur : sans gestionnaire, SIGTERM (docker stop) est ignoré.
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, arreter)
    log.info("recherche : écoute sur le port %d", args.port)
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        serveur.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
