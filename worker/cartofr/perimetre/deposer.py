"""Déposer les documents de périmètre des groupes, un par un ou en lot (T046, PRD FR-013).

Usage, depuis la racine du dépôt (ou dans le conteneur du worker) :
    CARTOFR_DATA=data .venv/bin/python -m cartofr.perimetre.deposer <SIREN de la tête> <fichier>
        [--mere "<raison sociale>" --pays-mere <code ISO>]
    CARTOFR_DATA=data .venv/bin/python -m cartofr.perimetre.deposer --dossier <dossier>
Avec `--dossier`, le fichier `<dossier>/index.csv` (UTF-8, séparateur virgule) donne une ligne par
document : `tete,fichier`, le chemin relatif au dossier, et en option `mere,pays_mere`.

Groupe dont la mère est à l'étranger (T054, décision de Loïc du 2026-10-21) : la tête est une
société française du groupe (sa holding en France, ou la plus souvent mère directe dans la liste),
et le dépôt garde qui est la mère et son pays (« Stellantis N.V. », « NL »). C'est une donnée de
société saisie par un humain, sourcée (GLEIF) : elle ne décide rien dans la carto.

Entrées : les documents (PDF, page HTML ou texte), déjà téléchargés : la commande ne va jamais sur
le réseau (principe 3). `<CARTOFR_DATA>/registre.duckdb` : lu pendant la correspondance, ouvert en
écriture le temps de la seule transaction finale.
Sorties :
- chaque document copié dans `<CARTOFR_DATA>/perimetre/`, sous un nom neuf : `<tête>-<horodatage
  UTC>` et son extension. Un fichier déposé n'est jamais écrasé ni effacé ;
- une ligne par document dans `documents_perimetre`. Un nouveau dépôt pour la même tête ferme la
  ligne du précédent (`fin`) : un seul document en vigueur par groupe. Un document identique
  (même empreinte, même mère étrangère) à celui en vigueur ne change rien ;
- à l'écran, par document : les lignes lues, retrouvées et refusées par raison, puis les lignes
  refusées. Seule la ligne de la société est recopiée, jamais les lignes d'avant du document : un
  pied de page pourrait porter un nom de personne (garde-fou 6). Le nom du fichier d'origine n'est
  pas affiché non plus, seulement celui qui est gardé.
Toute la demande est refusée avant la moindre écriture si un document est illisible, ne donne
aucune ligne (PDF scanné, autre format de liste), ou si une tête n'existe pas au registre : un
mauvais document ne remplace jamais un bon.
"""

import argparse
import collections
import csv
import hashlib
import os
import re
import shutil
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb
from pypdf.errors import PyPdfError

from cartofr.perimetre.correspondance import (
    COMMUNE,
    COMPACTE,
    CONFLIT,
    DEBUT,
    FERMEE,
    FONDS,
    HOMONYMES,
    INTROUVABLE,
    REGISTRE,
    UNIQUE,
    USUELLE,
    Correspondance,
    correspondre_plusieurs,
)
from cartofr.perimetre.extraction import LignePerimetre, extraire, texte_document
from cartofr.registre.schema import DDL_DOCUMENTS

NOM_REGISTRE = "registre.duckdb"
DOSSIER_DOCUMENTS = "perimetre"
INDEX = "index.csv"
_SIREN = re.compile(r"\d{9}")
_PAYS_ISO = re.compile(r"[A-Z]{2}")
OCCUPE = "Le registre est occupé (synchro en cours ?) : réessayez plus tard."


class DepotInvalide(ValueError):
    """Une demande de dépôt qu'on ne peut pas traiter ; le message est en français, pour l'écran."""


@dataclass(frozen=True)
class Demande:
    """Un document à déposer pour la tête d'un groupe."""

    tete: str
    source: Path
    mere: str | None = None  # raison sociale de la mère hors de France (T054)
    pays_mere: str | None = None  # son pays, code ISO à 2 lettres


