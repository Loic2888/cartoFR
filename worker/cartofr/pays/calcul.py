"""Carto du pays : ranger chaque société active dans un seul groupe, et l'écrire dans `pays.duckdb` (T048).

Usage, depuis la racine du dépôt :
    CARTOFR_DATA=data .venv/bin/python -m cartofr.pays.calcul
    (dans l'app : le travail `pays` de la file, `cartofr.jobs.pays`)

Entrées : `<CARTOFR_DATA>/registre.duckdb` (sièges, liens, arbre, documents en vigueur) et les
documents déposés dans `<CARTOFR_DATA>/perimetre/` (T046). Aucun appel extérieur (principe 3).
Sorties : `<CARTOFR_DATA>/pays.duckdb` (`pays.schema`), écrit à côté puis renommé : un calcul
raté laisse le fichier précédent. Une ligne `pays` dans `mises_a_jour` du registre : `ajoutes`
y compte les sociétés rangées, `fermes` les groupes.

Étapes (ARCHI, « Carto du pays ») :
1. l'arbre à une mère (T045), recalculé si le RNE a changé ;
2. les documents en vigueur lus, puis retrouvés dans le registre en un seul passage sur les noms ;
3. le moteur, tête seule + périmètre, pour chaque groupe à document. Un document illisible, ou un
   groupe dont la tête n'est pas une société active, est compté en échec : ses sociétés restent
   dans les arbres ;
4. les groupes mutualistes (T049, `pays.mutualiste`) : un groupe à document dont la tête est une
   caisse de Crédit Mutuel reçoit ses caisses locales, membres du GIE de sa caisse fédérale, sans
   celles d'une autre fédération. Elles passent ensuite par le départage comme ses autres sociétés ;
5. le départage entre groupes à document (T047). Les sociétés qu'aucun groupe à document ne garde
   forment les groupes des arbres, sans passer par le moteur : preuve « Mandat au registre :
   <rôle> », confiance A. Un arbre non réclamé perd toujours (règle 2 de T047) : il n'a donc pas
   besoin de passer par le départage ;
6. l'écriture de `pays.duckdb`.

Règles (décision de Loïc, 2026-10-18) :
- La carto d'une société est elle et ce qui descend d'elle, jamais les autres filiales de sa mère.
  Un groupe est donc la descente depuis sa tête, par `mere`, sans sortir du groupe.
- Seules les sociétés actives, au sens des sièges de SIRENE (personnes morales), sont rangées,
  comme dans le moteur. Une société dont la mère de l'arbre n'est pas une société active
  (entrepreneur individuel, société fermée) ou appartient à un groupe à document est la tête de
  son propre groupe : on ne regroupe pas les sociétés d'une même personne, ni les restes d'un
  arbre dont un groupe a pris la mère.
- Dans un groupe à document, la mère d'une société est celle de la carto de ce groupe. Si le
  départage a rangé cette mère ailleurs, la société est rattachée au plus proche ancêtre resté
  dans son groupe, en confiance C, et la preuve le dit. La tête d'un sous-groupe garde sa mère
  dans le groupe parent.

Aucun nom de personne n'est lu ni écrit : les noms viennent des sièges (sociétés), les journaux ne
portent que des volumes et des noms de classe.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, fields, replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa

from cartofr.moteur import cartographier
from cartofr.moteur.modele import Carto, Confiance, Societe
from cartofr.moteur.moteur import ROLE_LABEL, ciblable_par_fiche, date_des_donnees, ouvrir_registre
from cartofr.pays import mutualiste
from cartofr.pays.departage import Groupe, Maniere, Reclamation, departager
from cartofr.pays.schema import DDL
from cartofr.perimetre import (
    Correspondance,
    LignePerimetre,
    PerimetrePublie,
    correspondre_plusieurs,
    extraire,
    passage_federations,
    texte_document,
)
from cartofr.registre import arbre, journal
from cartofr.registre.construire import NOM_REGISTRE

log = logging.getLogger(__name__)

SOURCE = "pays"
NOM_PAYS = "pays.duckdb"
DOSSIER_DOCUMENTS = "perimetre"

# Réglages « tête seule » : aucune marque, aucune exclusion (non_regression.py --sans-reglages).
_LISTES = ("marques_sures", "marques_ambigues", "exclus", "familles_exclues", "marques_sures_homonymes",
           "marques_sigles", "priorite", "exclus_noms", "organigramme")  # fmt: skip


@dataclass(frozen=True)
class Ligne:
    """Une société rangée : une ligne de `pays_societes`."""

    siren: str
    groupe: str
    nom: str | None
    mere: str | None
    niveau: int
    preuve: str
    confiance: Confiance
    raison: str
    maniere: Maniere
    raison_departage: str | None
    ciblable: bool
    raison_ciblable: str
    opposition_prospection: bool
    non_diffusible: bool


@dataclass(frozen=True)
class LigneGroupe:
    """Un groupe : une ligne de `pays_groupes`."""

    tete: str
    nom: str | None
    taille: int
    document: str | None
    mutualiste: bool
    parent: str | None
    date_donnees: date | None
    mere_etrangere: str | None = None  # la mère hors de France, déclarée au dépôt (T054)
    pays_mere: str | None = None


@dataclass(frozen=True)
class Resultat:
    """La carto du pays, avant écriture."""

    groupes: tuple[LigneGroupe, ...]
    societes: tuple[Ligne, ...]
    documents: int
    documents_en_echec: int
    date_donnees: date | None


@dataclass(frozen=True)
class Bilan:
    groupes: int
    societes: int
    documents: int
    documents_en_echec: int
    duree_s: float


@dataclass(frozen=True)
class _GroupeDocument:
    tete: str
    fichier: str
    carto: Carto
    inscrites: dict[str, float]  # SIREN inscrit en intégration globale -> taux le plus haut
    passage: str = ""  # la liste des fédérations lue dans le document (groupes mutualistes, T049)
    caisses: int = 0  # caisses locales ajoutées à l'étape 4 (groupes mutualistes, T049)

    @property
    def mutualiste(self) -> bool:
        return self.caisses > 0


def reglages_tete_seule(tete: str, nom: str | None) -> dict[str, Any]:
    """Les réglages d'un groupe sans marque ni exclusion : la tête et son document suffisent."""
    return {k: [] for k in _LISTES} | {"groupe": nom or tete, "tete": tete}


