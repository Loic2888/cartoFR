"""Non-régression du moteur (principe 5) : LVMH, VINCI et CMAF contre leurs cartos de référence.

Usage, depuis la racine du dépôt :
    CARTOFR_DATA=data CARTOFR_REFERENCES=basile .venv/bin/python worker/scripts/non_regression.py [lvmh ...]

Entrées :
- `config/<groupe>.json` : les réglages du groupe ;
- `<CARTOFR_DATA>/registre.duckdb` (par défaut `data`), lu en lecture seule ;
- `<CARTOFR_REFERENCES>/<groupe>_entites.csv` ou `cargo_<groupe>_entites.csv` (par défaut `basile`) :
  la carto de référence, colonne `SIREN` ou `siren`. Données client : jamais copiées dans git.
Sortie : un tableau par groupe, mêmes mesures que `compare.py` (retrouvées, en plus, manquées,
même maison mère directe, même réponse ciblable), la durée et la mémoire au plus.
Aucun nom n'est affiché : seulement des volumes.

Option `--empreintes` (T021) : la carto mesurée exclut les familles par empreinte, comme une
carto lancée depuis l'app (`familles_exclues` remplacé par `familles_exclues_empreintes`, avec
une clé tirée au hasard pour ce passage, jamais affichée). Une seconde carto, avec les noms en
clair, est calculée dans le même processus : les sociétés, liens, participations et sociétés
étrangères des deux cartos doivent être identiques, champ par champ (colonne « = noms »).

Code de sortie : 0 si chaque groupe atteint ses seuils, 1 sinon, 2 si un fichier manque.
Les seuils sont les scores du prototype du 2026-10-06 : « 90 % » pour LVMH est l'arrondi de
154/172, et c'est 154/172 qui est exigé, pas 90 % exact.
"""

import argparse
import csv
import json
import multiprocessing
import os
import resource
import secrets
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cartofr.empreinte import empreinte
from cartofr.moteur import Carto, cartographier


@dataclass(frozen=True)
class Seuil:
    retrouvees: int  # sociétés de la référence retrouvées, au moins
    reference: int  # sur combien, au 2026-10-06
    en_plus_max: int | None  # sociétés en plus, au plus ; None : pas de seuil

    @property
    def taux(self) -> float:
        return self.retrouvees / self.reference


SEUILS = {
    "lvmh": Seuil(154, 172, 16),
    "vinci": Seuil(813, 1007, 193),
    "cmaf": Seuil(43, 52, None),  # la référence CMAF agrège des sous-ensembles : « en plus » non mesuré
}


@dataclass(frozen=True)
class Resultat:
    groupe: str
    reference: int
    nous: int
    retrouvees: int
    en_plus: int
    manquees: int
    meme_maison_mere: float | None
    meme_ciblable: float | None
    duree_s: float
    memoire_go: float
    # --empreintes : éléments qui diffèrent de la carto aux noms, par ensemble ; vide si identiques.
    ecarts_noms: dict[str, int] | None = None

    @property
    def taux(self) -> float:
        return self.retrouvees / self.reference if self.reference else 0.0


def _lire_reference(dossier: Path, groupe: str) -> list[dict[str, str]]:
    for nom in (f"{groupe}_entites.csv", f"cargo_{groupe}_entites.csv"):
        chemin = dossier / nom
        if chemin.is_file():
            with chemin.open(newline="", encoding="utf-8") as f:
                return list(csv.DictReader(f))
    raise FileNotFoundError(f"référence introuvable pour {groupe} dans {dossier}")


def _siren(ligne: dict[str, str]) -> str:
    return (ligne.get("SIREN") or ligne.get("siren") or "").strip()


def avec_empreintes(reglages: dict[str, Any], cle: str) -> dict[str, Any]:
    """Les réglages d'un fichier de config, familles exclues par empreinte comme dans l'app."""
    sortie = dict(reglages)
    noms = sortie.pop("familles_exclues", [])
    sortie["familles_exclues_empreintes"] = sorted({empreinte(n, cle) for n in noms})
    return sortie


def ecarts(a: Carto, b: Carto) -> dict[str, int]:
    """Nombre d'éléments présents dans une seule des deux cartos, par ensemble ; vide si identiques."""
    sortie = {}
    for nom in ("societes", "liens", "participations", "etrangeres"):
        difference = len(set(getattr(a, nom)) ^ set(getattr(b, nom)))
        if difference:
            sortie[nom] = difference
    return sortie


