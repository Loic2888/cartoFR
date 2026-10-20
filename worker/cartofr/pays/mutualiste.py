"""Groupes mutualistes : les caisses locales d'un groupe de Crédit Mutuel, étape 4 de la carto du pays (T049).

Mesure du 2026-10-20 (`rapport.md`, `worker/scripts/mesure_mutualiste.py`) : les caisses locales
n'ont aucune mère au registre. Elles sont « membre » (rôle 11) d'un GIE de moyens, dont la caisse
fédérale de leur groupe est aussi membre (CCS pour CMAF). Mais un GIE peut réunir les caisses de
plusieurs groupes : celles de Maine-Anjou et Basse-Normandie et d'Océan sont aussi membres de CCS.

Règle (décision de Loïc du 2026-10-20), pour un groupe à document dont la tête est une caisse de
Crédit Mutuel :
1. ses GIE : les sociétés actives dont la tête est membre et qui comptent plus de `SEUIL_GIE`
   caisses membres. Un GIE sans siège actif ne compte pas, ni pour le groupe ni comme GIE d'une
   autre fédération (celui des caisses de Normandie, fermé, les aurait exclues à tort) ;
2. ses caisses : les caisses actives membres d'un de ses GIE ;
3. une caisse membre de plusieurs GIE de fédération va à celui qui compte le moins de caisses, le
   plus propre à elle : les caisses de Maine-Anjou, membres de CCS (1 411 caisses) et
   d'Inter-Mutuel Services (79), ne vont pas à CMAF. À égalité entre un GIE du groupe et un autre,
   la caisse ne va pas au groupe ;
4. les territoires, d'après la table `TERRITOIRES` (publique et fixe) et la liste des fédérations
   lue dans le document (`passage_federations`) :
   - si la tête est dans le territoire d'une fédération de la table, seules ses caisses de ce
     territoire (départements propres et partagés) et de celui des fédérations que le document
     nomme sont retenues. Sans cela, la caisse fédérale d'Océan ou de Maine-Anjou, membre aussi de
     CCS, prendrait les caisses de CMAF (revue adverse du 2026-10-20) ;
   - sinon (CMAF), les caisses des départements propres aux fédérations de la table que le
     document ne nomme pas sont retirées. Un document sans liste les retire toutes.
Chaque caisse retenue a la tête pour mère, en confiance B (deux indices : le GIE et le
territoire), avec la preuve « Caisse membre du GIE <nom> (<SIREN>), comme la caisse fédérale ».
Une caisse que deux groupes réclament est départagée comme toute société (T047).

Seuls les liens de société à société et les dénominations et adresses des sièges sont lus :
jamais `dirigeants_personnes` (garde-fou 6).
"""

import re
from dataclasses import dataclass

import duckdb

from cartofr.moteur.marques import norm

SEUIL_GIE = 20  # caisses membres au-delà desquelles un GIE est celui d'une fédération
MEMBRE = "11"
# Une caisse de Crédit Mutuel : par son nom, ou par une forme de coopérative avec « CREDIT MUTUEL »
# dans le nom (mesure du 2026-10-20 : 1 721 caisses actives).
CAISSE = (
    "(s.nom like 'CAISSE%CREDIT MUTUEL%' or s.nom like '%CREDIT MUTUEL%'"
    " and s.cj in (5194, 5195, 5460, 5560, 5660, 6560, 6595, 6596))"
)


@dataclass(frozen=True)
class Federation:
    """Une fédération de Crédit Mutuel et les départements qui ne sont qu'à elle."""

    nom: str
    motifs: tuple[str, ...]  # comment un document la nomme, après `norm` et tirets retirés
    departements: tuple[str, ...]  # départements qui ne sont qu'à elle
    partages: tuple[str, ...] = ()  # départements qu'elle partage avec une autre fédération


# Fédérations hors CMAF dont les caisses sont dans le registre, et leurs départements. Sources : les
# sites des fédérations et du groupe (2026-10-20), et les GIE de leurs caisses au registre. Partagés :
# le 79 (Océan au sud, Loire-Atlantique Centre Ouest au nord), le 47 (Sud-Ouest et Midi-Atlantique).
# Le Calvados n'est à personne dans la table : ses caisses au registre sont celles de Normandie (CMAF),
# aucune n'est membre du GIE de Maine-Anjou et Basse-Normandie.
TERRITOIRES: tuple[Federation, ...] = (
    Federation("Crédit Mutuel Océan", ("OCEAN",), ("85", "17"), ("79",)),
    Federation("Crédit Mutuel Maine-Anjou, Basse-Normandie", ("MAINE ANJOU", "BASSE NORMANDIE"),
               ("53", "72", "50", "61")),
    Federation("Crédit Mutuel de Bretagne", ("BRETAGNE",), ("29", "22", "56", "35")),
    Federation("Crédit Mutuel du Sud-Ouest", ("SUD OUEST",), ("33", "24", "16"), ("47",)),
)  # fmt: skip


