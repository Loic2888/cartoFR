"""Cartographie d'un groupe : étapes 4 à 8 du plan, en boucle jusqu'à ce que plus rien ne bouge.

Usage : python engine.py config/lvmh.json
Entrées : config du groupe, out/<groupe>_candidates.csv (brand_scan.py), data/sieges.parquet (build_sieges.py).
Sorties : out/<groupe>_entites.csv, out/<groupe>_relations.csv, out/<groupe>_participations.csv.

Règle de licence INPI : les dirigeants personnes physiques servent seulement de preuve pendant le
calcul. Aucun nom de personne n'est écrit dans les sorties.
"""
import collections, json, re, sys
import duckdb, pandas as pd
import annuaire, bodacc, inpi
from brand_scan import norm as engine_norm
import pathlib
LINKS = pathlib.Path(__file__).parent / "data" / "rne_links"

# Codes de rôle RNE, reconstitués en croisant 195 fiches avec les rôles lus par Basile (role_codes.py).
STRONG = {"73": "Président", "30": "Gérant", "28": "Gérant et associé indéfiniment et solidairement responsable",
          "29": "Gérant et associé indéfiniment responsable", "74": "Associé indéfiniment et solidairement responsable",
          "75": "Associé indéfiniment responsable", "131": "Associé commandité"}
MEDIUM = {"65": "Administrateur", "11": "Membre", "64": "Membre du conseil de surveillance", "51": "Président du conseil d'administration"}
WEAK = {"99": "Autre"}
ROLE_LABEL = {**STRONG, **MEDIUM, **WEAK}
# Rôles d'une personne physique qui veulent dire "elle dirige la société".
DIRECTING = {"73", "30", "28", "29", "51", "53"}
CIVIL = lambda cj: str(cj).startswith("6") and not str(cj).startswith("62")  # sociétés civiles, SCI, GFA...
GIE = lambda cj: str(cj).startswith("62")
HOLDING_NAF = {"64.20Z", "64.30Z", "66.30Z", "68.20A", "68.20B", "68.10Z", "68.32A", "64.99Z"}
SMALL_TRANCHES = {None, "", "NN", "00", "01", "02", "03"}


