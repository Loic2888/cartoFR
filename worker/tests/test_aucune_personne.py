"""SC-005 (T023, C1) : aucun nom de dirigeant personne physique dans une carto ni dans son export.

But : confronter tout le texte que rend une carto à la table `dirigeants_personnes` du registre.
Le texte vérifié est celui qui sort du worker : chaque chaîne de la `Carto` (sociétés, liens,
participations, sociétés étrangères) et des lignes `carto_societes` et `carto_liens` écrites en
base (`cartofr.jobs.carto`), que l'export CSV reprend telles quelles. Deux sortes de texte :

- le texte écrit par le moteur (preuves, raisons, rôles, indices) : aucun nom complet de
  dirigeant, aucune clé brute. C'est là qu'un nom de personne pourrait fuir du calcul ;
- les champs recopiés tels quels de `sieges` (SIRENE) : dénomination d'une personne morale
  (`nom`, `maison_mere_nom`, noms des participations et des sociétés étrangères), adresse et
  commune du siège. Chacun doit être égal, caractère pour caractère, à la ligne `sieges` de son
  SIREN : le moteur n'a donc rien pu y mettre d'autre. Une dénomination peut porter le nom de
  son fondateur (maison de couture, entreprise de travaux), une adresse celui d'une rue : ces
  homonymies sont comptées et affichées, sans faire échouer le test (mesure du 2026-10-07 :
  LVMH 1, VINCI 2, CMAF 1 personne, toutes dans une dénomination ou une adresse de siège).

Un nom complet est « NOM PRÉNOM » ou « PRÉNOM NOM », bâti depuis la clé du registre
(« NOM|PRÉNOMS|AAAA-MM ») avec le premier prénom, puis avec tous les prénoms. La comparaison
ignore la casse, les accents et la ponctuation, et se fait mot à mot : « DURAND » ne se trouve
pas dans « DURANDE », et deux textes différents ne se lisent jamais bout à bout. Un nom de
famille seul (clé sans prénom) n'est pas un nom complet : il n'est pas cherché, sans quoi toute
société qui porte un nom de famille courant serait une fausse alerte. La clé brute est cherchée
partout.

Deux parties :
- CI : une carto calculée sur un mini-registre inventé (règle produit 6), où des dirigeants
  personnes font entrer une société, plus des tests du comparateur lui-même ;
- registre réel : LVMH, VINCI et CMAF (`config/<groupe>.json`) sur `<CARTOFR_DATA>/registre.duckdb`.
  Lancée seulement si CARTOFR_DATA désigne un dossier qui contient le registre (2,4 Go, absent
  en CI : le test y est sauté, avec la raison). 3 min 30 pour les trois groupes (2026-10-07).
  Usage, depuis la racine :
      CARTOFR_DATA=data .venv/bin/pytest worker/tests/test_aucune_personne.py -rs -v
  Les dirigeants confrontés sont ceux des sociétés de la carto (retenues, participations,
  sociétés étrangères) et de toutes les sociétés qui les dirigent ou les ont dirigées : ce sont
  les seules personnes que le moteur lit pendant le calcul (`prefetch`), donc les seules dont
  le nom pourrait fuir. Confronter les 13 millions de lignes du registre entier ferait surtout
  des fausses alertes (« SAINT JEAN » est aussi le nom d'une personne).

Aucun nom de personne n'est affiché : les tests ne rendent que des volumes, et leurs assertions
ne portent que sur des nombres (pytest affiche les opérandes d'une assertion qui échoue).
"""

import dataclasses
import json
import os
import re
import sys
import unicodedata
import uuid
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "moteur"))
from fabrique import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    PRESIDENT,
    MiniRegistre,
    reglages,
    siren,
)

from cartofr.jobs.carto import lignes_liens, lignes_societes  # noqa: E402
from cartofr.moteur import Carto, cartographier  # noqa: E402

CONFIG = Path(__file__).resolve().parents[2] / "config"
GROUPES = ["lvmh", "vinci", "cmaf"]
MOTS_MAX = 12  # un nom complet de plus de 12 mots n'est pas cherché en entier (prénoms en liste)
CLE_BRUTE = re.compile(r"\|[^|]*\|\d{4}-\d{2}")  # « NOM|PRÉNOMS|AAAA-MM » : le format d'une clé

