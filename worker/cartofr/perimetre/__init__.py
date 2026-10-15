"""Périmètre publié d'un groupe : la liste de ses sociétés consolidées, retrouvées dans le registre (T042).

Les groupes cotés publient la liste de leurs sociétés consolidées. Le worker en tire les sociétés
situées en France (`extraction`), puis les retrouve dans le registre par une règle écrite
(`correspondance`). Aucun appel réseau (principe 3), aucune IA (principe 1), aucun nom de personne
lu ni rendu (garde-fou 6).
"""

from cartofr.perimetre.correspondance import Correspondance, cle, correspondre, descendants
from cartofr.perimetre.extraction import Candidat, LignePerimetre, extraire, texte_document

__all__ = [
    "Candidat",
    "Correspondance",
    "LignePerimetre",
    "cle",
    "correspondre",
    "descendants",
    "extraire",
    "texte_document",
]
