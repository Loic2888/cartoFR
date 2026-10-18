"""Dépôt des documents de périmètre et correspondance de plusieurs documents (T046), sur données inventées.

Documents en texte, au format de la liste VINCI ; registres fabriqués par `fabrique.MiniRegistre`.
Tous les noms et SIREN sont inventés (règle produit 6).
"""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb
import pytest

from cartofr.moteur.marques import chercher_candidates
from cartofr.perimetre import correspondre, correspondre_plusieurs, extraire
from cartofr.perimetre import deposer as module
from cartofr.perimetre.deposer import Demande, DepotInvalide, deposer, main, resume

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "moteur"))
from fabrique import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    PRESIDENT,
    MiniRegistre,
    reglages,
    siren,
)

A, B, C = siren(1), siren(2), siren(3)
LE = datetime(2026, 10, 16, 7, 30, tzinfo=UTC)


def _ligne(nom: str) -> str:
    return f"{nom} France 100,00 Intégration globale"


def _mini() -> MiniRegistre:
    """Trois têtes ; « ALPHA INVENTEE » a deux porteurs, dont un seul est relié à A par le registre."""
    mini = MiniRegistre()
    for tete, nom in ((A, "TETE A INVENTEE"), (B, "TETE B INVENTEE"), (C, "TETE C INVENTEE")):
        mini.societe(tete, nom)
    mini.societe(siren(10), "ALPHA INVENTEE")
    mini.societe(siren(11), "ALPHA INVENTEE", commune="LYON")
    mini.lien(A, siren(10), PRESIDENT)
    mini.societe(siren(20), "BETA INVENTEE")
    mini.societe(siren(30), "GAMMA INVENTEE")
    return mini


DOCUMENTS = {
    A: [_ligne("Alpha Inventée"), _ligne("Beta Inventée")],
    B: [_ligne("Beta Inventée"), _ligne("Introuvable Inventée")],
    C: [_ligne("Gamma Inventée"), _ligne("Alpha Inventée")],
}


@pytest.fixture
def data(tmp_path: Path) -> Path:
    dossier = tmp_path / "data"
    dossier.mkdir()
    _mini().ecrire(dossier / "registre.duckdb")
    return dossier


def _document(tmp_path: Path, nom: str, lignes: list[str], avant: str = "") -> Path:
    chemin = tmp_path / nom
    chemin.write_text(avant + "\n".join(lignes) + "\n", encoding="utf-8")
    return chemin


def _lignes_table(data: Path) -> list[tuple[Any, ...]]:
    con = duckdb.connect(str(data / "registre.duckdb"), read_only=True)
    try:
        return con.execute(
            "select tete, fichier, fin is null, lignes, retenues, refusees"
            " from documents_perimetre order by id"
        ).fetchall()
    finally:
        con.close()


# ---------------------------------------------------------------- C2 : plusieurs documents, un passage


def test_plusieurs_documents_meme_resultat_que_un_par_un(data: Path) -> None:
    con = duckdb.connect(str(data / "registre.duckdb"), read_only=True)
    try:
        documents = [(t, extraire("\n".join(li))) for t, li in DOCUMENTS.items()]
        ensemble = correspondre_plusieurs(con, documents)
        un_par_un = [correspondre(con, t, lignes) for t, lignes in documents]
    finally:
        con.close()
    assert ensemble == un_par_un
    # L'homonyme est départagé par le registre pour A seulement : C ne relie aucun des deux porteurs.
    assert [c.siren for c in ensemble[0]] == [siren(10), siren(20)]
    assert [c.raison for c in ensemble[2]] == ["unique", "homonymes"]


# ---------------------------------------------------------------- C1 : dépôt, remplacement


def test_depot_d_un_document(data: Path, tmp_path: Path) -> None:
    doc = _document(tmp_path, "liste-a.txt", DOCUMENTS[A])
    [depot] = deposer([Demande(A, doc)], data, LE)
    nom = f"{A}-20261016T073000Z.txt"
    assert depot.fichier == nom
    assert (data / "perimetre" / nom).read_bytes() == doc.read_bytes()
    assert _lignes_table(data) == [(A, nom, True, 2, 2, 0)]


def test_un_nouveau_depot_remplace_et_garde_l_ancien(data: Path, tmp_path: Path) -> None:
    [premier] = deposer([Demande(A, _document(tmp_path, "v1.txt", DOCUMENTS[A][:1]))], data, LE)
    [second] = deposer(
        [Demande(A, _document(tmp_path, "v2.txt", DOCUMENTS[A]))], data, LE + timedelta(days=1)
    )
    assert premier.fichier and second.fichier and premier.fichier != second.fichier
    assert (data / "perimetre" / premier.fichier).is_file()  # jamais effacé
    assert _lignes_table(data) == [(A, premier.fichier, False, 1, 1, 0), (A, second.fichier, True, 2, 2, 0)]


