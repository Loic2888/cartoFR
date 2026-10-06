"""Rejoue les tours depuis le cache et montre pourquoi les sociétés sont entrées (diagnostic).

Usage : python debug_round.py config/lvmh.json 2
"""
import collections, json, sys
import pandas as pd
import engine

cfg = json.load(open(sys.argv[1]))
m = engine.Mapper(cfg)
m.run(max_rounds=int(sys.argv[2]))
c = collections.Counter(m.retained.values())
b = set(pd.read_csv(f"basile/{m.g}_entites.csv", dtype=str).SIREN)
for why, n in c.most_common():
    ss = [s for s, w in m.retained.items() if w == why]
    print(f"\n== {why} : {n}, dont {sum(s in b for s in ss)} chez Basile")
    for s in [x for x in ss if x not in b][:6]:
        print("  ", s, (m.info.get(s) or {}).get("nom"), sorted({k for k, _ in m.ev[s]}),
              [(p, c) for p, c in (m.rne.get(s) or {}).get("parents", []) if p in m.retained][:3],
              [d for k, d in m.ev[s] if k == "adresse"][:1])
