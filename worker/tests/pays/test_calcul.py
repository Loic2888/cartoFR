"""Carto du pays (T048), sur un mini-registre et des documents inventés.

Tous les noms, SIREN et dirigeants sont inventés (règle produit 6). Les documents sont en texte,
au format de la liste VINCI, déposés par la vraie commande de T046.

Ce que le mini-registre contient :
- un arbre sans document : H dirige X, Y et la SCI Z0, X dirige X1 ;
- une boucle dans l'arbre : L1 dirige L2, L2 dirige L1 ;
- le groupe à document A, qui inscrit P. P a pour mère au registre la holding H2, qui dirige
  aussi SOEUR. P dirige PF ;
- un entrepreneur individuel E (sans siège) qui préside E1 et E2 ; E1 dirige E11 ;
- une société fermée F qui préside F1 ; F1 dirige F11 ;
- deux groupes emboîtés : D inscrit la tête B, B inscrit BETA, que B dirige ;
- deux groupes qui inscrivent le même PIVOT (G1 à 100 %, G2 à 50 %) ; PIVOT dirige RAMEAU.
"""

import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pytest

from cartofr.moteur import cartographier
from cartofr.pays import calcul
from cartofr.perimetre import PerimetrePublie, correspondre_plusieurs, extraire
from cartofr.perimetre.deposer import Demande, deposer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "moteur"))
from fabrique import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    CJ_SCI,
    GERANT,
    PRESIDENT,
    MiniRegistre,
    personne,
    siren,
)

H, X, Y, X1, Z0 = siren(30), siren(31), siren(32), siren(33), siren(34)
L1, L2 = siren(90), siren(91)
A, H2, P, SOEUR, PF = siren(1), siren(20), siren(21), siren(22), siren(23)
E, E1, E2, E11 = siren(40), siren(41), siren(42), siren(43)
F, F1, F11 = siren(50), siren(51), siren(52)
D, B, BETA = siren(60), siren(61), siren(62)
G2, G1, PIVOT, RAMEAU = siren(70), siren(71), siren(72), siren(73)
SEULE = siren(80)
DIRIGEANT = personne(1, famille="DIRIGEANTE SECRETE")
LE = datetime(2026, 10, 18, 6, 0, tzinfo=UTC)


def _mini() -> MiniRegistre:
    mini = MiniRegistre()
    for s, nom in (
        (H, "HOLDING ARBRE INVENTEE"), (X, "XENON INVENTEE"), (Y, "YUCCA INVENTEE"),
        (X1, "XENON FILLE INVENTEE"),
        (A, "TETE A INVENTEE"), (H2, "HOLDING DEUX INVENTEE"), (P, "PRIMA INVENTEE"),
        (SOEUR, "SOEUR INVENTEE"), (PF, "PRIMA FILLE INVENTEE"),
        (E1, "EPSILON UN INVENTEE"), (E2, "EPSILON DEUX INVENTEE"), (E11, "EPSILON FILLE INVENTEE"),
        (F1, "FOX UN INVENTEE"), (F11, "FOX FILLE INVENTEE"),
        (D, "TETE D INVENTEE"), (B, "TETE B INVENTEE"), (BETA, "BETA INVENTEE"),
        (G2, "TETE G DEUX INVENTEE"), (G1, "TETE G UN INVENTEE"), (PIVOT, "PIVOT INVENTEE"),
        (RAMEAU, "RAMEAU INVENTEE"), (SEULE, "SEULE INVENTEE"),
    ):  # fmt: skip
        mini.societe(s, nom)
    mini.societe(F, "FERMEE INVENTEE", active=False)
    mini.societe(Z0, "ZETA CIVILE INVENTEE", cj=CJ_SCI, tranche=None)
    mini.societe(L1, "LAMBDA UN INVENTEE")
    mini.societe(L2, "LAMBDA DEUX INVENTEE")
    for parent, enfant, role in (
        (H, X, PRESIDENT), (H, Y, GERANT), (X, X1, PRESIDENT), (H, Z0, GERANT),
        (L1, L2, PRESIDENT), (L2, L1, PRESIDENT),
        (H2, P, PRESIDENT), (H2, SOEUR, PRESIDENT), (P, PF, PRESIDENT),
        (E, E1, PRESIDENT), (E, E2, PRESIDENT), (E1, E11, PRESIDENT),
        (F, F1, PRESIDENT), (F1, F11, PRESIDENT),
        (B, BETA, PRESIDENT),
        (PIVOT, RAMEAU, PRESIDENT),
    ):  # fmt: skip
        mini.lien(parent, enfant, role)
    mini.dirigeant(X, DIRIGEANT)
    mini.dirigeant(E1, DIRIGEANT)
    return mini


