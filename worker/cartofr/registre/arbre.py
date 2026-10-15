"""Arbre à une mère du registre (T045) : pour chaque société, sa mère et son sommet.

Usage, depuis la racine du dépôt :
    CARTOFR_DATA=data .venv/bin/python -m cartofr.registre.arbre

Entrées : la table `liens` de `<CARTOFR_DATA>/registre.duckdb`. `dirigeants_personnes`
n'est jamais lue.
Sorties : la table `arbre`, remplacée en entier dans une transaction, et une ligne
`arbre` dans `mises_a_jour`. Pour cette source, `ajoutes` est le nombre de sociétés
dont le sommet a changé et `fermes` vaut 0.

Règle, mesurée le 2026-10-15 (`rapport.md`) :
- seuls comptent les liens actifs (`fin` vide) entre deux SIREN différents ;
- un parent qui a plus de `MAX_ENFANTS` liens actifs n'est la mère de personne : gérants
  de défiscalisation, sociétés de gestion. On compte des lignes de `liens`, tous rôles et
  doublons du RNE compris, comme la mesure. Compter les enfants distincts ne change presque
  rien (VINCI Construction : 187 au lieu de 188 sociétés de la référence, 2026-10-15) ;
- la mère est le parent du rôle le plus fort (`RANGS`). Tout autre rôle est écarté,
  notamment les commissaires aux comptes (71, 72, 77). À rôle égal, le parent qui a le
  plus de liens actifs l'emporte, puis le plus petit SIREN ;
- le sommet se trouve en remontant de mère en mère jusqu'à une société sans mère. Dans
  une boucle, c'est le plus petit SIREN de la boucle, pour toutes les sociétés qui y
  mènent, marquées `boucle`. `profondeur` compte les liens jusqu'au sommet. Le sommet d'une
  boucle a donc une ligne, avec `profondeur` 0 : c'est la seule où `sommet = siren`.

Recalcul (`recalculer_si_change`, appelé par la synchro nocturne) : seulement si le RNE a
ajouté ou fermé une ligne depuis le dernier calcul réussi, ou si le dernier calcul n'a pas
réussi. SIRENE ne touche jamais `liens`. Une ligne `rne_diff` en `echec` compte aussi : ses
pages déjà validées ont bien changé `liens` (arrêt sur quota).

La table est dérivée : elle ne devient jamais une source. L'historique reste dans `liens`,
où rien n'est effacé (principe 4). Aucun nom n'est lu ni écrit : la sortie ne porte que
des volumes.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pyarrow as pa

from cartofr.registre import journal, synchro_rne
from cartofr.registre.schema import DDL_ARBRE

SOURCE = "arbre"
NOM_REGISTRE = "registre.duckdb"
MAX_ENFANTS = 500

# Rang de chaque rôle retenu : le plus petit l'emporte. Libellés dans `moteur.ROLE_LABEL`.
RANGS: dict[str, int] = {
    "73": 1,  # président
    "51": 2,  # président du conseil d'administration
    "30": 2,  # gérant
    "28": 3,  # gérant et associé indéfiniment et solidairement responsable
    "29": 3,  # gérant et associé indéfiniment responsable
    "131": 3,  # associé commandité
    "74": 4,  # associé indéfiniment et solidairement responsable
    "75": 4,  # associé indéfiniment responsable
    "53": 5,
    "65": 6,  # administrateur
    "64": 6,  # membre du conseil de surveillance
    "11": 7,  # membre
    "99": 8,  # autre
}

# Les rangs entrent par une table de valeurs, le seuil par paramètre : aucune concaténation.
_MERES = """
with actifs as (
    select parent, enfant, role from liens where fin is null and parent <> enfant
),
enfants as (
    select parent, count(*) as nombre from actifs group by parent
),
rangs as (
    select * from (values {valeurs}) as r(role, rang)
)
select a.enfant, a.parent, a.role
from actifs a
join rangs r on r.role = a.role
join enfants e on e.parent = a.parent
where e.nombre <= $max_enfants
qualify row_number() over (partition by a.enfant order by r.rang, e.nombre desc, a.parent, a.role) = 1
""".format(valeurs=", ".join(f"('{role}', {rang})" for role, rang in RANGS.items()))


@dataclass(frozen=True)
class Ligne:
    siren: str
    mere: str
    role_mere: str
    sommet: str
    profondeur: int
    boucle: bool


@dataclass(frozen=True)
class Bilan:
    lignes: int
    sommets_changes: int
    boucles: int
    duree_s: float


def meres(con: duckdb.DuckDBPyConnection, max_enfants: int = MAX_ENFANTS) -> dict[str, tuple[str, str]]:
    """La mère retenue de chaque société qui en a une : siren -> (mère, rôle)."""
    lignes = con.execute(_MERES, {"max_enfants": max_enfants}).fetchall()
    return {enfant: (parent, role) for enfant, parent, role in lignes}


def sommets(mere_de: dict[str, str]) -> dict[str, tuple[str, int, bool]]:
    """Sommet, profondeur et boucle de chaque société de `mere_de` (siren -> mère).

    Le résultat ne dépend que de `mere_de`, pas de l'ordre de ses clés.
    """
    resultat: dict[str, tuple[str, int, bool]] = {}
    for depart in mere_de:
        if depart in resultat:
            continue
        chemin: list[str] = []
        position: dict[str, int] = {}
        x = depart
        while x in mere_de and x not in resultat and x not in position:
            position[x] = len(chemin)
            chemin.append(x)
            x = mere_de[x]
        if x in position:
            # Boucle : chemin[i:] en fait le tour. Sommet = son plus petit SIREN.
            i = position[x]
            tour = chemin[i:]
            sommet = min(tour)
            k = tour.index(sommet)
            for j, y in enumerate(tour):
                resultat[y] = (sommet, (k - j) % len(tour), True)
            reste = chemin[:i]
        else:
            reste = chemin
        # Chaque société du reste a sa mère juste au-dessus, déjà résolue (ou sans mère).
        for y in reversed(reste):
            m = mere_de[y]
            if m in resultat:
                s, p, b = resultat[m]
                resultat[y] = (s, p + 1, b)
            else:
                resultat[y] = (m, 1, False)
    return resultat


def calculer(con: duckdb.DuckDBPyConnection, max_enfants: int = MAX_ENFANTS) -> list[Ligne]:
    """Les lignes de l'arbre, sans rien écrire : marche sur un registre ouvert en lecture seule."""
    choisies = meres(con, max_enfants)
    hauts = sommets({siren: mere for siren, (mere, _) in choisies.items()})
    return [Ligne(siren, mere, role, *hauts[siren]) for siren, (mere, role) in sorted(choisies.items())]


