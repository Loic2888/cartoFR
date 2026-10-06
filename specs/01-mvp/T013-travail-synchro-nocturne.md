# T013 — Planifier la synchro nocturne et publier l'état du registre

**Story** : US1 (P1) · **Phase** : US1 · **Parallèle** : séquentiel
**Couvre** : FR-001 · FR-003
**Estimé** : 2 h

## Contexte
Relie les deux synchros à la file de travaux, chaque nuit, et rend leur état visible par l'app.

## Périmètre
Un type de travail `synchro`, un cron qui l'insère chaque nuit, et la copie du dernier état dans `etat_registre`.

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/cartofr/jobs/synchro.py`
- `worker/cartofr/jobs/__init__.py` — enregistrement du type
- `infra/cron/synchro`
- `worker/tests/jobs/test_synchro.py`

### Fonctionnement attendu
- Reprise du lendemain si le quota coupe
- Échec visible dans `etat_registre` avec sa cause

### Technologies
- cron, psycopg

### Motifs d'architecture
Synchro et cartos ne se chevauchent jamais (ADR-004).

## Critères de succès
- [ ] **C1** : `test_synchro.py` vérifie qu'un passage réussi met à jour `etat_registre` (date, volumes)
- [ ] **C2** : `test_synchro.py` vérifie qu'un échec écrit sa cause dans `etat_registre`
- [ ] **C3** : `infra/cron/synchro` insère un travail `synchro` chaque nuit

## Tests et validation

### Vérification manuelle
1. Forcer un échec (identifiants faux) et lire `etat_registre`

### Cas limites
- Mise à jour en cours pendant une carto : la carto attend

## Dépendances

**À finir avant** : T008, T011, T012
**Bloque** : T014, T015, T030
**Fichiers partagés avec** : `worker/cartofr/jobs/__init__.py` (T008, T021, T025)

## Documentation
- **PRD** : FR-001, FR-003
- **ARCHI** : Le worker
