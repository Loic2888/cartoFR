"""Mesure du traitement mutualiste (T049, C1) : pistes pour ranger CMAF sans mêler ses fédérations.

Lecture seule. Rien n'est écrit dans le registre ni dans `pays.duckdb`.

Usage, depuis la racine du dépôt :
    CARTOFR_DATA=data CARTOFR_REFERENCES=basile .venv/bin/python \
        worker/scripts/mesure_mutualiste.py --deu <DEU CMAF : .zip ESEF de l'AMF ou .xhtml>
    (le DEU 2025, D.26-0233, paquet ESEF de la base BDIF de l'AMF : `out/perimetre/cmaf-deu-2025-esef.zip`)

Entrées :
- `<CARTOFR_DATA>/registre.duckdb` : sièges, liens, arbre (T045) ;
- `<CARTOFR_REFERENCES>/cargo_cmaf_entites.csv` : la carto de référence (données client, hors git) ;
- `--deu` (facultatif) : le document d'enregistrement universel de CMAF, tel que déposé à l'AMF
  (paquet ESEF). Sa note 3 « Périmètre de consolidation » est lue, puis réécrite au format VINCI
  (« <nom> France <taux> Intégration globale ») pour passer par l'extraction et la correspondance
  de T042 sans les modifier. Sans `--deu`, la piste du document est dite « en attente ».

Pistes mesurées (spécification de T049) :
- 0. tête seule, sans document : ce que fait la carto du pays aujourd'hui ;
- A. tête seule + le DEU comme périmètre publié (moteur, T043) ;
- B1. la caisse fédérale comme tête, et ce dont elle est « membre » (rôle 11), en direct ;
- B2. la caisse fédérale et les caisses de Crédit Mutuel membres du même GIE qu'elle ;
- C. le nom d'une fédération de CMAF dans la dénomination d'une caisse.
Pour chaque piste : sociétés de la référence retrouvées, « en plus », et caisses d'autres
fédérations entrées à tort (membres du GIE d'une autre fédération, ou sous la caisse fédérale
d'une autre fédération dans l'arbre). Des volumes et des noms de sociétés, aucun nom de personne.
"""

import argparse
import csv
import os
import re
import sys
import time
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

import duckdb

from cartofr.moteur import cartographier
from cartofr.pays.calcul import reglages_tete_seule
from cartofr.perimetre import PerimetrePublie, extraire

TETE = "588505354"  # Caisse Fédérale de Crédit Mutuel, tête de `config/cmaf.json`
# Les 14 fédérations de CMAF (DEU 2025, note 3a), telles qu'écrites dans les dénominations.
FEDERATIONS_CMAF = (
    "CENTRE EST EUROPE", "SUD EST", "ILE DE FRANCE", "SAVOIE MONT BLANC", "MIDI ATLANTIQUE",
    "LOIRE ATLANTIQUE", "CENTRE OUEST", "DU CENTRE", "DAUPHINE VIVARAIS", "MEDITERRANE",
    "NORMANDIE", "ANJOU", "MASSIF CENTRAL", "ANTILLES GUYANE", "NORD EUROPE",
)  # fmt: skip
# Fédérations hors CMAF, repérées dans le registre le 2026-10-20.
FEDERATIONS_AUTRES = ("MAINE ANJOU", "OCEAN", "ARKEA", "BRETAGNE", "SUD OUEST", "AGRICOLE RURAL")
# Caisses fédérales hors CMAF qui sont sommets d'un arbre (T045) mêlé à CMAF.
SOMMETS_AUTRES = ("556650208", "307049015", "775577018")  # Maine-Anjou et Basse-Normandie, Océan, Arkéa
COMMISSAIRES = ("71", "72", "77")
CAISSE = "(s.nom like 'CAISSE%CREDIT MUTUEL%' or s.nom like '%CREDIT MUTUEL%' and s.cj in (5194, 5195, 5460, 5560, 5660, 6560, 6595, 6596))"  # noqa: E501
METHODES = {"IG": "Intégration globale", "ME": "Mise en équivalence", "MEE": "Mise en équivalence"}
_NOMBRE = re.compile(r"^\d{1,3}(?:[,.]\d+)?$")
_SECTION = re.compile(r"^[A-H]\. \S")
_METHODES_NOTE3 = ("IG", "ME", "MEE", "NC", "FU")
_ENTETES = {
    "Pays", "31/12/2025", "31/12/2024", "Pourcentage", "Contrôle", "Intérêt", "Méthode*", "2025", "—",
    "DOCUMENT D’ENREGISTREMENT UNIVERSEL", "CRÉDIT MUTUEL ALLIANCE FÉDÉRALE/BFCM •",
    "COMPTES CONSOLIDÉS DE CRÉDIT MUTUEL ALLIANCE FÉDÉRALE",
    "Annexe aux comptes consolidés de Crédit Mutuel Alliance Fédérale",
    "www.creditmutuelalliancefederale.fr",
}  # fmt: skip


