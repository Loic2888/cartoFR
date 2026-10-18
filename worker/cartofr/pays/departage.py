"""Départage d'une société réclamée par plusieurs groupes : elle va dans un seul (T047, FR-012).

Usage : `departager(reclamations, groupes)` rend un `Departage`.
Entrées : les réclamations (un groupe, désigné par le SIREN de sa tête, réclame une société par
inscription en intégration globale dans son document, par descente du registre sous une de ses
sociétés, ou comme arbre non réclamé), et pour chaque groupe sa taille et les têtes de groupes
inscrites dans son document.
Sorties : pour chaque société un seul groupe, avec la raison du choix quand il y a eu départage ;
pour chaque groupe son groupe parent, ou aucun.

Règle (décidée le 2026-10-16 par Loïc pour les groupes emboîtés, proposée pour le reste) :
1. un groupe B dont la tête est inscrite dans le document de A devient sous-groupe de A et garde
   sa carto. Une société réclamée par A et par B va dans B, le plus proche d'elle. Boucle (A
   inscrit B, B inscrit A) : le parent est la plus petite tête par SIREN ;
2. un arbre non réclamé perd toujours contre une inscription ou une descente ;
3. l'inscription passe avant la descente ;
4. entre deux inscriptions : taux le plus haut, puis groupe le plus grand, puis plus petite tête ;
5. entre deux descentes : niveau le plus bas, puis plus petite tête.

Fonction pure : le résultat ne dépend pas de l'ordre des réclamations. Une raison ne cite que des
SIREN de têtes de groupe, jamais un nom de personne (garde-fou 6).
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

Maniere = Literal["inscription", "descente", "arbre"]

# Rang d'une manière : plus petit, plus fort (règles 2 et 3).
_RANG: dict[str, int] = {"inscription": 0, "descente": 1, "arbre": 2}


@dataclass(frozen=True)
class Reclamation:
    """Un groupe réclame une société."""

    groupe: str  # SIREN de la tête du groupe
    societe: str  # SIREN de la société réclamée
    maniere: Maniere
    taux: float | None = None  # % d'intérêt du document, pour une inscription
    niveau: int | None = None  # profondeur sous la tête, pour une descente (0 : la tête)

    def __post_init__(self) -> None:
        if self.maniere == "inscription" and self.taux is None:
            raise ValueError(f"inscription de {self.societe} par {self.groupe} sans taux")
        if self.maniere == "descente" and self.niveau is None:
            raise ValueError(f"descente vers {self.societe} depuis {self.groupe} sans niveau")


@dataclass(frozen=True)
class Groupe:
    """Ce que le départage sait d'un groupe."""

    tete: str  # SIREN de la tête
    taille: int  # nombre de sociétés du groupe
    tetes_inscrites: frozenset[str] = frozenset()  # têtes d'autres groupes inscrites en intégration globale


@dataclass(frozen=True)
class Rangement:
    """Une société et le seul groupe qui la garde."""

    societe: str
    groupe: str
    raison: str | None  # vide si un seul groupe la réclamait


@dataclass(frozen=True)
class GroupeRange:
    """Un groupe et son groupe parent : vide s'il n'est inscrit dans aucun autre document."""

    tete: str
    parent: str | None


@dataclass(frozen=True)
class Departage:
    """Résultat du départage, trié par SIREN."""

    societes: tuple[Rangement, ...]
    groupes: tuple[GroupeRange, ...]


def departager(reclamations: Iterable[Reclamation], groupes: Iterable[Groupe]) -> Departage:
    """Range chaque société réclamée dans un seul groupe et donne à chaque groupe son parent."""
    reclamations = list(reclamations)
    par_tete = {g.tete: g for g in groupes}
    tetes = set(par_tete) | {r.groupe for r in reclamations}
    parents = _parents(tetes, par_tete)

    # Par société, la meilleure réclamation de chaque groupe : un groupe qui réclame deux fois
    # la même société n'est pas un départage.
    par_societe: dict[str, dict[str, Reclamation]] = {}
    for r in reclamations:
        du_groupe = par_societe.setdefault(r.societe, {})
        avant = du_groupe.get(r.groupe)
        if avant is None or _cle_meme_groupe(r) < _cle_meme_groupe(avant):
            du_groupe[r.groupe] = r

    societes = tuple(_ranger(siren, par_societe[siren], parents, par_tete) for siren in sorted(par_societe))
    return Departage(
        societes=societes,
        groupes=tuple(GroupeRange(t, parents[t]) for t in sorted(tetes)),
    )


