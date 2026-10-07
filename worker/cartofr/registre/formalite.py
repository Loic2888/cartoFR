"""Lecture d'une fiche société du RNE (une formalité) : ce qui sert au registre.

But : tirer d'une fiche JSON de l'INPI (`/api/companies/diff`, ou une ligne du
stock) l'état actuel d'une personne morale : sa dénomination, son opposition à
la prospection, son effectif, sa radiation, ses dirigeants sociétés (les liens
« parent dirige enfant ») et ses dirigeants personnes physiques.

Usage :
    fiche = lire_fiche(company)   # None si ce n'est pas une personne morale

Entrées : un élément d'une page `/diff` (`{"company": {...}}`), ou directement
le dictionnaire `company` (`{"formality": ...}`, forme du stock et du cache).
Sorties : une `Fiche`, ou None. Aucune écriture, aucun journal.

Logique reprise de `build_links.py` (racine), champ par champ :
    - SIREN : `formality.siren`, sinon `siren` ;
    - personne morale : `formality.content.personneMorale` (sinon : pas une
      personne morale, la fiche est ignorée, comme dans le prototype) ;
    - dénomination et effectif : `personneMorale.identite.entreprise`
      (`denomination`, `nombreSalarie`) ;
    - opposition à la prospection : `formality.diffusionCommerciale` ;
    - dirigeants : `personneMorale.composition.pouvoirs[]`, rôle dans
      `roleEntreprise`, actif dans `actif`. `typeDePersonne` vaut
      `ENTREPRISE` (lien vers `entreprise.siren`) ou `INDIVIDU` (clé
      `NOM|PRÉNOM|naissance` tirée de `individu.descriptionPersonne`).
Un `actif` vide vaut actif (MEMORY.md, 2026-10-06) ; seul `actif = false`
retire un pouvoir. L'API ne rend que les pouvoirs en cours : un dirigeant
absent de la fiche n'est plus en fonction.

Ajout par rapport au prototype : la radiation, lue dans
`personneMorale.detailCessationEntreprise.dateRadiation`.

Les clés de personne sont des données personnelles : elles ne servent qu'au
calcul, dans `dirigeants_personnes`, et ne sont jamais affichées ni journalisées
(garde-fou 6). `Fiche.__repr__` ne les montre pas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class FormaliteInvalide(ValueError):
    """La fiche n'a pas la forme attendue. Le message ne cite aucune valeur lue."""


@dataclass(frozen=True)
class Fiche:
    """État actuel d'une personne morale selon le RNE.

    `liens` : couples (SIREN du parent, rôle) des sociétés qui la dirigent.
    `personnes` : couples (clé de la personne, rôle), usage interne seulement.
    """

    siren: str
    denomination: str | None
    diffusion_commerciale: bool | None
    salaries: int | None
    radiee: bool
    liens: frozenset[tuple[str, str | None]] = field(default_factory=frozenset)
    personnes: frozenset[tuple[str, str | None]] = field(default_factory=frozenset, repr=False)


def _dict(valeur: Any, nom: str) -> dict[str, Any]:
    """Un sous-objet JSON : absent ou null donne {}, un autre type est invalide."""
    if valeur is None:
        return {}
    if not isinstance(valeur, dict):
        raise FormaliteInvalide(f"champ {nom} : objet attendu")
    return valeur


def _entier(valeur: Any) -> int | None:
    """Effectif déclaré : un entier, ou None s'il est absent ou illisible."""
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return None


def _booleen(valeur: Any) -> bool | None:
    return valeur if isinstance(valeur, bool) else None


def cle_personne(description: dict[str, Any]) -> str | None:
    """Clé `NOM|PRÉNOM|naissance` d'un dirigeant personne, comme `build_links.py`.

    None si le nom est vide : le dirigeant n'est pas retenu.
    """
    nom = str(description.get("nom") or "").upper()
    if not nom:
        return None
    prenoms = description.get("prenoms") or [""]
    prenom = str((prenoms[0] if isinstance(prenoms, list) and prenoms else "") or "").upper()
    return f"{nom}|{prenom}|{description.get('dateDeNaissance', '')}"


def lire_fiche(company: Any) -> Fiche | None:
    """Lit une fiche société. None si ce n'est pas une personne morale avec SIREN.

    Lève `FormaliteInvalide` si la fiche n'a pas la forme attendue.
    """
    if not isinstance(company, dict):
        raise FormaliteInvalide("fiche : objet attendu")
    if "company" in company and "formality" not in company:
        # Élément d'une page `/diff` : `{"company": {...}}`.
        return lire_fiche(company["company"])
    formalite = _dict(company.get("formality"), "formality")
    siren = formalite.get("siren") or company.get("siren")
    personne_morale = _dict(formalite.get("content"), "formality.content").get("personneMorale")
    if not siren or not personne_morale:
        return None
    if not isinstance(siren, str):
        raise FormaliteInvalide("champ siren : texte attendu")
    personne_morale = _dict(personne_morale, "personneMorale")
    entreprise = _dict(_dict(personne_morale.get("identite"), "identite").get("entreprise"), "entreprise")
    cessation = _dict(personne_morale.get("detailCessationEntreprise"), "detailCessationEntreprise")
    pouvoirs = _dict(personne_morale.get("composition"), "composition").get("pouvoirs") or []
    if not isinstance(pouvoirs, list):
        raise FormaliteInvalide("champ pouvoirs : liste attendue")

    liens: set[tuple[str, str | None]] = set()
    personnes: set[tuple[str, str | None]] = set()
    for pouvoir in pouvoirs:
        pouvoir = _dict(pouvoir, "pouvoir")
        if pouvoir.get("actif") is False:
            continue
        role = pouvoir.get("roleEntreprise")
        role = None if role is None else str(role)
        if pouvoir.get("typeDePersonne") == "ENTREPRISE":
            parent = _dict(pouvoir.get("entreprise"), "pouvoir.entreprise").get("siren")
            if parent:
                liens.add((str(parent), role))
        elif pouvoir.get("typeDePersonne") == "INDIVIDU":
            individu = _dict(pouvoir.get("individu"), "pouvoir.individu")
            cle = cle_personne(_dict(individu.get("descriptionPersonne"), "descriptionPersonne"))
            if cle:
                personnes.add((cle, role))

    denomination = entreprise.get("denomination")
    return Fiche(
        siren=siren,
        denomination=None if denomination is None else str(denomination),
        diffusion_commerciale=_booleen(formalite.get("diffusionCommerciale")),
        salaries=_entier(entreprise.get("nombreSalarie")),
        radiee=bool(cessation.get("dateRadiation")),
        liens=frozenset(liens),
        personnes=frozenset(personnes),
    )
