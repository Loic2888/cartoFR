"""Mesure de l'arbre à une mère (T045 C5) : rejoue la mesure du 2026-10-15 sur le registre réel.

Usage, depuis la racine du dépôt :
    CARTOFR_DATA=data CARTOFR_REFERENCES=basile .venv/bin/python worker/scripts/mesure_arbre.py

Entrées :
- `<CARTOFR_DATA>/registre.duckdb`, lu en lecture seule : l'arbre est calculé en mémoire,
  la table `arbre` n'est ni lue ni écrite ;
- `config/<groupe>.json` : seule la tête est lue ;
- `<CARTOFR_REFERENCES>/<groupe>_entites.csv` ou `cargo_<groupe>_entites.csv` : la carto de
  référence. Données client : jamais copiées dans git.
Sortie : durée du calcul, plus gros arbres, et pour LVMH, VINCI et CMAF les arbres qui portent
le plus de sociétés de la référence. Code 1 si un seuil de C5 n'est pas tenu.

Aucun nom de personne : seules des dénominations d'`unites_legales` sont affichées, table qui
exclut les entreprises individuelles (catégorie 1000). Un sommet absent de cette table est
affiché par un tiret, jamais par un nom lu ailleurs.
"""

import collections
import json
import os
import sys
import time
from pathlib import Path

import duckdb
from non_regression import _lire_reference, _siren

from cartofr.registre.arbre import NOM_REGISTRE, calculer

GROUPES = ("lvmh", "vinci", "cmaf")
PLUS_GROS_ARBRE_MAX = 1_334  # sommet compris
DUREE_MAX_S = 600
# Seuils de C5 : (groupe, dénomination du sommet, sociétés de la référence au moins).
SEUILS = (
    ("vinci", "VINCI IMMOBILIER PROMOTION", 281),
    ("vinci", "VINCI CONSTRUCTION", 188),
    ("lvmh", "UFIPAR", 21),
)


def main() -> int:
    registre = Path(os.environ.get("CARTOFR_DATA", "data")) / NOM_REGISTRE
    references = Path(os.environ.get("CARTOFR_REFERENCES", "basile"))
    if not registre.is_file():
        print(f"Registre introuvable : {registre}", file=sys.stderr)
        return 2

    con = duckdb.connect(str(registre), read_only=True)
    try:
        debut = time.monotonic()
        lignes = calculer(con)
        duree = time.monotonic() - debut
        sql_noms = "select siren, denomination from unites_legales where fin is null"
        noms = dict(con.execute(sql_noms).fetchall())
    finally:
        con.close()

    sommet_de = {x.siren: x.sommet for x in lignes}
    # Sociétés de chaque arbre, sommet compris. Le sommet d'une boucle a déjà sa ligne.
    taille = collections.Counter(sommet_de.values())
    for sommet in taille:
        taille[sommet] += sommet not in sommet_de
    plus_gros = sorted(taille.values(), reverse=True)[:4] or [0]
    print(
        f"calcul : {duree:.0f} s, {len(lignes)} sociétés avec une mère, "
        f"{len(taille)} arbres de 2 sociétés ou plus"
    )
    print(f"plus gros arbres : {plus_gros}, dont {sum(x.boucle for x in lignes)} sociétés dans une boucle")

    tenus = [duree <= DUREE_MAX_S, plus_gros[0] <= PLUS_GROS_ARBRE_MAX]
    par_groupe: dict[str, collections.Counter[str]] = {}
    for groupe in GROUPES:
        try:
            ref = {_siren(ligne) for ligne in _lire_reference(references, groupe)} - {""}
        except FileNotFoundError as erreur:
            print(f"{erreur} : pas de comparaison", file=sys.stderr)
            continue
        tete = json.loads((Path("config") / f"{groupe}.json").read_text(encoding="utf-8"))["tete"]
        morceaux = collections.Counter(sommet_de.get(s, s) for s in ref)
        par_groupe[groupe] = morceaux
        print(f"\n{groupe} : référence {len(ref)}, arbres touchés {len(morceaux)}")
        for sommet, n in morceaux.most_common(5):
            total = taille.get(sommet, 1)
            marque = "  <- tête" if sommet == sommet_de.get(tete, tete) else ""
            print(
                f"  {n:5} de la référence dans un arbre de {total:6} ({total - n} hors référence)"
                f"  sommet {noms.get(sommet) or '-'}{marque}"
            )

    print()
    for groupe, nom, minimum in SEUILS:
        morceaux = par_groupe.get(groupe, collections.Counter())
        trouve = max((n for s, n in morceaux.items() if noms.get(s) == nom), default=0)
        tenus.append(trouve >= minimum)
        verdict = "tenu" if trouve >= minimum else "NON TENU"
        print(f"C5 {groupe} {nom} : {trouve} (au moins {minimum}) {verdict}")
    print(
        f"C5 plus gros arbre : {plus_gros[0]} (au plus {PLUS_GROS_ARBRE_MAX}), "
        f"durée : {duree:.0f} s (au plus {DUREE_MAX_S})"
    )
    return 0 if all(tenus) else 1


if __name__ == "__main__":
    sys.exit(main())