def _cle_meme_groupe(r: Reclamation) -> tuple[int, float, int]:
    """Ordre de deux réclamations d'un même groupe : manière, taux haut, niveau bas."""
    return (_RANG[r.maniere], -(r.taux or 0.0), r.niveau or 0)


def _parents(tetes: set[str], par_tete: Mapping[str, Groupe]) -> dict[str, str | None]:
    """Parent de chaque groupe (règle 1) : un groupe dont le document inscrit sa tête.

    Entre plusieurs documents qui l'inscrivent, le plus proche : celui qu'un autre candidat inscrit
    lui-même, directement ou non (trois niveaux : C inscrit par A et B, B inscrit par A → B). Puis la
    plus petite tête. Une boucle se casse à sa plus petite tête, qui n'y prend pas de parent.
    """
    # Depuis les documents seulement : le pays compte environ 335 000 groupes, dont quelques centaines
    # ont un document. Comparer chaque tête à chaque autre coûterait des dizaines de milliards de tours.
    candidats: dict[str, set[str]] = {t: set() for t in tetes}
    for a, g in par_tete.items():
        for b in g.tetes_inscrites:
            if b != a and b in candidats:
                candidats[b].add(a)
    inscrivants = {a for c in candidats.values() for a in c}
    atteint = {a: _atteignables(a, tetes, par_tete) for a in inscrivants}
    exclus: dict[str, set[str]] = {t: set() for t in tetes}

    def choisir(b: str) -> str | None:
        restants = candidats[b] - exclus[b]
        # Un candidat est écarté si un autre est plus proche : il l'atteint, sans réciproque.
        proches = [a for a in restants if not any(x in atteint[a] and a not in atteint[x] for x in restants)]
        return min(proches or restants, default=None)

    parents = {b: choisir(b) for b in tetes}
    while (boucle := _boucle(parents)) is not None:
        plus_petite = min(boucle)
        exclus[plus_petite] |= boucle
        parents[plus_petite] = choisir(plus_petite)
    return parents


def _atteignables(depart: str, tetes: set[str], par_tete: Mapping[str, Groupe]) -> set[str]:
    """Têtes que le document de `depart` inscrit, directement ou par un document inscrit."""
    vus: set[str] = set()
    a_voir = [depart]
    while a_voir:
        g = par_tete.get(a_voir.pop())
        for b in g.tetes_inscrites if g else ():
            if b in tetes and b not in vus:
                vus.add(b)
                a_voir.append(b)
    vus.discard(depart)
    return vus


def _boucle(parents: Mapping[str, str | None]) -> set[str] | None:
    """Une boucle de parents, s'il en reste une, parcourue dans l'ordre des SIREN."""
    for depart in sorted(parents):
        chemin: list[str] = []
        t: str | None = depart
        while t is not None and t not in chemin:
            chemin.append(t)
            t = parents[t]
        if t is not None:
            return set(chemin[chemin.index(t) :])
    return None


def _ancetres(tete: str, parents: Mapping[str, str | None]) -> set[str]:
    vus: set[str] = set()
    t = parents.get(tete)
    while t is not None and t not in vus:
        vus.add(t)
        t = parents.get(t)
    return vus


