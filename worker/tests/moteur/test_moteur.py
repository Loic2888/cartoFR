"""Moteur de cartographie sur un mini-registre généré (T016).

Tous les noms sont inventés (règle produit 6) : « ALPHAMARK », « PERSONNE FICTIVE UN ».
Couvre : un petit groupe trouvé par marque, second indice et mandat (FR-006) ; aucun appel
réseau (C2, principe 3) ; aucun champ ni aucune valeur de personne en sortie (C3, garde-fou 6) ;
registre lu sans être modifié ; résultat identique d'un lancement à l'autre.
"""

import ast
import dataclasses
import hashlib
import socket
import types
import typing
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pytest

from cartofr.moteur import Carto, cartographier, modele
from cartofr.moteur.marques import norm, norm_arrow
from cartofr.registre.schema import creer_tables

TETE, F1, F2, F3, F4, F5, F6 = (f"20000000{i}" for i in range(1, 8))
PERSONNE_1 = "PERSONNE FICTIVE UN|PRENOMFICTIF|1970-01"
PERSONNE_2 = "PERSONNE FICTIVE DEUX|AUTREPRENOM|1980-02"
DEBUT = date(2026, 3, 4)

REGLAGES: dict[str, Any] = {
    "groupe": "TEST",
    "tete": TETE,
    "marques_sures": ["Alphamark"],
    "marques_ambigues": ["Zeta"],
    "exclus": [],
    "familles_exclues": [],
    "marques_sures_homonymes": [],
    "marques_sigles": [],
    "priorite": [],
    "exclus_noms": [],
    "organigramme": [],
}

# siren, nom, catégorie juridique, naf, tranche, adresse : chacune à une adresse différente.
SOCIETES = [
    (TETE, "GROUPE TETE", 5599, "70.10Z", "22", "1 RUE UN 75001"),
    (F1, "ALPHAMARK DISTRIBUTION", 5710, "46.45Z", "12", "2 RUE DEUX 75002"),  # marque + mandat fort
    (F2, "ALPHAMARK SERVICES", 5710, "47.75Z", "11", "3 RUE TROIS 75003"),  # marque sûre seule
    (F3, "ZETA CONSEIL", 5710, "70.22Z", "03", "4 RUE QUATRE 75004"),  # marque ambiguë + dirigeants
    (F4, "OMEGA PARTICIPATIONS", 5710, "64.20Z", "NN", "5 RUE CINQ 75005"),  # administrateur seul
    (F5, "SANS LIEN", 5710, "62.01Z", "11", "6 RUE SIX 75006"),  # hors du groupe
    (F6, "DELTA LOGISTIQUE", 5710, "52.29A", "21", "7 RUE SEPT 75007"),  # présidée par F1
]
LIENS = [  # parent, enfant, rôle RNE
    (TETE, F1, "73"),  # Président
    (F1, F6, "73"),
    (F1, F4, "65"),  # Administrateur : participation sans contrôle
]
DIRIGEANTS = [  # deux dirigeants personnes en commun entre la tête et F3
    (TETE, PERSONNE_1, "73"),
    (TETE, PERSONNE_2, "65"),
    (F3, PERSONNE_1, "73"),
    (F3, PERSONNE_2, "65"),
    (F5, "PERSONNE FICTIVE TROIS|X|1990-03", "73"),
]
NOMS_DE_PERSONNES = ["FICTIVE", "PRENOMFICTIF", "AUTREPRENOM", "1970-01", "1980-02"]


@pytest.fixture
def registre(tmp_path: Path) -> Path:
    chemin = tmp_path / "registre.duckdb"
    con = duckdb.connect(str(chemin))
    creer_tables(con)
    for siren, nom, cj, naf, tranche, adresse in SOCIETES:
        con.execute(
            "insert into sieges values (?, ?, '1', 'RUE', 'TEST', '75001', 'PARIS', ?, ?, ?, ?, ?)",
            [siren, siren + "00011", adresse, nom, cj, naf, tranche],
        )
        con.execute(
            "insert into unites_legales values (?, ?, null, null, null, null, ?, ?, ?, 'A', ?, null)",
            [siren, nom, cj, naf, tranche, DEBUT],
        )
        con.execute(
            "insert into societes values (?, ?, ?, ?, false, 5, 'A', null, ?, null)",
            [siren, nom, siren != F2, siren == F2, DEBUT],  # F2 refuse la prospection
        )
    con.executemany(
        "insert into liens (parent, enfant, role, debut) values (?, ?, ?, ?)", [(*x, DEBUT) for x in LIENS]
    )
    # Un lien fermé ne compte plus : F5 n'entre pas par lui.
    con.execute(
        "insert into liens (parent, enfant, role, debut, fin) values (?, ?, '73', ?, ?)",
        [TETE, F5, DEBUT, date(2026, 4, 1)],
    )
    con.executemany(
        "insert into dirigeants_personnes (siren, personne, role, debut) values (?, ?, ?, ?)",
        [(*x, DEBUT) for x in DIRIGEANTS],
    )
    con.close()
    return chemin


def _par_siren(carto: Carto) -> dict[str, modele.Societe]:
    return {s.siren: s for s in carto.societes}


