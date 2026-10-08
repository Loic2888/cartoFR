"""Cartographie d'un groupe : étapes 4 à 8 du plan, en boucle jusqu'à ce que plus rien ne bouge.

Repris de `engine.py` (prototype), mode local seulement. Le mode API (INPI, Annuaire,
BODACC) est retiré : une carto ne fait aucun appel extérieur (principe 3). Le moteur
lit `registre.duckdb` en lecture seule.

Usage :
    from cartofr.moteur import cartographier
    carto = cartographier(reglages, Path("data/registre.duckdb"))
Entrées : les réglages d'un groupe (config/<groupe>.json, validés par un humain), le registre.
Sortie : une `Carto` (modele.py).

Ordre : l'ordre des indices compte (une société retenue plus tôt dans un tour peut en
faire entrer une autre dans le même tour). Toutes les lectures qui le fixent sont triées :
deux cartos des mêmes réglages sur le même registre sont identiques. Le prototype ne
triait pas : sur le même registre, il rend le même ensemble de sociétés, mais quelques
rattachements dans l'arbre peuvent différer (mesuré le 2026-10-07, voir non_regression.py).

Cas douteux (T027, FR-009) : la carto range aussi les cas que le consultant doit trancher
(confiance C, co-entreprise, participation sans contrôle, société étrangère), chacun avec la
règle qui l'a placé là et ses indices pour et contre (`ranger_cas`). Les décisions du consultant
(`decisions`) s'appliquent au calcul suivant : « écarter » fait sortir une société que les règles
retiennent, « retenir » fait entrer une société que le moteur voit encore liée au groupe
(`appliquer_decision`). Les règles ne changent pas : la carto dit laquelle aurait joué.

Règle de licence INPI : les dirigeants personnes physiques servent seulement de preuve pendant le
calcul. Aucun nom de personne n'est rendu : la `Carto` n'a aucun champ qui puisse en porter.
"""

import collections
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import Any

import duckdb

from cartofr.empreinte import cle_depuis_env, empreinte
from cartofr.moteur.marques import Candidate, chercher_candidates, norm
from cartofr.moteur.modele import (
    Carto,
    Cas,
    Confiance,
    Decision,
    Etrangere,
    Lien,
    Mandat,
    Participation,
    Societe,
    Tour,
    TypeCas,
)

# Codes de rôle RNE, reconstitués en croisant 195 fiches avec les rôles lus par Basile (role_codes.py).
STRONG = {
    "73": "Président",
    "30": "Gérant",
    "28": "Gérant et associé indéfiniment et solidairement responsable",
    "29": "Gérant et associé indéfiniment responsable",
    "74": "Associé indéfiniment et solidairement responsable",
    "75": "Associé indéfiniment responsable",
    "131": "Associé commandité",
}
MEDIUM = {
    "65": "Administrateur",
    "11": "Membre",
    "64": "Membre du conseil de surveillance",
    "51": "Président du conseil d'administration",
}
WEAK = {"99": "Autre"}
ROLE_LABEL = {**STRONG, **MEDIUM, **WEAK}
# Rôles d'une personne physique qui veulent dire "elle dirige la société".
DIRECTING = {"73", "30", "28", "29", "51", "53"}
HOLDING_NAF = {"64.20Z", "64.30Z", "66.30Z", "68.20A", "68.20B", "68.10Z", "68.32A", "64.99Z"}
SMALL_TRANCHES = {None, "", "NN", "00", "01", "02", "03"}
# Garde haute de la boucle : le point fixe arrive bien avant (VINCI en 7 tours, 2026-10-08). Si elle est
# atteinte, la carto le dit (GARDE_ATTEINTE) au lieu de perdre des niveaux en silence (T035).
MAX_TOURS = 50
GARDE_ATTEINTE = (
    f"Le calcul s'est arrêté après {MAX_TOURS} tours sans se stabiliser : des sociétés des "
    "niveaux les plus profonds peuvent manquer. Prévenez l'administrateur."
)

# Raison d'entrée d'une société qu'aucune règle ne retient, mais que le consultant a retenue (T027).
RETENUE_PAR_DECISION = "retenue par décision du consultant"

# Un indice : (type, détail). Types : marque_sure, marque_ambigue, registre, adresse, organigramme.
Indice = tuple[str, Any]


def civile(cj: Any) -> bool:
    """Sociétés civiles, SCI, GFA… (catégorie 6…, hors GIE)."""
    return str(cj).startswith("6") and not str(cj).startswith("62")


def gie(cj: Any) -> bool:
    return str(cj).startswith("62")