# --- Lecture ------------------------------------------------------------------------------------


def _actives(con: duckdb.DuckDBPyConnection, sirens: Iterable[str]) -> set[str]:
    """Les SIREN qui ont un siège actif (personnes morales actives de SIRENE)."""
    return {s for (s,) in con.execute(
        "select siren from sieges where siren in (select unnest($s))", {"s": sorted(set(sirens))}
    ).fetchall()}  # fmt: skip


def documents_en_vigueur(con: duckdb.DuckDBPyConnection) -> list[tuple[str, str]]:
    """(tête, fichier) de chaque document en vigueur, trié par tête. Aucun si la table manque."""
    existe = con.execute(
        "select count(*) from information_schema.tables where table_name = 'documents_perimetre'"
    ).fetchone()
    if not existe or not existe[0]:
        return []
    return [(t, f) for t, f in con.execute(
        "select tete, fichier from documents_perimetre where fin is null order by tete"
    ).fetchall()]  # fmt: skip


def meres_etrangeres(con: duckdb.DuckDBPyConnection) -> dict[str, tuple[str, str]]:
    """Tête -> (mère hors de France, pays), d'après les documents en vigueur (T054). Un registre
    d'avant T054 n'a pas ces colonnes : aucune."""
    colonnes = {c for (c,) in con.execute(
        "select column_name from information_schema.columns where table_name = 'documents_perimetre'"
    ).fetchall()}  # fmt: skip
    if not {"mere_etrangere", "pays_mere"} <= colonnes:
        return {}
    return {t: (m, p) for t, m, p in con.execute(
        "select tete, mere_etrangere, pays_mere from documents_perimetre"
        " where fin is null and mere_etrangere is not null"
    ).fetchall()}  # fmt: skip


