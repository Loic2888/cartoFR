# T033 — Faire entrer une marque sûre même avec un mandat « Autre »

**Story** : US2 (P1) · **Phase** : Moteur · **Parallèle** : [P]
**Couvre** : FR-006 · SC-001 · R8 · P5
**Estimé** : 1-2 h

## Contexte
Trouvé par T017 (`test_marque_sure_et_mandat_autre`, xfail). La branche du mandat faible (« Autre », code 99) sort avant la règle de la marque sûre : une société qui entrerait par sa marque seule est refusée dès qu'elle porte aussi un mandat « Autre ». Les règles écrites sont des alternatives.

## Périmètre
Corriger l'ordre des règles pour qu'un mandat faible n'empêche pas une autre règle de s'appliquer. Vérifier aussi le cas « adresse + un dirigeant commun + Autre ».

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/cartofr/moteur/moteur.py` — la correction
- `worker/tests/moteur/test_regles.py` — retirer le `xfail` du test qui la décrit
- `rapport.md` — scores avant et après

### Fonctionnement attendu
- La correction ne touche que cette règle
- Non-régression lancée avant et après : `CARTOFR_DATA=data CARTOFR_REFERENCES=basile .venv/bin/python worker/scripts/non_regression.py`

### Technologies
- DuckDB, pytest

### Motifs d'architecture
Pas de régression silencieuse (principe 5) : un score qui baisse ou des « en plus » qui montent nettement ne se rendent pas sans le dire.

## Critères de succès
- [ ] **C1** : `test_marque_sure_et_mandat_autre` passe sans `xfail`
- [ ] **C2** : `rapport.md` donne, datés, les scores LVMH, VINCI et CMAF avant et après la correction, et explique tout écart
- [ ] **C3** : Aucun score ne baisse sous ceux du 2026-10-06 (154/172, 813/1 007, 43/52)

## Tests et validation

### Vérification manuelle
1. Lancer la non-régression avant et après, comparer les « en plus ».

### Cas limites
- Aucun propre à cette tâche

## Dépendances

**À finir avant** : T016, T017
**Bloque** : —
**Fichiers partagés avec** : `worker/cartofr/moteur/moteur.py` (T033, T034, T035 : jamais en parallèle)

## Documentation
- **PRD** : FR-006, SC-001
- **ARCHI** : principe 5
