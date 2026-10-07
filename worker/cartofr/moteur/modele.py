"""Types de sortie du moteur : une carto, ses sociétés, ses liens et leurs preuves.

Usage : `cartographier(...)` (moteur.py) rend une `Carto`.
Entrées : aucune. Sorties : des dataclasses figées, sans logique.

Règle de licence INPI (garde-fou 6, principe 6) : aucun champ ne peut porter une
personne physique. Les dirigeants personnes servent de preuve pendant le calcul,
dans moteur.py, et ne sortent jamais. Une preuve est un texte lisible qui cite un
rôle, une marque ou une adresse de siège, jamais un nom de personne.
Le test `test_moteur.py` le vérifie par introspection.
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal

Confiance = Literal["A", "B", "C"]


@dataclass(frozen=True)
class Societe:
    """Une société retenue dans le groupe, avec son lien vers sa maison mère dans l'arbre."""

    siren: str
    nom: str | None  # dénomination de la personne morale (SIRENE)
    niveau: int  # 0 pour la tête du groupe
    siret_siege: str | None
    maison_mere_siren: str | None  # vide pour la tête du groupe
    maison_mere_nom: str | None
    preuve: str  # pourquoi ce rattachement : « Mandat au registre : Président », « Déduit : … »
    confiance: Confiance  # A : mandat au registre ; B : deux indices ; C : un seul indice
    pourquoi_dans_le_groupe: str  # règle qui l'a fait entrer
    indices: tuple[str, ...]  # types d'indices : marque_sure, registre, adresse, organigramme…
    ciblable: bool
    raison_ciblable: str
    naf: str | None
    forme_juridique: str | None  # catégorie juridique SIRENE
    tranche_effectif: str | None  # tranche SIRENE ; « NN » = non renseignée, pas zéro
    salaries_rne: int | None  # effectif déclaré au RNE
    opposition_prospection: bool  # diffusionCommerciale = false au RNE : marquée, jamais cachée
    non_diffusible: bool | None  # SIRENE : diffusion partielle ; vide si inconnue
    adresse_siege: str | None  # adresse normalisée du siège de la société
    commune: str | None
    compte_de_rattachement: str | None  # SIREN de la société ciblable la plus proche au-dessus


@dataclass(frozen=True)
class Lien:
    """Un mandat inscrit au registre entre deux sociétés retenues : `parent` dirige `enfant`."""

    parent: str
    enfant: str
    role: str  # libellé du rôle RNE : « Président », « Administrateur »…
    preuve: str
    confiance: Confiance


@dataclass(frozen=True)
class Mandat:
    """Un mandat moyen (administrateur, membre…) tenu par une société du groupe."""

    parent: str
    role: str


@dataclass(frozen=True)
class Participation:
    """Société hors du groupe où une société du groupe tient un mandat sans contrôle."""

    siren: str
    nom: str | None
    mandats: tuple[Mandat, ...]


@dataclass(frozen=True)
class Etrangere:
    """Société étrangère immatriculée en France (catégorie 3…) qui porte une marque sûre du groupe."""

    siren: str
    nom: str | None


@dataclass(frozen=True)
class Tour:
    """Volumes d'un tour de la boucle, pour le suivi. Aucun nom."""

    numero: int
    retenues: int
    candidates: int
    adresses_du_groupe: int


@dataclass(frozen=True)
class Carto:
    """La cartographie d'un groupe, calculée sur le registre local."""

    groupe: str
    tete: str  # SIREN de la tête du groupe
    date_donnees: date | None  # date la plus récente du registre lu (début ou fin d'une ligne)
    societes: tuple[Societe, ...]
    liens: tuple[Lien, ...]
    participations: tuple[Participation, ...]
    etrangeres: tuple[Etrangere, ...]
    tours: tuple[Tour, ...]
