"""Carto du pays : chaque société active rangée dans un seul groupe (US7).

`departage` tranche, par une règle écrite, quand deux groupes réclament la même société (T047).
Aucun registre ni base lus ici, aucune IA (principe 1), aucun nom de personne rendu (garde-fou 6).
"""

from cartofr.pays.departage import Departage, Groupe, GroupeRange, Maniere, Rangement, Reclamation, departager

__all__ = [
    "Departage",
    "Groupe",
    "GroupeRange",
    "Maniere",
    "Rangement",
    "Reclamation",
    "departager",
]