@dataclass(frozen=True)
class Caisse:
    """Une caisse locale rangée dans le groupe de sa caisse fédérale."""

    siren: str
    gie: str
    gie_nom: str | None

    @property
    def preuve(self) -> str:
        return f"Caisse membre du GIE {self.gie_nom or self.gie} ({self.gie}), comme la caisse fédérale"


def _motif(texte: str) -> str:
    return " ".join(norm(texte).replace("-", " ").split())


def _nommees(passage: str) -> list[Federation]:
    nomme = _motif(passage)
    return [f for f in TERRITOIRES if any(re.search(rf"\b{m}\b", nomme) for m in f.motifs)]


def federation_de(tete_departement: str | None) -> Federation | None:
    """La fédération de la table dont le département de la tête est un département propre."""
    return next((f for f in TERRITOIRES if tete_departement in f.departements), None)


def departements_permis(passage: str, tete_departement: str | None) -> list[str] | None:
    """Les seuls départements où une caisse peut être retenue, si la tête est dans le territoire
    d'une fédération de la table : le sien et celui des fédérations nommées. None sinon."""
    sienne = federation_de(tete_departement)
    if sienne is None:
        return None
    return sorted({d for f in {sienne, *_nommees(passage)} for d in (*f.departements, *f.partages)})


def departements_exclus(passage: str, tete_departement: str | None) -> list[str]:
    """Les départements propres aux fédérations de la table que le passage ne nomme pas, sauf ceux de
    la fédération de la tête."""
    garder = {federation_de(tete_departement), *_nommees(passage)}
    return sorted({
        d for f in TERRITOIRES if f not in garder for d in f.departements if d != tete_departement
    })  # fmt: skip


_TETE = f"select substr(s.cp, 1, 2) from sieges s where s.siren = $tete and {CAISSE}"

_CAISSES = f"""
with caisses as (
    select s.siren, substr(s.cp, 1, 2) dep from sieges s where {CAISSE}
), gie as (
    select l.enfant, count(distinct l.parent) n from liens l join caisses c on c.siren = l.parent
     where l.fin is null and l.role = '{MEMBRE}' and l.enfant in (select siren from sieges)
     group by l.enfant having count(distinct l.parent) > {SEUIL_GIE}
), siens as (
    select enfant from liens
     where parent = $tete and role = '{MEMBRE}' and fin is null and enfant in (select enfant from gie)
), adhesions as (
    select distinct l.parent caisse, l.enfant gie, g.n, l.enfant in (select enfant from siens) sien
      from liens l join gie g on g.enfant = l.enfant join caisses c on c.siren = l.parent
     where l.fin is null and l.role = '{MEMBRE}'
), plus_petit as (
    select caisse, min(n) n from adhesions group by caisse
)
select a.caisse, min(a.gie) gie, any_value(s.nom order by a.gie) gie_nom
  from adhesions a
  join plus_petit p on p.caisse = a.caisse and p.n = a.n
  join caisses c on c.siren = a.caisse
  left join sieges s on s.siren = a.gie
 where a.sien and a.caisse <> $tete
   and not exists (select 1 from adhesions b where b.caisse = a.caisse and not b.sien and b.n = p.n)
   and coalesce(c.dep, '') not in (select unnest($exclus::varchar[]))
   and (not $limite or c.dep in (select unnest($permis::varchar[])))
 group by a.caisse
 order by a.caisse
"""


def caisses(con: duckdb.DuckDBPyConnection, tete: str, passage: str) -> list[Caisse]:
    """Les caisses locales du groupe dont `tete` est la caisse fédérale ; aucune si la tête n'est pas
    une caisse de Crédit Mutuel. `passage` : la liste des fédérations lue dans le document."""
    ligne = con.execute(_TETE, {"tete": tete}).fetchone()
    if ligne is None:
        return []
    permis = departements_permis(passage, ligne[0])
    parametres = {"tete": tete, "exclus": departements_exclus(passage, ligne[0]),
                  "limite": permis is not None, "permis": permis or []}  # fmt: skip
    return [Caisse(s, g, n) for s, g, n in con.execute(_CAISSES, parametres).fetchall()]