def _lire_documents(
    documents: Sequence[tuple[str, str]], dossier: Path
) -> tuple[list[tuple[str, str, list[LignePerimetre], str]], int]:
    """Les lignes de chaque document lisible et sa liste des fédérations, et le nombre de documents
    illisibles."""
    lus, echecs = [], 0
    for tete, fichier in documents:
        try:
            texte = texte_document(dossier / fichier)
            lignes = extraire(texte)
        except Exception as exc:  # pypdf lève bien plus que PyPdfError sur un fichier abîmé
            log.warning("pays : document illisible (%s)", type(exc).__name__)
            echecs += 1
            continue
        lus.append((tete, fichier, lignes, passage_federations(texte)))
    return lus, echecs


def _taux_integration_globale(correspondances: Iterable[Correspondance], tete: str) -> dict[str, float]:
    """SIREN inscrit en intégration globale -> taux le plus haut, tête exclue. Une société retenue par
    le moteur sans y être inscrite en intégration globale est réclamée comme une descente."""
    sortie: dict[str, float] = {}
    for c in correspondances:
        if c.retenue and c.siren and c.siren != tete and c.ligne.controlee:
            sortie[c.siren] = max(sortie.get(c.siren, 0.0), c.ligne.taux)
    return sortie


def groupes_a_document(
    con: duckdb.DuckDBPyConnection, registre: Path, dossier_documents: Path
) -> tuple[list[_GroupeDocument], int, int]:
    """Étapes 2 et 3 : la carto de chaque groupe à document. Rend aussi le nombre de documents en
    vigueur et le nombre en échec."""
    documents = documents_en_vigueur(con)
    lus, echecs = _lire_documents(documents, dossier_documents)
    actives = _actives(con, (t for t, _, _, _ in lus))
    retenus = []
    for tete, fichier, lignes, passage in lus:
        if tete in actives:
            retenus.append((tete, fichier, lignes, passage))
        else:
            log.warning("pays : tête de document sans siège actif, groupe ignoré")
            echecs += 1
    if not retenus:
        return [], len(documents), echecs
    tetes = [t for t, _, _, _ in retenus]
    noms = dict(con.execute(
        "select siren, nom from sieges where siren in (select unnest($s))", {"s": tetes}
    ).fetchall())  # fmt: skip
    resultats = correspondre_plusieurs(con, [(t, li) for t, _, li, _ in retenus])
    groupes = []
    for (tete, fichier, lignes, passage), res in zip(retenus, resultats, strict=True):
        try:
            carto = cartographier(
                reglages_tete_seule(tete, noms.get(tete)),
                registre,
                perimetre=PerimetrePublie(fichier, tuple(lignes)),
                correspondances=res,
            )
        except Exception as exc:
            log.error("pays : moteur en échec pour un groupe (%s)", type(exc).__name__)
            echecs += 1
            continue
        groupes.append(_GroupeDocument(tete, fichier, carto, _taux_integration_globale(res, tete), passage))
    return groupes, len(documents), echecs


_FICHE_CAISSE = """
select s.siren, s.siret_siege, s.nom, s.cj, s.naf, s.tranche, o.salaries, o.opposition_prospection,
       o.non_diffusible, s.adresse_cle, s.commune
  from sieges s left join societes o on o.siren = s.siren
 where s.siren in (select unnest($s))
"""


def avec_caisses(con: duckdb.DuckDBPyConnection, groupes: Sequence[_GroupeDocument]) -> list[_GroupeDocument]:
    """Étape 4 : chaque groupe dont la tête est une caisse de Crédit Mutuel reçoit ses caisses
    locales (`pays.mutualiste`), sous la tête, sauf celles que sa carto a déjà."""
    sortie = []
    for g in groupes:
        dans = {s.siren for s in g.carto.societes}
        trouvees = [c for c in mutualiste.caisses(con, g.tete, g.passage) if c.siren not in dans]
        if not trouvees:
            sortie.append(g)
            continue
        tete = next(s for s in g.carto.societes if s.siren == g.tete)
        fiches = {r[0]: r for r in con.execute(_FICHE_CAISSE, {"s": [c.siren for c in trouvees]}).fetchall()}
        ajout = []
        for c in trouvees:
            fiche = fiches[c.siren]
            _, siret, nom, cj, naf, tranche, salaries, opposition, non_diffusible, adresse, commune = fiche
            ciblable, raison_ciblable = ciblable_par_fiche(cj, naf, tranche, salaries)
            ajout.append(Societe(
                siren=c.siren, nom=nom, niveau=1, siret_siege=siret, maison_mere_siren=g.tete,
                maison_mere_nom=tete.nom, preuve=c.preuve, confiance="B",
                pourquoi_dans_le_groupe="Caisse locale de la fédération (groupe mutualiste)",
                indices=("mutualiste",), ciblable=ciblable, raison_ciblable=raison_ciblable, naf=naf,
                forme_juridique=None if cj is None else str(cj), tranche_effectif=tranche,
                salaries_rne=salaries, opposition_prospection=bool(opposition),
                non_diffusible=non_diffusible, adresse_siege=adresse, commune=commune,
                compte_de_rattachement=c.siren if ciblable else tete.compte_de_rattachement,
            ))  # fmt: skip
        carto = replace(g.carto, societes=(*g.carto.societes, *ajout))
        sortie.append(replace(g, carto=carto, caisses=len(ajout)))
    return sortie


