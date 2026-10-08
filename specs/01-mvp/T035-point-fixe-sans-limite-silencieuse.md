# T035 — Atteindre le point fixe au-delà de 8 niveaux, ou le signaler

**Story** : US2 (P1) · **Phase** : Moteur · **Parallèle** : [P]
**Couvre** : FR-006 · SC-001 · R8 · P5
**Estimé** : 1-2 h

## Contexte
Trouvé par T017 (`test_point_fixe_atteint_au_dela_de_huit_niveaux`, xfail). `MAX_TOURS = 8` arrête la boucle avant le point fixe : une chaîne de 9 mandats perd son dernier niveau sans avertissement.

## Périmètre
Boucler jusqu'au point fixe avec une garde haute (ex. 50 tours) ; si la garde est atteinte, mettre un avertissement dans la carto au lieu de perdre des niveaux en silence.

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
- [x] **C1** : `test_point_fixe_atteint_au_dela_de_huit_niveaux` passe sans `xfail`
- [x] **C2** : La carto porte un avertissement si la garde haute est atteinte (test)
- [x] **C3** : `rapport.md` donne, datés, les scores LVMH, VINCI et CMAF avant et après la correction, et explique tout écart
- [x] **C4** : Aucun score ne baisse sous ceux du 2026-10-06 (154/172, 813/1 007, 43/52)

## Tests et validation

### Vérification manuelle
1. Lancer la non-régression avant et après, noter le nombre de tours sur VINCI.

### Cas limites
- Aucun propre à cette tâche

## Dépendances

**À finir avant** : T016, T017
**Bloque** : —
**Fichiers partagés avec** : `worker/cartofr/moteur/moteur.py` (T033, T034, T035 : jamais en parallèle)

## Documentation
- **PRD** : FR-006, SC-001
- **ARCHI** : principe 5