def _ranger(
    societe: str,
    par_groupe: Mapping[str, Reclamation],
    parents: Mapping[str, str | None],
    par_tete: Mapping[str, Groupe],
) -> Rangement:
    """Applique la règle à une société et rend son groupe avec la raison du choix."""
    if len(par_groupe) == 1:
        (seule,) = par_groupe.values()
        return Rangement(societe, seule.groupe, None)

    # Règle 2 : un arbre non réclamé perd contre toute inscription ou descente.
    restantes = [r for r in par_groupe.values() if r.maniere != "arbre"]
    motifs: list[str] = []
    if len(restantes) < len(par_groupe):
        perdants = sorted(r.groupe for r in par_groupe.values() if r.maniere == "arbre")
        motifs.append(f"l'emporte sur l'arbre non réclamé {_liste(perdants)}")

    # Règle 1 : un groupe s'efface devant son sous-groupe, plus proche de la société.
    if len(restantes) > 1:
        reclamants = {r.groupe for r in restantes}
        englobants = {a for r in restantes for a in _ancetres(r.groupe, parents) & reclamants}
    else:
        englobants = set()
    restantes = [r for r in restantes if r.groupe not in englobants]

    # Règles 3 à 5, entre groupes qui ne s'emboîtent pas.
    if len(restantes) > 1:
        gagnante, motif = _hors_emboitement(restantes, par_tete)
        restantes = [gagnante]
        motifs.append(motif)

    (gagnante,) = restantes
    au_dessus = englobants & _ancetres(gagnante.groupe, parents)
    if au_dessus:
        motifs.insert(0, f"dans le sous-groupe {gagnante.groupe} de {_liste(sorted(au_dessus))}")
    if englobants - au_dessus:
        motifs.insert(0, f"{_liste(sorted(englobants - au_dessus))} s'efface devant son sous-groupe")
    return Rangement(societe, gagnante.groupe, f"{_tenue(gagnante)} ; {' ; '.join(motifs)}")


def _hors_emboitement(
    restantes: list[Reclamation], par_tete: Mapping[str, Groupe]
) -> tuple[Reclamation, str]:
    """Inscription avant descente, puis taux, taille et SIREN, ou niveau et SIREN."""
    inscriptions = [r for r in restantes if r.maniere == "inscription"]
    if inscriptions and len(inscriptions) < len(restantes):
        autres = sorted(r.groupe for r in restantes if r.maniere != "inscription")
        if len(inscriptions) == 1:
            return inscriptions[0], f"l'inscription passe avant la descente depuis {_liste(autres)}"
        gagnante, motif = _hors_emboitement(inscriptions, par_tete)
        return gagnante, f"l'inscription passe avant la descente depuis {_liste(autres)} ; {motif}"

    def taille(r: Reclamation) -> int:
        g = par_tete.get(r.groupe)
        return g.taille if g else 0

    if inscriptions:
        haut = max(r.taux or 0.0 for r in restantes)
        restantes = [r for r in restantes if (r.taux or 0.0) == haut]
        if len(restantes) == 1:
            return restantes[0], "taux le plus haut"
        grand = max(taille(r) for r in restantes)
        restantes = [r for r in restantes if taille(r) == grand]
        if len(restantes) == 1:
            return restantes[0], "à taux égal, le groupe le plus grand"
        return min(restantes, key=lambda r: r.groupe), "à taux et taille égaux, la plus petite tête"

    bas = min(r.niveau or 0 for r in restantes)
    restantes = [r for r in restantes if (r.niveau or 0) == bas]
    if len(restantes) == 1:
        return restantes[0], "la plus proche de la tête de son groupe"
    return min(restantes, key=lambda r: r.groupe), "à niveau égal, la plus petite tête"


def _tenue(r: Reclamation) -> str:
    """Comment le groupe gagnant tient la société, en clair."""
    if r.maniere == "inscription":
        taux = f"{r.taux:g}".replace(".", ",")
        return f"inscrite au document de {r.groupe} ({taux} %)"
    if r.maniere == "descente":
        return f"atteinte par le registre sous {r.groupe}, niveau {r.niveau}"
    return f"arbre non réclamé {r.groupe}"


def _liste(sirens: list[str]) -> str:
    return ", ".join(sirens)
