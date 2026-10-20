"""Groupes mutualistes dans la carto du pays (T049), sur un mini-registre et des DEU inventés.

Tous les noms et SIREN sont inventés (règle produit 6). Les documents sont des paquets ESEF
inventés, déposés par la vraie commande de T046, puis la carto du pays est calculée en entier.

Ce que le mini-registre contient :
- la caisse fédérale CF (Bas-Rhin), dont le DEU nomme la fédération « Centre Inventé » et inscrit
  BANQUE. Au registre, la mère de BANQUE est l'autre caisse fédérale CF2, par un seul mandat
  d'administrateur : les deux fédérations sont dans le même arbre. BANQUE préside BF ;
- la caisse fédérale CF2 (Vendée), dont le DEU nomme la fédération « Océan » et inscrit OUEST ;
- le GIE_A, dont CF est membre, avec 21 caisses A de Loire-Atlantique, une caisse S79 des
  Deux-Sèvres (département partagé), deux caisses O85 de Vendée (territoire d'Océan) et trois
  caisses D membres aussi du GIE_B ;
- le GIE_B, plus petit, dont CF2 est membre, avec 21 caisses B de Vendée et les trois caisses D ;
- le GIE_F, fermé, dont les caisses A sont aussi membres.
"""

import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pytest

from cartofr.pays import calcul, mutualiste
from cartofr.perimetre.deposer import Demande, deposer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "moteur"))
from fabrique import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    ADMINISTRATEUR,
    CJ_GIE,
    MEMBRE,
    PRESIDENT,
    MiniRegistre,
    siren,
)

CJ_CAISSE = 5194
CF, CF2, GIE_A, GIE_B, GIE_F = siren(1), siren(2), siren(10), siren(11), siren(12)
BANQUE, BF, OUEST, SAS = siren(20), siren(21), siren(22), siren(23)
A = [siren(100 + i) for i in range(21)]
B = [siren(200 + i) for i in range(21)]
D = [siren(300 + i) for i in range(3)]
O85 = [siren(400), siren(401)]
S79 = siren(500)
LE = datetime(2026, 10, 20, 6, 0, tzinfo=UTC)


def _caisse(mini: MiniRegistre, s: str, nom: str, cp: str) -> None:
    mini.societe(s, nom, cj=CJ_CAISSE, cp=cp, naf="64.19Z")


def _mini() -> MiniRegistre:
    mini = MiniRegistre()
    _caisse(mini, CF, "CAISSE FEDERALE DE CREDIT MUTUEL INVENTEE", "67000")
    _caisse(mini, CF2, "CAISSE FEDERALE DU CREDIT MUTUEL OCEAN INVENTEE", "85000")
    mini.societe(GIE_A, "GIE CENTRE INVENTE", cj=CJ_GIE)
    mini.societe(GIE_B, "GIE OUEST INVENTE", cj=CJ_GIE)
    mini.societe(GIE_F, "GIE FERME INVENTE", cj=CJ_GIE, active=False)
    mini.societe(BANQUE, "BANQUE INVENTEE DU GROUPE")
    mini.societe(BF, "BANQUE FILLE INVENTEE")
    mini.societe(OUEST, "FILIALE OUEST INVENTEE")
    mini.societe(SAS, "SAS INVENTEE SANS CAISSE")
    for i, s in enumerate(A):
        _caisse(mini, s, f"CAISSE DE CREDIT MUTUEL INVENTEE A{i}", "44000")
    for i, s in enumerate(B):
        _caisse(mini, s, f"CAISSE DE CREDIT MUTUEL INVENTEE B{i}", "85000")
    for i, s in enumerate(D):
        _caisse(mini, s, f"CAISSE DE CREDIT MUTUEL INVENTEE D{i}", "49000")
    for i, s in enumerate(O85):
        _caisse(mini, s, f"CAISSE DE CREDIT MUTUEL INVENTEE O{i}", "85000")
    _caisse(mini, S79, "CAISSE DE CREDIT MUTUEL INVENTEE NIORT", "79000")
    for s in (CF, *A, S79, *O85, *D):
        mini.lien(s, GIE_A, MEMBRE)
    for s in (CF2, *B, *D):
        mini.lien(s, GIE_B, MEMBRE)
    for s in A:
        mini.lien(s, GIE_F, MEMBRE)
    mini.lien(CF2, BANQUE, ADMINISTRATEUR)
    mini.lien(BANQUE, BF, PRESIDENT)
    mini.lien(CF2, OUEST, PRESIDENT)
    return mini


