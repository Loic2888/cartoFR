# T003 — Brancher la CI sur chaque PR

**Story** : Socle · **Phase** : Setup · **Parallèle** : [P]
**Couvre** : Garde-fou 4
**Estimé** : 1 h

## Contexte
Le merge exige une CI verte (garde-fou 4). Sans CI, cette règle n'est vérifiée par personne.

## Périmètre
Un workflow GitHub Actions qui lance lint, typecheck et tests pour `worker/` et `web/` sur chaque PR.

## Mise en œuvre

### Fichiers à créer ou modifier
- `.github/workflows/ci.yml` — deux jobs, `worker` et `web`

### Fonctionnement attendu
- Node 22 (`web/.nvmrc`), `NEXT_TELEMETRY_DISABLED=1`, `npm ci` dans `web/`. Le build a besoin du réseau (polices Geist)
- Créer le venv à la racine (`.venv`), comme en local : `worker/pyproject.toml` y pointe pyright (`venvPath`). Lancer `pyright -p worker`, jamais `pyright worker` (faux vert)
- Aucun secret, aucune donnée du registre : tests sur fixtures seulement

### Technologies
- GitHub Actions

### Motifs d'architecture
La CI ne voit que du code (ARCHI, Contrôle constitutionnel R5).

## Critères de succès
- [x] **C1** : `.github/workflows/ci.yml` lance ruff, pyright, pytest, eslint, tsc, vitest
- [x] **C2** : Le workflow se déclenche sur `pull_request` vers `main`
- [x] **C3** : Aucune étape ne lit `data/`, `basile/`, `out/` ni un secret

## Tests et validation

### Vérification manuelle
1. Ouvrir une PR de test : les deux jobs passent au vert

### Cas limites
- Aucun propre à cette tâche

## Dépendances

**À finir avant** : T001, T002
**Bloque** : —
**Fichiers partagés avec** : aucun

## Documentation
- **PRD** : —
- **ARCHI** : Infrastructure, CI