def _ligne(nom: str, taux: str = "100,00") -> str:
    return f"{nom} France {taux} Intégration globale"


DOCUMENTS = {
    A: [_ligne("Prima Inventée")],
    D: [_ligne("Tete B Inventée")],
    B: [_ligne("Beta Inventée")],
    G1: [_ligne("Pivot Inventée")],
    G2: [_ligne("Pivot Inventée", "50,00")],
}


def _preparer(racine: Path) -> Path:
    data = racine / "data"
    data.mkdir()
    registre = _mini().ecrire(data / "registre.duckdb")
    # E est un entrepreneur individuel : connu du RNE, absent de SIRENE (ni siège ni unité légale).
    con = duckdb.connect(str(registre))
    try:
        con.execute(
            "insert into societes (siren, denomination, diffusion_commerciale, opposition_prospection,"
            " non_diffusible, etat_administratif, debut) values (?, 'ENTREPRENEUR INVENTE', true, false,"
            " false, 'A', date '2026-03-04')",
            [E],
        )
    finally:
        con.close()
    demandes = []
    for tete, lignes in DOCUMENTS.items():
        chemin = racine / f"{tete}.txt"
        chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")
        demandes.append(Demande(tete, chemin))
    deposer(demandes, data, maintenant=LE)
    return data


