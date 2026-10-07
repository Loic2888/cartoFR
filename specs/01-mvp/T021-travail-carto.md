# T021 — Lancer une carto et enregistrer le résultat

**Story** : US2 (P1) · **Phase** : US2 · **Parallèle** : séquentiel
**Couvre** : FR-005 · FR-006 · SC-004 · P2 · P3
**Estimé** : 2-3 h

## Contexte
Relie l'interface au moteur par la file de travaux.

## Périmètre
Un bouton « Lancer la carto », un type de travail `carto`, l'écriture du résultat dans `cartos` et `carto_*`.

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/cartofr/jobs/carto.py`
- `worker/cartofr/jobs/__init__.py` — enregistrement du type
- `web/app/(app)/groupes/[id]/cartos/actions.ts`
- `worker/tests/jobs/test_carto.py`

### Fonctionnement attendu
- Familles exclues : les réglages lus en base portent `familles_exclues_empreintes` ; le moteur compare l'empreinte (`cartofr.empreinte`, clé `CARTOFR_CLE_EMPREINTE`) du nom de chaque dirigeant à cette liste, au lieu de noms en clair. Une carto LVMH lancée depuis l'app doit garder les scores de la non-régression
- Refus si la version de réglages n'est pas validée
- `organisation_id` copié du travail
- Date des données et durée enregistrées
- Tête sans lien : carto réduite à la tête, avec avertissement

### Technologies
- psycopg

### Motifs d'architecture
Le worker écrit en rôle service mais respecte l'organisation du travail.

## Critères de succès
- [x] **C1** : `test_carto.py` vérifie le refus d'une version non validée
- [x] **C2** : `test_carto.py` vérifie que chaque ligne `carto_*` porte l'`organisation_id` du travail
- [x] **C3** : `cartos` enregistre la date des données et la durée du calcul
- [x] **C4** : `test_carto.py` vérifie l'avertissement pour une tête sans aucun lien

## Tests et validation

### Vérification manuelle
1. Lancer la carto LVMH depuis l'interface et mesurer la durée

### Cas limites
- Tête sans lien
- Synchro en cours

## Dépendances

**À finir avant** : T008, T016, T018, T019, T020
**Bloque** : T022, T023, T025, T027, T029
**Fichiers partagés avec** : `worker/cartofr/jobs/__init__.py` (T008, T013, T025)

## Documentation
- **PRD** : FR-005, FR-006, SC-004
- **ARCHI** : Le worker
