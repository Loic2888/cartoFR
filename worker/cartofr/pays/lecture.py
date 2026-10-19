"""Lecture de la carto d'une société dans la carto du pays (T050, US2).

But : rendre, sans aucun calcul de groupe, la carto déjà calculée par T048 :
la société et tout ce qui descend d'elle, jamais ses sœurs ni les autres
filiales de ses actionnaires (décidé le 2026-10-18) ; sa mère directe nommée à
part ; le groupe où elle est rangée et, si elle est dans un groupe plus grand
(groupes emboîtés), la tête de ce groupe entier.

Usage :
    con = duckdb.connect("registre.duckdb", read_only=True)
    attacher_pays(con, Path("pays.duckdb"))
    carto = lire_groupe(con, "552120222")  # None : SIREN inconnu

Entrées : une connexion au registre (lecture seule) où `pays.duckdb` est
attachée sous le nom `pays`. Sortie : `CartoSociete`, ou None.

Règles tenues ici :
- aucune personne (garde-fou 6, principe 6) : `dirigeants_personnes` n'est
  jamais lue. Une mère entrepreneur individuel (ni siège ni unité légale
  SIRENE) n'est rendue que par `mere_personne_physique`, sans SIREN ni nom ;
  un SIREN d'entrepreneur individuel demandé rend None ;
- la mère nommée est celle de la carto du pays. Une mère du registre que la
  carto du pays a coupée (fermée, ou rangée dans un autre groupe) n'est pas
  nommée (décision de Loïc, 2026-10-19) ;
- une société active absente de la carto du pays (seule, ou coupée de sa mère)
  rend sa carto à elle seule ;
- lecture seule, aucun appel extérieur (principe 3).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

from cartofr.moteur.moteur import ciblable_par_fiche

# Garde-fou contre une boucle de `mere` ou de `parent` : la carto du pays n'en
# écrit pas, mais une lecture ne doit jamais tourner sans fin.
PROFONDEUR_MAX = 200


@dataclass(frozen=True)
class SocieteCarto:
    """Une société de l'arbre, avec les champs de `carto_societes` que l'app affiche."""

    siren: str
    nom: str | None
    niveau: int  # 0 pour la société demandée
    maison_mere_siren: str | None  # vide pour la société demandée : sa mère est dans `CartoSociete.mere`
    confiance: str | None  # 'A', 'B', 'C' ; vide pour une société seule
    preuve: str | None
    ciblable: bool
    raison_ciblable: str | None
    opposition_prospection: bool
    non_diffusible: bool


@dataclass(frozen=True)
class Groupe:
    tete: str
    nom: str | None
    taille: int  # sociétés, tête comprise (sous-groupes compris pour le groupe entier)


@dataclass(frozen=True)
class Mere:
    siren: str
    nom: str | None


@dataclass(frozen=True)
class CartoSociete:
    siren: str
    nom: str | None
    date_donnees: str | None  # AAAA-MM-JJ
    groupe: Groupe | None  # le groupe où elle est rangée ; vide si elle est seule
    groupe_entier: Groupe | None  # le groupe le plus haut au-dessus d'elle, s'il n'est pas elle
    mere: Mere | None
    mere_personne_physique: bool
    societes: list[SocieteCarto]


def attacher_pays(con: duckdb.DuckDBPyConnection, chemin: Path) -> bool:
    """Attache `pays.duckdb` en lecture seule sous le nom `pays`. Faux si le fichier n'existe pas."""
    if not chemin.is_file():
        return False
    echappe = str(chemin).replace("'", "''")
    con.execute(f"attach '{echappe}' as pays (read_only)")
    return True


def _tables(con: duckdb.DuckDBPyConnection) -> set[str]:
    lignes = con.execute(
        "select table_name from information_schema.tables where table_catalog = current_database()"
    ).fetchall()
    return {str(ligne[0]) for ligne in lignes}