def mesurer(
    groupe: str, registre: Path, references: Path, configs: Path, empreintes: bool = False
) -> Resultat:
    """Lance la carto d'un groupe et la compare à sa référence, comme `compare.py`."""
    reference = _lire_reference(references, groupe)
    reglages = json.loads((configs / f"{groupe}.json").read_text(encoding="utf-8"))
    ecarts_noms = None
    if empreintes:
        cle = secrets.token_hex(32)
        aux_noms = cartographier(reglages, registre)
        debut = time.monotonic()
        carto = cartographier(avec_empreintes(reglages, cle), registre, cle_empreinte=cle)
        duree = time.monotonic() - debut
        ecarts_noms = ecarts(carto, aux_noms)
    else:
        debut = time.monotonic()
        carto = cartographier(reglages, registre)
        duree = time.monotonic() - debut
    memoire = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024  # ko -> Go (Linux)

    ref = {_siren(r): r for r in reference if _siren(r)}
    nous = {s.siren: s for s in carto.societes}
    communs = nous.keys() & ref.keys()
    meme_mere = meme_ciblable = None
    if communs and "SIREN de la maison mère" in next(iter(ref.values())):
        meme_mere = sum(
            (nous[s].maison_mere_siren or "") == (ref[s].get("SIREN de la maison mère") or "")
            for s in communs
        ) / len(communs)
    if communs and "Targetable" in next(iter(ref.values())):
        meme_ciblable = sum(
            ("Oui" if nous[s].ciblable else "Non") == ref[s].get("Targetable") for s in communs
        ) / len(communs)
    return Resultat(
        groupe=groupe,
        reference=len(ref),
        nous=len(nous),
        retrouvees=len(communs),
        en_plus=len(nous.keys() - ref.keys()),
        manquees=len(ref.keys() - nous.keys()),
        meme_maison_mere=meme_mere,
        meme_ciblable=meme_ciblable,
        duree_s=duree,
        memoire_go=memoire,
        ecarts_noms=ecarts_noms,
    )


def verdict(r: Resultat) -> list[str]:
    """Les seuils manqués par `r`, vide si le groupe passe."""
    seuil = SEUILS.get(r.groupe)
    if seuil is None:
        return []
    echecs = []
    if r.taux < seuil.taux:
        echecs.append(f"retrouvées {r.retrouvees}/{r.reference} < {seuil.retrouvees}/{seuil.reference}")
    if seuil.en_plus_max is not None and r.en_plus > seuil.en_plus_max:
        echecs.append(f"en plus {r.en_plus} > {seuil.en_plus_max}")
    if r.ecarts_noms:
        detail = ", ".join(f"{n} {k}" for k, n in r.ecarts_noms.items())
        echecs.append(f"empreintes ≠ noms ({detail})")
    return echecs


def _pourcent(x: float | None) -> str:
    return "—" if x is None else f"{x:.0%}".replace("%", " %")


def main(arguments: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description="Non-régression du moteur sur les groupes de référence.")
    parseur.add_argument("groupes", nargs="*", default=list(SEUILS), help="par défaut : lvmh vinci cmaf")
    parseur.add_argument(
        "--empreintes",
        action="store_true",
        help="familles exclues par empreinte, comme dans l'app, et comparaison à la carto aux noms",
    )
    options = parseur.parse_args(arguments)
    registre = Path(os.environ.get("CARTOFR_DATA", "data")) / "registre.duckdb"
    references = Path(os.environ.get("CARTOFR_REFERENCES", "basile"))
    configs = Path("config")
    manquants = [str(p) for p in (registre, references, configs) if not p.exists()]
    if manquants:
        print("Fichiers manquants : " + ", ".join(manquants), file=sys.stderr)
        return 2

    print(
        f"{'groupe':<7} {'retrouvées':>17} {'en plus':>8} {'manquées':>9} {'même mère':>10}"
        f" {'même ciblable':>14} {'durée':>7} {'mémoire':>8}"
        + (f" {'= noms':>7}" if options.empreintes else "")
        + "  verdict"
    )
    code = 0
    # Un processus neuf par groupe : la mémoire au plus est celle de ce groupe seul.
    contexte = multiprocessing.get_context("spawn")
    for groupe in options.groupes:
        with ProcessPoolExecutor(max_workers=1, mp_context=contexte) as pool:
            try:
                r = pool.submit(mesurer, groupe, registre, references, configs, options.empreintes).result()
            except FileNotFoundError as erreur:
                print(f"{groupe:<7} {erreur}", file=sys.stderr)
                code = max(code, 2)
                continue
        echecs = verdict(r)
        code = max(code, 1 if echecs else 0)
        retrouvees = f"{_pourcent(r.taux)} ({r.retrouvees}/{r.reference})"
        print(
            f"{r.groupe:<7} {retrouvees:>17} {r.en_plus:>8} {r.manquees:>9}"
            f" {_pourcent(r.meme_maison_mere):>10} {_pourcent(r.meme_ciblable):>14}"
            f" {r.duree_s:>6.0f}s {r.memoire_go:>6.2f}Go"
            + (f" {'oui' if not r.ecarts_noms else 'NON':>7}" if r.ecarts_noms is not None else "")
            + f"  {'OK' if not echecs else 'RÉGRESSION : ' + ' ; '.join(echecs)}",
            flush=True,
        )
    return code


if __name__ == "__main__":
    sys.exit(main())