# --- Groupes à document -------------------------------------------------------------------------


def _reclamations(groupes: Sequence[_GroupeDocument]) -> list[Reclamation]:
    sortie = []
    for g in groupes:
        for s in g.carto.societes:
            if s.siren in g.inscrites:
                sortie.append(Reclamation(g.tete, s.siren, "inscription", taux=g.inscrites[s.siren]))
            else:
                sortie.append(Reclamation(g.tete, s.siren, "descente", niveau=s.niveau))
    return sortie


def _lignes_documents(groupes: Sequence[_GroupeDocument]) -> tuple[list[Ligne], dict[str, str | None]]:
    """Départage des groupes à document, puis une ligne par société gardée. Rend aussi le parent de
    chaque groupe."""
    reclamations = _reclamations(groupes)
    tetes = {g.tete for g in groupes}
    descriptions = [
        # La taille sans les caisses locales : 1 200 caisses ne doivent pas faire gagner à un groupe
        # mutualiste les égalités de la règle 4 du départage (revue adverse T049).
        Groupe(g.tete, len(g.carto.societes) - g.caisses, frozenset(set(g.inscrites) & (tetes - {g.tete})))
        for g in groupes
    ]
    resultat = departager(reclamations, descriptions)
    groupe_de = {r.societe: r.groupe for r in resultat.societes}
    raison_de = {r.societe: r.raison for r in resultat.societes}
    # La tête d'un groupe à document reste dans son groupe, même si le départage la range ailleurs
    # (deux documents qui s'inscrivent l'un l'autre, ou deux documents qui inscrivent la même tête) :
    # sinon le groupe perd sa tête et les mères peuvent tourner en boucle. Le groupe qui l'inscrit
    # devient son parent, par la règle 1 de T047.
    for tete in tetes:
        if groupe_de.get(tete) != tete:
            groupe_de[tete] = tete
            raison_de[tete] = "tête de son propre groupe à document : elle y reste"
    parent_de = {g.tete: g.parent for g in resultat.groupes if g.tete in tetes}
    fiches = {g.tete: {s.siren: s for s in g.carto.societes} for g in groupes}
    maniere_de: dict[tuple[str, str], Maniere] = {(r.groupe, r.societe): r.maniere for r in reclamations}

    def mere_dans(fiche: Mapping[str, Societe], depart: str, cible: str) -> tuple[str, bool]:
        """Le plus proche ancêtre de `depart`, dans la carto `fiche`, rangé dans le groupe `cible`.
        Rend aussi si c'est la mère directe."""
        x = fiche[depart].maison_mere_siren
        directe = True
        vus = {depart}
        while x and x not in vus and groupe_de.get(x) != cible:
            vus.add(x)
            x = fiche[x].maison_mere_siren if x in fiche else None
            directe = False
        if x and groupe_de.get(x) == cible:
            return x, directe
        return cible, False  # à défaut, la tête du groupe

    lignes = []
    for siren, g in groupe_de.items():
        s = fiches[g][siren]
        preuve, confiance = s.preuve, s.confiance
        mere: str | None = None
        if siren == g:
            parent = parent_de.get(g)
            if parent and siren in fiches[parent]:
                mere, directe = mere_dans(fiches[parent], siren, parent)
                ancienne = fiches[parent][siren]
                preuve, confiance = ancienne.preuve, ancienne.confiance
                if not directe:
                    mere_directe = ancienne.maison_mere_siren
                    preuve, confiance = _deduite(mere_directe, groupe_de.get(mere_directe or ""))
        else:
            mere, directe = mere_dans(fiches[g], siren, g)
            if not directe:
                preuve, confiance = _deduite(s.maison_mere_siren, groupe_de.get(s.maison_mere_siren or ""))
        raison = "tête du groupe" if siren == g else s.pourquoi_dans_le_groupe
        lignes.append(Ligne(
            siren=siren, groupe=g, nom=s.nom, mere=mere, niveau=0, preuve=preuve, confiance=confiance,
            raison=raison, maniere=maniere_de[(g, siren)], raison_departage=raison_de[siren],
            ciblable=s.ciblable, raison_ciblable=s.raison_ciblable,
            opposition_prospection=bool(s.opposition_prospection), non_diffusible=bool(s.non_diffusible),
        ))  # fmt: skip
    return lignes, parent_de