@dataclass
class _Fiche:
    """Ce que le registre dit des dirigeants d'une société. Usage interne au calcul seulement."""

    parents: list[tuple[str, str]]  # (SIREN de la société dirigeante, code de rôle)
    persons: dict[str, set[str]]  # clé de personne -> codes de rôle : jamais rendu
    salaries: int | None = None
    diffusion_commerciale: bool | None = None
    non_diffusible: bool | None = None


_COLONNES_SIEGE = ("siren", "siret_siege", "adresse_cle", "nom", "cj", "naf", "tranche", "commune")


class _Moteur:
    def __init__(
        self,
        cfg: dict[str, Any],
        con: duckdb.DuckDBPyConnection,
        cle_empreinte: str | None = None,
        decisions: Mapping[str, Decision] | None = None,
    ) -> None:
        self.cfg = cfg
        self.db = con
        self.info: dict[str, dict[str, Any] | None] = {}
        self.rne: dict[str, _Fiche] = {}
        self.ev: collections.defaultdict[str, list[Indice]] = collections.defaultdict(list)
        self.retained: dict[str, str] = {}  # siren -> raison d'entrée
        self.foreign: dict[str, str | None] = {}
        # Familles exclues : en clair (config/*.json, non-régression) ou par empreinte (réglages de
        # l'app, garde-fou 6). Les deux listes peuvent coexister ; une famille de l'une ou l'autre
        # est exclue.
        self.family = {n.upper() for n in cfg.get("familles_exclues", [])}
        self.family_empreintes = frozenset(cfg.get("familles_exclues_empreintes", []))
        self.cle_empreinte = cle_empreinte
        if self.family_empreintes and not cle_empreinte:
            self.cle_empreinte = cle_depuis_env()  # CleManquante : jamais de comparaison sans clé
        self._famille_vue: dict[str, bool] = {}
        self.excluded = set(cfg.get("exclus", []))
        # Décisions du consultant sur les cas douteux (T027). La tête n'en reçoit pas : elle est
        # le groupe. Une décision s'applique dans `run`, la règle qui aurait joué reste écrite.
        self.decisions: dict[str, Decision] = {s: d for s, d in (decisions or {}).items() if s != cfg["tete"]}
        self.ecartees: dict[str, str] = {}  # siren -> règle qui l'aurait fait entrer
        self.local_done: set[str] = set()
        self.heads: dict[str, str] = {}
        self.tours: list[Tour] = []
        self.point_fixe = False

    # ---------- données ----------
    def load_info(self, sirens: Iterable[str]) -> None:
        missing = [s for s in sirens if s not in self.info]
        if not missing:
            return
        rows = self.db.execute(
            f"select {', '.join(_COLONNES_SIEGE)} from sieges where siren in (select unnest($s))",
            {"s": missing},
        ).fetchall()
        for r in rows:
            self.info[r[0]] = dict(zip(_COLONNES_SIEGE, r, strict=True))
        for s in missing:
            self.info.setdefault(s, None)  # inactive ou absente de SIRENE : écartée

    def prefetch(self, sirens: Iterable[str]) -> None:
        """Remplit d'un coup les fiches de plusieurs sociétés depuis le registre."""
        todo = [s for s in set(sirens) if s not in self.rne]
        if not todo:
            return
        for s in todo:
            self.rne[s] = _Fiche(parents=[], persons={})
        for p, c, r in self.db.execute(
            "select parent, enfant, role from liens where fin is null and enfant in (select unnest($s))"
            " order by enfant, parent, role",
            {"s": todo},
        ).fetchall():
            self.rne[c].parents.append((p, r))
        for s, key, r in self.db.execute(
            "select siren, personne, role from dirigeants_personnes"
            " where fin is null and siren in (select unnest($s))",
            {"s": todo},
        ).fetchall():
            if not self.famille_exclue(key.split("|")[0]):
                self.rne[s].persons.setdefault(key, set()).add(r)
        for s, dc, sal, nd in self.db.execute(
            "select siren, diffusion_commerciale, salaries, non_diffusible from societes"
            " where siren in (select unnest($s))",
            {"s": todo},
        ).fetchall():
            fiche = self.rne[s]
            fiche.diffusion_commerciale, fiche.salaries, fiche.non_diffusible = dc, sal, nd

    def famille_exclue(self, nom: str) -> bool:
        """Le nom de famille d'un dirigeant (début de sa clé) est-il exclu par les réglages ?

        En clair : égalité avec un nom en majuscules, comme le prototype. Par empreinte :
        HMAC du nom (`cartofr.empreinte`, mêmes majuscules, espaces des bords retirés) présent
        dans la liste. Le résultat est gardé par nom : une empreinte par famille, pas par ligne.
        Seul écart entre les deux : un nom écrit au registre avec des blancs au bord est exclu par
        empreinte, pas en clair (LVMH, 2026-10-07 : une variante, 5 mandats ; cartos identiques).
        """
        if nom in self.family:
            return True
        if not self.family_empreintes:
            return False
        vu = self._famille_vue.get(nom)
        if vu is None:
            vu = empreinte(nom, self.cle_empreinte or "") in self.family_empreintes
            self._famille_vue[nom] = vu
        return vu

    def discover_local(self) -> None:
        """Toutes les sociétés dont une société retenue est dirigeante, d'après le registre."""
        new = [r for r in self.retained if r not in self.local_done]
        self.local_done.update(new)
        for p, c, r in self.db.execute(
            "select parent, enfant, role from liens where fin is null and parent in (select unnest($s))"
            " order by parent, enfant, role",
            {"s": new},
        ).fetchall():
            if p != c:
                self.add(c, "registre", (p, r))

    # ---------- indices ----------
    def add(self, siren: str, kind: str, detail: Any) -> None:
        if (kind, detail) not in self.ev[siren]:
            self.ev[siren].append((kind, detail))

    def group_addresses(self, pidx: dict[str, set[str]] | None = None) -> dict[str, tuple[int, int]]:
        """Adresses où le groupe est majoritaire. Comme Basile : on compte les sociétés de l'adresse
        (sans les associations ni fondations), et sont "du groupe" les retenues et celles qui ont déjà
        un indice propre (marque du groupe, mandat trouvé, dirigeant cadre du groupe)."""
        self.load_info(list(self.retained))
        addrs = collections.Counter(
            (self.info[r] or {}).get("adresse_cle") for r in self.retained if self.info.get(r)
        )
        pidx = pidx or {}
        cles = [a for a, n in addrs.items() if a and "[ND]" not in a and n >= 2]
        voisines: dict[str, list[str]] = {a: [] for a in cles}
        for s, cj, a in self.db.execute(
            "select siren, cj, adresse_cle from sieges"
            " where adresse_cle in (select unnest($a)) order by siren",
            {"a": cles},
        ).fetchall():
            if not str(cj).startswith("9"):
                voisines[a].append(s)

        def group_like(s: str) -> bool:
            if s in self.retained:
                return True
            if s in self.excluded or self.decisions.get(s) == "ecarter" or self.name_excluded(s):
                return False
            kinds = {k for k, _ in self.ev[s]}
            fiche = self.rne.get(s)
            cadre = any(len(pidx.get(k, ())) >= 2 for k in (fiche.persons if fiche else {}))
            return bool(kinds & {"marque_sure", "registre"}) or cadre

        out = {}
        for a in cles:
            rows = voisines[a]
            g = sum(group_like(s) for s in rows)
            if rows and g / len(rows) >= 0.5:
                out[a] = (g, len(rows))
                for s in rows:
                    self.ev[s] = [x for x in self.ev[s] if x[0] != "adresse"]
                    self.add(s, "adresse", (a, g, len(rows)))
        return out

    def add_organigramme(self) -> None:
        """Organigramme public du groupe (liste des maisons, validée par un humain dans les réglages) :
        pour chaque maison, la plus grande société active qui porte ce nom devient sa tête."""
        maisons = self.cfg.get("organigramme", [])
        if not maisons:
            return
        # Les noms des sièges éligibles (ni société civile, ni association, ni société étrangère),
        # normalisés une fois pour toutes les maisons.
        order = "case tranche when 'NN' then -1 when null then -2 else try_cast(tranche as integer) end"
        self.db.execute(f"""
            create or replace temp table sieges_organigramme as
            select siren, regexp_replace(upper(strip_accents(nom)), '[^A-Z0-9]+', ' ', 'g') n,
                   {order} taille
            from sieges
            where not (cast(cj as varchar) like '6%' and cast(cj as varchar) not like '62%')
              and cast(cj as varchar) not like '9%' and cast(cj as varchar) not like '3%'
        """)
        for maison in maisons:
            m = norm(maison)
            rows = self.db.execute(
                "select siren from sieges_organigramme where n similar to $motif"
                " order by taille desc nulls last, siren limit 1",
                {"motif": f"((SOC|STE|SOCIETE|LES|LE|LA|L) )*{re.escape(m)}( .*)?"},
            ).fetchall()
            for (s,) in rows:
                self.add(s, "organigramme", maison)

    def name_excluded(self, s: str) -> bool:
        nom = ((self.info.get(s) or {}).get("nom") or "").upper()
        return any(nom.startswith(p.upper()) for p in self.cfg.get("exclus_noms", []))

    def persons_index(self) -> dict[str, set[str]]:
        idx: collections.defaultdict[str, set[str]] = collections.defaultdict(set)
        for r in self.retained:
            v = self.rne.get(r)
            for k in v.persons if v else {}:
                idx[k].add(r)
        return idx

    # ---------- décision ----------
    def decide(self, s: str, pidx: dict[str, set[str]]) -> str | None:
        info = self.info.get(s)
        if s in self.retained or s in self.excluded or not info or self.name_excluded(s):
            return None
        # Le nom est normalisé (majuscules, accents retirés) : « COMITÉ » est un comité (T034).
        if str(info["cj"]).startswith("9") or re.match(
            r"(CSE|COMITE|AMICALE|ASSOCIATION)\b", norm(info["nom"])
        ):
            return None  # associations, fondations, comités d'entreprise : jamais des filiales
        if str(info["cj"]).startswith("3"):
            if any(k == "marque_sure" for k, _ in self.ev[s]):
                self.foreign[s] = info["nom"]
            return None
        ev = self.ev[s]
        v = self.rne.get(s)
        parents = v.parents if v else []
        persons = v.persons if v else {}
        cj = info["cj"]
        mandates = [(p, c) for p, c in parents if p in self.retained]
        strong = [m for m in mandates if m[1] in STRONG]
        medium = [m for m in mandates if m[1] in MEDIUM]
        weak = [m for m in mandates if m[1] in WEAK]
        brand = [d for k, d in ev if k in ("marque_sure", "marque_ambigue")]
        sure = any(k == "marque_sure" for k, _ in ev)
        addr = [d for k, d in ev if k == "adresse"]
        common, directs = 0, False
        for key, codes in persons.items():
            if key in pidx:
                common += 1
                directs |= bool(codes & DIRECTING)
        cadre = any(len(pidx.get(k, ())) >= 2 for k in persons)
        people_ok = (common >= 2 or (common >= 1 and cadre)) and not (civile(cj) and not sure)
        if strong:
            return "mandat fort au registre"
        if any(k == "organigramme" for k, _ in ev):
            return "tête de maison (organigramme public du groupe)"
        others = sum([bool(brand), bool(addr), people_ok])
        # Règle Basile : un GIE dont tous les membres sont des sociétés du groupe entre aussi.
        members = [p for p, c in parents if c == "11"]
        if gie(cj) and len(members) >= 2 and all(p in self.retained for p in members):
            return "GIE dont tous les membres sont du groupe"
        outside = [p for p, c in parents if p not in self.retained and c in STRONG]
        if medium and outside:
            return None  # partagée avec une société extérieure : participation sans contrôle (règle Basile)
        if medium:
            if (people_ok and directs) or brand or addr:
                return "mandat au registre et indice indépendant"
            return None  # participation sans contrôle
        # Un mandat « Autre » est une règle de plus, pas un veto : sans deux indices, la société reste
        # jugée par les règles suivantes, comme si ce mandat n'existait pas (T033).
        if weak and others >= 2:
            return "mandat 'Autre' et deux indices"
        sure_brands = [d for k, d in ev if k == "marque_sure"]

        def bare(b: str) -> bool:
            return len(norm(info["nom"]).split()) <= len(b.split()) + 1

        def risky(b: str) -> bool:
            return b in self.cfg.get("marques_sures_homonymes", []) or (
                b in self.cfg.get("marques_sigles", []) and bare(b)
            )

        tiny = info.get("tranche") in (None, "", "NN", "00") and not ((v.salaries if v else None) or 0)
        if (
            sure
            and not civile(cj)
            and not any(risky(b) for b in sure_brands)
            and not (tiny and all(bare(b) for b in sure_brands))
        ):
            return "nom de marque propre au groupe"
        if brand and (people_ok or addr):
            return "nom de marque et second indice"
        if addr and (people_ok or (common >= 1 and not civile(cj))):
            return "adresse du groupe et second indice"
        return None

    def appliquer_decision(self, s: str, why: str | None) -> str | None:
        """La décision du consultant sur `s`, appliquée à ce que les règles ont décidé (T027).

        - « écarter » : la société n'entre pas, même si une règle la retient ; la règle qui
          l'aurait fait entrer est gardée (`ecartees`) pour le dire dans le cas.
        - « retenir » : la société entre, même si aucune règle ne la retient. Elle n'est appelée
          ici que si le moteur la voit encore : active au registre et liée au groupe par au
          moins un indice (elle est dans la liste des candidates du tour). Une société disparue
          ou qui n'a plus aucun lien avec le groupe n'entre pas : la décision est sans objet.
        Sans décision, la règle décide seule.
        """
        decision = self.decisions.get(s)
        if decision == "ecarter":
            if why:
                self.ecartees[s] = why
            return None
        if decision == "retenir" and not why:
            return RETENUE_PAR_DECISION
        return why

    # ---------- boucle ----------
    def run(self, candidates: Iterable[Candidate], max_rounds: int | None = None) -> "_Moteur":
        """Boucle jusqu'au point fixe, `max_rounds` tours au plus (MAX_TOURS par défaut, lu à l'appel).
        `point_fixe` dit si la boucle s'est arrêtée parce que plus rien ne changeait."""
        limite = MAX_TOURS if max_rounds is None else max_rounds
        tete = self.cfg["tete"]
        self.retained[tete] = "tête du groupe"
        for c in candidates:
            self.add(c.siren, "marque_" + c.type_marque, c.marque)
        self.add_organigramme()
        for rnd in range(1, limite + 1):
            before = len(self.retained)
            self.load_info(list(self.retained))
            self.discover_local()
            addrs = self.group_addresses()
            pool = [s for s in self.ev if s not in self.retained and s not in self.excluded]
            self.load_info(pool + list(self.retained))
            pool = [s for s in pool if self.info.get(s)]
            self.prefetch(set(pool) | set(self.retained))
            pidx = self.persons_index()
            addrs = self.group_addresses(pidx)
            for s in pool:
                why = self.appliquer_decision(s, self.decide(s, pidx))
                if why:
                    self.retained[s] = why
            self.tours.append(Tour(rnd, len(self.retained), len(pool), len(addrs)))
            if len(self.retained) == before:
                self.point_fixe = True
                break
        return self

    # ---------- arbre ----------
    def parent_of(self, s: str) -> tuple[str, str, Confiance]:
        order = [self.cfg["tete"]] + self.cfg.get("priorite", [])

        def rank(p: str) -> int:
            return order.index(p) if p in order else len(order)

        v = self.rne.get(s)
        links = [
            (0 if c in STRONG else 1 if c in WEAK else 2, rank(p), p, c)
            for p, c in (v.parents if v else [])
            if p in self.retained and p != s
        ]
        if links:
            _, _, p, c = min(links)
            return p, f"Mandat au registre : {ROLE_LABEL.get(c, c)}", "A"
        n_ev = len({k.split("_")[0] for k, _ in self.ev[s]}) + (
            1 if self.retained[s].endswith("indice") else 0
        )
        conf: Confiance = "B" if n_ev >= 2 or "second indice" in self.retained[s] else "C"
        for k, brand in self.ev[s]:
            head = self.heads.get(brand) if k.startswith("marque") else None
            if head and head != s:
                return head, f"Déduit : même maison ({brand})", conf
        return self.cfg["tete"], "Déduit : rattachée à la tête du groupe", conf

    def build(self, date_donnees: date | None) -> Carto:
        tete = self.cfg["tete"]

        # Tête de maison : pour chaque marque, la société retenue de cette marque qui a le plus de salariés.
        def size(x: str) -> tuple[int, str]:
            v = self.rne.get(x)
            return ((v.salaries if v else None) or 0, (self.info.get(x) or {}).get("tranche") or "")

        self.heads = {}
        for x in self.retained:
            for k, brand in self.ev[x]:
                if k.startswith("marque") and (brand not in self.heads or size(x) > size(self.heads[brand])):
                    self.heads[brand] = x
        parent = {s: self.parent_of(s) for s in self.retained if s != tete}
        # 1. Les rattachements d'abord : une boucle de mandats croisés (A → B → A) est coupée en
        # rattachant à la tête la première société de la boucle atteinte en remontant.
        vus = {tete}
        for s in self.retained:
            chemin: list[str] = []
            x = s
            while x not in vus and x not in chemin:
                chemin.append(x)
                x = parent[x][0]
            if x in chemin:
                parent[x] = (tete, "Déduit : boucle de mandats coupée", "C")
            vus.update(chemin)
        # 2. Puis les niveaux, sur des rattachements fixés : niveau = niveau de la maison mère + 1 (T036).
        level = {tete: 0}
        for s in self.retained:
            chemin = []
            x = s
            while x not in level:
                chemin.append(x)
                x = parent[x][0]
            for y in reversed(chemin):
                level[y] = level[x] + 1
                x = y
        ciblable = {s: self.targetable(s, self.info.get(s) or {}, self.rne.get(s)) for s in self.retained}

        # Compte de rattachement : la société ciblable la plus proche au-dessus.
        def account(s: str | None) -> str | None:
            while s and not (s in ciblable and ciblable[s][0]):
                s = parent.get(s, (None,))[0]
            return s

        societes = []
        for s in self.retained:
            i = self.info.get(s) or {}
            v = self.rne.get(s)
            p = parent.get(s)
            tgt, why = ciblable[s]
            cj = i.get("cj")
            societes.append(
                Societe(
                    siren=s,
                    nom=i.get("nom"),
                    niveau=level[s],
                    siret_siege=i.get("siret_siege"),
                    maison_mere_siren=p[0] if p else None,
                    maison_mere_nom=(self.info.get(p[0]) or {}).get("nom") if p else None,
                    preuve=p[1] if p else "Tête du groupe",
                    confiance=p[2] if p else "A",
                    pourquoi_dans_le_groupe=self.retained[s],
                    indices=tuple(sorted({k for k, _ in self.ev[s]})),
                    ciblable=tgt,
                    raison_ciblable=why,
                    naf=i.get("naf"),
                    forme_juridique=None if cj is None else str(cj),
                    tranche_effectif=i.get("tranche"),
                    salaries_rne=v.salaries if v else None,
                    opposition_prospection=(v.diffusion_commerciale if v else None) is False,
                    non_diffusible=v.non_diffusible if v else None,
                    adresse_siege=i.get("adresse_cle"),
                    commune=i.get("commune"),
                    compte_de_rattachement=account(s),
                )
            )
        societes.sort(key=lambda x: (x.niveau, x.nom is None, x.nom or ""))
        liens = [
            Lien(parent=p, enfant=s, role=ROLE_LABEL[c], preuve=f"Mandat au registre : {ROLE_LABEL[c]}",
                 confiance="A")
            for s in self.retained
            for p, c in self._parents(s)
            if p in self.retained and c in ROLE_LABEL
        ]  # fmt: skip
        participations = [
            Participation(
                siren=s,
                nom=(self.info.get(s) or {}).get("nom"),
                mandats=tuple(
                    Mandat(p, ROLE_LABEL[c])
                    for p, c in self._parents(s)
                    if p in self.retained and c in MEDIUM
                ),
            )
            for s in self.ev
            if s not in self.retained
            and self.info.get(s)
            and any(p in self.retained and c in MEDIUM for p, c in self._parents(s))
        ]
        return Carto(
            groupe=self.cfg["groupe"],
            tete=tete,
            date_donnees=date_donnees,
            societes=tuple(societes),
            liens=tuple(liens),
            participations=tuple(participations),
            # Une société étrangère retenue par le consultant est dans `societes`, plus ici.
            etrangeres=tuple(Etrangere(k, v) for k, v in self.foreign.items() if k not in self.retained),
            tours=tuple(self.tours),
            cas=self.ranger_cas(parent, {p.siren for p in participations}),
        )

    def _parents(self, s: str) -> list[tuple[str, str]]:
        v = self.rne.get(s)
        return v.parents if v else []

    # ---------- cas douteux (T027) ----------
    def _exterieurs(self, s: str) -> list[tuple[str, str]]:
        """Les mandats forts ou moyens tenus sur `s` par une société hors du groupe."""
        return [
            (p, c)
            for p, c in self._parents(s)
            if p != s and p not in self.retained and (c in STRONG or c in MEDIUM)
        ]

    def _designation(self, p: str) -> str:
        """Une société hors du groupe, désignée par son SIREN seulement si c'est une personne morale
        connue de SIRENE. Un entrepreneur individuel (catégorie 1…) ou une entité inconnue reste
        anonyme : son SIREN désignerait une personne (garde-fou 6)."""
        cj = str((self.info.get(p) or {}).get("cj") or "")
        return f"la société {p}" if cj and not cj.startswith("1") else "une entité"

    def _indices_pour(self, s: str, pidx: dict[str, set[str]]) -> list[str]:
        """Ce qui rattache `s` au groupe, en textes du moteur : jamais un nom de personne."""
        # La marque et la maison ne sont pas recopiées : une marque peut être le nom complet d'un
        # dirigeant (maison de couture au nom de son fondateur ; LVMH, 2026-10-08). Le nom de la
        # société, affiché à côté, montre déjà la marque qu'elle porte.
        pour = []
        for kind, d in self.ev[s]:
            if kind == "marque_sure":
                pour.append("Porte une marque sûre du groupe")
            elif kind == "marque_ambigue":
                pour.append("Porte une marque ambiguë du groupe")
            elif kind == "registre" and d[0] in self.retained and d[1] in ROLE_LABEL:
                pour.append(f"Mandat au registre : {ROLE_LABEL[d[1]]}, tenu par la société du groupe {d[0]}")
            elif kind == "adresse":
                pour.append(f"Siège à une adresse du groupe : {d[1]} sociétés du groupe sur {d[2]}")
            elif kind == "organigramme":
                pour.append("Tête d'une maison de l'organigramme public du groupe")
        fiche = self.rne.get(s)
        # Dirigeants personnes en commun avec une AUTRE société du groupe : un nombre, jamais un nom.
        communs = sum(1 for k in (fiche.persons if fiche else {}) if pidx.get(k, set()) - {s})
        if communs:
            pour.append(f"Dirigeants en commun avec d'autres sociétés du groupe : {communs}")
        return pour

    def _indices_contre(self, s: str, types: list[TypeCas]) -> list[str]:
        """Ce qui fait douter que `s` soit une filiale du groupe."""
        contre = []
        mandats = [p for p, c in self._parents(s) if p in self.retained and p != s and c in ROLE_LABEL]
        if not any(c in STRONG for p, c in self._parents(s) if p in self.retained and p != s):
            contre.append(
                "Aucun mandat fort (président, gérant…) tenu par une société du groupe"
                if mandats
                else "Aucun mandat au registre tenu par une société du groupe"
            )
        if "confiance_c" in types:
            contre.append("Un seul indice : rattachement déduit, pas lu au registre")
        for p, c in self._exterieurs(s):
            tenu = f"tenu par {self._designation(p)} hors du groupe"
            contre.append(f"Mandat au registre : {ROLE_LABEL[c]}, {tenu}")
        if "etrangere" in types:
            cj = (self.info.get(s) or {}).get("cj")
            contre.append(f"Société étrangère (catégorie juridique {cj}) : hors du périmètre France")
        if self.decisions.get(s) == "ecarter":
            contre.append("Écartée par le consultant")
        return contre

    def _regle(self, s: str, types: list[TypeCas], parent: dict[str, tuple[str, str, Confiance]]) -> str:
        """La règle qui a placé `s` là où elle est : dans le groupe (et comment), ou hors du groupe."""
        if s in self.retained:
            texte = f"Entrée dans le groupe : {self.retained[s]}"
            return f"{texte} · rattachement : {parent[s][1]}" if s in parent else texte
        if s in self.ecartees:
            return f"Écartée par le consultant ; règle du moteur qui l'aurait retenue : {self.ecartees[s]}"
        if "participation" in types:
            if any(c in STRONG for _, c in self._exterieurs(s)):
                return "Non retenue : contrôle partagé avec une société hors du groupe (mandat fort)"
            return "Non retenue : participation sans contrôle (mandat moyen sans indice indépendant)"
        if "etrangere" in types:
            return "Non retenue : société étrangère, jamais retenue par le moteur"
        return "Non retenue"

    def ranger_cas(
        self, parent: dict[str, tuple[str, str, Confiance]], participations: set[str]
    ) -> tuple[Cas, ...]:
        """Les cas douteux du calcul, chacun avec sa règle et ses indices (T027, FR-009).

        Le moteur range, il ne tranche pas (principe 1) : un cas retenu reste dans la carto, un
        cas non retenu reste dehors, jusqu'à la décision du consultant. Une société qui a une
        décision en vigueur est rangée aussi, même si elle n'est plus douteuse (type `decision`),
        pour que le consultant puisse revenir dessus ; sauf si la décision est sans objet : la
        société a disparu du registre ou n'a plus aucun indice qui la lie au groupe.
        """
        tete = self.cfg["tete"]
        pidx = self.persons_index()
        self.load_info({p for s in set(self.retained) | participations for p, _ in self._exterieurs(s)})
        sirens = set(self.retained) | participations | set(self.foreign) | set(self.ecartees)
        cas = []
        for s in sorted(sirens - {tete}):
            types: list[TypeCas] = []
            if s in self.retained and s in parent and parent[s][2] == "C":
                types.append("confiance_c")
            if s in self.retained and self._exterieurs(s):
                types.append("co_entreprise")
            if s in participations:
                types.append("participation")
            if s in self.foreign:
                types.append("etrangere")
            decision = self.decisions.get(s)
            if not types and (s in self.ecartees or (decision == "retenir" and s in self.retained)):
                types.append("decision")
            if not types:
                continue
            cas.append(
                Cas(
                    siren=s,
                    nom=(self.info.get(s) or {}).get("nom"),
                    types=tuple(types),
                    regle=self._regle(s, types, parent),
                    retenue=s in self.retained,
                    indices_pour=tuple(self._indices_pour(s, pidx)),
                    indices_contre=tuple(self._indices_contre(s, types)),
                    decision=decision,
                )
            )
        return tuple(cas)

    def targetable(self, s: str, i: dict[str, Any], v: _Fiche | None) -> tuple[bool, str]:
        """Oui : société opérationnelle, tête de maison ou société mère. Non : nœud purement structurel.
        Une tranche INSEE "NN" veut dire non renseignée, pas zéro salarié."""
        if s == self.cfg["tete"]:
            return True, "Société mère du groupe"
        if any(k == "organigramme" for k, _ in self.ev[s]):
            return True, "Tête de maison"
        cj, naf, tr, sal = i.get("cj"), i.get("naf"), i.get("tranche"), (v.salaries if v else None)
        big = (tr not in SMALL_TRANCHES) or bool(sal and sal >= 10)
        if civile(cj) and not big:
            return False, "Société civile ou SCI"
        if gie(cj) and not big:
            return False, "GIE de moyens"
        if naf in HOLDING_NAF and not big:
            return False, "Holding ou société immobilière sans salarié déclaré"
        if tr == "00" and not sal:
            return False, "Aucun salarié"
        return True, "Société opérationnelle"


