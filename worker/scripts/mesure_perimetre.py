"""Mesure du périmètre publié (T042 C3) : un document de groupe croisé avec le registre.

Usage, depuis la racine du dépôt :
    CARTOFR_DATA=data CARTOFR_REFERENCES=basile .venv/bin/python worker/scripts/mesure_perimetre.py \
        out/perimetre/vinci.pdf vinci [--refus out/perimetre/vinci_refus.csv]

Entrées :
- le document de périmètre (PDF, HTML ou texte), gardé hors git (`out/`) ;
- `config/<groupe>.json` : seule la tête est lue ;
- `<CARTOFR_DATA>/registre.duckdb`, lu en lecture seule ;
- `<CARTOFR_REFERENCES>/<groupe>_entites.csv` ou `cargo_<groupe>_entites.csv` : la carto de
  référence. Données client : jamais copiées dans git.
Sortie : les comptes par raison (retenues uniques, par la commune, par le registre ; homonymes,
introuvables), puis la liste seule et la liste avec les blocs du registre en dessous, comparées à
la référence. `--refus` écrit les lignes non retenues avec leur raison (C4).
Aucun nom de personne : seules des dénominations de sociétés sont lues.
"""

import argparse
import collections
import csv
import json
import os
import sys
import time
from pathlib import Path

import duckdb
from non_regression import _lire_reference, _siren

from cartofr.perimetre import correspondre, descendants, extraire, texte_document
from cartofr.perimetre.correspondance import COMMUNE, CONFLIT, HOMONYMES, INTROUVABLE, REGISTRE, UNIQUE


def main(arguments: list[str]) -> int:
    parseur = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parseur.add_argument("document", type=Path)
    parseur.add_argument("groupe")
    parseur.add_argument("--refus", type=Path, help="CSV des lignes non retenues, avec leur raison")
    options = parseur.parse_args(arguments)

    registre = Path(os.environ.get("CARTOFR_DATA", "data")) / "registre.duckdb"
    references = Path(os.environ.get("CARTOFR_REFERENCES", "basile"))
    config = Path("config") / f"{options.groupe}.json"
    manquants = [str(p) for p in (options.document, registre, config) if not p.exists()]
    if manquants:
        print("Fichiers manquants : " + ", ".join(manquants), file=sys.stderr)
        return 2

    debut = time.monotonic()
    tete = json.loads(config.read_text(encoding="utf-8"))["tete"]
    lignes = extraire(texte_document(options.document))
    con = duckdb.connect(str(registre), read_only=True)
    try:
        resultats = correspondre(con, tete, lignes)
        retenues = {c.siren for c in resultats if c.siren}
        # Blocs sous les seules sociétés contrôlées : une mise en équivalence n'en apporte pas.
        avec_blocs = descendants(
            con, {c.siren for c in resultats if c.siren and c.ligne.methode == "IG"} | {tete}
        )
    finally:
        con.close()

    raisons = collections.Counter(c.raison for c in resultats)
    methodes = dict(collections.Counter(li.methode for li in lignes))
    print(f"lignes en France : {len(lignes)} | méthodes : {methodes}")
    print(
        f"retenues : {raisons[UNIQUE]} uniques, {raisons[COMMUNE]} par la commune, "
        f"{raisons[REGISTRE]} par le registre | non retenues : {raisons[HOMONYMES]} homonymes, "
        f"{raisons[INTROUVABLE]} introuvables, {raisons[CONFLIT]} en conflit"
    )
    try:
        ref = {_siren(ligne) for ligne in _lire_reference(references, options.groupe)} - {""}
    except FileNotFoundError as erreur:
        print(f"{erreur} : pas de comparaison", file=sys.stderr)
    else:
        for nom, sirens in (("liste seule", retenues | {tete}), ("liste + blocs du registre", avec_blocs)):
            r = len(sirens & ref)
            print(
                f"{nom:<26} trouvées {len(sirens):>5}  retrouvées {r:>5}/{len(ref)} ({r / len(ref):.0%})"
                f"  en plus {len(sirens - ref):>5}"
            )
    print(f"durée : {time.monotonic() - debut:.0f} s")

    if options.refus:
        options.refus.parent.mkdir(parents=True, exist_ok=True)
        with options.refus.open("w", newline="", encoding="utf-8") as f:
            ecrire = csv.writer(f)
            # Seule la ligne de la société est écrite, jamais les lignes d'avant du document : un
            # pied de page ou une signature pourrait porter un nom de personne (garde-fou 6).
            ecrire.writerow(["raison", "porteurs", "ligne"])
            for c in resultats:
                if not c.retenue:
                    ecrire.writerow([c.raison, c.porteurs, c.ligne.texte])
        print(f"refus écrits : {options.refus}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