class _Cellules(HTMLParser):
    """Le texte d'un xhtml ESEF : une ligne par bloc ou cellule."""

    def __init__(self) -> None:
        super().__init__()
        self.morceaux: list[str] = []
        self._cache = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("style", "script"):
            self._cache += 1
        elif tag in ("div", "p", "tr", "td", "th", "br", "li"):
            self.morceaux.append("\n")
        elif tag == "span":
            self.morceaux.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("style", "script"):
            self._cache = max(0, self._cache - 1)

    def handle_data(self, data: str) -> None:
        if not self._cache:
            self.morceaux.append(data)


def lignes_deu(chemin: Path) -> list[str]:
    """Les lignes de texte du DEU (paquet ESEF .zip ou .xhtml), sans les lignes vides."""
    if chemin.suffix.lower() == ".zip":
        with zipfile.ZipFile(chemin) as z:
            nom = next(n for n in z.namelist() if n.endswith(".xhtml") and "/reports/" in n)
            texte = z.read(nom).decode("utf-8")
    else:
        texte = chemin.read_text(encoding="utf-8")
    lecteur = _Cellules()
    lecteur.feed(texte)
    lecteur.close()
    lignes = (
        re.sub(r"\s+", " ", ligne.replace("\xa0", " ")).strip()
        for ligne in "".join(lecteur.morceaux).split("\n")
    )
    return [ligne for ligne in lignes if ligne]


@dataclass(frozen=True)
class LigneNote3:
    nom: str
    pays: str
    controle: float
    interet: float
    methode: str  # IG, ME, NC, FU


def note3(lignes: list[str]) -> list[LigneNote3]:
    """Les lignes 2025 de la note 3a des comptes de CMAF : nom, pays, % contrôle, % intérêt, méthode."""
    debut = next(
        i for i in range(len(lignes) - 2)
        if lignes[i] == "Note 3" and lignes[i + 1] == "Périmètre de consolidation"
        and any("CRÉDIT MUTUEL ALLIANCE FÉDÉRALE" in x for x in lignes[max(0, i - 3):i])
    )  # fmt: skip
    fin = next(i for i in range(debut, len(lignes)) if lignes[i] == "3b")
    t = lignes[debut:fin]
    sortie: list[LigneNote3] = []
    coupe = 0  # première ligne qui peut appartenir au nom de la ligne suivante
    i = 3
    while i < len(t):
        meth = t[i].upper()
        if (
            meth in _METHODES_NOTE3
            and _NOMBRE.match(t[i - 1]) and _NOMBRE.match(t[i - 2])
            and not _NOMBRE.match(t[i - 3]) and t[i - 3].upper() not in _METHODES_NOTE3
        ):  # fmt: skip
            nom: list[str] = []
            for x in reversed(t[coupe : i - 3]):
                arret = x in _ENTETES or _SECTION.match(x) or _NOMBRE.match(x) or x.upper() in _METHODES_NOTE3
                if arret or x.startswith("*") or len(nom) == 3:
                    break
                nom.insert(0, x)
            if nom:
                taux = float(t[i - 1].replace(",", "."))
                sortie.append(
                    LigneNote3(" ".join(nom), t[i - 3], float(t[i - 2].replace(",", ".")), taux, meth)
                )
            # Le trio 2024, s'il suit, n'appartient à aucun nom.
            j = i + 1
            if j + 2 < len(t) and _NOMBRE.match(t[j]) and _NOMBRE.match(t[j + 1]):
                j += 3
            coupe = j
            i = j + 3
            continue
        i += 1
    return sortie