@dataclass(frozen=True)
class Depot:
    """Ce que le dépôt a fait d'un document."""

    demande: Demande
    resultats: tuple[Correspondance, ...]
    fichier: str | None  # nom du fichier gardé ; None si identique au document en vigueur
    empreinte: str

    @property
    def retenues(self) -> int:
        return sum(c.retenue for c in self.resultats)


def lire_index(dossier: Path) -> list[Demande]:
    """Les demandes de `<dossier>/index.csv` (colonnes `tete`, `fichier`), ligne par ligne vérifiées."""
    index = dossier / INDEX
    if not index.is_file():
        raise DepotInvalide(f"Index introuvable : {index}. Il faut un fichier {INDEX} (tete,fichier).")
    try:
        # utf-8-sig : un CSV enregistré par Excel commence par une marque d'ordre des octets.
        with index.open(newline="", encoding="utf-8-sig") as f:
            lecteur = csv.DictReader(f)
            colonnes = lecteur.fieldnames or []
            lignes = list(lecteur)
    except UnicodeDecodeError as erreur:
        raise DepotInvalide(f"{index} doit être enregistré en UTF-8.") from erreur
    if not {"tete", "fichier"} <= set(colonnes):
        conseil = (
            " Le séparateur doit être la virgule, pas le point-virgule." if ";" in "".join(colonnes) else ""
        )
        raise DepotInvalide(f"{index} : les colonnes attendues sont « tete » et « fichier ».{conseil}")
    demandes = []
    for numero, ligne in enumerate(lignes, start=2):  # la ligne 1 est l'en-tête
        tete, fichier = (ligne.get("tete") or "").strip(), (ligne.get("fichier") or "").strip()
        if not tete or not fichier:
            raise DepotInvalide(f"{index}, ligne {numero} : il faut une tête et un fichier.")
        mere, pays = (ligne.get("mere") or "").strip(), (ligne.get("pays_mere") or "").strip()
        demandes.append(Demande(tete, dossier / fichier, mere or None, _pays(pays)))
    return demandes


def verifier(demandes: Sequence[Demande]) -> None:
    """Refuse la demande entière avant toute lecture : SIREN mal formé, fichier absent, tête en double."""
    if not demandes:
        raise DepotInvalide("Aucun document à déposer.")
    vues: set[str] = set()
    for d in demandes:
        if not _SIREN.fullmatch(d.tete):
            raise DepotInvalide(f"SIREN de tête invalide : « {d.tete} » (9 chiffres attendus).")
        if not d.source.is_file():
            raise DepotInvalide(f"Document introuvable : {d.source}")
        if d.tete in vues:
            raise DepotInvalide(f"La tête {d.tete} a deux documents dans ce dépôt : un seul par groupe.")
        vues.add(d.tete)
        if (d.mere is None) != (d.pays_mere is None):
            raise DepotInvalide(f"Tête {d.tete} : la mère étrangère et son pays vont ensemble.")
        if d.pays_mere is not None and (not _PAYS_ISO.fullmatch(d.pays_mere) or d.pays_mere == "FR"):
            raise DepotInvalide(
                f"Tête {d.tete} : pays de la mère « {d.pays_mere} » invalide (code ISO à 2 lettres, hors FR)."
            )


def _lire(demande: Demande) -> list[LignePerimetre]:
    """Les lignes d'un document, ou un refus en français : jamais un document vide en vigueur."""
    try:
        lignes = extraire(texte_document(demande.source))
    except (ValueError, OSError, PyPdfError) as erreur:
        raise DepotInvalide(
            f"Document illisible pour la tête {demande.tete} : fichier abîmé, ou trop gros"
            " (50 Mo, 300 Mo pour un paquet ESEF ou une page HTML)."
        ) from erreur
    if not lignes:
        raise DepotInvalide(
            f"Aucune société située en France lue dans le document de la tête {demande.tete} :"
            " PDF scanné, ou format de liste encore inconnu. Rien n'est déposé."
        )
    return lignes


