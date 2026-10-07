# T034 — Exclure les comités même avec un nom accentué

**Story** : US2 (P1) · **Phase** : Moteur · **Parallèle** : [P]
**Couvre** : FR-006 · SC-001 · R8 · P5
**Estimé** : 1-2 h

## Contexte
Trouvé par T017 (xfail). Le filtre des comités compare le nom brut, sans retirer les accents : « COMITÉ … » n'est pas exclu et entre par son mandat.

## Périmètre
Normaliser le nom (accents retirés) avant le filtre des comités, amicales et associations.

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
- [ ] **C1** : Le cas accentué de `test_comite_d_entreprise_et_association_jamais_filiales` passe sans `xfail`
- [ ] **C2** : `rapport.md` donne, datés, les scores LVMH, VINCI et CMAF avant et après la correction, et explique tout écart
- [ ] **C3** : Aucun score ne baisse sous ceux du 2026-10-06 (154/172, 813/1 007, 43/52)

## Tests et validation

### Vérification manuelle
1. Lancer la non-régression avant et après.

### Cas limites
- Aucun propre à cette tâche

## Dépendances

**À finir avant** : T016, T017
**Bloque** : —
**Fichiers partagés avec** : `worker/cartofr/moteur/moteur.py` (T033, T034, T035 : jamais en parallèle)

## Documentation
- **PRD** : FR-006, SC-001
- **ARCHI** : principe 5