def _rangee(*cellules: str) -> str:
    return "<tr>" + "".join(f"<td><div><span>{c}</span></div></td>" for c in cellules) + "</tr>"


def _paquet(chemin: Path, federations: str, *noms: str) -> Path:
    rangees = "".join(_rangee(n, "France", "100", "98", "IG", "100", "98", "IG") for n in noms)
    xhtml = (
        '<html xmlns="http://www.w3.org/1999/xhtml"><body>'
        f"<p>les Fédérations du Crédit Mutuel {federations} ; les caisses.</p>"
        f"<table>{rangees}</table></body></html>"
    )
    with zipfile.ZipFile(chemin, "w") as z:
        z.writestr("deu/reports/deu.xhtml", xhtml)
    return chemin


@pytest.fixture(scope="module")
def data(tmp_path_factory: pytest.TempPathFactory) -> Path:
    racine = tmp_path_factory.mktemp("mutualiste")
    data = racine / "data"
    data.mkdir()
    _mini().ecrire(data / "registre.duckdb")
    deposer(
        [
            Demande(CF, _paquet(racine / "cf.zip", "Centre Inventé (FCMCI)", "Banque Inventée du Groupe")),
            Demande(CF2, _paquet(racine / "cf2.zip", "Océan (FCMO)", "Filiale Ouest Inventée")),
        ],
        data,
        maintenant=LE,
    )
    calcul.lancer(data)
    return data


def _table(data: Path, table: str) -> dict[str, dict[str, Any]]:
    con = duckdb.connect(str(data / "pays.duckdb"), read_only=True)
    try:
        curseur = con.execute(f"select * from {table}")
        colonnes = [c[0] for c in curseur.description or []]
        return {r[0]: dict(zip(colonnes, r, strict=True)) for r in curseur.fetchall()}
    finally:
        con.close()


@pytest.fixture(scope="module")
def societes(data: Path) -> dict[str, dict[str, Any]]:
    return _table(data, "pays_societes")


@pytest.fixture(scope="module")
def groupes(data: Path) -> dict[str, dict[str, Any]]:
    return _table(data, "pays_groupes")


def membres(societes: dict[str, dict[str, Any]], tete: str) -> set[str]:
    return {s for s, li in societes.items() if li["groupe"] == tete}


# --- C2 : deux fédérations dans un même arbre sont séparées ---------------------------------------


def test_c2_filiale_sous_une_autre_federation_par_un_mandat_d_administrateur(
    societes: dict[str, dict[str, Any]],
) -> None:
    # Dans l'arbre du registre, BANQUE et BF sont sous CF2 ; le DEU de CF les range chez CF.
    assert {BANQUE, BF} <= membres(societes, CF)
    assert membres(societes, CF2) & {BANQUE, BF} == set()
    assert OUEST in membres(societes, CF2)


def test_c2_une_caisse_locale_rejoint_sa_federation(societes: dict[str, dict[str, Any]]) -> None:
    assert set(A) <= membres(societes, CF)
    caisse = societes[A[0]]
    assert (caisse["mere"], caisse["niveau"], caisse["confiance"]) == (CF, 1, "B")
    assert caisse["preuve"] == f"Caisse membre du GIE GIE CENTRE INVENTE ({GIE_A}), comme la caisse fédérale"
    assert caisse["raison"] == "Caisse locale de la fédération (groupe mutualiste)"


