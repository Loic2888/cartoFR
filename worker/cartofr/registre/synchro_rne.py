"""Synchro RNE : applique au registre les fiches modifiées d'une période (API INPI diff).

But : tenir `registre.duckdb` à jour avec le RNE. Pour chaque société dont la
fiche a changé, le registre reprend son état actuel : société créée ou mise à
jour, nouveaux liens ouverts, liens disparus fermés, mêmes règles pour les
dirigeants personnes.

Usage, depuis la racine du dépôt :
    CARTOFR_DATA=data .venv/bin/python -m cartofr.registre.synchro_rne --jour 2026-10-05 \
        [--registre data/registre.duckdb]

Entrées :
    - le registre DuckDB (`<CARTOFR_DATA>/registre.duckdb` par défaut) ;
    - l'API INPI `/api/companies/diff`, via `cartofr.registre.inpi_diff`
      (identifiants INPI dans l'environnement ou le fichier CARTOFR_ENV_FILE).
Sorties :
    - le registre mis à jour, une transaction par page de 100 fiches ;
    - une ligne `rne_diff` dans `mises_a_jour` : `succes` ou `echec` ;
    - le curseur de lecture dans `<CARTOFR_DATA>/inpi_diff/curseur.json`.
La sortie standard ne porte que des volumes, jamais un nom.

Règles :
    - rien n'est effacé (principe 4) : un lien, un dirigeant ou une société qui
      disparaît reçoit une date de fin `fin = jour` ;
    - une fiche donne l'état complet de la société : un lien (parent, enfant,
      rôle) en vigueur dans le registre et absent de la fiche est fermé, un
      couple de la fiche absent du registre est ouvert avec `debut = jour` ;
    - le registre contient des doublons (même parent, enfant et rôle) : fermer
      ferme tous les doublons ouverts, ouvrir n'ajoute rien si le couple est
      déjà ouvert. Appliquer deux fois la même fiche ne change rien ;
    - société radiée (`dateRadiation`) : `fin = jour`, et ses liens et
      dirigeants (elle comme enfant) sont fermés. Les liens où elle est parent
      restent : ils appartiennent à la fiche de l'autre société ;
    - société fermée qui revient avec une fiche non radiée : elle est rouverte
      (`fin` vidée), et comptée dans `societes_rouvertes` ;
    - dénomination et opposition à la prospection : une valeur absente de la
      fiche ne remplace pas la valeur connue (une opposition ne se perd pas
      par un champ vide) ; l'effectif suit la fiche ;
    - `jour` doit suivre les dates déjà posées : fermer un lien ouvert après
      `jour` viole `fin >= debut`, et la page entière est annulée ;
    - une erreur dans une page : rollback, le registre reste tel qu'avant la
      page, puis la ligne du journal passe en `echec` avec le type d'erreur
      seulement (un message de DuckDB peut citer une valeur lue).

Dates : la période `depuis`..`jusqua` est incluse aux deux bouts ; le client
traduit en `from = depuis - 1` (exclu par l'API), `to = jusqua`. Tout ce qui
change pendant la période est daté `jusqua`.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, fields
from datetime import date
from pathlib import Path
from typing import Any, Protocol

import duckdb

from cartofr.registre import journal
from cartofr.registre.formalite import Fiche, FormaliteInvalide, lire_fiche
from cartofr.registre.inpi_diff import Client, Curseur, Page, QuotaAtteint, charger_env, chemin_curseur

SOURCE = "rne_diff"
NOM_REGISTRE = "registre.duckdb"
MESSAGE_QUOTA = "quota INPI atteint, reprise au curseur"


@dataclass
class Bilan:
    """Volumes d'un passage. Aucun nom, aucun identifiant."""

    fiches: int = 0  # fiches de personne morale appliquées
    ignorees: int = 0  # fiches sans personne morale (entreprise individuelle, exploitation)
    invalides: int = 0  # fiches mal formées, laissées de côté
    societes_creees: int = 0
    societes_maj: int = 0  # au moins un champ a changé
    societes_fermees: int = 0  # radiées
    societes_rouvertes: int = 0
    liens_ouverts: int = 0
    liens_fermes: int = 0
    personnes_ouvertes: int = 0
    personnes_fermees: int = 0

    @property
    def ajoutes(self) -> int:
        """Lignes ajoutées au sens du journal : sociétés et liens."""
        return self.societes_creees + self.liens_ouverts

    @property
    def fermes(self) -> int:
        """Lignes fermées au sens du journal : sociétés et liens."""
        return self.societes_fermees + self.liens_fermes

    def ajouter(self, autre: Bilan) -> None:
        for f in fields(self):
            setattr(self, f.name, getattr(self, f.name) + getattr(autre, f.name))


