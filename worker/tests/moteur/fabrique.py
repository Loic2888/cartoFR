"""Fabrique de mini-registres pour tester le moteur, une règle à la fois (T017).

Usage :
    mini = MiniRegistre()
    tete = mini.societe(siren(1), "TETE INVENTEE")
    x = mini.societe(siren(2), "ALPHAMARK SERVICES")
    mini.lien(tete, x, PRESIDENT)
    carto = cartographier(reglages(tete, marques_sures=["Alphamark"]), mini.ecrire(tmp_path / "r.duckdb"))
Entrées : des sociétés, liens et dirigeants décrits en Python.
Sortie : un fichier `registre.duckdb` au schéma réel (`creer_tables`), prêt pour `cartographier`.

Tous les noms sont inventés (règle produit 6) : SIREN 9000000NN, personnes « PERSONNE INVENTEE ».
Une société porte la même ligne dans `sieges`, `unites_legales` et `societes`, comme dans le
vrai registre ; une société inactive n'a pas de siège, comme dans SIRENE.
"""

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import duckdb

from cartofr.registre.schema import creer_tables

DEBUT = date(2026, 3, 4)  # date du stock RNE

# Codes de rôle RNE (moteur.py) : les tests écrivent le nom du rôle, pas le code.
PRESIDENT, GERANT, COMMANDITE = "73", "30", "131"
ADMINISTRATEUR, MEMBRE = "65", "11"
AUTRE = "99"
COMMISSAIRE_AUX_COMPTES = "71"

CJ_SAS, CJ_SCI, CJ_GIE, CJ_ETRANGERE, CJ_ASSOCIATION = 5710, 6540, 6220, 3120, 9220


def siren(n: int) -> str:
    """Un SIREN inventé : 900000001, 900000002…"""
    return f"{900_000_000 + n}"


def personne(n: int, famille: str = "PERSONNE INVENTEE") -> str:
    """Une clé de dirigeant inventée, au format du registre : nom|prénoms|naissance."""
    return f"{famille}|PRENOM{n}|1970-01"


def reglages(tete: str, **surcharges: Any) -> dict[str, Any]:
    """Des réglages de groupe complets, vides par défaut, à surcharger règle par règle."""
    base: dict[str, Any] = {
        "groupe": "TEST",
        "tete": tete,
        "marques_sures": [],
        "marques_ambigues": [],
        "exclus": [],
        "familles_exclues": [],
        "marques_sures_homonymes": [],
        "marques_sigles": [],
        "priorite": [],
        "exclus_noms": [],
        "organigramme": [],
    }
    return base | surcharges


@dataclass
class _Societe:
    siren: str
    nom: str
    cj: int
    naf: str
    tranche: str | None
    adresse: str
    salaries: int | None
    diffusion_commerciale: bool
    active: bool


@dataclass
class MiniRegistre:
    """Un petit registre décrit en mémoire, écrit en DuckDB par `ecrire`."""

    societes: list[_Societe] = field(default_factory=list)
    liens: list[tuple[str, str, str, date | None]] = field(default_factory=list)
    dirigeants: list[tuple[str, str, str, date | None]] = field(default_factory=list)

    def societe(
        self,
        siren: str,
        nom: str,
        *,
        cj: int = CJ_SAS,
        naf: str = "70.22Z",
        tranche: str | None = "11",
        adresse: str | None = None,
        salaries: int | None = None,
        diffusion_commerciale: bool = True,
        active: bool = True,
    ) -> str:
        """Ajoute une société ; par défaut une SAS de 10 à 19 salariés, seule à son adresse."""
        self.societes.append(
            _Societe(siren, nom, cj, naf, tranche, adresse or f"{siren} RUE INVENTEE 75000", salaries,
                     diffusion_commerciale, active)
        )  # fmt: skip
        return siren

    def domicilier(self, adresse: str, *sirens: str) -> None:
        """Place le siège de sociétés déjà ajoutées à cette adresse."""
        for s in self.societes:
            if s.siren in sirens:
                s.adresse = adresse

    def lien(self, parent: str, enfant: str, role: str, *, fin: date | None = None) -> None:
        """La société `parent` dirige `enfant` avec ce rôle RNE ; `fin` le ferme."""
        self.liens.append((parent, enfant, role, fin))

    def dirigeant(self, siren: str, cle: str, role: str = PRESIDENT, *, fin: date | None = None) -> None:
        """Une personne physique (clé inventée) dirige la société `siren`."""
        self.dirigeants.append((siren, cle, role, fin))

    def dirigeants_communs(self, a: str, b: str, n: int = 2, *, premier: int = 1) -> None:
        """`n` personnes dirigent à la fois `a` et `b` : l'indice « dirigeants communs »."""
        for i in range(premier, premier + n):
            self.dirigeant(a, personne(i))
            self.dirigeant(b, personne(i))

    def ecrire(self, chemin: Path) -> Path:
        """Écrit le registre au schéma réel et rend son chemin."""
        con = duckdb.connect(str(chemin))
        try:
            creer_tables(con)
            for s in self.societes:
                etat = "A" if s.active else "C"
                if s.active:
                    con.execute(
                        "insert into sieges values"
                        " (?, ?, '1', 'RUE', 'INVENTEE', '75000', 'PARIS', ?, ?, ?, ?, ?)",
                        [s.siren, s.siren + "00011", s.adresse, s.nom, s.cj, s.naf, s.tranche],
                    )
                con.execute(
                    "insert into unites_legales (siren, denomination, categorie_juridique, naf,"
                    " tranche_effectifs, etat_administratif, debut) values (?, ?, ?, ?, ?, ?, ?)",
                    [s.siren, s.nom, s.cj, s.naf, s.tranche, etat, DEBUT],
                )
                con.execute(
                    "insert into societes (siren, denomination, diffusion_commerciale,"
                    " opposition_prospection, non_diffusible, salaries, etat_administratif, debut)"
                    " values (?, ?, ?, ?, false, ?, ?, ?)",
                    [
                        s.siren,
                        s.nom,
                        s.diffusion_commerciale,
                        not s.diffusion_commerciale,
                        s.salaries,
                        etat,
                        DEBUT,
                    ],  # fmt: skip
                )
            for table, colonne, lignes in (
                ("liens", "parent, enfant", self.liens),
                ("dirigeants_personnes", "siren, personne", self.dirigeants),
            ):
                for a, b, role, fin in lignes:
                    con.execute(
                        f"insert into {table} ({colonne}, role, debut, fin) values (?, ?, ?, ?, ?)",
                        [a, b, role, DEBUT, fin],
                    )
        finally:
            con.close()
        return chemin