# La descendance d'une société est dans son groupe ou dans ses sous-groupes : la descente ne
# parcourt que ces lignes-là, pas toute la carto du pays (VINCI : 0,3 s gagnées).
_DESCENTE = f"""
with recursive sous(tete, n) as (
    select $groupe::varchar, 0
    union all
    select g.tete, s.n + 1
      from pays.pays_groupes g join sous s on g.parent = s.tete
     where s.n < {PROFONDEUR_MAX}
),
candidates as materialized (
    select siren, mere from pays.pays_societes where groupe in (select tete from sous)
),
bas(siren, niveau) as (
    select $siren::varchar, 0
    union all
    select c.siren, b.niveau + 1
      from candidates c join bas b on c.mere = b.siren
     where b.niveau < {PROFONDEUR_MAX}
),
uniques as (select siren, min(niveau) as niveau from bas group by siren)
select s.siren, s.nom, u.niveau, case when u.niveau = 0 then null else s.mere end,
       s.confiance, s.preuve, s.ciblable, s.raison_ciblable, s.opposition_prospection, s.non_diffusible
  from uniques u join pays.pays_societes s on s.siren = u.siren
 order by u.niveau, s.siren
"""

_SOMMET = f"""
with recursive haut(tete, n) as (
    select $tete::varchar, 0
    union all
    select g.parent, h.n + 1
      from pays.pays_groupes g join haut h on g.tete = h.tete
     where g.parent is not null and h.n < {PROFONDEUR_MAX}
)
select tete from haut order by n desc limit 1
"""

_TAILLE_ENTIERE = f"""
with recursive sous(tete, n) as (
    select $tete::varchar, 0
    union all
    select g.tete, s.n + 1
      from pays.pays_groupes g join sous s on g.parent = s.tete
     where s.n < {PROFONDEUR_MAX}
)
select coalesce(sum(g.taille), 0) from pays.pays_groupes g where g.tete in (select tete from sous)
"""


def _groupe(con: duckdb.DuckDBPyConnection, tete: str) -> Groupe | None:
    ligne = con.execute("select tete, nom, taille from pays.pays_groupes where tete = ?", [tete]).fetchone()
    return Groupe(str(ligne[0]), ligne[1], int(ligne[2])) if ligne else None


def _groupe_entier(con: duckdb.DuckDBPyConnection, groupe: str, siren: str) -> Groupe | None:
    """Le groupe le plus haut au-dessus du groupe `groupe`, en remontant les groupes emboîtés.
    Vide quand ce sommet est la société demandée elle-même : sa carto est déjà le groupe entier."""
    ligne = con.execute(_SOMMET, {"tete": groupe}).fetchone()
    sommet = str(ligne[0]) if ligne else groupe
    if sommet == siren:
        return None
    haut = _groupe(con, sommet)
    if haut is None:
        return None
    total = con.execute(_TAILLE_ENTIERE, {"tete": sommet}).fetchone()
    return Groupe(haut.tete, haut.nom, int(total[0]) if total else haut.taille)


def _date_donnees(con: duckdb.DuckDBPyConnection) -> str | None:
    requete = "select date_donnees from pays.pays_bilan order by calcule_le desc limit 1"
    ligne = con.execute(requete).fetchone()
    return ligne[0].isoformat() if ligne and ligne[0] else None


def _mere_personne_physique(con: duckdb.DuckDBPyConnection, siren: str) -> bool:
    """Vrai si la mère de `siren` au registre est un entrepreneur individuel : connue du RNE,
    sans siège ni unité légale SIRENE (les deux tables écartent les entrepreneurs individuels).
    Sans `unites_legales`, on ne peut pas la distinguer d'une société fermée : on ne dit rien."""
    tables = _tables(con)
    if not {"arbre", "sieges", "unites_legales"} <= tables:
        return False
    ligne = con.execute("select mere from arbre where siren = ?", [siren]).fetchone()
    if ligne is None:
        return False
    mere = ligne[0]
    societe = con.execute(
        "select count(*) from sieges where siren = ? and (cj is null or cj not between 1000 and 1999)", [mere]
    ).fetchone()
    unite = con.execute("select count(*) from unites_legales where siren = ?", [mere]).fetchone()
    return not (societe and societe[0]) and not (unite and unite[0])


