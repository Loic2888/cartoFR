"""Diagnostic : à une adresse donnée, qui est retenu, et quels indices ont les autres sociétés."""
import json, sys
import pandas as pd
import engine
cfg = json.load(open(sys.argv[1])); addr = sys.argv[2]
m = engine.Mapper(cfg); m.run()
b = set(pd.read_csv(f"basile/{m.g}_entites.csv", dtype=str).SIREN)
pidx = m.persons_index()
rows = m.db.execute("select siren, nom, cj, naf, tranche from s where adresse_cle = ?", [addr]).fetchall()
print(f"{addr} : {len(rows)} sociétés, {sum(r[0] in m.retained for r in rows)} retenues, {sum(r[0] in b for r in rows)} chez Basile")
for s, nom, cj, naf, tr in rows:
    v = m.rne.get(s) or m.view(s) or {}
    common = [k for k in v.get("persons", {}) if k in pidx]
    cadre = sum(len(pidx[k]) >= 2 for k in common)
    print(("R " if s in m.retained else "  ") + ("B " if s in b else "  "), s, (nom or "")[:38].ljust(38), cj, naf,
          f"communs={len(common)} cadres={cadre}", sorted({k for k, _ in m.ev[s]}))