# Champs de la `Carto` recopiés de `sieges` : vérifiés par égalité au registre, pas par recherche.
CHAMPS_REGISTRE = frozenset({"nom", "maison_mere_nom", "adresse_siege", "commune"})
# Colonnes texte écrites par le moteur dans les lignes de `cartofr.jobs.carto` (ordre des INSERT).
TEXTE_CARTO_SOCIETES = {7: "preuve", 9: "raison_ciblable"}
TEXTE_CARTO_LIENS = {4: "role", 5: "preuve"}


# ---------- le comparateur ----------


def normaliser(texte: str) -> str:
    """Majuscules sans accents, tout ce qui n'est ni lettre ni chiffre devient une espace."""
    sans_accents = "".join(c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", sans_accents.upper()).split())


def noms_complets(cle: str) -> set[str]:
    """Les formes d'un nom complet tirées d'une clé « NOM|PRÉNOMS|AAAA-MM » ; vide sans prénom."""
    nom, _, reste = cle.partition("|")
    prenoms = normaliser(reste.partition("|")[0])
    nom = normaliser(nom)
    if not nom or not prenoms:
        return set()
    premier = prenoms.split()[0]
    formes = {f"{nom} {premier}", f"{premier} {nom}", f"{nom} {prenoms}", f"{prenoms} {nom}"}
    return {f for f in formes if len(f.split()) <= MOTS_MAX}


def textes_de(objet: Any, sauf: frozenset[str] = frozenset()) -> Iterator[str]:
    """Les chaînes d'une valeur (dataclasses, tuples, listes, dictionnaires), hors champs `sauf`."""
    if isinstance(objet, str):
        yield objet
    elif dataclasses.is_dataclass(objet) and not isinstance(objet, type):
        for champ in dataclasses.fields(objet):
            if champ.name not in sauf:
                yield from textes_de(getattr(objet, champ.name), sauf)
    elif isinstance(objet, dict):
        for cle, valeur in objet.items():
            yield from textes_de(cle, sauf)
            yield from textes_de(valeur, sauf)
    elif isinstance(objet, (list, tuple, set, frozenset)):
        for valeur in objet:
            yield from textes_de(valeur, sauf)


def textes_moteur(carto: Carto) -> list[str]:
    """Le texte écrit par le moteur : la `Carto` hors champs du registre, et les colonnes texte
    des lignes `carto_societes` et `carto_liens` (la preuve y est recomposée)."""
    zero = uuid.UUID(int=0)
    societes = lignes_societes(carto, zero, zero)
    liens = lignes_liens(carto, zero, zero)
    assert all(len(ligne) == 12 for ligne in societes) and all(len(ligne) == 7 for ligne in liens)
    return [
        *textes_de(carto, sauf=CHAMPS_REGISTRE),
        *(ligne[i] for ligne in societes for i in TEXTE_CARTO_SOCIETES if ligne[i] is not None),
        *(ligne[i] for ligne in liens for i in TEXTE_CARTO_LIENS if ligne[i] is not None),
    ]


def valeurs_registre(carto: Carto) -> list[tuple[str, str, str]]:
    """Les champs recopiés de `sieges` : (SIREN de la ligne `sieges`, colonne `sieges`, valeur)."""
    valeurs: list[tuple[str, str, str | None]] = []
    for s in carto.societes:
        valeurs += [(s.siren, "nom", s.nom), (s.siren, "adresse_cle", s.adresse_siege)]
        valeurs.append((s.siren, "commune", s.commune))
        if s.maison_mere_siren:
            valeurs.append((s.maison_mere_siren, "nom", s.maison_mere_nom))
    valeurs += [(p.siren, "nom", p.nom) for p in carto.participations]
    valeurs += [(e.siren, "nom", e.nom) for e in carto.etrangeres]
    valeurs += [(c.siren, "nom", c.nom) for c in carto.cas]
    return [(s, c, v) for s, c, v in valeurs if v is not None]


def ecarts_au_registre(registre: Path, valeurs: list[tuple[str, str, str]]) -> int:
    """Nombre de champs recopiés qui ne sont pas la valeur de `sieges` pour leur SIREN."""
    con = duckdb.connect(str(registre), read_only=True)
    try:
        lignes = con.execute(
            "select siren, nom, adresse_cle, commune from sieges where siren in (select unnest($s))",
            {"s": sorted({s for s, _, _ in valeurs})},
        ).fetchall()
    finally:
        con.close()
    attendu: dict[tuple[str, str], set[Any]] = {}
    for siren_, nom, adresse, commune in lignes:
        for colonne, valeur in (("nom", nom), ("adresse_cle", adresse), ("commune", commune)):
            attendu.setdefault((siren_, colonne), set()).add(valeur)
    return sum(1 for s, c, v in valeurs if v not in attendu.get((s, c), set()))


def suites_de_mots(textes: Iterable[str], longueur_max: int = MOTS_MAX) -> set[str]:
    """Chaque suite de 1 à `longueur_max` mots consécutifs d'un même texte normalisé."""
    suites: set[str] = set()
    for texte in textes:
        mots = normaliser(texte).split()
        for i in range(len(mots)):
            for j in range(i + 1, min(i + longueur_max, len(mots)) + 1):
                suites.add(" ".join(mots[i:j]))
    return suites


@dataclasses.dataclass(frozen=True)
class Constat:
    """Volumes d'une confrontation. Aucun nom : seulement des nombres."""

    textes: int
    personnes: int
    noms_cherches: int
    personnes_trouvees: int  # personnes dont un nom complet est présent dans le texte
    cles_brutes: int  # textes qui contiennent une clé brute

    @property
    def fuites(self) -> int:
        return self.personnes_trouvees + self.cles_brutes


def confronter(textes: list[str], cles: Iterable[str]) -> Constat:
    """Compte les personnes de `cles` dont un nom complet est dans `textes`, et les clés brutes."""
    formes = {cle: noms_complets(cle) for cle in set(cles)}
    suites = suites_de_mots(textes)
    brutes = sum(1 for t in textes if "|" in t and (CLE_BRUTE.search(t) or any(c in t for c in formes)))
    return Constat(
        textes=len(textes),
        personnes=len(formes),
        noms_cherches=sum(len(f) for f in formes.values()),
        personnes_trouvees=sum(1 for f in formes.values() if f & suites),
        cles_brutes=brutes,
    )


# ---------- le comparateur lui-même ----------

CLE_A = "FICTIFNOM|ZÉPHYRIN|1970-01"
CLE_B = "DUPOND-INVENTÉ|MARIE, CLAIRE|1980-02"
CLE_SANS_PRENOM = "SEULNOMINVENTE||1990-03"


@pytest.mark.parametrize(
    "texte",
    [
        "Dirigeant commun : FICTIFNOM ZÉPHYRIN",
        "dirigeant commun : zephyrin fictifnom",
        "Preuve (Fictifnom, Zéphyrin)",
        "Marie Dupond-Inventé",
        "DUPOND INVENTE MARIE CLAIRE",
        "Claire, Marie : Dupond Inventé",
    ],
)
def test_le_comparateur_trouve_un_nom_complet(texte: str) -> None:
    assert confronter([texte], [CLE_A, CLE_B]).personnes_trouvees == 1


@pytest.mark.parametrize(
    "textes",
    [
        ["FICTIFNOMS ZEPHYRIN"],  # autre mot
        ["Président · entrée par la marque FICTIFNOM"],  # nom de famille seul
        ["Fin du premier texte FICTIFNOM", "ZEPHYRIN début du second"],  # deux textes
        ["SEULNOMINVENTE HOLDING"],  # clé sans prénom : pas un nom complet
        ["ZEPHYRIN AUTRE FICTIFNOM"],  # mots non consécutifs
    ],
)
def test_le_comparateur_ne_trouve_pas_ce_qui_n_est_pas_un_nom_complet(textes: list[str]) -> None:
    assert confronter(textes, [CLE_A, CLE_SANS_PRENOM]).personnes_trouvees == 0


def test_le_comparateur_trouve_une_cle_brute() -> None:
    assert confronter(["Preuve : DUPOND-INVENTÉ|MARIE, CLAIRE|1980-02"], [CLE_A]).cles_brutes == 1
    assert confronter(["Preuve : SEULNOMINVENTE||1990-03"], [CLE_SANS_PRENOM]).cles_brutes == 1
    assert confronter(["Mandat au registre : Président"], [CLE_A]).cles_brutes == 0


# ---------- CI : une carto sur un mini-registre inventé ----------

TETE, FILIALE, SOUS_FILIALE, ZETA, HORS = siren(1), siren(10), siren(11), siren(20), siren(90)
DIRIGEANTS = {  # société -> clés de ses dirigeants personnes (inventés)
    TETE: [CLE_A, CLE_B],
    ZETA: [CLE_A, CLE_B],  # dirigeants communs avec la tête : font entrer ZETA
    FILIALE: ["AUTRENOM|ÉLODIE|1975-05", CLE_SANS_PRENOM],
    HORS: ["HORSGROUPE|PRENOMHORS|1960-06"],
}
CLES = [c for liste in DIRIGEANTS.values() for c in liste]


@pytest.fixture
def fabrique(tmp_path: Path) -> tuple[Carto, Path]:
    """La carto d'un groupe inventé, où deux dirigeants personnes font entrer ZETA, et son registre."""
    mini = MiniRegistre()
    mini.societe(TETE, "TETE INVENTEE", naf="70.10Z", tranche="22")
    mini.societe(FILIALE, "ALPHAMARK DISTRIBUTION")
    mini.societe(SOUS_FILIALE, "DELTA LOGISTIQUE")
    mini.societe(ZETA, "ZETA CONSEIL")
    mini.societe(HORS, "SANS LIEN")
    mini.lien(TETE, FILIALE, PRESIDENT)
    mini.lien(FILIALE, SOUS_FILIALE, PRESIDENT)
    for societe, cles in DIRIGEANTS.items():
        for cle in cles:
            mini.dirigeant(societe, cle)
    registre = mini.ecrire(tmp_path / "registre.duckdb")
    reglages_ = reglages(TETE, marques_sures=["Alphamark"], marques_ambigues=["Zeta"])
    return cartographier(reglages_, registre), registre


def test_carto_fabriquee_sans_nom_de_personne(fabrique: tuple[Carto, Path]) -> None:
    carto, registre = fabrique
    retenues = {s.siren for s in carto.societes}
    # Les dirigeants personnes ont bien servi au calcul : ZETA (marque ambiguë) n'entre que par eux.
    assert {TETE, FILIALE, SOUS_FILIALE, ZETA} <= retenues
    assert HORS not in retenues

    moteur = confronter(textes_moteur(carto), CLES)
    assert moteur.noms_cherches > 0
    assert moteur.textes > 0
    assert moteur.fuites == 0
    valeurs = valeurs_registre(carto)
    assert len(valeurs) >= 3 * len(carto.societes)
    assert ecarts_au_registre(registre, valeurs) == 0
    assert confronter([v for _, _, v in valeurs], CLES).fuites == 0


@pytest.mark.parametrize("champ", ["preuve", "raison_ciblable", "pourquoi_dans_le_groupe"])
def test_un_nom_glisse_dans_un_texte_du_moteur_est_trouve(fabrique: tuple[Carto, Path], champ: str) -> None:
    carto, _ = fabrique
    piegee = dataclasses.replace(carto.societes[-1], **{champ: "Dirigeant : fictifnom zéphyrin"})
    carto = dataclasses.replace(carto, societes=(*carto.societes[:-1], piegee))
    assert confronter(textes_moteur(carto), CLES).personnes_trouvees == 1


def test_un_nom_glisse_dans_un_lien_est_trouve(fabrique: tuple[Carto, Path]) -> None:
    carto, _ = fabrique
    lien = dataclasses.replace(carto.liens[0], preuve="Mandat : ZEPHYRIN FICTIFNOM")
    carto = dataclasses.replace(carto, liens=(lien, *carto.liens[1:]))
    assert confronter(textes_moteur(carto), CLES).personnes_trouvees == 1


@pytest.mark.parametrize("champ", ["nom", "maison_mere_nom", "adresse_siege", "commune"])
def test_un_champ_du_registre_modifie_est_un_ecart(fabrique: tuple[Carto, Path], champ: str) -> None:
    """Un nom de personne mis à la place d'une dénomination ou d'une adresse ne passe pas."""
    carto, registre = fabrique
    i = next(i for i, s in enumerate(carto.societes) if s.maison_mere_siren)
    piegee = dataclasses.replace(carto.societes[i], **{champ: "ZEPHYRIN FICTIFNOM"})
    carto = dataclasses.replace(carto, societes=(*carto.societes[:i], piegee, *carto.societes[i + 1 :]))
    assert ecarts_au_registre(registre, valeurs_registre(carto)) == 1


# ---------- registre réel : LVMH, VINCI, CMAF ----------


def _registre_reel() -> Path | None:
    dossier = os.environ.get("CARTOFR_DATA")
    if not dossier:
        return None
    chemin = Path(dossier) / "registre.duckdb"
    return chemin if chemin.is_file() else None


REGISTRE_REEL = _registre_reel()


def personnes_impliquees(registre: Path, carto: Carto) -> tuple[int, set[str]]:
    """Les sociétés de la carto et celles qui les dirigent (ou les ont dirigées), et leurs dirigeants."""
    sirens = (
        {s.siren for s in carto.societes}
        | {p.siren for p in carto.participations}
        | {e.siren for e in carto.etrangeres}
    )
    con = duckdb.connect(str(registre), read_only=True)
    try:
        con.execute("set enable_progress_bar = false")
        parents = {
            r[0]
            for r in con.execute(
                "select distinct parent from liens where enfant in (select unnest($s))", {"s": list(sirens)}
            ).fetchall()
        }
        societes = sirens | parents
        cles = {
            r[0]
            for r in con.execute(
                "select distinct personne from dirigeants_personnes where siren in (select unnest($s))",
                {"s": list(societes)},
            ).fetchall()
        }
    finally:
        con.close()
    return len(societes), cles


@pytest.mark.skipif(
    REGISTRE_REEL is None,
    reason="registre réel absent en CI (2,4 Go) : CARTOFR_DATA doit désigner un dossier avec registre.duckdb",
)
@pytest.mark.parametrize("groupe", GROUPES)
def test_registre_reel_aucun_nom_de_personne(groupe: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert REGISTRE_REEL is not None
    config = json.loads((CONFIG / f"{groupe}.json").read_text(encoding="utf-8"))
    carto = cartographier(config, REGISTRE_REEL)
    nb_societes, cles = personnes_impliquees(REGISTRE_REEL, carto)
    textes = textes_moteur(carto)
    moteur = confronter(textes, cles)
    valeurs = valeurs_registre(carto)
    ecarts = ecarts_au_registre(REGISTRE_REEL, valeurs)
    registre = confronter([v for _, _, v in valeurs], cles)

    # Le comparateur marche sur ces données : un nom réel de la liste, glissé dans une copie du
    # texte (en minuscules, prénom d'abord), est trouvé. Le nom n'est jamais affiché.
    temoin = next(c for c in sorted(cles) if noms_complets(c))
    nom, prenoms, _ = temoin.split("|", 2)
    glisse = f"preuve : {prenoms.split(',')[0].strip().lower()} {nom.lower()}"
    temoin_trouve = confronter([*textes, glisse], cles).personnes_trouvees

    with capsys.disabled():
        print(
            f"\nSC-005 {groupe} : {len(carto.societes)} sociétés retenues, {len(carto.liens)} liens ; "
            f"{moteur.personnes} dirigeants personnes de {nb_societes} sociétés impliquées, "
            f"{moteur.noms_cherches} formes de nom cherchées ; texte du moteur : {moteur.textes} textes, "
            f"{moteur.personnes_trouvees} personnes trouvées, {moteur.cles_brutes} clés brutes ; "
            f"champs du registre : {len(valeurs)} valeurs, {ecarts} écarts à sieges, "
            f"{registre.cles_brutes} clés brutes, {registre.personnes_trouvees} homonymies "
            f"(dénomination ou adresse) ; témoin glissé trouvé : {temoin_trouve > moteur.personnes_trouvees}"
        )

    assert len(carto.societes) > 1
    assert moteur.personnes > 0
    assert temoin_trouve > moteur.personnes_trouvees
    assert moteur.fuites == 0
    assert ecarts == 0
    assert registre.cles_brutes == 0