class Mapper:
    def __init__(self, cfg):
        self.cfg = cfg
        self.g = cfg["groupe"].lower()
        self.db = duckdb.connect()
        self.db.sql("create table s as select * from 'data/sieges.parquet'")
        self.info = {}
        self.rne = {}
        self.fetch_failed = False
        self.ev = collections.defaultdict(list)  # siren -> [(type, détail)]
        self.retained = {}  # siren -> raison d'entrée
        self.bodacc_done = set()
        self._longer = {}
        self.annuaire_done = set()
        self.foreign = {}
        self.family = {n.upper() for n in cfg.get("familles_exclues", [])}
        self.excluded = set(cfg.get("exclus", []))
        # Mode local : les tables tirées du stock RNE complet (build_links.py) remplacent l'API INPI,
        # l'Annuaire et le BODACC. Aucun quota, aucun appel extérieur.
        self.local = LINKS.joinpath("liens.parquet").exists() and cfg.get("source", "local") == "local"
        if self.local:
            self.db.sql(f"create table liens as select * from '{LINKS}/liens.parquet' where coalesce(actif, true)")
            self.db.sql(f"create view personnes as select * from '{LINKS}/personnes.parquet'")
            self.db.sql(f"create view societes as select * from '{LINKS}/societes.parquet'")
        self.local_done = set()

    # ---------- données ----------
    def load_info(self, sirens):
        missing = [s for s in sirens if s not in self.info]
        if not missing:
            return
        df = self.db.execute("select * from s where siren in (select unnest(?))", [missing]).df()
        for r in df.to_dict("records"):
            self.info[r["siren"]] = r
        for s in missing:
            self.info.setdefault(s, None)  # inactive ou absente de SIRENE : écartée

    def prefetch(self, sirens):
        """Mode local : remplit d'un coup les fiches de plusieurs sociétés depuis les tables du stock."""
        todo = [s for s in set(sirens) if s not in self.rne]
        if not todo:
            return
        for s in todo:
            self.rne[s] = {"parents": [], "persons": {}, "salaries": None, "diffusion_commerciale": None}
        for p, c, r in self.db.execute("select parent, enfant, role from liens where enfant in (select unnest(?))", [todo]).fetchall():
            self.rne[c]["parents"].append((p, r))
        for s, key, r in self.db.execute("""select siren, personne, role from personnes
                where siren in (select unnest(?)) and coalesce(actif, true)""", [todo]).fetchall():
            if key.split("|")[0] not in self.family:
                self.rne[s]["persons"].setdefault(key, set()).add(r)
        for s, dc, sal in self.db.execute("""select siren, any_value(diffusion_commerciale), max(salaries)
                from societes where siren in (select unnest(?)) group by siren""", [todo]).fetchall():
            self.rne[s]["diffusion_commerciale"], self.rne[s]["salaries"] = dc, sal

    def discover_local(self):
        """Mode local : toutes les sociétés dont une société retenue est dirigeante, d'après le registre."""
        new = [r for r in self.retained if r not in self.local_done]
        self.local_done.update(new)
        for p, c, r in self.db.execute("select parent, enfant, role from liens where parent in (select unnest(?))", [new]).fetchall():
            if p != c:
                self.add(c, "registre", (p, r))

    def view(self, siren):
        """Ce que la fiche RNE dit des dirigeants de `siren`, ou None si elle n'a pas pu être lue."""
        if siren in self.rne:
            return self.rne[siren]
        if self.local:
            self.prefetch([siren])
            return self.rne[siren]
        if self.fetch_failed and not (inpi.CACHE / f"{siren}.json").exists():
            return None
        try:
            d = inpi.company(siren)
        except RuntimeError:
            self.fetch_failed = True
            return None
        v = {"parents": [], "persons": {}, "salaries": None, "diffusion_commerciale": None}
        if d:
            f = d["formality"]
            v["diffusion_commerciale"] = f.get("diffusionCommerciale")
            pm = f["content"].get("personneMorale") or {}
            v["salaries"] = ((pm.get("identite") or {}).get("entreprise") or {}).get("nombreSalarie")
            for p in (pm.get("composition") or {}).get("pouvoirs", []):
                if p.get("actif") is False:
                    continue
                code = p.get("roleEntreprise")
                if p["typeDePersonne"] == "ENTREPRISE":
                    e = p.get("entreprise") or {}
                    if e.get("siren"):
                        v["parents"].append((e["siren"], code))
                elif p["typeDePersonne"] == "INDIVIDU":
                    dp = (p.get("individu") or {}).get("descriptionPersonne") or {}
                    nom = (dp.get("nom") or "").upper()
                    if not nom or nom in self.family:
                        continue
                    key = f"{nom}|{(dp.get('prenoms') or [''])[0].upper()}|{dp.get('dateDeNaissance', '')}"
                    v["persons"].setdefault(key, set()).add(code)
        self.rne[siren] = v
        return v

    # ---------- indices ----------
    def add(self, siren, kind, detail):
        if (kind, detail) not in self.ev[siren]:
            self.ev[siren].append((kind, detail))

    def discover_bodacc(self):
        for r in list(self.retained):
            if r in self.bodacc_done:
                continue
            self.bodacc_done.add(r)
            name = (self.info.get(r) or {}).get("nom")
            if not name:
                continue
            # Règle Basile : une annonce ne compte que si le nom de la société du groupe n'a pas d'homonyme.
            if self.homonyms(name) > 1:
                continue
            for t, a in bodacc.officer_of(name, r, self.longer_name).items():
                if not a["partant"]:
                    self.add(t, "bodacc", (r, a["role"], a["date"]))

    def homonyms(self, name):
        return self.db.execute("select count(*) from s where upper(nom) = upper(?)", [name]).fetchone()[0]

    def longer_name(self, name, word):
        if (name, word) not in self._longer:
            self._longer[(name, word)] = self.db.execute(
                "select count(*) > 0 from s where upper(nom) like ?", [f"{name} {word}%"]).fetchone()[0]
        return self._longer[(name, word)]

    def discover_annuaire(self):
        for r in list(self.retained):
            if r in self.annuaire_done:
                continue
            self.annuaire_done.add(r)
            for name in self.name_variants(r):
                for t, q in annuaire.officer_of(name, r).items():
                    self.add(t, "annuaire", (r, q))

    def group_addresses(self, pidx=None):
        """Adresses où le groupe est majoritaire. Comme Basile : on compte les sociétés de l'adresse
        (sans les associations ni fondations), et sont "du groupe" les retenues et celles qui ont déjà
        un indice propre (marque du groupe, mandat trouvé, dirigeant cadre du groupe)."""
        self.load_info(list(self.retained))
        addrs = collections.Counter((self.info[r] or {}).get("adresse_cle") for r in self.retained if self.info.get(r))
        pidx = pidx or {}
        out = {}
        for a, n in addrs.items():
            if not a or "[ND]" in a or n < 2:
                continue
            rows = [s for (s, cj) in self.db.execute("select siren, cj from s where adresse_cle = ?", [a]).fetchall()
                    if not str(cj).startswith("9")]
            def group_like(s):
                if s in self.retained:
                    return True
                if s in self.excluded or self.name_excluded(s):
                    return False
                kinds = {k for k, _ in self.ev[s]}
                cadre = any(len(pidx.get(k, ())) >= 2 for k in (self.rne.get(s) or {}).get("persons", {}))
                return bool(kinds & {"marque_sure", "annuaire", "bodacc", "registre"}) or cadre
            g = sum(group_like(s) for s in rows)
            if rows and g / len(rows) >= 0.5:
                out[a] = (g, len(rows))
                for s in rows:
                    self.ev[s] = [x for x in self.ev[s] if x[0] != "adresse"]
                    self.add(s, "adresse", (a, g, len(rows)))
        return out

    def add_organigramme(self):
        """Organigramme public du groupe (liste des maisons, validée par un humain dans la config) :
        pour chaque maison, la plus grande société active qui porte ce nom devient sa tête."""
        order = "case tranche when 'NN' then -1 when null then -2 else try_cast(tranche as integer) end"
        for maison in self.cfg.get("organigramme", []):
            m = engine_norm(maison)
            rows = self.db.execute(f"""select siren, nom, cj from s
                where regexp_replace(upper(strip_accents(nom)), '[^A-Z0-9]+', ' ', 'g') similar to ?
                  and not (cast(cj as varchar) like '6%' and cast(cj as varchar) not like '62%')
                  and cast(cj as varchar) not like '9%' and cast(cj as varchar) not like '3%'
                order by {order} desc nulls last limit 1""",
                [f"((SOC|STE|SOCIETE|LES|LE|LA|L) )*{re.escape(m)}( .*)?"]).fetchall()
            for s, nom, cj in rows:
                self.add(s, "organigramme", maison)

    def name_variants(self, s):
        nom = (self.info.get(s) or {}).get("nom") or ""
        sigle = self.db.execute("select sigleUniteLegale from 'data/unite_legale.parquet' where siren = ?", [s]).fetchone()
        out = {nom, re.sub(r"\b([A-Z]) (?=[A-Z]\b)", r"\1", nom)}
        if sigle and sigle[0] and len(sigle[0]) >= 3:
            out.add(sigle[0])
        return [n for n in out if n.strip()]

    def name_excluded(self, s):
        nom = ((self.info.get(s) or {}).get("nom") or "").upper()
        return any(nom.startswith(p.upper()) for p in self.cfg.get("exclus_noms", []))

    def persons_index(self):
        idx = collections.defaultdict(set)
        for r in self.retained:
            v = self.rne.get(r)
            for k in (v or {}).get("persons", {}):
                idx[k].add(r)
        return idx

    # ---------- décision ----------
    def decide(self, s, pidx):
        info = self.info.get(s)
        if s in self.retained or s in self.excluded or not info or self.name_excluded(s):
            return None
        if str(info["cj"]).startswith("9") or re.match(r"(CSE|COMITE|AMICALE|ASSOCIATION)\b", (info["nom"] or "").upper()):
            return None  # associations, fondations, comités d'entreprise : jamais des filiales
        if str(info["cj"]).startswith("3"):
            if any(k in ("marque_sure", "bodacc") for k, _ in self.ev[s]):
                self.foreign[s] = info["nom"]
            return None
        ev = self.ev[s]
        v = self.rne.get(s)
        cj = info["cj"]
        mandates = [(p, c) for p, c in (v or {}).get("parents", []) if p in self.retained]
        strong = [m for m in mandates if m[1] in STRONG]
        medium = [m for m in mandates if m[1] in MEDIUM]
        weak = [m for m in mandates if m[1] in WEAK]
        bod = [d for k, d in ev if k == "bodacc"]
        brand = [d for k, d in ev if k in ("marque_sure", "marque_ambigue")]
        sure = any(k == "marque_sure" for k, _ in ev)
        addr = [d for k, d in ev if k == "adresse"]
        common, directs = 0, False
        for key, codes in (v or {}).get("persons", {}).items():
            if key in pidx:
                common += 1
                directs |= bool(codes & DIRECTING)
        cadre = any(len(pidx.get(k, ())) >= 2 for k in (v or {}).get("persons", {}))
        people_ok = (common >= 2 or (common >= 1 and cadre)) and not (CIVIL(cj) and not sure)
        if strong:
            return "mandat fort au registre"
        if any(k == "organigramme" for k, _ in ev):
            return "tête de maison (organigramme public du groupe)"
        if any(r in ("president", "gerant") and d >= "2018" for _, r, d in bod):
            return "annonce BODACC (président ou gérant)"
        others = sum([bool(brand), bool(addr), people_ok, bool(bod)])
        # Règle Basile : un GIE dont tous les membres sont des sociétés du groupe entre aussi.
        members = [p for p, c in (v or {}).get("parents", []) if c == "11"]
        if GIE(cj) and len(members) >= 2 and all(p in self.retained for p in members):
            return "GIE dont tous les membres sont du groupe"
        outside = [p for p, c in (v or {}).get("parents", []) if p not in self.retained and c in STRONG]
        if medium and outside:
            return None  # partagée avec une société extérieure : participation sans contrôle (règle Basile)
        if medium:
            if (people_ok and directs) or brand or addr:
                return "mandat au registre et indice indépendant"
            return None  # participation sans contrôle
        if weak:
            return "mandat 'Autre' et deux indices" if others >= 2 else None
        sure_brands = [d for k, d in ev if k == "marque_sure"]
        bare = lambda b: len(engine_norm(info["nom"]).split()) <= len(b.split()) + 1
        risky = lambda b: b in self.cfg.get("marques_sures_homonymes", []) or (b in self.cfg.get("marques_sigles", []) and bare(b))
        tiny = info.get("tranche") in (None, "", "NN", "00") and not ((v or {}).get("salaries") or 0)
        if sure and not CIVIL(cj) and not any(risky(b) for b in sure_brands) and not (tiny and all(bare(b) for b in sure_brands)):
            return "nom de marque propre au groupe"
        if brand and (people_ok or addr or bod):
            return "nom de marque et second indice"
        if addr and (people_ok or bod or (common >= 1 and not CIVIL(cj))):
            return "adresse du groupe et second indice"
        return None

    # ---------- boucle ----------
    def run(self, max_rounds=8):
        tete = self.cfg["tete"]
        self.retained[tete] = "tête du groupe"
        cand = pd.read_csv(f"out/{self.g}_candidates.csv", dtype=str)
        for r in cand.itertuples():
            self.add(r.siren, "marque_" + r.type_marque, r.marque)
        self.add_organigramme()
        for rnd in range(1, max_rounds + 1):
            before = len(self.retained)
            self.load_info(list(self.retained))
            if self.local:
                self.discover_local()
            else:
                self.discover_bodacc()
                self.discover_annuaire()
            addrs = self.group_addresses()
            pool = [s for s in self.ev if s not in self.retained and s not in self.excluded]
            self.load_info(pool + list(self.retained))
            pool = [s for s in pool if self.info.get(s)]
            # Fiches RNE : d'abord les candidates qui ont un indice fort, puis les marques ambiguës.
            if self.local:
                self.prefetch(set(pool) | set(self.retained))
            else:
                prio = lambda s: 0 if any(k in ("annuaire", "bodacc", "registre", "adresse", "marque_sure") for k, _ in self.ev[s]) else 1
                for s in sorted(set(pool) | set(self.retained), key=prio):
                    self.view(s)
            pidx = self.persons_index()
            addrs = self.group_addresses(pidx)
            for s in pool:
                why = self.decide(s, pidx)
                if why:
                    self.retained[s] = why
            print(f"tour {rnd} : {len(self.retained)} sociétés retenues (+{len(self.retained) - before}), "
                  f"{len(pool)} candidates, {len(addrs)} adresses du groupe, fiches RNE lues {len(self.rne)}"
                  + (" [quota INPI atteint]" if self.fetch_failed else ""), flush=True)
            if len(self.retained) == before:
                break
        return self

    # ---------- arbre ----------
    def parent_of(self, s):
        order = [self.cfg["tete"]] + self.cfg.get("priorite", [])
        rank = lambda p: (order.index(p) if p in order else len(order))
        v = self.rne.get(s) or {}
        links = [(0 if c in STRONG else 1 if c in WEAK else 2, rank(p), p, c) for p, c in v.get("parents", []) if p in self.retained and p != s]
        if links:
            _, _, p, c = min(links)
            return p, f"Mandat au registre : {ROLE_LABEL.get(c, c)}", "A"
        bod = sorted((d for k, d in self.ev[s] if k == "bodacc" and d[2] >= "2018" and d[0] != s), key=lambda d: (rank(d[0]), d[2]))
        if bod:
            return bod[0][0], f"Annonce BODACC du {bod[0][2]} ({bod[0][1]})", "A"
        n_ev = len({k.split("_")[0] for k, _ in self.ev[s]}) + (1 if self.retained[s].endswith("indice") else 0)
        conf = "B" if n_ev >= 2 or "second indice" in self.retained[s] else "C"
        for k, brand in self.ev[s]:
            head = self.heads.get(brand) if k.startswith("marque") else None
            if head and head != s:
                return head, f"Déduit : même maison ({brand})", conf
        return self.cfg["tete"], "Déduit : rattachée à la tête du groupe", conf

    def build(self):
        tete = self.cfg["tete"]
        # Tête de maison : pour chaque marque, la société retenue de cette marque qui a le plus de salariés.
        size = lambda x: ((self.rne.get(x) or {}).get("salaries") or 0, (self.info.get(x) or {}).get("tranche") or "")
        self.heads = {}
        for x in self.retained:
            for k, brand in self.ev[x]:
                if k.startswith("marque") and (brand not in self.heads or size(x) > size(self.heads[brand])):
                    self.heads[brand] = x
        parent = {s: self.parent_of(s) for s in self.retained if s != tete}
        level = {tete: 0}

        def lvl(s, seen=()):
            if s in level:
                return level[s]
            if s in seen:  # boucle de mandats croisés : on la coupe en rattachant à la tête
                parent[s] = (tete, "Déduit : boucle de mandats coupée", "C")
                level[s] = 1
                return 1
            level[s] = lvl(parent[s][0], seen + (s,)) + 1
            return level[s]

        for s in self.retained:
            lvl(s)
        rows = []
        for s in self.retained:
            i = self.info.get(s) or {}
            v = self.rne.get(s) or {}
            p = parent.get(s)
            tgt, why = self.targetable(s, i, v)
            rows.append({"siren": s, "nom": i.get("nom"), "niveau": level[s], "siret_siege": i.get("siret_siege"),
                         "maison_mere_siren": p[0] if p else None, "maison_mere": (self.info.get(p[0]) or {}).get("nom") if p else None,
                         "type_lien": p[1] if p else "Tête du groupe", "confiance": p[2] if p else "A",
                         "pourquoi_dans_le_groupe": self.retained[s],
                         "indices": " ; ".join(sorted({k for k, _ in self.ev[s]})),
                         "targetable": tgt, "raison": why, "naf": i.get("naf"), "forme_juridique": i.get("cj"),
                         "tranche_effectif": i.get("tranche"), "salaries_rne": v.get("salaries"),
                         "opposition_prospection": v.get("diffusion_commerciale") is False,
                         "adresse_siege": i.get("adresse_cle"), "commune": i.get("commune")})
        df = pd.DataFrame(rows).sort_values(["niveau", "nom"])
        # Compte de rattachement : la société ciblable la plus proche au-dessus.
        tg = dict(zip(df.siren, df.targetable))
        def account(s):
            while s and tg.get(s) != "Oui":
                s = parent.get(s, (None,))[0]
            return s
        df["compte_de_rattachement"] = [account(s) for s in df.siren]
        df.to_csv(f"out/{self.g}_entites.csv", index=False)
        rel = [{"maison_mere": p, "filiale": s, "role": ROLE_LABEL.get(c, c)} for s in self.retained
               for p, c in (self.rne.get(s) or {}).get("parents", []) if p in self.retained and c in ROLE_LABEL]
        pd.DataFrame(rel).to_csv(f"out/{self.g}_relations.csv", index=False)
        part = [{"siren": s, "nom": (self.info.get(s) or {}).get("nom"),
                 "mandats": " ; ".join(f"{p}:{ROLE_LABEL[c]}" for p, c in (self.rne.get(s) or {}).get("parents", []) if p in self.retained and c in MEDIUM)}
                for s in self.ev if s not in self.retained and self.info.get(s)
                and any(p in self.retained and c in MEDIUM for p, c in (self.rne.get(s) or {}).get("parents", []))]
        pd.DataFrame(part).to_csv(f"out/{self.g}_participations.csv", index=False)
        pd.DataFrame([{"siren": k, "nom": v} for k, v in self.foreign.items()]).to_csv(f"out/{self.g}_etrangeres.csv", index=False)
        print(f"{len(df)} sociétés, {int((df.targetable == 'Oui').sum())} ciblables, confiance {df.confiance.value_counts().to_dict()}, "
              f"{len(part)} participations sans contrôle")
        return df

    def targetable(self, s, i, v):
        """Oui : société opérationnelle, tête de maison ou société mère. Non : nœud purement structurel.
        Une tranche INSEE "NN" veut dire non renseignée, pas zéro salarié."""
        if s == self.cfg["tete"]:
            return "Oui", "Société mère du groupe"
        if any(k == "organigramme" for k, _ in self.ev[s]):
            return "Oui", "Tête de maison"
        cj, naf, tr, sal = i.get("cj"), i.get("naf"), i.get("tranche"), v.get("salaries")
        big = (tr not in SMALL_TRANCHES) or bool(sal and sal >= 10)
        if CIVIL(cj) and not big:
            return "Non", "Société civile ou SCI"
        if GIE(cj) and not big:
            return "Non", "GIE de moyens"
        if naf in HOLDING_NAF and not big:
            return "Non", "Holding ou société immobilière sans salarié déclaré"
        if tr == "00" and not sal:
            return "Non", "Aucun salarié"
        return "Oui", "Société opérationnelle"


if __name__ == "__main__":
    cfg = json.load(open(sys.argv[1]))
    Mapper(cfg).run().build()