def perimetre_deu(lignes: list[LigneNote3]) -> PerimetrePublie:
    """La note 3 réécrite au format VINCI, lue par l'extraction de T042. Les succursales sont
    écartées : ce ne sont pas des sociétés."""
    texte = "\n".join(
        f"{ligne.nom} France {ligne.interet:.2f}".replace(".", ",") + f" {METHODES[ligne.methode]}"
        for ligne in lignes
        if ligne.methode in METHODES and "succursale" not in ligne.nom.lower()
        and (ligne.pays == "France" or ligne.pays in ("Martinique", "Guadeloupe", "Guyane", "La Réunion"))
    )  # fmt: skip
    return PerimetrePublie("Document d'enregistrement universel 2025 de CMAF, note 3", tuple(extraire(texte)))


def reference(dossier: Path) -> set[str]:
    with (dossier / "cargo_cmaf_entites.csv").open(newline="", encoding="utf-8") as f:
        return {r["siren"].strip() for r in csv.DictReader(f) if (r.get("siren") or "").strip()}


def hors_cmaf(con: duckdb.DuckDBPyConnection) -> set[str]:
    """Les sociétés d'autres fédérations :
    - les caisses membres d'un GIE de plus de 20 caisses dont la caisse fédérale de CMAF n'est pas
      membre (Federal Service, Inter-Mutuel Services…) ;
    - les caisses au nom d'une fédération hors CMAF ;
    - les caisses fédérales hors CMAF, et ce qui descend d'elles dans l'arbre par un rôle fort : un
      mandat d'administrateur ou de conseil de surveillance seul ne suffit pas. L'arbre range BFCM
      sous Maine-Anjou et ACM Vie SA sous Océan par un tel mandat : ce sont des filiales de CMAF.
    Une caisse membre à la fois du GIE de CMAF et d'un autre GIE compte ici : c'est le mélange."""
    autres = "|".join(FEDERATIONS_AUTRES)
    return {s for (s,) in con.execute(f"""
        with recursive gie as (
            select l.enfant from liens l join sieges s on s.siren = l.parent
             where l.fin is null and l.role = '11' and {CAISSE}
             group by l.enfant having count(distinct l.parent) > 20
               and l.enfant not in (select enfant from liens where parent = $tete and fin is null)
        ), sous(siren) as (
            select unnest($sommets) union
            select a.siren from arbre a join sous on a.mere = sous.siren where a.role_mere not in ('64', '65')
        )
        select l.parent from liens l join gie using (enfant) where l.fin is null and l.role = '11'
        union select siren from sous
        union select s.siren from sieges s
         where {CAISSE} and regexp_matches(replace(s.nom, '-', ' '), $autres)
    """, {"tete": TETE, "sommets": list(SOMMETS_AUTRES), "autres": autres}).fetchall()}  # fmt: skip


def piste_b1(con: duckdb.DuckDBPyConnection) -> set[str]:
    """La caisse fédérale et les sociétés dont elle est mandataire, tous rôles hors commissaires,
    descendues de proche en proche."""
    return {s for (s,) in con.execute("""
        with recursive d(siren) as (
            select $tete union
            select l.enfant from liens l join d on l.parent = d.siren
             where l.fin is null and l.role not in (select unnest($cac))
        ) select siren from d where siren in (select siren from sieges)
    """, {"tete": TETE, "cac": list(COMMISSAIRES)}).fetchall()}  # fmt: skip


def piste_b2(con: duckdb.DuckDBPyConnection) -> set[str]:
    """La caisse fédérale et les caisses de Crédit Mutuel membres (rôle 11) d'un même GIE qu'elle."""
    return {s for (s,) in con.execute(f"""
        select $tete union
        select l.parent from liens l join sieges s on s.siren = l.parent
         where l.fin is null and l.role = '11' and {CAISSE}
           and l.enfant in (select enfant from liens where parent = $tete and role = '11' and fin is null)
    """, {"tete": TETE}).fetchall()}  # fmt: skip


def piste_b3(con: duckdb.DuckDBPyConnection, hors: set[str]) -> set[str]:
    """B2, sans les caisses qu'une preuve range dans une autre fédération (`hors_cmaf`)."""
    return piste_b2(con) - hors


