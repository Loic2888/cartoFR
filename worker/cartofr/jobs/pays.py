"""Travail `pays` : calculer la carto du pays et l'écrire dans `pays.duckdb` (T048, US7).

Usage : inséré par `cartofr.travaux.planifier_pays` après chaque synchro terminée, et au plus tard
7 jours après le dernier calcul réussi ; exécuté par la boucle du worker. Il est global
(`organisation_id` vide) : la carto du pays est commune à toutes les organisations.

Entrées et sorties : celles de `cartofr.pays.calcul` (registre, documents déposés, `pays.duckdb`,
une ligne `pays` dans `mises_a_jour`). Le registre est ouvert en écriture seulement au début et à
la fin, en réessayant tant que la recherche le lit (`ouvrir_en_ecriture`).

Échec : une exception dont le message ne porte aucune donnée ; la colonne `erreur` de `travaux`
ne reçoit que le nom de la classe (T008). Le `pays.duckdb` précédent reste en place.
"""

from __future__ import annotations

from cartofr.jobs import Contexte, enregistrer
from cartofr.jobs.synchro import dossier_donnees, ouvrir_en_ecriture
from cartofr.pays.calcul import NOM_REGISTRE, lancer

TYPE = "pays"


class PaysEnEchec(RuntimeError):
    """Échec du travail `pays`, avec un message sûr (aucune donnée)."""


@enregistrer(TYPE)
def travail_pays(ctx: Contexte) -> None:
    """Le travail `pays` de la file."""
    dossier = dossier_donnees()
    if not (dossier / NOM_REGISTRE).is_file():
        raise PaysEnEchec("registre introuvable : la carto du pays attend le registre")
    lancer(dossier, ouvrir_en_ecriture)
