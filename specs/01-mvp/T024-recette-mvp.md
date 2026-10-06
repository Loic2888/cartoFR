# T024 — Faire la recette du MVP

**Story** : US2 (P1) · **Phase** : US2 · **Parallèle** : séquentiel
**Couvre** : SC-001 · SC-002 · SC-004 · R2 · R3
**Estimé** : 2-3 h

## Contexte
Prouver que le parcours P1 tient ses chiffres de bout en bout, dans l'app.

## Périmètre
Non-régression depuis l'app, trois sessions chronométrées, contrôle à 320 px et au clavier, résultat dans `rapport.md`.

## Mise en œuvre

### Fichiers à créer ou modifier
- `rapport.md` — résultats datés
- `worker/scripts/non_regression.py` — option pour lire une carto depuis Postgres

### Fonctionnement attendu
- Trois groupes jamais réglés, de moins de 200 sociétés

### Technologies
- —

### Motifs d'architecture
—

## Critères de succès
- [ ] **C1** : `rapport.md` donne, datés, les scores LVMH, VINCI et CMAF obtenus depuis l'app (SC-001)
- [ ] **C2** : `rapport.md` donne trois durées de saisie à export, chacune sous 30 minutes (SC-002)
- [ ] **C3** : `rapport.md` donne la durée du calcul de VINCI, sous 5 minutes (SC-004)
- [ ] **C4** : `rapport.md` consigne le contrôle à 320 px et au clavier des écrans de US2

## Tests et validation

### Vérification manuelle
1. Suivre le parcours complet comme un consultant

### Cas limites
- Aucun propre à cette tâche

## Dépendances

**À finir avant** : T015, T022, T023
**Bloque** : T032
**Fichiers partagés avec** : `rapport.md`

## Documentation
- **PRD** : SC-001, SC-002, SC-004
- **ARCHI** : —