def test_c2_caisse_d_un_departement_partage_gardee(societes: dict[str, dict[str, Any]]) -> None:
    assert societes[S79]["groupe"] == CF


def test_c2_caisse_du_territoire_d_une_federation_que_le_document_ne_nomme_pas(
    societes: dict[str, dict[str, Any]],
) -> None:
    # Membres du GIE de CF, mais en Vendée : Océan n'est pas dans le DEU de CF. Ni dans le GIE de
    # CF2 : chacune reste seule, sa propre carto (une société seule n'est pas écrite).
    for s in O85:
        assert s not in societes


def test_c2_caisse_de_deux_gie_va_au_plus_petit(societes: dict[str, dict[str, Any]]) -> None:
    assert set(D) <= membres(societes, CF2)
    assert set(B) <= membres(societes, CF2)  # le territoire d'Océan est nommé par le DEU de CF2


def test_c2_gie_ferme_ne_compte_pas(societes: dict[str, dict[str, Any]]) -> None:
    # Les caisses A sont aussi membres du GIE_F, plus petit mais fermé : elles restent chez CF.
    assert all(societes[s]["groupe"] == CF for s in A)


def test_groupes_mutualistes_marques(groupes: dict[str, dict[str, Any]]) -> None:
    assert groupes[CF]["mutualiste"] and groupes[CF2]["mutualiste"]
    assert groupes[CF]["taille"] == 1 + 2 + len(A) + 1  # tête, BANQUE et BF, caisses A, S79
    assert SAS not in groupes  # seule : ni groupe ni drapeau


# --- C4 : aucune société dans deux groupes mutualistes -------------------------------------------


def test_c4_aucune_societe_dans_deux_groupes_mutualistes(
    data: Path, societes: dict[str, dict[str, Any]]
) -> None:
    con = duckdb.connect(str(data / "pays.duckdb"), read_only=True)
    try:
        doublons = con.execute(
            "select siren from pays_societes group by siren having count(*) > 1"
        ).fetchall()
    finally:
        con.close()
    assert doublons == []
    assert membres(societes, CF) & membres(societes, CF2) == set()


# --- La règle seule ------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def con(tmp_path_factory: pytest.TempPathFactory):
    chemin = _mini().ecrire(tmp_path_factory.mktemp("regle") / "r.duckdb")
    connexion = duckdb.connect(str(chemin), read_only=True)
    yield connexion
    connexion.close()


def test_tete_qui_n_est_pas_une_caisse_n_a_pas_de_caisses(con: duckdb.DuckDBPyConnection) -> None:
    assert mutualiste.caisses(con, SAS, "") == []
    assert mutualiste.caisses(con, BANQUE, "Centre Inventé") == []


def test_document_sans_liste_exclut_tous_les_territoires_sauf_celui_de_la_tete() -> None:
    tous = sorted(d for f in mutualiste.TERRITOIRES for d in f.departements)
    assert mutualiste.departements_exclus("", None) == tous
    assert "85" not in mutualiste.departements_exclus("", "85")


def test_federation_nommee_par_le_document_non_exclue() -> None:
    exclus = mutualiste.departements_exclus("Océan (FCMO), du Sud-Ouest (FCMSO)", "67")
    assert not {"85", "17", "33", "24", "16"} & set(exclus)
    assert {"53", "72", "50", "61", "29"} <= set(exclus)
    # « Sud-Est » n'est pas « Sud-Ouest », « Anjou » n'est pas « Maine-Anjou ».
    assert {"33", "53"} <= set(mutualiste.departements_exclus("du Sud-Est (FCMSE), d’Anjou (FCMA)", "67"))


def test_caisses_d_une_caisse_federale_sans_document(con: duckdb.DuckDBPyConnection) -> None:
    trouvees = {c.siren for c in mutualiste.caisses(con, CF, "Centre Inventé")}
    assert trouvees == {*A, S79}
