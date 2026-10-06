"""Construit `registre.duckdb` depuis les parquets du prototype (chargement initial).

Usage, depuis la racine du dépôt :
    CARTOFR_DATA=data .venv/bin/python -m cartofr.registre.construire [--remplacer]

Entrées, dans le dossier `CARTOFR_DATA` (par défaut `data`, relatif au dossier courant) :
- rne_links/liens.parquet, rne_links/societes.parquet, rne_links/personnes.parquet (build_links.py)
- sieges.parquet (build_sieges.py)
- unite_legale.parquet (stock SIRENE) : seules quatre colonnes sont lues, aucune
  colonne de personne (prénom, nom, sexe) n'entre dans le registre (règle produit 4).
Sortie : `<CARTOFR_DATA>/registre.duckdb`, et une ligne dans sa table `mises_a_jour`.

Écriture atomique : la base est construite dans un fichier temporaire du même
dossier, puis renommée. Un échec ne laisse ni demi-fichier, ni registre abîmé.
Un registre existant n'est remplacé qu'avec `--remplacer`.

Dates au chargement initial : tout commence à la date du stock RNE (`DATE_STOCK`).
Un lien marqué inactif au RNE (`actif = false`) était déjà fermé à cette date :
il reçoit `fin = DATE_STOCK` et `fin_inconnue = true`. Un `actif` vide vaut actif,
comme dans le moteur (`coalesce(actif, true)`).

La sortie standard ne porte que des volumes, jamais un nom.
"""

import argparse
import os
import sys
from datetime import date
from pathlib import Path

import duckdb

from cartofr.registre import journal
from cartofr.registre.schema import creer_tables

DATE_STOCK = date(2026, 3, 4)  # photo du stock RNE INPI utilisé pour build_links.py
NOM_REGISTRE = "registre.duckdb"
SOURCE = "construction_initiale"
MEMOIRE = "6GB"

SOURCES = {
    "liens": "rne_links/liens.parquet",
    "societes": "rne_links/societes.parquet",
    "personnes": "rne_links/personnes.parquet",
    "sieges": "sieges.parquet",
    "unite_legale": "unite_legale.parquet",
}

# Les chemins et la date passent en paramètres ($nom), jamais par concaténation.
CHARGEMENTS = {
    # Une ligne par SIREN : les rares doublons du RNE gardent la fiche la plus récente.
    "societes": """
        insert into societes
        select s.siren, s.denomination, s.diffusion_commerciale,
               not s.diffusion_commerciale,
               u.statutDiffusionUniteLegale <> 'O',
               s.salaries, u.etatAdministratifUniteLegale, u.dateCreationUniteLegale,
               $debut, null
        from (
            select * from read_parquet($societes)
            qualify row_number() over (partition by siren order by maj desc, denomination) = 1
        ) s
        left join (
            select siren, statutDiffusionUniteLegale, etatAdministratifUniteLegale, dateCreationUniteLegale
            from read_parquet($unite_legale)
        ) u using (siren)
    """,
    "liens": """
        insert into liens (parent, enfant, role, source, debut, fin, fin_inconnue)
        select parent, enfant, role, 'rne_stock', $debut,
               case when actif = false then $debut end,
               coalesce(actif = false, false)
        from read_parquet($liens)
    """,
    "dirigeants_personnes": """
        insert into dirigeants_personnes (siren, personne, role, debut, fin, fin_inconnue)
        select siren, personne, role, $debut,
               case when actif = false then $debut end,
               coalesce(actif = false, false)
        from read_parquet($personnes)
    """,
    "sieges": "insert into sieges by name select * from read_parquet($sieges)",
}

COMPTES = {
    "societes": "select count(*) from societes",
    "societes_non_diffusibles": "select count(*) from societes where non_diffusible",
    "societes_opposition": "select count(*) from societes where opposition_prospection",
    "liens": "select count(*) from liens",
    "liens_en_vigueur": "select count(*) from liens where fin is null",
    "liens_fermes": "select count(*) from liens where fin is not null",
    "dirigeants_personnes": "select count(*) from dirigeants_personnes",
    "sieges": "select count(*) from sieges",
}


class ErreurConstruction(Exception):
    """Échec prévu de la construction, avec un message sans donnée personnelle."""


class RegistreExistant(ErreurConstruction):
    """Refus avant de commencer : rien n'est construit, rien n'est journalisé."""


def dossier_donnees() -> Path:
    """Le dossier des données : `CARTOFR_DATA`, ou `data` par défaut."""
    return Path(os.environ.get("CARTOFR_DATA", "data"))