@pytest.fixture(scope="module")
def data(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _preparer(tmp_path_factory.mktemp("pays"))


@pytest.fixture(scope="module")
def bilan(data: Path) -> calcul.Bilan:
    return calcul.lancer(data)


def _lire(data: Path, requete: str) -> list[tuple[Any, ...]]:
    con = duckdb.connect(str(data / "pays.duckdb"), read_only=True)
    try:
        return con.execute(requete).fetchall()
    finally:
        con.close()


@pytest.fixture(scope="module")
def societes(data: Path, bilan: calcul.Bilan) -> dict[str, dict[str, Any]]:
    con = duckdb.connect(str(data / "pays.duckdb"), read_only=True)
    try:
        curseur = con.execute("select * from pays_societes")
        colonnes = [c[0] for c in curseur.description or []]
        return {r[0]: dict(zip(colonnes, r, strict=True)) for r in curseur.fetchall()}
    finally:
        con.close()


@pytest.fixture(scope="module")
def groupes(data: Path, bilan: calcul.Bilan) -> dict[str, dict[str, Any]]:
    con = duckdb.connect(str(data / "pays.duckdb"), read_only=True)
    try:
        curseur = con.execute("select * from pays_groupes")
        colonnes = [c[0] for c in curseur.description or []]
        return {r[0]: dict(zip(colonnes, r, strict=True)) for r in curseur.fetchall()}
    finally:
        con.close()


def membres(societes: dict[str, dict[str, Any]], tete: str) -> set[str]:
    return {s for s, li in societes.items() if li["groupe"] == tete}


def descente(societes: dict[str, dict[str, Any]], depart: str) -> set[str]:
    """La carto d'une société : elle et tout ce qui descend d'elle par `mere`."""
    sortie, front = {depart}, [depart]
    while front:
        x = front.pop()
        for s, li in societes.items():
            if li["mere"] == x and s not in sortie:
                sortie.add(s)
                front.append(s)
    return sortie


# --- C1 : rangement ----------------------------------------------------------------------------


def test_c1_arbre_non_reclame_est_son_groupe_avec_la_preuve_du_role(
    societes: dict[str, dict[str, Any]], groupes: dict[str, dict[str, Any]]
) -> None:
    assert membres(societes, H) == {H, X, Y, X1, Z0}
    assert groupes[H]["taille"] == 5 and groupes[H]["document"] is None and groupes[H]["parent"] is None
    assert (societes[H]["mere"], societes[H]["niveau"], societes[H]["preuve"]) == (None, 0, "Tête du groupe")
    assert (societes[Y]["mere"], societes[Y]["niveau"]) == (H, 1)
    assert (societes[Y]["preuve"], societes[Y]["confiance"]) == ("Mandat au registre : Gérant", "A")
    assert (societes[X1]["mere"], societes[X1]["niveau"]) == (X, 2)
    assert {societes[s]["maniere"] for s in (H, X, Y, X1)} == {"arbre"}
    # La règle « ciblable » du moteur s'applique aussi aux arbres.
    assert (societes[Y]["ciblable"], societes[Y]["raison_ciblable"]) == (True, "Société opérationnelle")
    assert (societes[Z0]["ciblable"], societes[Z0]["raison_ciblable"]) == (False, "Société civile ou SCI")
    assert (societes[H]["ciblable"], societes[H]["raison_ciblable"]) == (True, "Société mère du groupe")


def test_c1_boucle_de_l_arbre_coupee_au_plus_petit_siren(societes: dict[str, dict[str, Any]]) -> None:
    assert membres(societes, L1) == {L1, L2}
    assert (societes[L1]["mere"], societes[L1]["niveau"]) == (None, 0)
    assert (societes[L2]["mere"], societes[L2]["niveau"]) == (L1, 1)


def test_c1_inscrite_entre_avec_ses_filiales_jamais_avec_ses_soeurs(
    societes: dict[str, dict[str, Any]], groupes: dict[str, dict[str, Any]]
) -> None:
    """Décision du 2026-10-18 : P entre dans A avec PF ; SOEUR, l'autre filiale de H2, n'y entre pas."""
    assert membres(societes, A) == {A, P, PF}
    assert societes[P]["maniere"] == "inscription" and societes[P]["mere"] == A
    assert societes[PF]["mere"] == P and societes[PF]["niveau"] == 2
    assert groupes[A]["document"] and groupes[A]["document"].startswith(A)
    # Le reste de l'arbre de H2 forme son propre groupe.
    assert membres(societes, H2) == {H2, SOEUR}


def test_c1_chaque_groupe_est_la_descente_depuis_sa_tete(
    societes: dict[str, dict[str, Any]], groupes: dict[str, dict[str, Any]]
) -> None:
    for tete, g in groupes.items():
        assert membres(societes, tete) <= descente(societes, tete), tete
        assert g["taille"] == len(membres(societes, tete))
    # La carto d'une filiale ne remonte pas : X ne voit que lui et X1.
    assert descente(societes, X) == {X, X1}


def test_c1_groupes_emboites(societes: dict[str, dict[str, Any]], groupes: dict[str, dict[str, Any]]) -> None:
    """B, inscrite au document de D, garde son groupe ; la carto de D descend dans B."""
    assert groupes[B]["parent"] == D and groupes[D]["parent"] is None
    assert membres(societes, B) == {B, BETA}
    assert societes[B]["groupe"] == B and societes[B]["mere"] == D and societes[B]["niveau"] == 0
    assert societes[BETA]["raison_departage"]  # réclamée par B et par D
    assert descente(societes, D) == {D, B, BETA}


def test_c1_mere_rangee_ailleurs_rattachement_deduit(societes: dict[str, dict[str, Any]]) -> None:
    """PIVOT va à G1 (taux plus haut) ; RAMEAU, à égalité de niveau, va à la plus petite tête G2.
    Sa mère directe est dans G1 : RAMEAU est rattachée à G2 en confiance C, et la preuve le dit."""
    assert societes[PIVOT]["groupe"] == G1
    assert societes[RAMEAU]["groupe"] == G2
    assert (societes[RAMEAU]["mere"], societes[RAMEAU]["confiance"]) == (G2, "C")
    assert PIVOT in societes[RAMEAU]["preuve"] and G1 in societes[RAMEAU]["preuve"]


def test_c1_une_societe_dans_un_seul_groupe_et_les_isolees_absentes(
    data: Path, societes: dict[str, dict[str, Any]], groupes: dict[str, dict[str, Any]]
) -> None:
    lignes = _lire(data, "select siren, count(*) from pays_societes group by siren having count(*) > 1")
    assert lignes == []
    assert SEULE not in societes and SEULE not in groupes
    assert all(li["groupe"] in groupes for li in societes.values())


# --- C3 : personnes ----------------------------------------------------------------------------


def test_c3_entrepreneur_individuel_jamais_ecrit_ses_societes_separees(
    data: Path, societes: dict[str, dict[str, Any]], groupes: dict[str, dict[str, Any]]
) -> None:
    """Décision du 2026-10-18 : les sociétés d'une même personne ne forment pas un groupe."""
    assert membres(societes, E1) == {E1, E11} and societes[E1]["mere"] is None
    assert E2 not in societes  # seule, sans filiale
    assert E not in societes and E not in groupes
    texte = repr(_lire(data, "select * from pays_societes")) + repr(_lire(data, "select * from pays_groupes"))
    assert E not in texte and "ENTREPRENEUR INVENTE" not in texte
    assert "DIRIGEANTE SECRETE" not in texte


def test_c3_mere_fermee_coupe_l_arbre(societes: dict[str, dict[str, Any]]) -> None:
    assert membres(societes, F1) == {F1, F11} and F not in societes


def test_c3_aucune_colonne_de_personne(data: Path, bilan: calcul.Bilan) -> None:
    colonnes = {c for (c,) in _lire(data, "select column_name from information_schema.columns")}
    assert not {c for c in colonnes if "personne" in c or "dirigeant" in c}


def test_c3_journal_sans_nom(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    data = _preparer(tmp_path)
    with caplog.at_level(logging.DEBUG):
        calcul.lancer(data)
    assert "DIRIGEANTE SECRETE" not in caplog.text and E not in caplog.text
    assert "INVENTE" not in caplog.text


# --- C5 : journal, échec ------------------------------------------------------------------------


def _journal(data: Path) -> list[tuple[Any, ...]]:
    con = duckdb.connect(str(data / "registre.duckdb"), read_only=True)
    try:
        return con.execute(
            "select statut, ajoutes, fermes, erreur from mises_a_jour where source = 'pays' order by id"
        ).fetchall()
    finally:
        con.close()


def test_c5_succes_journalise_societes_et_groupes(data: Path, bilan: calcul.Bilan) -> None:
    assert _journal(data)[0] == ("succes", bilan.societes, bilan.groupes, None)
    assert _lire(data, "select groupes, societes, documents, documents_en_echec from pays_bilan") == [
        (bilan.groupes, bilan.societes, 5, 0)
    ]


def test_c5_echec_laisse_le_fichier_precedent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = _preparer(tmp_path)
    premier = calcul.lancer(data)
    avant = (data / "pays.duckdb").read_bytes()

    def panne(*_: Any) -> calcul.Resultat:
        raise RuntimeError("panne inventée")

    monkeypatch.setattr(calcul, "ranger", panne)
    with pytest.raises(RuntimeError):
        calcul.lancer(data)
    assert (data / "pays.duckdb").read_bytes() == avant
    assert [ligne[0] for ligne in _journal(data)] == ["succes", "echec"]
    assert _journal(data)[1][3] == "RuntimeError pendant le calcul de la carto du pays"
    assert premier.groupes > 0
    assert not list(data.glob("pays.duckdb.*.en-construction*"))


def test_c5_echec_d_ecriture_ne_laisse_rien(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = _preparer(tmp_path)

    def remplacer(*_: Any) -> None:
        raise OSError("disque plein inventé")

    monkeypatch.setattr(calcul.os, "replace", remplacer)
    with pytest.raises(OSError):
        calcul.lancer(data)
    assert not (data / "pays.duckdb").exists()
    assert not list(data.glob("pays.duckdb.*"))
    assert _journal(data)[-1][0] == "echec"


def test_document_absent_compte_en_echec_ses_societes_restent_aux_arbres(tmp_path: Path) -> None:
    data = _preparer(tmp_path)
    for fichier in (data / "perimetre").glob(f"{A}-*"):
        fichier.unlink()
    bilan = calcul.lancer(data)
    assert (bilan.documents, bilan.documents_en_echec) == (5, 1)
    con = duckdb.connect(str(data / "pays.duckdb"), read_only=True)
    try:
        rangs = dict(con.execute("select siren, groupe from pays_societes").fetchall())
    finally:
        con.close()
    assert rangs[P] == H2 and rangs[PF] == H2 and A not in rangs


def test_registre_sans_documents(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    _mini().ecrire(data / "registre.duckdb")
    bilan = calcul.lancer(data)
    assert bilan.documents == 0 and bilan.groupes > 0


def test_registre_absent(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        calcul.lancer(tmp_path)


# --- Moteur : correspondances déjà calculées ----------------------------------------------------


def test_moteur_meme_carto_avec_correspondances_deja_calculees(data: Path, bilan: calcul.Bilan) -> None:
    lignes = extraire("\n".join(DOCUMENTS[A]) + "\n")
    registre = data / "registre.duckdb"
    document = PerimetrePublie("a.txt", tuple(lignes))
    reglages = calcul.reglages_tete_seule(A, "TETE A INVENTEE")
    seule = cartographier(reglages, registre, perimetre=document)
    con = duckdb.connect(str(registre), read_only=True)
    try:
        (res,) = correspondre_plusieurs(con, [(A, lignes)])
    finally:
        con.close()
    avec = cartographier(reglages, registre, perimetre=document, correspondances=res)
    assert avec == seule


# --- Échecs comptés, sans arrêter le calcul -----------------------------------------------------


@pytest.mark.parametrize("etape", ["texte_document", "cartographier", "_actives"])
def test_document_illisible_moteur_en_echec_tete_inactive_comptes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, etape: str
) -> None:
    """Un PDF abîmé (pypdf lève n'importe quoi), un moteur qui plante ou une tête sans siège actif : le
    groupe est compté en échec, ses sociétés restent aux arbres, le calcul continue."""
    data = _preparer(tmp_path)
    if etape == "_actives":
        monkeypatch.setattr(calcul, "_actives", lambda *_: set())
    else:

        def panne(*_: Any, **__: Any) -> Any:
            raise KeyError("panne inventée")

        monkeypatch.setattr(calcul, etape, panne)
    bilan = calcul.lancer(data)
    assert (bilan.documents, bilan.documents_en_echec) == (5, 5)
    rangs = dict(_lire(data, "select siren, groupe from pays_societes"))
    assert rangs[P] == H2 and A not in rangs


# --- Têtes de groupes à document : jamais rangées dans un autre groupe ---------------------------


def _registre(
    racine: Path, noms: dict[str, str], liens: list[tuple[str, str]], documents: dict[str, list[str]]
) -> Path:
    data = racine / "data"
    data.mkdir()
    mini = MiniRegistre()
    for s, nom in noms.items():
        mini.societe(s, nom)
    for parent, enfant in liens:
        mini.lien(parent, enfant, PRESIDENT)
    mini.ecrire(data / "registre.duckdb")
    demandes = []
    for tete, lignes in documents.items():
        chemin = racine / f"{tete}.txt"
        chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")
        demandes.append(Demande(tete, chemin))
    deposer(demandes, data, maintenant=LE)
    calcul.lancer(data)
    return data


def _table(data: Path) -> dict[str, dict[str, Any]]:
    con = duckdb.connect(str(data / "pays.duckdb"), read_only=True)
    try:
        curseur = con.execute("select * from pays_societes")
        colonnes = [c[0] for c in curseur.description or []]
        return {r[0]: dict(zip(colonnes, r, strict=True)) for r in curseur.fetchall()}
    finally:
        con.close()


def test_deux_documents_qui_s_inscrivent_l_un_l_autre(tmp_path: Path) -> None:
    """K1 inscrit K2, K2 inscrit K1 : chaque tête reste dans son groupe, K2 est le sous-groupe de K1
    (plus petite tête), et les mères ne tournent pas en boucle (revue du 2026-10-18 : avant, la tête K1
    était rangée dans K2 et K1 et K2 étaient mères l'une de l'autre)."""
    k1, k2, kf = siren(100), siren(101), siren(102)
    data = _registre(
        tmp_path,
        {k1: "TETE KAPPA UN INVENTEE", k2: "TETE KAPPA DEUX INVENTEE", kf: "KAPPA FILLE INVENTEE"},
        [(k1, kf)],
        {k1: [_ligne("Tete Kappa Deux Inventée")], k2: [_ligne("Tete Kappa Un Inventée")]},
    )
    lignes = _table(data)
    assert (lignes[k1]["groupe"], lignes[k1]["mere"], lignes[k1]["niveau"]) == (k1, None, 0)
    assert (lignes[k2]["groupe"], lignes[k2]["mere"], lignes[k2]["niveau"]) == (k2, k1, 0)
    # Données contradictoires : la règle de T047 range la fille de K1 dans le sous-groupe K2, réclamé de
    # plus près. Elle reste dans la carto de K1, rattachée à K2 en confiance C.
    assert (lignes[kf]["groupe"], lignes[kf]["mere"], lignes[kf]["confiance"]) == (k2, k2, "C")
    assert dict(_lire(data, "select tete, parent from pays_groupes")) == {k1: None, k2: k1}
    assert descente(lignes, k1) == {k1, k2, kf}


def test_meme_tete_inscrite_par_deux_documents(tmp_path: Path) -> None:
    """P (100 %) et Q (60 %) inscrivent la tête T : T garde son groupe et sa fille, sous P."""
    t, tf, p, q = siren(110), siren(111), siren(112), siren(113)
    data = _registre(
        tmp_path,
        {t: "TETE TAU INVENTEE", tf: "TAU FILLE INVENTEE", p: "TETE PI INVENTEE", q: "TETE QOPPA INVENTEE"},
        [(t, tf)],
        {
            t: [_ligne("Tau Fille Inventée")],
            p: [_ligne("Tete Tau Inventée")],
            q: [_ligne("Tete Tau Inventée", "60,00")],
        },
    )
    lignes = _table(data)
    assert (lignes[t]["groupe"], lignes[t]["mere"]) == (t, p)
    assert (lignes[tf]["groupe"], lignes[tf]["mere"], lignes[tf]["niveau"]) == (t, t, 1)
    assert dict(_lire(data, "select tete, parent from pays_groupes"))[t] == p


def test_tete_de_sous_groupe_dont_la_mere_directe_est_rangee_ailleurs(tmp_path: Path) -> None:
    """D inscrit la tête B et MU (50 %) ; Z inscrit MU (100 %), qui préside B. B garde D pour mère, en
    confiance C, et la preuve nomme le groupe qui a pris MU : Z, pas D."""
    d, b, mu, z, bf = siren(120), siren(121), siren(122), siren(123), siren(124)
    data = _registre(
        tmp_path,
        {
            d: "TETE DELTA INVENTEE",
            b: "TETE BETA INVENTEE",
            mu: "MU INVENTEE",
            z: "TETE ZETA INVENTEE",
            bf: "BETA FILLE INVENTEE",
        },  # fmt: skip
        [(mu, b), (b, bf)],
        {
            d: [_ligne("Tete Beta Inventée"), _ligne("Mu Inventée", "50,00")],
            z: [_ligne("Mu Inventée")],
            b: [_ligne("Beta Fille Inventée")],
        },
    )
    lignes = _table(data)
    assert lignes[mu]["groupe"] == z
    assert (lignes[b]["groupe"], lignes[b]["mere"], lignes[b]["confiance"]) == (b, d, "C")
    assert lignes[b]["preuve"] == f"Déduit : maison mère directe {mu} rangée dans le groupe {z}"