def _deduite(mere_directe: str | None, groupe: str | None) -> tuple[str, Confiance]:
    if mere_directe and groupe:
        return f"Déduit : maison mère directe {mere_directe} rangée dans le groupe {groupe}", "C"
    return "Déduit : rattachée à la tête du groupe", "C"


# --- Arbres -------------------------------------------------------------------------------------

_ARBRE = """
select a.siren, a.mere, a.role_mere from arbre a
 where a.siren in (select siren from sieges) and a.mere in (select siren from sieges)
"""

_FICHES = """
select s.siren, s.nom, s.cj, s.naf, s.tranche, o.salaries, o.opposition_prospection, o.non_diffusible
  from sieges s
  left join societes o on o.siren = s.siren
 where s.siren in (select siren from membres)
"""


def _lignes_arbres(con: duckdb.DuckDBPyConnection, pris: set[str]) -> list[Ligne]:
    """Étape 5 : les groupes des arbres, entre sociétés actives qu'aucun groupe à document ne garde."""
    mere_de: dict[str, str] = {}
    role_de: dict[str, str] = {}
    for siren, mere, role in con.execute(_ARBRE).fetchall():
        if siren in pris or mere in pris:
            continue
        mere_de[siren] = mere
        role_de[siren] = role
    hauts = arbre.sommets(mere_de)
    membres = set(mere_de) | set(mere_de.values())
    con.register("membres", pa.table({"siren": pa.array(sorted(membres), pa.string())}))
    try:
        fiches = {r[0]: r for r in con.execute(_FICHES).fetchall()}
    finally:
        con.unregister("membres")
    lignes = []
    for siren in sorted(membres):
        sommet, profondeur, _ = hauts.get(siren, (siren, 0, False))
        _, nom, cj, naf, tranche, salaries, opposition, non_diffusible = fiches[siren]
        if siren == sommet:
            mere, preuve, raison = None, "Tête du groupe", "tête de l'arbre du registre"
            ciblable, raison_ciblable = True, "Société mère du groupe"
        else:
            mere = mere_de[siren]
            role = role_de[siren]
            preuve = f"Mandat au registre : {ROLE_LABEL.get(role, f'rôle {role}')}"
            raison = "arbre du registre"
            ciblable, raison_ciblable = ciblable_par_fiche(cj, naf, tranche, salaries)
        lignes.append(Ligne(
            siren=siren, groupe=sommet, nom=nom, mere=mere, niveau=profondeur, preuve=preuve, confiance="A",
            raison=raison, maniere="arbre", raison_departage=None, ciblable=ciblable,
            raison_ciblable=raison_ciblable, opposition_prospection=bool(opposition),
            non_diffusible=bool(non_diffusible),
        ))  # fmt: skip
    return lignes


# --- Assemblage ---------------------------------------------------------------------------------


