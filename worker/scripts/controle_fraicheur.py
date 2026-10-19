"""Contrôle hebdomadaire de fraîcheur du registre (T015, SC-003).

But : tirer au hasard 10 changements publiés par l'INPI (RNE) et l'INSEE (SIRENE) pendant les
7 derniers jours, et dire combien le registre porte déjà. Critère SC-003 : 10 sur 10.
La règle est dans `cartofr.registre.fraicheur` : rejouer le changement, dans une transaction
annulée, ne doit rien modifier. Le registre n'est jamais modifié.

Usage, depuis la racine du dépôt, quand aucune synchro ne tourne (le registre est ouvert en
écriture le temps du rejeu annulé) :
    CARTOFR_DATA=data .venv/bin/python worker/scripts/controle_fraicheur.py \
        [--rne 5] [--sirene 5] [--jour 2026-10-13] [--graine 42] [--registre data/registre.duckdb]

Entrées : le registre `<CARTOFR_DATA>/registre.duckdb` ; INPI_USERNAME, INPI_PASSWORD et
INSEE_API_KEY dans l'environnement ou le fichier CARTOFR_ENV_FILE (`.env` par défaut).
Coût : une page de 20 fiches du quota INPI par tirage RNE, une requête Sirene par tirage.
Sortie : une ligne par changement (source, jour, SIREN de la personne morale, retrouvé ou
non et les tables qui auraient bougé), puis « Retrouvés : N/10 ». Aucun nom.
Puis la date des données de la carto du pays (`--pays`, CARTOFR_PAYS, ou à côté du registre) et son
retard : 7 jours au plus (T052, SC-009).
Code de sortie : 0 si tous sont retrouvés et la carto du pays a 7 jours au plus, 1 sinon (une carto
du pays absente compte comme en retard), 2 si le registre manque.
"""

import argparse
import os
import random
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path

import duckdb

from cartofr.registre.fraicheur import (
    FENETRE_JOURS,
    FraicheurPays,
    Source,
    Tirage,
    controler,
    fraicheur_pays,
    tirer_rne,
    tirer_sirene,
)
from cartofr.registre.inpi_diff import Client as ClientInpi
from cartofr.registre.inpi_diff import charger_env
from cartofr.registre.synchro_sirene import Client as ClientSirene


def ligne_pays(f: FraicheurPays) -> str:
    """La ligne du bilan pour la carto du pays."""
    if f.date_donnees is None or f.retard_jours is None:
        return "Carto du pays : absente ou sans date des données (RETARD)."
    etat = "à jour" if f.a_jour else "RETARD"
    return (
        f"Carto du pays : données au {f.date_donnees:%d/%m/%Y}, {f.retard_jours} jour(s) de retard"
        f" ({FENETRE_JOURS} au plus) : {etat}."
    )


def main(arguments: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Contrôle de fraîcheur du registre (SC-003).")
    p.add_argument("--rne", type=int, default=5, help="changements RNE à tirer (5 par défaut)")
    p.add_argument("--sirene", type=int, default=5, help="changements SIRENE à tirer (5 par défaut)")
    p.add_argument("--jour", type=date.fromisoformat, default=date.today(), help="jour du contrôle")
    p.add_argument("--graine", type=int, default=None, help="graine du tirage, pour le rejouer")
    p.add_argument("--registre", type=Path, default=None)
    p.add_argument(
        "--pays", type=Path, default=None, help="la carto du pays (CARTOFR_PAYS, ou à côté du registre)"
    )
    a = p.parse_args(arguments)

    registre = a.registre or Path(os.environ.get("CARTOFR_DATA", "data")) / "registre.duckdb"
    pays = a.pays or Path(os.environ.get("CARTOFR_PAYS") or registre.parent / "pays.duckdb")
    if not registre.is_file():
        print(f"Registre introuvable : {registre}", file=sys.stderr)
        return 2
    charger_env()
    hasard = random.Random(a.graine)
    inpi, sirene = ClientInpi(), ClientSirene()
    tirer: dict[Source, Callable[[list[date]], Tirage | None]] = {
        "rne": lambda jours: tirer_rne(inpi, jours, hasard),
        "sirene": lambda jours: tirer_sirene(sirene, jours, hasard),
    }
    con = duckdb.connect(str(registre))
    try:
        resultat = controler(con, a.jour, tirer, {"rne": a.rne, "sirene": a.sirene})
    finally:
        con.close()

    for v in resultat.verdicts:
        t = v.tirage
        etat = (
            "retrouvé" if v.retrouve else "MANQUANT : " + ", ".join(f"{k} {n}" for k, n in v.ecarts.items())
        )
        print(f"{t.source:6} {t.jour.isoformat()} {t.siren} {etat}")
    if resultat.non_tires:
        print(f"{resultat.non_tires} tirage(s) impossible(s) : aucun changement lu (compté manquant).")
    print(f"Retrouvés : {resultat.retrouves}/{resultat.demandes}")
    carto_du_pays = fraicheur_pays(pays, a.jour)
    print(ligne_pays(carto_du_pays))
    return 0 if resultat.retrouves == resultat.demandes and carto_du_pays.a_jour else 1


if __name__ == "__main__":
    sys.exit(main())