@dataclass
class Resultat:
    """Issue de `synchroniser` : statut du journal, volumes, pages appliquées."""

    id_maj: int
    statut: str  # 'succes' ou 'echec'
    bilan: Bilan
    pages: int
    requetes: int
    erreur: str | None = None


class LecteurDiff(Protocol):
    """Ce que `synchroniser` attend du client INPI (remplaçable dans les tests)."""

    requetes: int

    def lire(
        self,
        depuis: date,
        jusqua: date,
        curseur: Curseur | None = None,
        page_size: int = ...,
        chemin: Path | None = None,
    ) -> Iterator[Page]: ...


def lire_fiches(companies: Iterable[Any]) -> tuple[list[Fiche], Bilan]:
    """Lit les fiches d'une page. Rend les fiches de personne morale et les volumes écartés."""
    bilan = Bilan()
    fiches: list[Fiche] = []
    for company in companies:
        try:
            fiche = lire_fiche(company)
        except FormaliteInvalide:
            bilan.invalides += 1
            continue
        if fiche is None:
            bilan.ignorees += 1
        else:
            fiches.append(fiche)
    return fiches, bilan


# Les tables de travail d'un lot. Elles vivent dans la transaction et la connexion.
_TABLES_LOT = """
    create or replace temp table lot_fiches (
        siren varchar, denomination varchar, diffusion_commerciale boolean, salaries bigint, radiee boolean
    );
    create or replace temp table lot_liens (parent varchar, enfant varchar, role varchar);
    create or replace temp table lot_personnes (siren varchar, personne varchar, role varchar);
"""

# Chaque requête rend le nombre de lignes touchées. `$jour` est un paramètre.
_ETAPES: list[tuple[str, str]] = [
    (
        "societes_maj",
        """
        update societes s set
            denomination = coalesce(f.denomination, s.denomination),
            diffusion_commerciale = coalesce(f.diffusion_commerciale, s.diffusion_commerciale),
            opposition_prospection = not coalesce(f.diffusion_commerciale, s.diffusion_commerciale),
            salaries = f.salaries
        from lot_fiches f
        where s.siren = f.siren
          and (s.denomination is distinct from coalesce(f.denomination, s.denomination)
               or s.diffusion_commerciale is distinct from
                  coalesce(f.diffusion_commerciale, s.diffusion_commerciale)
               or s.salaries is distinct from f.salaries)
        """,
    ),
    (
        "societes_creees",
        """
        insert into societes (siren, denomination, diffusion_commerciale, opposition_prospection,
                              salaries, debut, fin)
        select f.siren, f.denomination, f.diffusion_commerciale, not f.diffusion_commerciale,
               f.salaries, $jour, case when f.radiee then $jour end
        from lot_fiches f
        where not exists (select 1 from societes s where s.siren = f.siren)
        """,
    ),
    (
        "societes_fermees",
        """
        update societes s set fin = $jour
        from lot_fiches f
        where s.siren = f.siren and f.radiee and s.fin is null
        """,
    ),
    (
        "societes_rouvertes",
        """
        update societes s set fin = null
        from lot_fiches f
        where s.siren = f.siren and not f.radiee and s.fin is not null
        """,
    ),
    (
        "liens_fermes",
        """
        update liens l set fin = $jour
        where l.fin is null
          and l.enfant in (select siren from lot_fiches)
          and not exists (
              select 1 from lot_liens n
              where n.parent = l.parent and n.enfant = l.enfant and n.role is not distinct from l.role)
        """,
    ),
    (
        "liens_ouverts",
        """
        insert into liens (parent, enfant, role, source, debut)
        select n.parent, n.enfant, n.role, 'rne_diff', $jour
        from lot_liens n
        where not exists (
            select 1 from liens l
            where l.fin is null and l.enfant = n.enfant and l.parent = n.parent
              and l.role is not distinct from n.role)
        """,
    ),
    (
        "personnes_fermees",
        """
        update dirigeants_personnes d set fin = $jour
        where d.fin is null
          and d.siren in (select siren from lot_fiches)
          and not exists (
              select 1 from lot_personnes n
              where n.siren = d.siren and n.personne = d.personne and n.role is not distinct from d.role)
        """,
    ),
    (
        "personnes_ouvertes",
        """
        insert into dirigeants_personnes (siren, personne, role, debut)
        select n.siren, n.personne, n.role, $jour
        from lot_personnes n
        where not exists (
            select 1 from dirigeants_personnes d
            where d.fin is null and d.siren = n.siren and d.personne = n.personne
              and d.role is not distinct from n.role)
        """,
    ),
]