def date_des_donnees(con: duckdb.DuckDBPyConnection) -> date | None:
    """La date la plus récente portée par le registre : début ou fin d'un lien ou d'une société."""
    ligne = con.execute("""
        select max(d) from (
            select max(greatest(debut, coalesce(fin, debut))) d from liens
            union all
            select max(greatest(debut, coalesce(fin, debut))) from societes
        )
    """).fetchone()
    return ligne[0] if ligne else None


DECISIONS: dict[str, Decision] = {"retenir": "retenir", "ecarter": "ecarter"}


def decisions_en_vigueur(lignes: Iterable[tuple[str, str, datetime, int]]) -> dict[str, Decision]:
    """La décision en vigueur pour chaque SIREN, parmi toutes celles prises pour un groupe (T027).

    `lignes` : (SIREN, décision, date, numéro d'ordre), dans n'importe quel ordre. Une décision
    n'est jamais effacée : la plus récente l'emporte, et à date égale, la dernière enregistrée
    (numéro d'ordre le plus grand). Une valeur inconnue est ignorée, sans masquer une décision
    plus ancienne.
    """
    retenues: dict[str, tuple[datetime, int, Decision]] = {}
    for siren, valeur, le, numero in lignes:
        decision = DECISIONS.get(valeur)
        if decision is None:
            continue
        actuelle = retenues.get(siren)
        if actuelle is None or (le, numero) > actuelle[:2]:
            retenues[siren] = (le, numero, decision)
    return {s: d for s, (_, _, d) in retenues.items()}