def _seule(con: duckdb.DuckDBPyConnection, siren: str) -> SocieteCarto | None:
    """Une société active absente de la carto du pays, d'après sa fiche. None si elle n'a pas de
    siège actif ou si le RNE l'a fermée : inconnue, fermée, ou entrepreneur individuel (jamais rendu)."""
    ligne = con.execute(
        """
        select g.nom, g.cj, g.naf, g.tranche, o.salaries, o.opposition_prospection, o.non_diffusible
          from sieges g left join societes o on o.siren = g.siren
         where g.siren = ? and (g.cj is null or g.cj not between 1000 and 1999)
           and o.fin is null  -- fermée au RNE : la recherche la dit radiée, pas de carto
         limit 1
        """,
        [siren],
    ).fetchone()
    if ligne is None:
        return None
    nom, cj, naf, tranche, salaries, opposition, non_diffusible = ligne
    ciblable, raison = ciblable_par_fiche(cj, naf, tranche, salaries)
    return SocieteCarto(
        siren=siren, nom=nom, niveau=0, maison_mere_siren=None, confiance=None, preuve=None,
        ciblable=ciblable, raison_ciblable=raison, opposition_prospection=bool(opposition),
        non_diffusible=bool(non_diffusible),
    )  # fmt: skip


def _societe(ligne: tuple[Any, ...]) -> SocieteCarto:
    siren, nom, niveau, mere, confiance, preuve, ciblable, raison, opposition, non_diffusible = ligne
    return SocieteCarto(
        siren=str(siren), nom=nom, niveau=int(niveau), maison_mere_siren=mere, confiance=confiance,
        preuve=preuve, ciblable=bool(ciblable), raison_ciblable=raison,
        opposition_prospection=bool(opposition), non_diffusible=bool(non_diffusible),
    )  # fmt: skip


def lire_groupe(con: duckdb.DuckDBPyConnection, siren: str) -> CartoSociete | None:
    """La carto de `siren` : elle et sa descendance dans la carto du pays. None si le SIREN n'est ni
    dans la carto du pays ni une société active du registre."""
    ligne = con.execute("select groupe, mere from pays.pays_societes where siren = ?", [siren]).fetchone()
    date_donnees = _date_donnees(con)
    if ligne is None:
        seule = _seule(con, siren)
        if seule is None:
            return None
        return CartoSociete(
            siren=siren, nom=seule.nom, date_donnees=date_donnees, groupe=None, groupe_entier=None,
            mere=None, mere_personne_physique=_mere_personne_physique(con, siren), societes=[seule],
        )  # fmt: skip

    groupe, mere_siren = str(ligne[0]), ligne[1]
    societes = [_societe(r) for r in con.execute(_DESCENTE, {"siren": siren, "groupe": groupe}).fetchall()]
    mere: Mere | None = None
    if mere_siren:
        nom_mere = con.execute("select nom from pays.pays_societes where siren = ?", [mere_siren]).fetchone()
        mere = Mere(str(mere_siren), nom_mere[0] if nom_mere else None)
    return CartoSociete(
        siren=siren,
        nom=societes[0].nom,
        date_donnees=date_donnees,
        groupe=_groupe(con, groupe),
        groupe_entier=_groupe_entier(con, groupe, siren),
        mere=mere,
        mere_personne_physique=mere is None and _mere_personne_physique(con, siren),
        societes=societes,
    )


def groupes_de(con: duckdb.DuckDBPyConnection, sirens: list[str]) -> dict[str, Groupe]:
    """Le groupe où chaque SIREN est rangé, pour les résultats de la recherche. Absent : seule."""
    if not sirens:
        return {}
    lignes = con.execute(
        """
        select s.siren, g.tete, g.nom, g.taille
          from pays.pays_societes s join pays.pays_groupes g on g.tete = s.groupe
         where s.siren in (select unnest($sirens::varchar[]))
        """,
        {"sirens": sirens},
    ).fetchall()
    return {str(s): Groupe(str(t), n, int(taille)) for s, t, n, taille in lignes}