def _charger_lot(con: duckdb.DuckDBPyConnection, fiches: list[Fiche]) -> None:
    """Remplit les tables de travail. Une fiche répétée dans le lot : la dernière l'emporte."""
    par_siren = {f.siren: f for f in fiches}
    retenues = list(par_siren.values())
    con.execute(_TABLES_LOT)
    con.execute(
        "insert into lot_fiches select unnest($siren::varchar[]), unnest($denomination::varchar[]),"
        " unnest($diffusion::boolean[]), unnest($salaries::bigint[]), unnest($radiee::boolean[])",
        {
            "siren": [f.siren for f in retenues],
            "denomination": [f.denomination for f in retenues],
            "diffusion": [f.diffusion_commerciale for f in retenues],
            "salaries": [f.salaries for f in retenues],
            "radiee": [f.radiee for f in retenues],
        },
    )
    # Une société radiée n'a plus de dirigeant : ses couples ne sont pas repris.
    liens = [(p, f.siren, r) for f in retenues if not f.radiee for p, r in f.liens]
    personnes = [(f.siren, k, r) for f in retenues if not f.radiee for k, r in f.personnes]
    con.execute(
        "insert into lot_liens select unnest($a::varchar[]), unnest($b::varchar[]), unnest($c::varchar[])",
        {"a": [x[0] for x in liens], "b": [x[1] for x in liens], "c": [x[2] for x in liens]},
    )
    con.execute(
        "insert into lot_personnes select unnest($a::varchar[]), unnest($b::varchar[]),"
        " unnest($c::varchar[])",
        {"a": [x[0] for x in personnes], "b": [x[1] for x in personnes], "c": [x[2] for x in personnes]},
    )


def _compte(con: duckdb.DuckDBPyConnection) -> int:
    ligne = con.fetchone()
    return int(ligne[0]) if ligne else 0


def appliquer(con: duckdb.DuckDBPyConnection, fiches: list[Fiche], jour: date) -> Bilan:
    """Applique un lot de fiches au registre, en une seule transaction.

    Sur une erreur, tout le lot est annulé (rollback) et l'erreur remonte :
    le registre reste exactement tel qu'avant l'appel.
    """
    bilan = Bilan(fiches=len(fiches))
    if not fiches:
        return bilan
    con.begin()
    try:
        _charger_lot(con, fiches)
        for nom, sql in _ETAPES:
            con.execute(sql, {"jour": jour} if "$jour" in sql else None)
            setattr(bilan, nom, _compte(con))
        con.execute("drop table lot_fiches; drop table lot_liens; drop table lot_personnes")
        con.commit()
    except BaseException:
        con.rollback()
        raise
    return bilan