def _table(lignes: list[Ligne]) -> pa.Table:
    return pa.table(
        {
            "siren": pa.array([x.siren for x in lignes], pa.string()),
            "mere": pa.array([x.mere for x in lignes], pa.string()),
            "role_mere": pa.array([x.role_mere for x in lignes], pa.string()),
            "sommet": pa.array([x.sommet for x in lignes], pa.string()),
            "profondeur": pa.array([x.profondeur for x in lignes], pa.int32()),
            "boucle": pa.array([x.boucle for x in lignes], pa.bool_()),
        }
    )


# Une société absente d'un côté est son propre sommet : son SIREN est lu de l'autre côté.
_SOMMETS_CHANGES = """
select count(*)
from arbre a
full outer join nouvel_arbre n on n.siren = a.siren
where coalesce(a.sommet, n.siren) is distinct from coalesce(n.sommet, a.siren)
"""


def recalculer(con: duckdb.DuckDBPyConnection, max_enfants: int = MAX_ENFANTS) -> Bilan:
    """Remplace la table `arbre` dans une transaction, et journalise le calcul.

    Un échec laisse l'ancienne table et une ligne `echec` dans `mises_a_jour`, puis relance
    l'exception. À appeler hors de toute transaction ouverte : elle ouvre la sienne.
    """
    debut = time.monotonic()
    con.execute(DDL_ARBRE)
    id_maj = journal.ouvrir(con, SOURCE)
    try:
        lignes = calculer(con, max_enfants)
        nouvel_arbre = _table(lignes)
        con.register("nouvel_arbre", nouvel_arbre)
        con.execute("begin transaction")
        try:
            ligne = con.execute(_SOMMETS_CHANGES).fetchone()
            changes = int(ligne[0]) if ligne else 0
            con.execute("delete from arbre")
            con.execute("insert into arbre by name select * from nouvel_arbre")
            con.execute("commit")
        except BaseException:
            con.execute("rollback")
            raise
        finally:
            con.unregister("nouvel_arbre")
    except BaseException as exc:
        # Arrêt du worker compris : la ligne ne reste pas `en_cours`. Si la base ne répond
        # plus, l'erreur d'origine passe avant celle du journal.
        try:
            journal.echouer(con, id_maj, f"{type(exc).__name__} pendant le calcul de l'arbre")
        except duckdb.Error:
            pass
        raise
    journal.terminer(con, id_maj, ajoutes=changes, fermes=0)
    return Bilan(len(lignes), changes, sum(x.boucle for x in lignes), time.monotonic() - debut)


_DERNIER_CALCUL = """
select id, statut from mises_a_jour where source = ? and statut <> 'en_cours' order by id desc limit 1
"""

_CHANGEMENTS = """
select coalesce(sum(coalesce(ajoutes, 0) + coalesce(fermes, 0)), 0)
from mises_a_jour
where id > ? and source = ?
"""


def a_recalculer(con: duckdb.DuckDBPyConnection) -> bool:
    """Vrai si l'arbre n'a jamais été calculé, si son dernier calcul a échoué, ou si le RNE a
    ajouté ou fermé une ligne depuis, quel que soit le statut de la ligne `rne_diff`.
    """
    dernier = con.execute(_DERNIER_CALCUL, [SOURCE]).fetchone()
    if dernier is None or dernier[1] != "succes":
        return True
    ligne = con.execute(_CHANGEMENTS, [dernier[0], synchro_rne.SOURCE]).fetchone()
    return ligne is not None and int(ligne[0]) > 0


def recalculer_si_change(con: duckdb.DuckDBPyConnection) -> Bilan | None:
    """Recalcule l'arbre si `a_recalculer` le dit, sinon rend `None`."""
    return recalculer(con) if a_recalculer(con) else None


def main(arguments: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parseur.parse_args(arguments)
    chemin = Path(os.environ.get("CARTOFR_DATA", "data")) / NOM_REGISTRE
    if not chemin.is_file():
        print(f"Registre introuvable : {chemin}", file=sys.stderr)
        return 2
    con = duckdb.connect(str(chemin))
    try:
        bilan = recalculer(con)
        con.execute("checkpoint")
    except Exception as erreur:
        print(f"Échec : {type(erreur).__name__}, voir la table mises_a_jour.", file=sys.stderr)
        return 1
    finally:
        con.close()
    print(
        f"arbre : {bilan.lignes} sociétés avec une mère, {bilan.sommets_changes} sommets changés, "
        f"{bilan.boucles} dans une boucle, {bilan.duree_s:.0f} s"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