def _ouvrir(registre: Path, lecture_seule: bool) -> duckdb.DuckDBPyConnection:
    try:
        con = duckdb.connect(str(registre), read_only=lecture_seule)
    except (duckdb.IOException, duckdb.ConnectionException) as erreur:
        raise DepotInvalide(OCCUPE) from erreur
    con.execute("set enable_progress_bar = false")
    return con


def _empreinte(chemin: Path) -> str:
    h = hashlib.sha256()
    with chemin.open("rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def deposer(demandes: Sequence[Demande], data: Path, maintenant: datetime | None = None) -> list[Depot]:
    """Lit, retrouve et enregistre les documents. Rien n'est écrit si une étape échoue."""
    verifier(demandes)
    registre = data / NOM_REGISTRE
    if not registre.is_file():
        raise DepotInvalide(f"Registre introuvable : {registre}")
    lignes = [_lire(d) for d in demandes]

    # La correspondance (25 à 40 s) se fait en lecture : le registre reste lisible par les autres.
    con = _ouvrir(registre, lecture_seule=True)
    try:
        connues = {
            s
            for (s,) in con.execute(
                "select siren from unites_legales where siren in (select unnest($t))"
                " union select siren from societes where siren in (select unnest($t))",
                {"t": [d.tete for d in demandes]},
            ).fetchall()
        }
        inconnues = [d.tete for d in demandes if d.tete not in connues]
        if inconnues:
            raise DepotInvalide(f"Tête absente du registre : {', '.join(inconnues)}. Vérifiez le SIREN.")
        resultats = correspondre_plusieurs(
            con, [(d.tete, li) for d, li in zip(demandes, lignes, strict=True)]
        )
    finally:
        con.close()

    maintenant = maintenant or datetime.now(UTC)
    horodatage = f"{maintenant.astimezone(UTC):%Y%m%dT%H%M%SZ}"
    dossier = data / DOSSIER_DOCUMENTS
    dossier.mkdir(parents=True, exist_ok=True)
    con = _ouvrir(registre, lecture_seule=False)
    copies: list[Path] = []
    try:
        con.execute(DDL_DOCUMENTS)
        con.execute("begin")
        depots = []
        numero = con.execute("select coalesce(max(id), 0) from documents_perimetre").fetchone()
        prochain = (numero[0] if numero else 0) + 1
        for demande, res in zip(demandes, resultats, strict=True):
            empreinte = _empreinte(demande.source)
            en_vigueur = con.execute(
                "select empreinte, mere_etrangere, pays_mere from documents_perimetre"
                " where tete = ? and fin is null",
                [demande.tete],
            ).fetchone()
            if en_vigueur and tuple(en_vigueur) == (empreinte, demande.mere, demande.pays_mere):
                depots.append(Depot(demande, tuple(res), None, empreinte))
                continue
            nom = f"{demande.tete}-{horodatage}{demande.source.suffix.lower()}"
            cible = dossier / nom
            if cible.exists():
                raise DepotInvalide(f"Le fichier {cible} existe déjà : relancez dans une seconde.")
            copies.append(cible)  # avant la copie : une copie interrompue est retirée aussi
            shutil.copy2(demande.source, cible)
            con.execute(
                "update documents_perimetre set fin = ? where tete = ? and fin is null",
                [maintenant, demande.tete],
            )
            retenues = sum(c.retenue for c in res)
            con.execute(
                "insert into documents_perimetre (id, tete, fichier, empreinte, debut, lignes, retenues,"
                " refusees, mere_etrangere, pays_mere) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    prochain,
                    demande.tete,
                    nom,
                    empreinte,
                    maintenant,
                    len(res),
                    retenues,
                    len(res) - retenues,
                    demande.mere,
                    demande.pays_mere,
                ],  # fmt: skip
            )
            prochain += 1
            depots.append(Depot(demande, tuple(res), nom, empreinte))
        con.execute("commit")
        copies = []  # écrites et enregistrées : elles restent
        return depots
    except BaseException:
        try:
            con.execute("rollback")
        except duckdb.Error:
            pass  # pas de transaction ouverte (échec avant `begin`, ou `commit` déjà défait)
        raise
    finally:
        for copie in copies:  # nos copies d'un dépôt raté seulement, jamais un fichier déjà gardé
            copie.unlink(missing_ok=True)
        con.close()


