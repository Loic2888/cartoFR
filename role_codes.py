"""Déduit le sens des codes de rôle RNE en les croisant avec les rôles lus par Basile sur les mêmes liens."""
import collections, pandas as pd, inpi

rels = pd.concat([pd.read_csv(f"basile/{g}_relations.csv", dtype=str).assign(g=g) for g in ("lvmh", "vinci")])
col = "Lien" if "Lien" in rels else "Type de lien"
rels["role"] = rels.get("Lien", pd.Series(dtype=str)).fillna(rels.get("Type de lien", pd.Series(dtype=str)))
rels = rels[rels.role.str.contains("Mandat au registre|^Registre|Président|Gérant|Administrateur|Associé|Membre", regex=True, na=False)]
rels = rels.drop_duplicates(["SIREN maison mère", "SIREN filiale"]).head(400)
seen = collections.defaultdict(collections.Counter)
for _, r in rels.iterrows():
    d = inpi.company(r["SIREN filiale"])
    if not d:
        continue
    for p in d["formality"]["content"].get("personneMorale", {}).get("composition", {}).get("pouvoirs", []):
        e = p.get("entreprise") or {}
        if e.get("siren") == r["SIREN maison mère"]:
            seen[p["roleEntreprise"]][r.role.replace("Mandat au registre : ", "").replace("Registre : ", "")] += 1
for code, c in sorted(seen.items()):
    print(code, dict(c.most_common(4)))
