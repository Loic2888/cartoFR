# T016 — Ranger le moteur dans le paquet et le brancher sur `registre.duckdb`

**Story** : US2 (P1) · **Phase** : US2 · **Parallèle** : [P]
**Couvre** : FR-006 · SC-001 · SC-004 · P3 · P5
**Estimé** : 3 h

## Contexte
Le moteur du prototype (`engine.py`, `brand_scan.py`) devient une fonction du paquet, qui prend des réglages et rend une carto.

## Périmètre
`cartofr.moteur.cartographier(reglages, registre) -> Carto`, sans appel réseau, avec les mêmes scores que le prototype.

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/cartofr/moteur/moteur.py` — depuis `engine.py`
- `worker/cartofr/moteur/marques.py` — depuis `brand_scan.py`
- `worker/cartofr/moteur/modele.py` — types de sortie (société, lien, preuve, confiance)
- `worker/scripts/non_regression.py` — LVMH, VINCI, CMAF contre `basile/`

### Fonctionnement attendu
- Aucun appel réseau
- Aucun nom de personne dans la sortie

### Technologies
- DuckDB, pandas

### Motifs d'architecture
Le registre est lu en lecture seule.

## Critères de succès
- [ ] **C1** : `worker/scripts/non_regression.py` donne au moins 90 % (LVMH), 81 % (VINCI) et 83 % (CMAF), avec au plus 16 et 193 « en plus »
- [ ] **C2** : Un test lance le moteur avec le réseau coupé (socket bloqué) et réussit
- [ ] **C3** : Le type de sortie de `modele.py` n'a aucun champ de personne physique

## Tests et validation

### Vérification manuelle
1. Lancer la non-régression et comparer à `rapport.md` du 2026-10-06

### Cas limites
- Aucun propre à cette tâche

## Dépendances

**À finir avant** : T007
**Bloque** : T017, T021, T027
**Fichiers partagés avec** : `worker/cartofr/moteur/moteur.py` (T027)

## Documentation
- **PRD** : FR-006, SC-001
- **ARCHI** : Le worker