def resume(depot: Depot) -> list[str]:
    """Le compte rendu d'un document, en français : des nombres et les lignes refusées."""
    raisons = collections.Counter(c.raison for c in depot.resultats)
    etat = f"gardé sous {depot.fichier}" if depot.fichier else "identique au document en vigueur, rien changé"
    mere = depot.demande.mere
    # Étape 6 (T055) : dites seulement quand elle a servi, le compte rendu d'avant ne change pas.
    retrouvees_6 = [(raisons[COMPACTE], "sans espaces"), (raisons[USUELLE], "par la dénomination usuelle"),
                    (raisons[DEBUT], "par le début de la raison sociale")]  # fmt: skip
    refusees_6 = [(raisons[FONDS], "fonds"), (raisons[FERMEE], "fermées")]
    sortie = [
        f"{depot.demande.tete} · {etat}"
        + (f" · mère étrangère : {mere} ({depot.demande.pays_mere})" if mere else ""),
        f"  lignes en France : {len(depot.resultats)} · retrouvées : {depot.retenues}"
        f" ({raisons[UNIQUE]} uniques, {raisons[COMMUNE]} par la commune,"
        f" {raisons[REGISTRE]} par le registre{_en_plus(retrouvees_6)})"
        f" · refusées : {raisons[HOMONYMES]} homonymes, {raisons[INTROUVABLE]} introuvables,"
        f" {raisons[CONFLIT]} en conflit{_en_plus(refusees_6)}",
    ]
    for c in depot.resultats:
        if not c.retenue:
            porteurs = f", {c.porteurs} porteurs" if c.porteurs else ""
            sortie.append(f"  refusée ({c.raison}{porteurs}) : {c.ligne.texte}")
    return sortie


def _en_plus(comptes: list[tuple[int, str]]) -> str:
    return "".join(f", {n} {quoi}" for n, quoi in comptes if n)


def _pays(code: str | None) -> str | None:
    return (code or "").strip().upper() or None


def main(arguments: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parseur.add_argument("tete", nargs="?", help="SIREN de la tête du groupe")
    parseur.add_argument("fichier", nargs="?", type=Path, help="le document du groupe")
    parseur.add_argument("--dossier", type=Path, help=f"un dossier de documents, avec {INDEX}")
    parseur.add_argument("--mere", help="raison sociale de la mère, si elle est hors de France")
    parseur.add_argument("--pays-mere", help="pays de la mère, code ISO à 2 lettres (« NL »)")
    options = parseur.parse_args(arguments)
    if options.dossier and (options.tete or options.fichier or options.mere or options.pays_mere):
        parseur.error("donnez soit une tête et un fichier, soit --dossier (la mère va dans index.csv)")
    if not options.dossier and not (options.tete and options.fichier):
        parseur.error("il faut une tête et un fichier, ou --dossier")
    data = Path(os.environ.get("CARTOFR_DATA", "data"))
    try:
        demandes = (
            lire_index(options.dossier)
            if options.dossier
            else [
                Demande(
                    options.tete,
                    options.fichier,
                    (options.mere or "").strip() or None,
                    _pays(options.pays_mere),
                )
            ]
        )
        depots = deposer(demandes, data)
    except DepotInvalide as erreur:
        print(erreur, file=sys.stderr)
        return 2
    for depot in depots:
        print("\n".join(resume(depot)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
