"""Schéma des réglages d'un groupe (T020, FR-005, principe 2).

Les réglages disent au moteur ce qui fait partie d'un groupe : marques,
exclusions, organigramme (sens de chaque clé :
skills/account-mapping/references/moteur-france.md). Ils sont saisis dans
l'interface, vérifiés par Zod (web/lib/reglages/schema.ts), stockés dans
`reglages.contenu`, puis vérifiés ici avant que le moteur s'en serve. Les deux
schémas ont la même forme : les fixtures de worker/tests/fixtures/reglages/
sont acceptées ou refusées pareil des deux côtés (C1).

Règles :
- `groupe` et `tete` sont obligatoires ; les listes sont facultatives (vides
  par défaut), comme dans config/*.json ;
- aucune clé inconnue, aucun changement de type (un SIREN est une chaîne de
  9 chiffres, jamais un nombre) ;
- `familles_exclues` (noms de famille en clair) est refusé : seules leurs
  empreintes HMAC (`familles_exclues_empreintes`, cartofr.empreinte) entrent
  dans les réglages (garde-fou 6).

Usage : valider(contenu) -> Reglages, ou ReglagesInvalides (message français).
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError, model_validator

# Blancs reconnus des deux côtés (Python et JavaScript ne s'accordent pas sur
# `\s`) : un texte fait d'eux seuls est vide.
_BLANCS = "    -     　﻿\u0085"
# Un texte : au moins un caractère non blanc, aucun caractère de contrôle
# (retour à la ligne compris). Même motif dans schema.ts.
MOTIF_TEXTE = f"^[{_BLANCS}]*[^{_BLANCS}\\x00-\\x1f\\x7f][^\\x00-\\x1f\\x7f]*$"
MOTIF_SIREN = r"^[0-9]{9}$"
MOTIF_EMPREINTE = r"^[0-9a-f]{64}$"
TEXTE_MAX = 200
LISTE_MAX = 1000

Texte = Annotated[str, StringConstraints(pattern=MOTIF_TEXTE, max_length=TEXTE_MAX)]
Siren = Annotated[str, StringConstraints(pattern=MOTIF_SIREN)]
Empreinte = Annotated[str, StringConstraints(pattern=MOTIF_EMPREINTE)]

CLE_EN_CLAIR = "familles_exclues"


class ReglagesInvalides(ValueError):
    """Les réglages ne respectent pas le schéma."""

    def __init__(self, erreurs: list[str]):
        super().__init__("Réglages invalides : " + " ; ".join(erreurs))
        self.erreurs = erreurs


class Reglages(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    groupe: Texte
    tete: Siren
    marques_sures: list[Texte] = Field(default_factory=list, max_length=LISTE_MAX)
    marques_ambigues: list[Texte] = Field(default_factory=list, max_length=LISTE_MAX)
    marques_sures_homonymes: list[Texte] = Field(default_factory=list, max_length=LISTE_MAX)
    marques_sigles: list[Texte] = Field(default_factory=list, max_length=LISTE_MAX)
    exclus: list[Siren] = Field(default_factory=list, max_length=LISTE_MAX)
    exclus_noms: list[Texte] = Field(default_factory=list, max_length=LISTE_MAX)
    familles_exclues_empreintes: list[Empreinte] = Field(default_factory=list, max_length=LISTE_MAX)
    priorite: list[Siren] = Field(default_factory=list, max_length=LISTE_MAX)
    organigramme: list[Texte] = Field(default_factory=list, max_length=LISTE_MAX)

    @model_validator(mode="before")
    @classmethod
    def _sans_famille_en_clair(cls, donnees: Any) -> Any:
        if isinstance(donnees, dict) and CLE_EN_CLAIR in donnees:
            raise ValueError(
                "`familles_exclues` en clair est interdit : seules les empreintes "
                "(`familles_exclues_empreintes`) entrent dans les réglages"
            )
        return donnees


_MESSAGES = {
    "extra_forbidden": "clé inconnue",
    "missing": "obligatoire",
    "string_pattern_mismatch": "format invalide",
    "string_type": "doit être un texte",
    "list_type": "doit être une liste",
    "string_too_long": f"{TEXTE_MAX} caractères au plus",
    "too_long": f"{LISTE_MAX} éléments au plus",
}


def valider(contenu: object) -> Reglages:
    """Vérifie un contenu de réglages (dict lu du JSON). Lève ReglagesInvalides."""
    if not isinstance(contenu, dict):
        raise ReglagesInvalides(["les réglages doivent être un objet JSON"])
    try:
        return Reglages.model_validate(contenu)
    except ValidationError as e:
        erreurs = []
        for err in e.errors():
            # La valeur saisie n'est jamais recopiée : elle peut être un nom.
            if err["type"] == "value_error" and not err["loc"]:
                erreurs.append(f"{CLE_EN_CLAIR} : en clair interdit, seules les empreintes entrent")
                continue
            chemin = ".".join(str(p) for p in err["loc"]) or "réglages"
            erreurs.append(f"{chemin} : {_MESSAGES.get(err['type'], 'valeur invalide')}")
        raise ReglagesInvalides(erreurs) from None
