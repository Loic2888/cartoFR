"""Étape 4 : chercher dans tout SIRENE les sociétés actives dont le nom commence par une marque du groupe.

Repris de `brand_scan.py` (prototype). Lit la table `unites_legales` du registre au lieu
du parquet SIRENE, et rend les candidates en mémoire au lieu d'écrire un CSV.

Usage :
    con = duckdb.connect(str(registre), read_only=True)
    candidates = chercher_candidates(con, reglages)
Entrées : une connexion au registre, les réglages du groupe (`marques_sures`, `marques_ambigues`).
Sorties : une liste de `Candidate`, une par SIREN.
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.compute as _pc

# Formes juridiques qu'on accepte devant la marque : « STE CIVILE CHATEAU YQUEM » est candidate.
PREFIXES = [
    "SOCIETE CIVILE IMMOBILIERE", "SOCIETE CIVILE", "STE CIVILE", "SOCIETE", "STE", "SCI", "SCEA", "SCE",
    "GFA", "GFV", "GAEC", "EARL", "SA", "SAS", "SASU", "SARL", "EURL", "SNC", "SC", "GIE", "SE", "SCA", "SOC",
    "CIE", "COMPAGNIE", "ETS", "ETABLISSEMENTS", "LES", "LE", "LA", "L", "DES", "DU", "DE", "D",
]  # fmt: skip

TABLE_NOMS = "noms_normalises"
pc: Any = _pc  # fonctions générées à l'exécution : inconnues du vérificateur de types


@dataclass(frozen=True)
class Candidate:
    """Une société dont un nom commence par une marque du groupe."""

    siren: str
    marque: str  # la marque, normalisée
    type_marque: str  # 'sure' ou 'ambigue'


def norm(s: str | None) -> str:
    """Majuscules sans accents, « & » lu « ET », tout ce qui n'est ni lettre ni chiffre devient une espace."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper()
    s = s.replace("&", " ET ")
    return re.sub(r"[^A-Z0-9]+", " ", s).strip()


def norm_arrow(noms: pa.Array) -> pa.Array:
    """`norm` sur toute une colonne d'un coup, même résultat, pour les 9 millions de noms de SIRENE.

    Mêmes étapes que `norm` : décomposition NFKD, caractères non ASCII retirés, majuscules,
    « & » lu « ET », le reste réduit à des espaces simples, espaces de bord retirées.
    """
    n = pc.utf8_normalize(pc.fill_null(noms, ""), "NFKD")
    n = pc.replace_substring_regex(n, r"[^\x00-\x7F]", "")
    n = pc.ascii_upper(n)
    n = pc.replace_substring(n, "&", " ET ")
    n = pc.replace_substring_regex(n, r"[^A-Z0-9]+", " ")
    return pc.utf8_trim(n, " ")


def marques(reglages: dict[str, Any]) -> list[tuple[str, str]]:
    """Les marques du groupe, normalisées, avec leur type : les sûres d'abord, puis les ambiguës."""
    return [(norm(b), "sure") for b in reglages["marques_sures"]] + [
        (norm(b), "ambigue") for b in reglages["marques_ambigues"]
    ]


def preparer_noms(con: duckdb.DuckDBPyConnection) -> None:
    """Noms normalisés des personnes morales actives, dans la table `noms_normalises` de la connexion.

    Les entrepreneurs individuels (catégorie 1000) ne sont pas dans `unites_legales`.
    Les noms sont normalisés côté Arrow, d'un bloc, puis la table est enregistrée sur la
    connexion : le registre, ouvert en lecture seule, n'est pas modifié.
    """
    table = con.execute("""
        select siren, coalesce(denomination, '') n0, coalesce(sigle, '') n1,
               coalesce(denomination_usuelle_1, '') n2
        from unites_legales
        where etat_administratif = 'A' and fin is null and denomination is not null
    """).to_arrow_table()
    noms = pa.table({
        "siren": table.column("siren"),
        **{col: norm_arrow(table.column(col).combine_chunks()) for col in ("n0", "n1", "n2")},
    })  # fmt: skip
    con.register(TABLE_NOMS, noms)


def chercher_candidates(con: duckdb.DuckDBPyConnection, reglages: dict[str, Any]) -> list[Candidate]:
    """Toutes les sociétés actives dont la dénomination, le sigle ou l'enseigne commence par une marque.

    Une société qui répond à plusieurs marques garde la plus longue (la plus précise) ;
    à longueur égale, la première dans l'ordre des réglages.
    """
    preparer_noms(con)
    prefixe = "(?:(?:" + "|".join(PREFIXES) + ") )*"
    lignes: list[tuple[str, str, str]] = []
    for marque, type_marque in marques(reglages):
        motif = "^" + prefixe + re.escape(marque) + "( |$)"
        for (siren,) in con.execute(
            f"select siren from {TABLE_NOMS}"
            " where regexp_matches(n0, $m) or regexp_matches(n1, $m) or regexp_matches(n2, $m)"
            " order by siren",
            {"m": motif},
        ).fetchall():
            lignes.append((siren, marque, type_marque))
    lignes.sort(key=lambda ligne: len(ligne[1]), reverse=True)  # tri stable
    vues: set[str] = set()
    candidates = []
    for siren, marque, type_marque in lignes:
        if siren not in vues:
            vues.add(siren)
            candidates.append(Candidate(siren, marque, type_marque))
    return candidates