def _niveaux(lignes: list[Ligne]) -> list[Ligne]:
    """Niveau de chaque société sous la tête de son groupe, d'après les mères retenues. La mère d'une
    tête (sous-groupe) est hors de son groupe : elle ne compte pas."""
    par_siren = {li.siren: li for li in lignes}
    niveau: dict[str, int] = {}

    def de(siren: str) -> int:
        chemin = []
        x = siren
        while x not in niveau:
            li = par_siren[x]
            if li.siren == li.groupe or li.mere not in par_siren or li.mere in chemin:
                niveau[x] = 0
                break
            chemin.append(x)
            x = li.mere
        n = niveau[x]
        for y in reversed(chemin):
            n += 1
            niveau[y] = n
        return niveau[siren]

    return [replace(li, niveau=de(li.siren)) for li in lignes]


def ranger(con: duckdb.DuckDBPyConnection, registre: Path, dossier_documents: Path) -> Resultat:
    """Étapes 2 à 5, sur un registre ouvert en lecture (l'arbre doit être à jour)."""
    date_donnees = date_des_donnees(con)
    groupes_doc, documents, echecs = groupes_a_document(con, registre, dossier_documents)
    groupes_doc = avec_caisses(con, groupes_doc)
    lignes_doc, parent_de = _lignes_documents(groupes_doc) if groupes_doc else ([], {})
    lignes_doc = _niveaux(lignes_doc)
    pris = {li.siren for li in lignes_doc}
    lignes_arbre = _lignes_arbres(con, pris)
    taille: dict[str, int] = {}
    for li in (*lignes_doc, *lignes_arbre):
        taille[li.groupe] = taille.get(li.groupe, 0) + 1
    noms = {li.siren: li.nom for li in (*lignes_doc, *lignes_arbre)}
    tetes_doc = {g.tete for g in groupes_doc}
    meres = meres_etrangeres(con)
    groupes = [
        LigneGroupe(tete=g.tete, nom=noms.get(g.tete), taille=taille[g.tete], document=g.fichier,
                    mutualiste=g.mutualiste, parent=parent_de.get(g.tete), date_donnees=date_donnees,
                    mere_etrangere=meres.get(g.tete, (None, None))[0],
                    pays_mere=meres.get(g.tete, (None, None))[1])
        for g in groupes_doc
    ] + [
        LigneGroupe(tete=t, nom=noms.get(t), taille=n, document=None, mutualiste=False, parent=None,
                    date_donnees=date_donnees)
        for t, n in sorted(taille.items())
        if t not in tetes_doc
    ]  # fmt: skip
    societes = sorted((*lignes_doc, *lignes_arbre), key=lambda li: li.siren)
    return Resultat(tuple(groupes), tuple(societes), documents, echecs, date_donnees)


# --- Écriture -----------------------------------------------------------------------------------


def _colonnes(lignes: Sequence[Any], champs: Sequence[str]) -> dict[str, list[Any]]:
    return {c: [getattr(li, c) for li in lignes] for c in champs}


def ecrire(resultat: Resultat, sortie: Path, duree_s: float, maintenant: datetime | None = None) -> None:
    """Écrit `pays.duckdb` à côté, puis le renomme : un échec laisse le fichier précédent."""
    temporaire = sortie.with_name(f"{sortie.name}.{os.getpid()}.en-construction")
    _retirer(temporaire)
    try:
        con = duckdb.connect(str(temporaire))
        try:
            con.execute(DDL)
            champs_g = [f.name for f in fields(LigneGroupe)]
            champs_s = [f.name for f in fields(Ligne)]
            for table, lignes, champs in (
                ("pays_groupes", resultat.groupes, champs_g),
                ("pays_societes", resultat.societes, champs_s),
            ):
                if not lignes:
                    continue
                donnees = pa.table(_colonnes(lignes, champs))
                con.register("donnees", donnees)
                try:
                    con.execute(f"insert into {table} by name select * from donnees")
                finally:
                    con.unregister("donnees")
            con.execute(
                "insert into pays_bilan values (?, ?, ?, ?, ?, ?, ?)",
                [maintenant or datetime.now(UTC), resultat.date_donnees, len(resultat.groupes),
                 len(resultat.societes), resultat.documents, resultat.documents_en_echec, duree_s],
            )  # fmt: skip
            con.execute("checkpoint")
        finally:
            con.close()
        # Un WAL laissé par un ancien lecteur en écriture serait rejoué sur le nouveau fichier.
        sortie.with_name(sortie.name + ".wal").unlink(missing_ok=True)
        os.replace(temporaire, sortie)
    except BaseException:
        _retirer(temporaire)
        raise