def test_un_document_identique_ne_change_rien(data: Path, tmp_path: Path) -> None:
    doc = _document(tmp_path, "liste-a.txt", DOCUMENTS[A])
    deposer([Demande(A, doc)], data, LE)
    [encore] = deposer([Demande(A, doc)], data, LE + timedelta(days=1))
    assert encore.fichier is None
    assert len(_lignes_table(data)) == 1
    assert len(list((data / "perimetre").iterdir())) == 1


def test_depot_d_un_dossier_par_son_index(
    data: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lot = tmp_path / "lot"
    lot.mkdir()
    for i, lignes in enumerate(DOCUMENTS.values()):
        _document(lot, f"doc{i}.txt", lignes)
    (lot / "index.csv").write_text(
        "tete,fichier\n" + "".join(f"{t},doc{i}.txt\n" for i, t in enumerate(DOCUMENTS)), encoding="utf-8"
    )
    monkeypatch.setenv("CARTOFR_DATA", str(data))
    assert main(["--dossier", str(lot)]) == 0
    assert [(t, actif, retenues) for t, _, actif, _, retenues, _ in _lignes_table(data)] == [
        (A, True, 2), (B, True, 1), (C, True, 1)
    ]  # fmt: skip


@pytest.mark.parametrize(
    ("tete", "fichier", "message"),
    [
        ("12345", "liste.txt", "SIREN de tête invalide"),
        (A, "absent.txt", "Document introuvable"),
    ],
)
def test_demande_invalide_refusee_sans_rien_ecrire(
    data: Path, tmp_path: Path, tete: str, fichier: str, message: str
) -> None:
    _document(tmp_path, "liste.txt", DOCUMENTS[A])
    with pytest.raises(DepotInvalide, match=message):
        deposer([Demande(A, tmp_path / "liste.txt"), Demande(tete, tmp_path / fichier)], data, LE)
    assert not (data / "perimetre").exists()


def test_deux_documents_pour_la_meme_tete_refuses(data: Path, tmp_path: Path) -> None:
    doc = _document(tmp_path, "liste.txt", DOCUMENTS[A])
    with pytest.raises(DepotInvalide, match="deux documents"):
        deposer([Demande(A, doc), Demande(A, doc)], data, LE)


def test_un_echec_en_cours_defait_tout(data: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Le second fichier ne se copie pas : la première copie est retirée, la table reste vide."""
    copier = module.shutil.copy2
    appels: list[Path] = []

    def copie_qui_casse(source: Path, cible: Path) -> None:
        appels.append(cible)
        if len(appels) == 2:
            raise OSError("disque plein")
        copier(source, cible)

    monkeypatch.setattr(module.shutil, "copy2", copie_qui_casse)
    demandes = [Demande(t, _document(tmp_path, f"{t}.txt", li)) for t, li in list(DOCUMENTS.items())[:2]]
    with pytest.raises(OSError, match="disque plein"):
        deposer(demandes, data, LE)
    assert list((data / "perimetre").iterdir()) == []
    assert _lignes_table(data) == []


# ---------------------------------------------------------------- C4 : rien que des sociétés et des nombres


def test_le_compte_rendu_ne_recopie_que_la_ligne_de_la_societe(data: Path, tmp_path: Path) -> None:
    avant = "Signé : PERSONNE INVENTEE, directrice financière\n"
    doc = _document(tmp_path, "liste-c.txt", DOCUMENTS[C], avant=avant)
    [depot] = deposer([Demande(C, doc)], data, LE)
    texte = "\n".join(resume(depot))
    assert "PERSONNE INVENTEE" not in texte
    assert f"refusée (homonymes, 2 porteurs) : {_ligne('Alpha Inventée')}" in texte
    assert "retrouvées : 1" in texte and "1 homonymes" in texte


# ---------------------------------------------------------------- C5 : pas de lecture des noms sans marque


class _ConnexionInterdite:
    def execute(self, *_: object, **__: object) -> None:
        raise AssertionError("la recherche des marques ne doit rien lire sans marque")


def test_aucune_marque_aucune_lecture() -> None:
    assert chercher_candidates(_ConnexionInterdite(), reglages(A)) == []  # type: ignore[arg-type]


# ---------------------------------------------------------------- revue du 2026-10-16


def test_un_document_sans_ligne_ne_remplace_pas_le_bon(data: Path, tmp_path: Path) -> None:
    """Un PDF scanné ou un format inconnu ne donne aucune ligne : refusé, le document en vigueur reste."""
    deposer([Demande(A, _document(tmp_path, "bon.txt", DOCUMENTS[A]))], data, LE)
    vide = _document(tmp_path, "vide.txt", ["Rapport annuel", "Sommaire"])
    with pytest.raises(DepotInvalide, match="Aucune société située en France"):
        deposer([Demande(A, vide)], data, LE + timedelta(days=1))
    assert [actif for _, _, actif, *_ in _lignes_table(data)] == [True]


def test_une_tete_absente_du_registre_est_refusee(data: Path, tmp_path: Path) -> None:
    with pytest.raises(DepotInvalide, match="Tête absente du registre : 999999999"):
        deposer([Demande("999999999", _document(tmp_path, "x.txt", DOCUMENTS[A]))], data, LE)
    assert not (data / "perimetre").exists()


def test_un_document_illisible_est_refuse_en_francais(data: Path, tmp_path: Path) -> None:
    abime = tmp_path / "abime.pdf"
    abime.write_bytes(b"%PDF-1.7 pas vraiment un pdf")
    with pytest.raises(DepotInvalide, match="Document illisible pour la tête"):
        deposer([Demande(A, abime)], data, LE)


@pytest.mark.parametrize(
    ("contenu", "encodage", "message"),
    [
        ("tete;fichier\n", "utf-8", "pas le point-virgule"),
        ("tete,fichier\n900000001\n", "utf-8", "ligne 2 : il faut une tête et un fichier"),
        ("tete,fichier\n900000001,Société.txt\n", "cp1252", "UTF-8"),
    ],
)
def test_un_index_mal_forme_est_refuse_en_francais(
    tmp_path: Path, contenu: str, encodage: str, message: str
) -> None:
    (tmp_path / "index.csv").write_bytes(contenu.encode(encodage))
    with pytest.raises(DepotInvalide, match=message):
        module.lire_index(tmp_path)


def test_un_index_enregistre_par_excel_est_lu(tmp_path: Path) -> None:
    (tmp_path / "index.csv").write_bytes("tete,fichier\n900000001,a.txt\n".encode("utf-8-sig"))
    assert module.lire_index(tmp_path) == [Demande(A, tmp_path / "a.txt")]


def test_un_commit_rate_retire_les_copies(
    data: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """L'échec du commit lui-même : l'erreur d'origine remonte, et les copies sont retirées."""
    vraie = module.duckdb.connect

    class Connexion:
        def __init__(self, con: duckdb.DuckDBPyConnection) -> None:
            self.con = con

        def execute(self, sql: str, *args: Any) -> Any:
            if sql == "commit":
                raise duckdb.IOException("disque plein")
            return self.con.execute(sql, *args)

        def close(self) -> None:
            self.con.close()

    monkeypatch.setattr(module.duckdb, "connect", lambda *a, **k: Connexion(vraie(*a, **k)))
    with pytest.raises(duckdb.IOException, match="disque plein"):
        deposer([Demande(A, _document(tmp_path, "a.txt", DOCUMENTS[A]))], data, LE)
    assert list((data / "perimetre").iterdir()) == []


def test_la_reconstruction_du_registre_garde_les_depots(data: Path, tmp_path: Path) -> None:
    """`construire --remplacer` part d'une base neuve : l'historique des dépôts y est recopié."""
    from cartofr.registre import construire

    deposer([Demande(A, _document(tmp_path, "v1.txt", DOCUMENTS[A][:1]))], data, LE)
    deposer([Demande(A, _document(tmp_path, "v2.txt", DOCUMENTS[A]))], data, LE + timedelta(days=1))
    avant = _lignes_table(data)
    neuf = tmp_path / "neuf"
    neuf.mkdir()
    _mini().ecrire(neuf / "registre.duckdb")
    construire._reprendre_documents(data / "registre.duckdb", neuf / "registre.duckdb")  # pyright: ignore[reportPrivateUsage]
    assert _lignes_table(neuf) == avant
    [troisieme] = deposer(
        [Demande(B, _document(tmp_path, "b.txt", DOCUMENTS[B]))], neuf, LE + timedelta(days=2)
    )
    con = duckdb.connect(str(neuf / "registre.duckdb"), read_only=True)
    try:
        assert con.execute("select max(id) from documents_perimetre").fetchone() == (3,)
    finally:
        con.close()
    assert troisieme.fichier