def _noter_volumes(con: duckdb.DuckDBPyConnection, id_maj: int, bilan: Bilan) -> None:
    """Garde dans le journal les volumes des pages déjà validées, même en échec."""
    con.execute(
        "update mises_a_jour set ajoutes = ?, fermes = ? where id = ?", [bilan.ajoutes, bilan.fermes, id_maj]
    )


def synchroniser(
    con: duckdb.DuckDBPyConnection,
    depuis: date,
    jusqua: date,
    client: LecteurDiff | None = None,
    chemin: Path | None = None,
) -> Resultat:
    """Lit les fiches modifiées de `depuis` à `jusqua` (inclus) et les applique, page par page.

    Reprend au curseur sauvegardé s'il porte sur la même période et n'est pas fini ;
    sinon repart du début (réappliquer une période ne change rien au registre).
    Le quota INPI atteint arrête proprement le passage : statut `echec`, message
    MESSAGE_QUOTA, curseur sauvegardé par le client. Toute autre erreur est
    journalisée (type seul) puis relancée.
    """
    if jusqua < depuis:
        raise ValueError("la période est vide : jusqua précède depuis")
    client = client if client is not None else Client()
    chemin = chemin or chemin_curseur()
    curseur = Curseur.charger(chemin)
    if curseur is None or curseur.fini or (curseur.depuis, curseur.jusqua) != (depuis, jusqua):
        curseur = None

    id_maj = journal.ouvrir(con, SOURCE)
    total = Bilan()
    pages = 0
    try:
        for page in client.lire(depuis, jusqua, curseur=curseur, chemin=chemin):
            fiches, ecartees = lire_fiches(page.formalites)
            bilan = appliquer(con, fiches, jusqua)
            bilan.ajouter(ecartees)
            total.ajouter(bilan)
            pages += 1
    except QuotaAtteint:
        journal.echouer(con, id_maj, MESSAGE_QUOTA)
        _noter_volumes(con, id_maj, total)
        return Resultat(id_maj, "echec", total, pages, client.requetes, MESSAGE_QUOTA)
    except BaseException as erreur:
        # Après le rollback d'`appliquer` : le journal note le type, jamais le message.
        message = f"{type(erreur).__name__} pendant la synchro RNE, page {pages + 1}"
        journal.echouer(con, id_maj, message)
        _noter_volumes(con, id_maj, total)
        raise
    journal.terminer(con, id_maj, ajoutes=total.ajoutes, fermes=total.fermes)
    return Resultat(id_maj, "succes", total, pages, client.requetes)


def main(arguments: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description="Applique au registre les changements RNE d'une journée.")
    parseur.add_argument("--jour", required=True, type=date.fromisoformat, help="journée à lire, AAAA-MM-JJ")
    parseur.add_argument("--registre", type=Path, help="chemin du registre DuckDB")
    options = parseur.parse_args(arguments)
    registre = options.registre or Path(os.environ.get("CARTOFR_DATA", "data")) / NOM_REGISTRE
    if not registre.is_file():
        print(f"Échec : registre introuvable : {registre}", file=sys.stderr)
        return 1
    charger_env()
    depart = time.monotonic()
    con = duckdb.connect(str(registre))
    try:
        try:
            resultat = synchroniser(con, options.jour, options.jour)
        except Exception as erreur:
            print(f"Échec : {type(erreur).__name__}, voir la table mises_a_jour.", file=sys.stderr)
            return 1
        con.execute("checkpoint")
    finally:
        con.close()
    print(f"statut : {resultat.statut}")
    if resultat.erreur:
        print(f"erreur : {resultat.erreur}")
    print(f"journal (mises_a_jour.id) : {resultat.id_maj}")
    print(f"pages : {resultat.pages}")
    print(f"requetes INPI : {resultat.requetes}")
    for f in fields(resultat.bilan):
        print(f"{f.name} : {getattr(resultat.bilan, f.name)}")
    print(f"duree : {time.monotonic() - depart:.0f} s")
    return 0 if resultat.statut == "succes" else 2


if __name__ == "__main__":
    sys.exit(main())
