"""Mesure le quota réel de l'API diff de l'INPI sur une journée complète (T010).

But : lire toutes les formalités d'un jour, jusqu'à la fin ou jusqu'au premier
429, et dire combien on en a lu, en combien de pages et de temps.

Usage (depuis la racine du dépôt) :
    .venv/bin/python worker/scripts/mesure_quota_diff.py [AAAA-MM-JJ]

Le jour par défaut est le dernier jour ouvré complet (hier, ou le vendredi
précédent). La lecture se reprend toute seule si elle a été interrompue : le
curseur est dans <CARTOFR_DATA>/inpi_diff/curseur.json.

Entrées : INPI_USERNAME, INPI_PASSWORD (via CARTOFR_ENV_FILE, `.env` par défaut).
Sorties : un résumé chiffré sur la sortie standard. Aucune formalité n'est
gardée : on compte seulement. Attention, consomme du quota INPI.
"""

from __future__ import annotations

import sys
import time
from datetime import date, timedelta

from cartofr.registre.inpi_diff import PAGE_MAX, Client, Curseur, QuotaAtteint, charger_env, chemin_curseur


def dernier_jour_ouvre(aujourdhui: date) -> date:
    """Hier si c'est un jour de semaine, sinon le vendredi d'avant."""
    jour = aujourdhui - timedelta(days=1)
    while jour.weekday() >= 5:
        jour -= timedelta(days=1)
    return jour


def mesurer(jour: date) -> dict[str, object]:
    """Lit le jour `jour` en entier ou jusqu'au 429, et rend les chiffres."""
    charger_env()
    chemin = chemin_curseur()
    curseur = Curseur.charger(chemin)
    if curseur is not None and (curseur.depuis, curseur.jusqua) != (jour, jour):
        curseur = None  # un curseur d'un autre jour : on repart de zéro pour celui-ci
    reprise = curseur is not None and curseur.pages > 0
    client = Client()
    debut = time.monotonic()
    pagination: dict[str, str] = {}
    compte = None
    quota = False
    try:
        if curseur is None or curseur.pages == 0:
            compte = client.compter(jour, jour)
        for page in client.lire(jour, jour, curseur, page_size=PAGE_MAX, chemin=chemin):
            if page.numero == 1 or not pagination:
                pagination = page.pagination
            if page.numero % 20 == 0:
                print(f"  page {page.numero}, {client.requetes} requêtes", flush=True)
    except QuotaAtteint:
        quota = True
    fin = Curseur.charger(chemin)
    return {
        "jour": jour.isoformat(),
        "reprise": reprise,
        "pages": fin.pages if fin else 0,
        "formalites": fin.formalites if fin else 0,
        "jour_complet": bool(fin and fin.fini),
        "arret_429": quota,
        "requetes_cette_session": client.requetes,
        "duree_s": round(time.monotonic() - debut, 1),
        "count_api": None if compte is None else (compte.total, compte.plus_de_10000),
        "pagination_premiere_page": pagination,
    }


def main() -> None:
    jour = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else dernier_jour_ouvre(date.today())
    print(f"Mesure de l'API diff INPI pour le {jour.isoformat()} (pageSize {PAGE_MAX})", flush=True)
    resultat = mesurer(jour)
    for cle, valeur in resultat.items():
        print(f"{cle} : {valeur}")


if __name__ == "__main__":
    main()
