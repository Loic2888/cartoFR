# T008 — Écrire la file de travaux du worker

**Story** : Socle · **Phase** : Foundational · **Parallèle** : séquentiel
**Couvre** : FR-005 · ADR-004
**Estimé** : 2 h

## Contexte
Les synchros (US1) et les cartos (US2) passent par la même file, un travail à la fois.

## Périmètre
Une boucle qui prend le plus ancien travail en attente, l'exécute selon son type, enregistre le statut, la durée et l'erreur.

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/cartofr/travaux.py` — boucle `for update skip locked`, interrogée toutes les 5 s
- `worker/cartofr/jobs/__init__.py` — registre des types de travaux
- `worker/cartofr/__main__.py` — `python -m cartofr` lance la boucle
- `worker/tests/test_travaux.py`

### Fonctionnement attendu
- Un type inconnu passe en échec avec un message clair
- Une exception n'arrête pas la boucle
- Journaux sans aucune donnée personnelle

### Technologies
- psycopg

### Motifs d'architecture
Un seul processus, pas de Redis (ADR-004).

## Critères de succès
- [x] **C1** : `worker/tests/test_travaux.py` vérifie qu'un travail passe de `en_attente` à `termine` ou `echec`
- [x] **C2** : Deux travaux ne tournent jamais en même temps (test avec deux boucles)
- [x] **C3** : La durée de chaque travail est enregistrée dans `travaux`

## Tests et validation

### Vérification manuelle
1. Insérer un travail factice et regarder la boucle le traiter

### Cas limites
- Aucun propre à cette tâche

## Dépendances

**À finir avant** : T006
**Bloque** : T013, T021
**Fichiers partagés avec** : `worker/cartofr/jobs/__init__.py` (T013, T021, T025)

## Documentation
- **PRD** : FR-005
- **ARCHI** : Le worker, ADR-004
