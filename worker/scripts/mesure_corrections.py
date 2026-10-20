"""Mesure d'une carto corrigée (T051, C3) : les réglages de `config/<groupe>.json` appliqués comme
corrections, par le calcul du travail `carto`, contre la référence du groupe.

Usage, depuis la racine du dépôt :
    CARTOFR_DATA=data CARTOFR_REFERENCES=basile .venv/bin/python \
        worker/scripts/mesure_corrections.py [lvmh ...]

Entrées :
- `config/<groupe>.json` : les réglages, familles exclues passées en empreintes avec une clé tirée au
  hasard pour ce passage (comme une version enregistrée dans l'app) ;
- `<CARTOFR_DATA>/registre.duckdb` et le document en vigueur de la tête (T046), comme le travail ;
- `<CARTOFR_REFERENCES>/<groupe>_entites.csv` : la carto de référence (données client, hors git).
Sortie : par groupe, retrouvées, en plus, manquées, et l'effet des corrections (sociétés ajoutées
et retirées par rapport à la carto sans correction, même tête, même document). Des volumes, aucun nom.
Seuil (PRD US8) : les retrouvées de la non-régression (LVMH 154/172, VINCI 813/1 007, CMAF 43/52).
Code de sortie : 0 si chaque groupe passe, 1 sinon, 2 si un fichier manque.
"""

import argparse
import json
import os
import secrets
import sys
import time
from pathlib import Path

from non_regression import SEUILS, _lire_reference, avec_empreintes, comparer

from cartofr.jobs.carto import calculer


def main(arguments: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description="Carto corrigée (T051) contre les groupes de référence.")
    parseur.add_argument("groupes", nargs="*", default=list(SEUILS), help="par défaut : lvmh vinci cmaf")
    options = parseur.parse_args(arguments)
    data = Path(os.environ.get("CARTOFR_DATA", "data"))
    registre = data / "registre.duckdb"
    references = Path(os.environ.get("CARTOFR_REFERENCES", "basile"))
    configs = Path("config")
    manquants = [str(p) for p in (registre, references, configs) if not p.exists()]
    if manquants:
        print("Fichiers manquants : " + ", ".join(manquants), file=sys.stderr)
        return 2

    print(f"{'groupe':<7} {'retrouvées':>17} {'en plus':>8} {'manquées':>9} {'ajoutées':>9} {'retirées':>9}"
          f" {'durée':>7}  verdict")  # fmt: skip
    code = 0
    for groupe in options.groupes:
        reference = _lire_reference(references, groupe)
        cle = secrets.token_hex(32)
        reglages = avec_empreintes(json.loads((configs / f"{groupe}.json").read_text(encoding="utf-8")), cle)
        debut = time.monotonic()
        calcul = calculer(reglages, registre, cle_empreinte=cle)
        duree = time.monotonic() - debut
        nous = {s.siren: (s.maison_mere_siren, s.ciblable) for s in calcul.carto.societes}
        r = comparer(groupe, reference, nous, duree, None)
        seuil = SEUILS.get(groupe)
        echec = seuil is not None and r.taux < seuil.taux
        code |= int(echec)
        ajoutees, retirees = calcul.effet.ajoutees, calcul.effet.retirees
        retrouvees = f"{r.retrouvees}/{r.reference} ({r.taux:.0%})".replace("%", " %")
        verdict = f"échec : < {seuil.retrouvees}/{seuil.reference}" if echec and seuil else "ok"
        print(f"{groupe:<7} {retrouvees:>17} {r.en_plus:>8} {r.manquees:>9} {ajoutees:>9} {retirees:>9}"
              f" {duree:>6.0f}s  {verdict}")  # fmt: skip
        for message in calcul.avertissements:
            print(f"        {message}")
    return code


if __name__ == "__main__":
    sys.exit(main())
