"""Couverture de la carto du pays (T052, SC-008) : sociétés actives rangées, groupes cotés sans document.

Usage, depuis la racine du dépôt :
    CARTOFR_DATA=data .venv/bin/python worker/scripts/mesure_couverture.py [--cotees out/cotees.csv]

Entrées :
- `<CARTOFR_DATA>/registre.duckdb` (les sociétés actives : `sieges`) et `<CARTOFR_DATA>/pays.duckdb`
  (ou CARTOFR_PAYS), lus en lecture seule ;
- avec `--cotees` : la liste des sociétés cotées à Paris, un CSV avec une colonne `SIREN` ou
  `siren` (fourni par Loïc, hors git).
Sortie :
- sociétés actives, rangées dans un groupe de 2 sociétés ou plus, seules ; la part rangée ;
- avec `--cotees` : pour chaque société cotée, le groupe de la carto du pays où elle est rangée,
  et si ce groupe a un document de périmètre. Puis la liste des groupes cotés sans document
  (SIREN et nom de la tête : des sociétés, jamais une personne), et les sociétés cotées absentes
  du registre actif.
Code de sortie : 0, ou 2 si un fichier manque ou si la liste des cotées n'a aucun SIREN lisible.
C'est une mesure : aucun seuil.
"""

import argparse
import csv
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import duckdb


@dataclass(frozen=True)
class Couverture:
    actives: int
    rangees: int  # actives dans un groupe de 2 sociétés ou plus

    @property
    def part(self) -> float:
        return self.rangees / self.actives if self.actives else 0.0


@dataclass(frozen=True)
class GroupeCote:
    tete: str
    nom: str | None
    document: bool
    cotees: int  # sociétés cotées rangées dans ce groupe


@dataclass(frozen=True)
class Cotation:
    groupes: list[GroupeCote]
    seules: list[str]  # cotées actives qui ne sont dans aucun groupe : sans document par définition
    absentes: list[str]  # cotées sans siège actif au registre (inconnues, fermées)

    @property
    def avec_document(self) -> list[GroupeCote]:
        return [g for g in self.groupes if g.document]

    @property
    def sans_document(self) -> list[GroupeCote]:
        return [g for g in self.groupes if not g.document]


def ouvrir(registre: Path, pays: Path) -> duckdb.DuckDBPyConnection:
    """Le registre en lecture seule, la carto du pays attachée sous le nom `pays`."""
    con = duckdb.connect(str(registre), read_only=True)
    chemin = str(pays).replace("'", "''")  # attach ne prend pas de paramètre
    con.execute(f"attach '{chemin}' as pays (read_only)")
    return con


def couverture(con: duckdb.DuckDBPyConnection) -> Couverture:
    """Sociétés actives (un siège SIRENE) et, parmi elles, celles rangées dans un groupe."""
    (actives,) = con.execute("select count(distinct siren) from sieges").fetchone() or (0,)
    (rangees,) = con.execute(
        "select count(*) from pays.pays_societes where siren in (select siren from sieges)"
    ).fetchone() or (0,)
    return Couverture(int(actives), int(rangees))


def cotation(con: duckdb.DuckDBPyConnection, cotees: list[str]) -> Cotation:
    """Le groupe de chaque société cotée, et si ce groupe a un document de périmètre."""
    uniques = sorted(set(cotees))
    lignes = con.execute(
        """
        with c(siren) as (select unnest($sirens::varchar[]))
        select c.siren, s.groupe, g.nom, g.document is not null and g.document <> '',
               c.siren in (select siren from sieges)
          from c
          left join pays.pays_societes s on s.siren = c.siren
          left join pays.pays_groupes g on g.tete = s.groupe
        """,
        {"sirens": uniques},
    ).fetchall()
    groupes: dict[str, GroupeCote] = {}
    seules, absentes = [], []
    for siren, tete, nom, document, active in lignes:
        if tete is None:
            (seules if active else absentes).append(str(siren))
            continue
        avant = groupes.get(tete)
        groupes[tete] = GroupeCote(str(tete), nom, bool(document), (avant.cotees if avant else 0) + 1)
    return Cotation(sorted(groupes.values(), key=lambda g: g.tete), sorted(seules), sorted(absentes))


def lire_cotees(chemin: Path) -> list[str]:
    """Les SIREN d'un CSV à colonne `SIREN` (casse indifférente ; séparateur `,`, `;` ou tabulation ;
    une seule colonne possible), tous les espaces retirés, insécables compris."""
    with chemin.open(newline="", encoding="utf-8-sig") as f:
        entete = f.readline()
        f.seek(0)
        separateur = max(",;\t", key=entete.count) if any(c in entete for c in ",;\t") else ","
        lecteur = csv.reader(f, delimiter=separateur)
        colonnes = [c.strip().lower() for c in next(lecteur, [])]
        if "siren" not in colonnes:
            return []
        rang = colonnes.index("siren")
        sortie = []
        for ligne in lecteur:
            siren = "".join(ligne[rang].split()) if rang < len(ligne) else ""
            if len(siren) == 9 and siren.isdigit():
                sortie.append(siren)
    return sortie


def nombre(n: int) -> str:
    """« 7 827 096 »."""
    return f"{n:,}".replace(",", " ")


def pourcent(x: float) -> str:
    """« 12,0 % »."""
    return f"{x:.1%}".replace(".", ",").replace("%", " %")


def main(arguments: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Couverture de la carto du pays (T052, SC-008).")
    p.add_argument("--cotees", type=Path, help="CSV des sociétés cotées à Paris, colonne SIREN")
    a = p.parse_args(arguments)
    data = Path(os.environ.get("CARTOFR_DATA", "data"))
    registre = data / "registre.duckdb"
    pays = Path(os.environ["CARTOFR_PAYS"]) if os.environ.get("CARTOFR_PAYS") else data / "pays.duckdb"
    manquants = [str(c) for c in (registre, pays, a.cotees) if c is not None and not c.is_file()]
    if manquants:
        print("Fichiers manquants : " + ", ".join(manquants), file=sys.stderr)
        return 2

    sirens = lire_cotees(a.cotees) if a.cotees else []
    if a.cotees and not sirens:
        print(f"Aucun SIREN lu dans {a.cotees} : il faut une colonne SIREN.", file=sys.stderr)
        return 2
    con = ouvrir(registre, pays)
    try:
        c = couverture(con)
        cotes = cotation(con, sirens) if a.cotees else None
    finally:
        con.close()
    print(
        f"Sociétés actives : {nombre(c.actives)} ; dans un groupe : {nombre(c.rangees)}"
        f" ({pourcent(c.part)}) ; seules : {nombre(c.actives - c.rangees)}"
    )
    if cotes is None:
        print("Groupes cotés : non mesurés (--cotees absent).")
        return 0
    print(
        f"Groupes cotés : {len(cotes.groupes)}, dont {len(cotes.avec_document)} avec document et"
        f" {len(cotes.sans_document)} sans ; cotées seules (sans groupe ni document) : {len(cotes.seules)} ;"
        f" cotées absentes du registre actif : {len(cotes.absentes)}"
    )
    for g in cotes.sans_document:
        print(f"  sans document : {g.tete} {g.nom or ''} ({g.cotees} cotée(s))")
    for siren in cotes.seules:
        print(f"  seule : {siren}")
    for siren in cotes.absentes:
        print(f"  absente : {siren}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