def ouvrir_registre(registre: Path) -> duckdb.DuckDBPyConnection:
    """Ouvre le registre en lecture seule : le moteur n'écrit jamais dedans."""
    if not registre.is_file():
        raise FileNotFoundError(f"registre introuvable : {registre}")
    con = duckdb.connect(str(registre), read_only=True)
    con.execute("set enable_progress_bar = false")
    return con


def cartographier(
    reglages: dict[str, Any],
    registre: Path,
    candidates: Callable[[duckdb.DuckDBPyConnection, dict[str, Any]], list[Candidate]] = chercher_candidates,
    cle_empreinte: str | None = None,
    decisions: Mapping[str, Decision] | None = None,
) -> Carto:
    """Calcule la carto du groupe décrit par `reglages` sur le registre local, sans appel réseau.

    `candidates` permet de fournir les sociétés de marque autrement (diagnostic, tests).
    `cle_empreinte` : la clé des empreintes de `familles_exclues_empreintes` ; sans elle,
    CARTOFR_CLE_EMPREINTE (CleManquante si elle manque alors que la liste n'est pas vide).
    `decisions` : les décisions du consultant en vigueur pour ce groupe, SIREN -> « retenir » ou
    « écarter » (`decisions_en_vigueur`). Sans elles, les règles décident seules.
    """
    con = ouvrir_registre(registre)
    try:
        trouvees = candidates(con, reglages)
        moteur = _Moteur(reglages, con, cle_empreinte, decisions).run(trouvees)
        carto = moteur.build(date_des_donnees(con))
        return carto if moteur.point_fixe else replace(carto, avertissements=(GARDE_ATTEINTE,))
    finally:
        con.close()
