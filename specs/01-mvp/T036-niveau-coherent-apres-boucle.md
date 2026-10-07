# T036 — Garder un niveau cohérent avec la maison mère après une boucle coupée

**Story** : US2 (P1) · **Phase** : Moteur · **Parallèle** : [P]
**Couvre** : FR-006 · SC-001 · R8 · P5
**Estimé** : 1 h

## Contexte
Trouvé à l'essai de T022 (2026-10-07) : sur VINCI, des sociétés affichent « Niveau 3 » alors que leur maison mère directe est la tête. Cause, dans `build()` de `worker/cartofr/moteur/moteur.py` : quand `lvl()` détecte une boucle de mandats croisés (A → B → A), il rattache A à la tête avec `level[A] = 1` ; mais l'appel récursif qui avait commencé par A reprend la main et écrase `level[A] = lvl(B) + 1` (= 3). La maison mère dit « tête », le niveau dit 3.

## Périmètre
Calculer les niveaux une fois les rattachements fixés (coupure des boucles d'abord, puis profondeur depuis la tête), pour que `niveau` = `niveau de la maison mère + 1` pour toute société. Ajouter le test d'une boucle A → B → A, et un test d'invariant sur toute carto.

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
- [ ] **C1** : Un test de `test_regles.py` (boucle A → B → A) vérifie que chaque société a `niveau = niveau(maison mère) + 1` et la tête 0
- [ ] **C2** : Un test vérifie cet invariant sur la carto complète des tests du moteur
- [ ] **C3** : `rapport.md` donne, datés, les scores LVMH, VINCI et CMAF avant et après la correction, et le nombre de niveaux corrigés
- [ ] **C4** : Aucun score ne baisse sous ceux du 2026-10-06 (154/172, 813/1 007, 43/52)

## Tests et validation

### Vérification manuelle
1. Lancer la non-régression avant et après ; compter sur VINCI les sociétés dont le niveau change.

### Cas limites
- Aucun propre à cette tâche

## Dépendances

**À finir avant** : T016, T017
**Bloque** : —
**Fichiers partagés avec** : `worker/cartofr/moteur/moteur.py` (T033 à T036 : jamais en parallèle)

## Documentation
- **PRD** : FR-006, SC-001
- **ARCHI** : principe 5
