"""Mesure SC-007 (T026 C3) : corrections d'une proposition IA, revue simulée contre `config/`.

But : rejouer le protocole de `rapport.md` (2026-10-08) sans clics. Pour chaque groupe, une
vraie proposition (API réelle, groupe neuf : aucune version validée), puis la revue qu'aurait
faite un consultant en prenant `config/<groupe>.json` comme référence, comptée comme l'écran
(web/lib/reglages/proposition.ts, `appliquerRevue`) :
- élément de l'IA présent dans `config/` (valeur normalisée), dans une liste où `config/` le
  range : gardé, 0 ;
- présent seulement dans d'autres listes : corrigé (liste changée), 1 ;
- en double (même valeur déjà rencontrée) : rejeté, 1 ;
- absent de `config/` : vrai ou faux, la machine ne sait pas. Rejeté s'il est faux (1), gardé
  s'il est vrai (0). D'où une fourchette : `min` les garde tous, `max` les rejette tous ;
  `estimé` ne rejette que ceux qu'aucune société du registre ne porte (signal T040) ;
- valeur de `config/` que l'IA n'a pas proposée : ajoutée, 1.
Seules les cinq listes proposées comptent (LISTES_PROPOSEES) : `marques_sures_homonymes`,
`exclus` (SIREN) et le reste ne se proposent pas.

Usage, depuis la racine du dépôt (clé et modèle lus dans l'environnement, jamais affichés) :
    set -a; . ./.env; set +a
    CARTOFR_DATA=data .venv/bin/python worker/scripts/mesure_sc007.py [lvmh vinci cmaf] [--refaire]

Une proposition déjà enregistrée dans `out/sc007/` est relue au lieu d'être redemandée :
`--refaire` la redemande.

Entrées : `config/<groupe>.json`, `<CARTOFR_DATA>/registre.duckdb` (lecture seule),
OPENROUTER_API_KEY, CARTOFR_MODELE_IA. Coût : quelques dizaines de centimes par groupe.
Sorties : un tableau de volumes (aucune valeur proposée) ; la proposition rangée de chaque
groupe dans `out/sc007/<groupe>.json`, hors git, pour la relire.
Code de sortie : 0 si la moyenne `min` est sous 5 corrections, 1 sinon.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import duckdb

from cartofr.ia.proposition import (
    LISTES_PROPOSEES,
    Consommation,
    ElementBrut,
    ElementRange,
    Entree,
    PropositionImpossible,
    appeler,
    client_ia,
    compter_porteurs,
    construire_requete,
    lire_entree,
    lire_reponse,
    modele,
    nettoyer,
    ranger,
    sans_societe,
    societes_du_groupe,
)
from cartofr.moteur.marques import norm

GROUPES = ("lvmh", "vinci", "cmaf")
SEUIL = 5  # SC-007 : moins de 5 corrections en moyenne
ESSAIS = 3  # par groupe, sur une erreur de l'API
PAUSE_S = 90.0  # avant un nouvel essai, multipliée par le numéro de l'essai


@dataclass
class Revue:
    elements: int = 0
    gardes: int = 0
    corriges: int = 0
    doublons: int = 0
    hors_config: int = 0
    hors_config_sans_societe: int = 0
    ajouts: int = 0

    @property
    def certaines(self) -> int:
        return self.corriges + self.doublons + self.ajouts

    @property
    def min(self) -> int:
        return self.certaines

    @property
    def estime(self) -> int:
        return self.certaines + self.hors_config_sans_societe

    @property
    def max(self) -> int:
        return self.certaines + self.hors_config


def reference(config: dict[str, Any]) -> dict[str, set[str]]:
    """Valeur normalisée → les listes de `config/` où elle figure (listes proposées seulement).
    Une valeur peut être dans deux listes (marque sûre et maison) : l'une ou l'autre convient."""
    ref: dict[str, set[str]] = {}
    for liste in LISTES_PROPOSEES:
        for v in config.get(liste) or []:
            if isinstance(v, str) and norm(v):
                ref.setdefault(norm(v), set()).add(liste)
    return ref


def revoir(ranges: list[ElementRange], ref: dict[str, set[str]]) -> Revue:
    """La revue simulée : voir la docstring du module."""
    r = Revue(elements=len(ranges))
    vues: set[str] = set()
    for e in ranges:
        cle = norm(e.valeur)
        if cle in vues:
            r.doublons += 1
            continue
        vues.add(cle)
        if cle not in ref:
            r.hors_config += 1
            r.hors_config_sans_societe += e.sans_societe
        elif e.liste in ref[cle]:
            r.gardes += 1
        else:
            r.corriges += 1
    r.ajouts = sum(1 for cle in ref if cle not in vues)
    return r


def _demander(entree: Entree, nom_modele: str) -> tuple[list[ElementBrut], Consommation, float]:
    """L'appel à l'API. Une erreur (429 d'OpenRouter, panne) : nouvel essai après une pause."""
    essai = 1
    while True:
        conso = Consommation()
        debut = time.monotonic()
        try:
            bruts = lire_reponse(appeler(client_ia(), construire_requete(entree, nom_modele), conso=conso))
            return bruts, conso, time.monotonic() - debut
        except PropositionImpossible:
            if essai == ESSAIS:
                raise
        finally:
            conso.journaliser(nom_modele)
        time.sleep(PAUSE_S * essai)
        essai += 1


def proposer_groupe(con: duckdb.DuckDBPyConnection, config: dict[str, Any]) -> Mesure:
    """Une proposition réelle, rangée comme le travail `proposition`, sans version validée."""
    nom_modele = modele()
    entree = lire_entree(con, str(config["groupe"]), str(config["tete"]))
    bruts, conso, duree = _demander(entree, nom_modele)
    elements = nettoyer(bruts)
    marques = [e.valeur for e in elements if e.type == "marque"]
    porteurs = compter_porteurs(con, marques, societes_du_groupe(con, str(config["tete"]))) if marques else {}
    homonymes = {m: p.hors_groupe for m, p in porteurs.items()}
    return Mesure(nom_modele, conso.cout, duree, ranger(elements, homonymes, sans_societe(porteurs)))


@dataclass
class Mesure:
    """Une proposition et ce qu'elle a coûté. Enregistrée dans `out/sc007/<groupe>.json`."""

    modele: str
    cout: float | None
    duree_s: float | None
    elements: list[ElementRange]

    def ecrire(self, chemin: Path) -> None:
        donnees = asdict(self) | {"elements": [e.en_json() for e in self.elements]}
        chemin.write_text(json.dumps(donnees, ensure_ascii=False, indent=1), encoding="utf-8")

    @classmethod
    def lire(cls, chemin: Path) -> Mesure | None:
        donnees = json.loads(chemin.read_text(encoding="utf-8")) if chemin.is_file() else None
        if not isinstance(donnees, dict):
            return None
        elements = [ElementRange(**e) for e in donnees["elements"]]
        return cls(donnees["modele"], donnees["cout"], donnees["duree_s"], elements)


def main(arguments: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    refaire = "--refaire" in arguments
    groupes = [a for a in arguments if not a.startswith("--")] or list(GROUPES)
    registre = Path(os.environ.get("CARTOFR_DATA", "data")) / "registre.duckdb"
    sortie = Path("out/sc007")
    sortie.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(registre), read_only=True)
    lignes: list[tuple[str, Revue, Mesure]] = []
    try:
        for g in groupes:
            config = json.loads(Path(f"config/{g}.json").read_text(encoding="utf-8"))
            chemin = sortie / f"{g}.json"
            mesure = None if refaire else Mesure.lire(chemin)
            if mesure is None:
                mesure = proposer_groupe(con, config)
                mesure.ecrire(chemin)
            lignes.append((g, revoir(mesure.elements, reference(config)), mesure))
    finally:
        con.close()

    print(f"\nModèle : {', '.join(sorted({m.modele for _, _, m in lignes}))}\n")
    print(
        "| Groupe | Proposés | Gardés | Liste corrigée | Doublons | Hors config. (dont sans société) "
        "| Ajouts | Corrections min / estimé / max | Coût | Durée IA |"
    )
    print("|---|---|---|---|---|---|---|---|---|---|")
    for g, r, m in lignes:
        cout = "?" if m.cout is None else f"{m.cout:.3f} $"
        duree = "?" if m.duree_s is None else f"{m.duree_s / 60:.1f} min"
        print(
            f"| {g} | {r.elements} | {r.gardes} | {r.corriges} | {r.doublons} "
            f"| {r.hors_config} ({r.hors_config_sans_societe}) | {r.ajouts} "
            f"| {r.min} / {r.estime} / {r.max} | {cout} | {duree} |"
        )
    n = len(lignes)
    moy_min = sum(r.min for _, r, _ in lignes) / n
    moy_est = sum(r.estime for _, r, _ in lignes) / n
    moy_max = sum(r.max for _, r, _ in lignes) / n
    print(
        f"\nMoyenne des corrections : min {moy_min:.1f}, estimé {moy_est:.1f}, max {moy_max:.1f} "
        f"(SC-007 : moins de {SEUIL})."
    )
    return 0 if moy_min < SEUIL else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