def construire(dossier: Path | None = None, remplacer: bool = False) -> dict[str, int]:
    """Construit `<dossier>/registre.duckdb` et rend les volumes chargés."""
    dossier = dossier if dossier is not None else dossier_donnees()
    cible = dossier / NOM_REGISTRE
    temporaire = dossier / f"{NOM_REGISTRE}.{os.getpid()}.en-construction"
    if cible.exists() and not remplacer:
        raise RegistreExistant(f"{cible} existe déjà : relancer avec --remplacer pour le reconstruire")
    if temporaire.exists():
        raise RegistreExistant(f"{temporaire} existe déjà : fichier d'une construction précédente")
    try:
        chemins = {nom: dossier / relatif for nom, relatif in SOURCES.items()}
        manquants = [str(p) for p in chemins.values() if not p.is_file()]
        if manquants:
            raise ErreurConstruction("fichiers sources manquants : " + ", ".join(manquants))
        comptes = _construire_dans(temporaire, chemins)
        _publier(temporaire, cible, remplacer)
        return comptes
    except BaseException as erreur:
        _retirer_temporaire(temporaire)
        _noter_echec(cible, erreur)
        raise


def _construire_dans(chemin: Path, sources: dict[str, Path]) -> dict[str, int]:
    """Crée la base à `chemin`, charge les sources et journalise le passage."""
    con = duckdb.connect(str(chemin))
    try:
        con.execute(f"set memory_limit = '{MEMOIRE}'")
        con.execute("set preserve_insertion_order = false")
        creer_tables(con)
        id_maj = journal.ouvrir(con, SOURCE)
        parametres = {"debut": DATE_STOCK, **{nom: str(p) for nom, p in sources.items()}}
        for sql in CHARGEMENTS.values():
            utilises = {k: v for k, v in parametres.items() if f"${k}" in sql}
            con.execute(sql, utilises)
        comptes = {nom: _compter(con, sql) for nom, sql in COMPTES.items()}
        journal.terminer(
            con, id_maj, ajoutes=comptes["societes"] + comptes["liens"], fermes=comptes["liens_fermes"]
        )
        con.execute("checkpoint")
        return comptes
    finally:
        con.close()


def _compter(con: duckdb.DuckDBPyConnection, sql: str) -> int:
    ligne = con.execute(sql).fetchone()
    assert ligne is not None
    return int(ligne[0])


def _publier(temporaire: Path, cible: Path, remplacer: bool) -> None:
    """Met le registre construit à sa place, d'un seul coup."""
    if remplacer:
        os.replace(temporaire, cible)
        return
    # Sans --remplacer : un lien physique échoue si la cible est apparue entre-temps.
    try:
        os.link(temporaire, cible)
    except FileExistsError as erreur:
        raise ErreurConstruction(
            f"{cible} est apparu pendant la construction : rien n'est remplacé"
        ) from erreur
    temporaire.unlink()


def _retirer_temporaire(temporaire: Path) -> None:
    """Retire le fichier temporaire de cette construction (et son journal DuckDB)."""
    for chemin in (temporaire, temporaire.with_name(temporaire.name + ".wal")):
        chemin.unlink(missing_ok=True)


def _message(erreur: BaseException) -> str:
    """Message à journaliser : le nôtre en entier, sinon le type seul.

    Un message de DuckDB peut citer une valeur lue ; on ne le recopie pas.
    """
    if isinstance(erreur, ErreurConstruction):
        return str(erreur)
    return f"{type(erreur).__name__} pendant la construction"


def _noter_echec(cible: Path, erreur: BaseException) -> None:
    """Note l'échec dans le journal du registre en place, s'il y en a un."""
    if not cible.exists():
        return
    try:
        con = duckdb.connect(str(cible))
        try:
            journal.echouer(con, journal.ouvrir(con, SOURCE), _message(erreur))
        finally:
            con.close()
    except duckdb.Error:
        print("Échec non journalisé : registre en place illisible ou verrouillé.", file=sys.stderr)


def main(arguments: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description="Construit registre.duckdb depuis les parquets.")
    parseur.add_argument("--remplacer", action="store_true", help="reconstruit un registre existant")
    options = parseur.parse_args(arguments)
    try:
        comptes = construire(remplacer=options.remplacer)
    except ErreurConstruction as erreur:
        print(f"Échec : {erreur}", file=sys.stderr)
        return 1
    for nom, valeur in comptes.items():
        print(f"{nom} : {valeur}")
    print(f"Registre écrit : {dossier_donnees() / NOM_REGISTRE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