def test_petit_groupe_par_marque_second_indice_et_mandat(registre: Path) -> None:
    carto = cartographier(REGLAGES, registre)
    societes = _par_siren(carto)
    assert set(societes) == {TETE, F1, F2, F3, F6}
    assert societes[TETE].niveau == 0 and societes[TETE].preuve == "Tête du groupe"
    assert societes[F1].pourquoi_dans_le_groupe == "mandat fort au registre"
    assert (societes[F1].maison_mere_siren, societes[F1].preuve, societes[F1].confiance) == (
        TETE,
        "Mandat au registre : Président",
        "A",
    )
    assert societes[F2].pourquoi_dans_le_groupe == "nom de marque propre au groupe"
    assert societes[F3].pourquoi_dans_le_groupe == "nom de marque et second indice"
    assert societes[F6].maison_mere_siren == F1 and societes[F6].niveau == 2
    assert [(p.siren, p.mandats) for p in carto.participations] == [
        (F4, (modele.Mandat(F1, "Administrateur"),))
    ]
    assert {(lien.parent, lien.enfant, lien.role) for lien in carto.liens} == {
        (TETE, F1, "Président"),
        (F1, F6, "Président"),
    }
    assert carto.date_donnees == date(2026, 4, 1)  # la fermeture du lien est la date la plus récente


def test_opposition_a_la_prospection_marquee_pas_cachee(registre: Path) -> None:
    societes = _par_siren(cartographier(REGLAGES, registre))
    assert societes[F2].opposition_prospection is True
    assert societes[F1].opposition_prospection is False


def test_aucun_appel_reseau(registre: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 : réseau coupé, la carto réussit (principe 3)."""

    def coupe(*args: object, **kwargs: object) -> typing.NoReturn:
        raise OSError("réseau coupé par le test")

    monkeypatch.setattr(socket.socket, "connect", coupe)
    monkeypatch.setattr(socket.socket, "connect_ex", coupe)
    monkeypatch.setattr(socket, "create_connection", coupe)
    monkeypatch.setattr(socket, "getaddrinfo", coupe)
    carto = cartographier(REGLAGES, registre)
    assert len(carto.societes) == 5


def test_le_paquet_moteur_n_importe_aucun_client_reseau() -> None:
    interdits = {"socket", "http", "urllib", "httpx", "requests", "ftplib", "inpi", "annuaire", "bodacc"}
    dossier = Path(modele.__file__).parent
    for fichier in dossier.glob("*.py"):
        for noeud in ast.walk(ast.parse(fichier.read_text(encoding="utf-8"))):
            if isinstance(noeud, ast.Import):
                noms = [a.name for a in noeud.names]
            elif isinstance(noeud, ast.ImportFrom):
                noms = [noeud.module or ""]
            else:
                continue
            for nom in noms:
                assert not set(nom.split(".")) & interdits, f"{fichier.name} importe {nom}"


MOTS_DE_PERSONNE = ("personne", "prenom", "dirigeant", "naissance", "sexe", "pseudonyme", "usage", "individu")
TYPES_SIMPLES = {str, int, bool, float, date, type(None)}


def _types_feuilles(annotation: Any) -> set[Any]:
    origine = typing.get_origin(annotation)
    if origine is typing.Literal:
        return {type(v) for v in typing.get_args(annotation)}
    if origine in (typing.Union, types.UnionType, tuple):
        return set().union(*(_types_feuilles(a) for a in typing.get_args(annotation) if a is not Ellipsis))
    return {annotation}


def test_le_modele_de_sortie_n_a_aucun_champ_de_personne() -> None:
    """C3 : par introspection, de `Carto` jusqu'aux feuilles."""
    a_voir: list[Any] = [modele.Carto]
    vus: set[Any] = set()
    while a_voir:
        classe = a_voir.pop()
        if classe in vus:
            continue
        vus.add(classe)
        indices = typing.get_type_hints(classe)
        for champ in dataclasses.fields(classe):
            assert not any(mot in champ.name.lower() for mot in MOTS_DE_PERSONNE), (classe, champ.name)
            for feuille in _types_feuilles(indices[champ.name]):
                if dataclasses.is_dataclass(feuille):
                    a_voir.append(feuille)
                else:
                    assert feuille in TYPES_SIMPLES, (classe.__name__, champ.name, feuille)
    assert {c.__name__ for c in vus} >= {"Carto", "Societe", "Lien", "Participation", "Mandat", "Etrangere"}


def test_aucun_nom_de_personne_dans_la_sortie(registre: Path) -> None:
    sortie = repr(cartographier(REGLAGES, registre))
    for fragment in NOMS_DE_PERSONNES:
        assert fragment not in sortie


def test_registre_lu_sans_etre_modifie_et_resultat_stable(registre: Path) -> None:
    empreinte = hashlib.sha256(registre.read_bytes()).hexdigest()
    premiere = cartographier(REGLAGES, registre)
    seconde = cartographier(REGLAGES, registre)
    assert premiere == seconde
    assert hashlib.sha256(registre.read_bytes()).hexdigest() == empreinte
    assert not list(registre.parent.glob("*.wal"))


def test_registre_absent(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        cartographier(REGLAGES, tmp_path / "absent.duckdb")


@pytest.mark.parametrize(
    "nom",
    [
        "Moët & Chandon",
        "L'ŒUVRE  d'Art",
        "  été\tà Paris ",
        "Straße",
        "ÅNGSTRÖM-12",
        "",
        "ﬁnance ①",
        "日本 SA",
    ],
)
def test_normalisation_vectorisee_identique(nom: str) -> None:
    assert norm_arrow(pa.array([nom])).to_pylist() == [norm(nom)]


def test_normalisation_vide() -> None:
    assert norm(None) == ""
    assert norm_arrow(pa.array([None], type=pa.string())).to_pylist() == [""]