def _retirer(chemin: Path) -> None:
    for c in (chemin, chemin.with_name(chemin.name + ".wal")):
        c.unlink(missing_ok=True)


# --- Lancement ----------------------------------------------------------------------------------


def calculer(dossier: Path) -> Bilan:
    """Étapes 2 à 6 : lit le registre en lecture seule, écrit `pays.duckdb`. N'écrit pas le journal."""
    debut = time.monotonic()
    registre = dossier / NOM_REGISTRE
    con = ouvrir_registre(registre)
    try:
        resultat = ranger(con, registre, dossier / DOSSIER_DOCUMENTS)
    finally:
        con.close()
    duree = time.monotonic() - debut
    ecrire(resultat, dossier / NOM_PAYS, duree)
    return Bilan(len(resultat.groupes), len(resultat.societes), resultat.documents,
                 resultat.documents_en_echec, duree)  # fmt: skip


def _connecter(chemin: Path) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(chemin))


def lancer(dossier: Path, ouvrir: Callable[[Path], duckdb.DuckDBPyConnection] = _connecter) -> Bilan:
    """Tout le calcul, journal compris. Le registre n'est ouvert en écriture qu'au début (journal,
    arbre) et à la fin (journal) : entre les deux, la recherche peut le lire.

    `ouvrir` : ouverture du registre en écriture (le travail `pays` réessaie si un lecteur le tient).
    """
    registre = dossier / NOM_REGISTRE
    if not registre.is_file():
        raise FileNotFoundError("registre introuvable")
    con = ouvrir(registre)
    try:
        id_maj = journal.ouvrir(con, SOURCE)
        try:
            arbre.recalculer_si_change(con)
            con.execute("checkpoint")
        except BaseException as exc:
            _echouer(con, id_maj, exc, "pendant l'arbre")
            raise
    finally:
        con.close()
    try:
        bilan = calculer(dossier)
    except BaseException as exc:
        # L'erreur d'origine remonte, même si le journal ne peut pas être écrit.
        _journaliser(ouvrir, registre, lambda c, e=exc: _echouer(c, id_maj, e, "pendant le calcul"))
        raise
    # `pays.duckdb` est déjà neuf : un journal qu'on ne peut pas écrire ne fait pas échouer le calcul.
    _journaliser(
        ouvrir, registre, lambda c: journal.terminer(c, id_maj, ajoutes=bilan.societes, fermes=bilan.groupes)
    )
    log.info(
        "pays : %s groupes, %s sociétés rangées, %s documents dont %s en échec, %.0f s",
        bilan.groupes, bilan.societes, bilan.documents, bilan.documents_en_echec, bilan.duree_s,
    )  # fmt: skip
    return bilan


def _journaliser(
    ouvrir: Callable[[Path], duckdb.DuckDBPyConnection],
    registre: Path,
    ecrire_ligne: Callable[[duckdb.DuckDBPyConnection], None],
) -> None:
    """Écrit dans le journal au mieux : registre occupé ou erreur DuckDB, l'échec est seulement loggé."""
    try:
        con = ouvrir(registre)
    except Exception as exc:
        log.error("pays : journal non écrit, registre inaccessible (%s)", type(exc).__name__)
        return
    try:
        ecrire_ligne(con)
        con.execute("checkpoint")
    except duckdb.Error as exc:
        log.error("pays : journal non écrit (%s)", type(exc).__name__)
    finally:
        con.close()


def _echouer(con: duckdb.DuckDBPyConnection, id_maj: int, exc: BaseException, etape: str) -> None:
    try:
        journal.echouer(con, id_maj, f"{type(exc).__name__} {etape} de la carto du pays")
    except duckdb.Error:
        pass


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    dossier = Path(os.environ.get("CARTOFR_DATA", "data"))
    try:
        bilan = lancer(dossier)
    except FileNotFoundError:
        print(f"Registre introuvable dans {dossier}.", file=sys.stderr)
        return 2
    print(
        f"{bilan.groupes} groupes, {bilan.societes} sociétés rangées, {bilan.documents} documents"
        f" dont {bilan.documents_en_echec} en échec, {bilan.duree_s:.0f} s"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
