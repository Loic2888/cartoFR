"""Mesure de la carto du pays (T048 C4 et C6) sur le registre réel.

Usage, depuis la racine du dépôt, après le dépôt des documents (T046) :
    CARTOFR_DATA=data CARTOFR_REFERENCES=basile .venv/bin/python worker/scripts/mesure_pays.py \
        --perimetre out/perimetre

Entrées :
- `<CARTOFR_DATA>/registre.duckdb` et les documents déposés : le calcul complet est lancé
  (`cartofr.pays.calcul.lancer`), il écrit `<CARTOFR_DATA>/pays.duckdb` et une ligne `pays` dans
  `mises_a_jour`, comme le travail de nuit ;
- avec `--perimetre DOSSIER` : `config/<groupe>.json` (la tête), `DOSSIER/<groupe>.pdf` et la
  référence `<CARTOFR_REFERENCES>/<groupe>_entites.csv`, pour LVMH et VINCI (C4). Données client :
  jamais copiées dans git.
Sortie : durée, mémoire au plus, groupes, sociétés rangées, part des sociétés actives rangées ;
pour LVMH et VINCI, l'écart entre la carto lue dans `pays.duckdb` (la tête et ce qui descend
d'elle) et celle de `non_regression.py --perimetre --sans-reglages`. Code 1 si une carto diffère.

Aucun nom n'est affiché : des volumes seulement.
"""

import argparse
import json
import logging
import os
import resource
import sys
import time
from pathlib import Path

import duckdb
from non_regression import _lire_reference, _siren

from cartofr.moteur import cartographier
from cartofr.pays import calcul
from cartofr.perimetre import PerimetrePublie, extraire, texte_document

GROUPES = ("lvmh", "vinci")
DUREE_MAX_S = 3600  # C6 : moins d'une heure pour les documents déposés


def descente(con: duckdb.DuckDBPyConnection, tete: str) -> set[str]:
    """La carto d'une société dans `pays.duckdb` : elle et tout ce qui descend d'elle."""
    lignes = con.execute(
        """
        with recursive bas(siren) as (
            select ?::varchar
            union
            select s.siren from pays_societes s join bas on s.mere = bas.siren
        )
        select siren from bas
        """,
        [tete],
    ).fetchall()
    return {s for (s,) in lignes}


def main() -> int:
    parseur = argparse.ArgumentParser(description="Mesure de la carto du pays (T048).")
    parseur.add_argument("--perimetre", type=Path, help="dossier des PDF de LVMH et VINCI (C4)")
    arguments = parseur.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    data = Path(os.environ.get("CARTOFR_DATA", "data"))
    registre = data / calcul.NOM_REGISTRE
    if not registre.is_file():
        print(f"Registre introuvable : {registre}", file=sys.stderr)
        return 2

    debut = time.monotonic()
    bilan = calcul.lancer(data)
    duree = time.monotonic() - debut
    memoire = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024  # ko -> Go (Linux)

    # Mesuré, pas supposé : sociétés actives dans un groupe, et lignes de pays_societes hors des sociétés
    # actives (doit être 0). Une société active absente de pays_societes est rangée seule.
    con = duckdb.connect(str(registre), read_only=True)
    try:
        chemin = str(data / calcul.NOM_PAYS).replace("'", "''")  # attach ne prend pas de paramètre
        con.execute(f"attach '{chemin}' as pays (read_only)")
        (actives,) = con.execute("select count(distinct siren) from sieges").fetchone() or (0,)
        (dans_un_groupe,) = con.execute(
            "select count(*) from pays.pays_societes where siren in (select siren from sieges)"
        ).fetchone() or (0,)
        (hors_actives,) = con.execute(
            "select count(*) from pays.pays_societes where siren not in (select siren from sieges)"
        ).fetchone() or (0,)
    finally:
        con.close()
    print(f"Durée totale : {duree:.0f} s (cible : moins de {DUREE_MAX_S} s)")
    print(f"Mémoire au plus : {memoire:.1f} Go")
    print(f"Documents : {bilan.documents}, dont {bilan.documents_en_echec} en échec")
    print(f"Groupes de 2 sociétés ou plus : {bilan.groupes} ; sociétés dans ces groupes : {bilan.societes}")
    part = dans_un_groupe / actives if actives else 0.0
    print(
        f"Sociétés actives : {actives} ; dans un groupe : {dans_un_groupe} ({part:.1%}) ;"
        f" seules : {actives - dans_un_groupe} ; lignes hors des sociétés actives : {hors_actives}"
    )
    tenus = [duree < DUREE_MAX_S, bilan.documents_en_echec == 0, hors_actives == 0]

    if arguments.perimetre:
        references = Path(os.environ.get("CARTOFR_REFERENCES", "basile"))
        pays = duckdb.connect(str(data / calcul.NOM_PAYS), read_only=True)
        try:
            for groupe in GROUPES:
                cfg = json.loads((Path("config") / f"{groupe}.json").read_text(encoding="utf-8"))
                pdf = arguments.perimetre / f"{groupe}.pdf"
                reglages = calcul.reglages_tete_seule(cfg["tete"], cfg["groupe"])
                document = PerimetrePublie(pdf.name, tuple(extraire(texte_document(pdf))))
                attendu = {s.siren for s in cartographier(reglages, registre, perimetre=document).societes}
                lu = descente(pays, cfg["tete"])
                ref = {_siren(ligne) for ligne in _lire_reference(references, groupe)}
                print(
                    f"{groupe} : pays {len(lu)} sociétés, non-régression {len(attendu)} ;"
                    f" seulement au pays {len(lu - attendu)},"
                    f" seulement en non-régression {len(attendu - lu)} ;"
                    f" référence retrouvée {len(lu & ref)}/{len(ref)}"
                )
                tenus.append(lu == attendu)
        finally:
            pays.close()
    return 0 if all(tenus) else 1


if __name__ == "__main__":
    sys.exit(main())
