"""Journal des mises à jour du registre : la table `mises_a_jour`.

Usage :
    id_maj = ouvrir(con, "construction_initiale")
    terminer(con, id_maj, ajoutes=..., fermes=...)   # ou echouer(con, id_maj, "message")

Le message d'erreur est écrit tel quel : l'appelant n'y met jamais de donnée
personnelle (règle produit 4).
"""

import duckdb

LONGUEUR_ERREUR = 500


def ouvrir(con: duckdb.DuckDBPyConnection, source: str) -> int:
    """Écrit une ligne 'en_cours' pour `source` et rend son id."""
    ligne = con.execute("insert into mises_a_jour (source) values (?) returning id", [source]).fetchone()
    assert ligne is not None
    return int(ligne[0])


def terminer(con: duckdb.DuckDBPyConnection, id_maj: int, ajoutes: int, fermes: int) -> None:
    """Passe la ligne `id_maj` en 'succes' avec ses volumes."""
    con.execute(
        "update mises_a_jour set statut = 'succes', fin_le = current_timestamp, ajoutes = ?, fermes = ?"
        " where id = ?",
        [ajoutes, fermes, id_maj],
    )


def echouer(con: duckdb.DuckDBPyConnection, id_maj: int, erreur: str) -> None:
    """Passe la ligne `id_maj` en 'echec' avec un message court."""
    con.execute(
        "update mises_a_jour set statut = 'echec', fin_le = current_timestamp, erreur = ? where id = ?",
        [erreur[:LONGUEUR_ERREUR], id_maj],
    )
