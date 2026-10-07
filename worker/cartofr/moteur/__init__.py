"""Moteur de cartographie : des réglages de groupe et le registre local donnent une carto.

Aucun appel réseau (principe 3), aucun nom de personne en sortie (garde-fou 6).
"""

from cartofr.moteur.modele import Carto
from cartofr.moteur.moteur import cartographier

__all__ = ["Carto", "cartographier"]
