"""Étape 10 : compare notre cartographie à celle de Basile.

Usage : python compare.py lvmh
Affiche combien de sociétés Basile on retrouve, combien on en ajoute en plus, et des exemples des deux.
Écrit out/<groupe>_comparaison.csv (une ligne par société vue d'un côté ou de l'autre).
"""
import sys
import pandas as pd

g = sys.argv[1]
ours = pd.read_csv(f"out/{g}_entites.csv", dtype=str)
ref = pd.read_csv(f"basile/{g}_entites.csv", dtype=str)
o, b = set(ours.siren), set(ref.SIREN)
both, only_b, only_o = o & b, b - o, o - b
print(f"Basile : {len(b)} | nous : {len(o)} | en commun : {len(both)} ({len(both) / len(b):.0%} de Basile) | "
      f"en plus chez nous : {len(only_o)} | manquées : {len(only_b)}")

# Même maison mère directe sur les sociétés en commun ?
m = ours.merge(ref, left_on="siren", right_on="SIREN")
same_parent = (m.maison_mere_siren.fillna("") == m["SIREN de la maison mère"].fillna("")).mean()
print(f"même maison mère directe sur les sociétés en commun : {same_parent:.0%}")
if "Targetable" in ref:
    same_t = (m.targetable == m.Targetable).mean()
    print(f"même réponse Oui/Non sur 'ciblable' : {same_t:.0%}")

cols_b = [c for c in ["Nom", "SIREN", "Type de lien", "Confiance"] if c in ref]
print("\nManquées (exemples) :")
print(ref[ref.SIREN.isin(only_b)][cols_b].head(20).to_string(index=False))
print("\nEn plus chez nous (exemples) :")
print(ours[ours.siren.isin(only_o)][["nom", "siren", "pourquoi_dans_le_groupe", "indices"]].head(20).to_string(index=False))

rows = [{"siren": s, "statut": "les deux" if s in both else ("Basile seulement" if s in b else "nous seulement")} for s in o | b]
pd.DataFrame(rows).to_csv(f"out/{g}_comparaison.csv", index=False)