def piste_c(con: duckdb.DuckDBPyConnection) -> tuple[set[str], int]:
    """Les caisses dont la dénomination nomme une fédération de CMAF. Rend aussi le nombre de caisses."""
    caisses = {s: n for s, n in con.execute(f"select s.siren, s.nom from sieges s where {CAISSE}").fetchall()}
    motif = re.compile("|".join(FEDERATIONS_CMAF))
    autres = re.compile("|".join(FEDERATIONS_AUTRES))
    nommees = {
        s
        for s, n in caisses.items()
        if motif.search(n.replace("-", " ")) and not autres.search(n.replace("-", " "))
    }
    return nommees, len(caisses)


def caisses(con: duckdb.DuckDBPyConnection, sirens: set[str]) -> int:
    return con.execute(f"select count(*) from sieges s where {CAISSE} and siren in (select unnest($s))",
                       {"s": sorted(sirens)}).fetchone()[0]  # type: ignore[index]  # fmt: skip


def ligne(nom: str, sirens: set[str], ref: set[str], hors: set[str], con: duckdb.DuckDBPyConnection) -> str:
    return (f"{nom:<44} {len(sirens & ref):>3}/{len(ref):<3} {len(sirens - ref):>7} {caisses(con, sirens):>8}"
            f" {len((sirens - ref) & hors):>8}")  # fmt: skip


def main(arguments: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(
        description="Pistes du traitement mutualiste (T049), mesurées sur CMAF."
    )
    parseur.add_argument("--deu", type=Path, help="DEU de CMAF : paquet ESEF (.zip) ou .xhtml")
    parseur.add_argument("--sans-moteur", action="store_true", help="pistes B et C seulement (rapide)")
    options = parseur.parse_args(arguments)
    data = Path(os.environ.get("CARTOFR_DATA", "data"))
    registre = data / "registre.duckdb"
    references = Path(os.environ.get("CARTOFR_REFERENCES", "basile"))
    manquants = [str(p) for p in (registre, references / "cargo_cmaf_entites.csv") if not p.exists()]
    if options.deu and not options.deu.exists():
        manquants.append(str(options.deu))
    if manquants:
        print("Fichiers manquants : " + ", ".join(manquants), file=sys.stderr)
        return 2

    ref = reference(references)
    con = duckdb.connect(str(registre), read_only=True)
    hors = hors_cmaf(con)
    print(f"Sociétés d'autres fédérations repérées : {len(hors)}")
    print(f"{'piste':<44} {'retrouvées':>7} {'en plus':>7} {'caisses':>8} {'hors CMAF':>8}")

    pistes: dict[str, set[str]] = {}
    if not options.sans_moteur:
        reglages = reglages_tete_seule(TETE, "CMAF")
        debut = time.monotonic()
        pistes["0. tête seule, sans document"] = {s.siren for s in cartographier(reglages, registre).societes}
        print(ligne("0. tête seule, sans document", pistes["0. tête seule, sans document"], ref, hors, con),
              f"  ({time.monotonic() - debut:.0f} s)")  # fmt: skip
        if options.deu:
            lignes = note3(lignes_deu(options.deu))
            document = perimetre_deu(lignes)
            print(f"Note 3 : {len(lignes)} lignes, {len(document.lignes)} en France lues par l'extraction")
            debut = time.monotonic()
            carto = cartographier(reglages, registre, perimetre=document)
            pistes["A. tête seule + DEU"] = {s.siren for s in carto.societes}
            print(ligne("A. tête seule + DEU", pistes["A. tête seule + DEU"], ref, hors, con),
                  f"  ({time.monotonic() - debut:.0f} s)")  # fmt: skip
        else:
            print(f"{'A. tête seule + DEU':<44} en attente du document")
    pistes["B1. caisse fédérale, mandats descendus"] = piste_b1(con)
    pistes["B2. caisse fédérale + caisses du même GIE"] = piste_b2(con)
    pistes["B3. B2 sans les caisses d'un autre GIE"] = piste_b3(con, hors)
    nommees, total = piste_c(con)
    pistes["C. nom d'une fédération de CMAF"] = nommees | {TETE}
    for nom in list(pistes)[-4:]:
        print(ligne(nom, pistes[nom], ref, hors, con))
    print(f"   (caisses de Crédit Mutuel actives au registre : {total})")
    if "A. tête seule + DEU" in pistes:
        union = pistes["A. tête seule + DEU"] | pistes["B3. B2 sans les caisses d'un autre GIE"]
        print(ligne("A + B3", union, ref, hors, con))
    return 0


if __name__ == "__main__":
    sys.exit(main())
