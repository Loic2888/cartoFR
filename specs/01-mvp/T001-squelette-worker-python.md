# T001 — Poser le paquet Python du worker et son outillage

**Story** : Socle · **Phase** : Setup · **Parallèle** : [P]
**Couvre** : —
**Estimé** : 1-2 h

## Contexte
Tout le code métier vivra dans le paquet `cartofr` (principe 7). Cette tâche pose le paquet et les commandes de validation qui manquent aujourd'hui (lint, typecheck, tests).

## Périmètre
Paquet `worker/cartofr` installable, ruff, pyright et pytest configurés, un test minimal vert.

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/pyproject.toml` — dépendances (duckdb, pandas, pyarrow, psycopg, pydantic, httpx), ruff, pyright, pytest
- `worker/cartofr/__init__.py` — paquet vide
- `worker/tests/conftest.py` — fixtures communes
- `worker/tests/test_smoke.py` — import du paquet
- `AGENTS.md` — ligne des commandes lint / typecheck / tests

### Fonctionnement attendu
- Installation par `pip install -e worker[dev]` dans `.venv`
- Python 3.12 imposé

### Technologies
- ruff (lint + format), pyright (typecheck), pytest

### Motifs d'architecture
Scripts courts, docstring en tête de fichier (convention CLAUDE.md).

## Critères de succès
- [x] **C1** : `.venv/bin/ruff check worker` sort en code 0
- [x] **C2** : `.venv/bin/pyright -p worker` sort en code 0 (sans `-p`, pyright ne trouve aucun fichier et sort à 0 sans rien vérifier)
- [x] **C3** : `.venv/bin/pytest worker` passe avec au moins 1 test
- [x] **C4** : `AGENTS.md` liste ces trois commandes

## Tests et validation

### Vérification manuelle
1. Créer un venv neuf, installer `worker[dev]`, lancer les trois commandes

### Cas limites
- Aucun propre à cette tâche

## Dépendances

**À finir avant** : —
**Bloque** : T003, T004, T007, T010
**Fichiers partagés avec** : aucun

## Documentation
- **PRD** : —
- **ARCHI** : Arborescence, Phase 1 §1
