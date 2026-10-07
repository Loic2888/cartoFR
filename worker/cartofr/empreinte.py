"""Empreinte d'un nom de famille exclu des réglages (garde-fou 6).

Un réglage `familles_exclues` contient des noms de famille : ceux de la famille
qui contrôle le groupe, dont les holdings personnelles ne doivent pas entrer
dans la carto. Ces noms ne s'écrivent jamais en clair dans la base de l'app ni
à l'écran. On garde leur empreinte HMAC-SHA256, calculée avec une clé secrète du
serveur (CARTOFR_CLE_EMPREINTE). Sans la clé, on ne retrouve pas le nom, même en
essayant des noms connus (ce qu'un simple SHA-256 permettrait).

Normalisation : espaces retirés aux bords, puis majuscules. Le seed Postgres
(`upper(btrim(...))`) et l'interface (T020) appliquent la même ; le moteur
(T021) compare l'empreinte du nom de chaque dirigeant à la liste.

Usage : empreinte("Nom", cle) -> 64 caractères hexadécimaux.
"""

import hashlib
import hmac
import os

VARIABLE_CLE = "CARTOFR_CLE_EMPREINTE"


class CleManquante(RuntimeError):
    """La clé d'empreinte n'est pas définie dans l'environnement."""


def normaliser(nom: str) -> str:
    return nom.strip().upper()


def empreinte(nom: str, cle: str) -> str:
    if not cle:
        raise CleManquante(f"{VARIABLE_CLE} est vide.")
    return hmac.new(cle.encode(), normaliser(nom).encode(), hashlib.sha256).hexdigest()


def cle_depuis_env() -> str:
    cle = os.environ.get(VARIABLE_CLE, "")
    if not cle:
        raise CleManquante(f"{VARIABLE_CLE} n'est pas définie : impossible de comparer les familles exclues.")
    return cle
