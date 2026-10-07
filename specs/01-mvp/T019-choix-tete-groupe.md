# T019 — Chercher et choisir la tête d'un groupe

**Story** : US2 (P1) · **Phase** : US2 · **Parallèle** : [P]
**Couvre** : FR-004
**Estimé** : 2-3 h

## Contexte
Premier écran du parcours P1 : saisir un nom ou un SIREN et choisir la société tête.

## Périmètre
Route interne `/recherche` du worker, page « Nouveau groupe », création du groupe.

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/cartofr/api_recherche.py` — HTTP interne, lecture seule
- `infra/docker-compose.yml` — démarrage de la route, sans port publié
- `web/app/(app)/groupes/nouveau/page.tsx`
- `web/app/(app)/groupes/actions.ts`
- `worker/tests/test_api_recherche.py`

### Fonctionnement attendu
- 20 résultats au plus : SIREN, nom, ville, statut
- Tête radiée signalée avant de continuer

### Technologies
- HTTP stdlib ou Starlette, DuckDB

### Motifs d'architecture
Seul pont entre l'interface et le registre (ARCHI, Recherche de la tête).

## Critères de succès
- [x] **C1** : `test_api_recherche.py` vérifie la recherche par nom et par SIREN
- [x] **C2** : `test_api_recherche.py` vérifie que la réponse ne contient aucun champ de personne
- [x] **C3** : `infra/docker-compose.yml` ne publie aucun port pour le worker
- [x] **C4** : La page affiche « Aucune société trouvée » et propose la saisie d'un SIREN quand rien ne correspond

## Tests et validation

### Vérification manuelle
1. Chercher « LVMH », puis un SIREN, puis un nom absurde, à 320 px

### Cas limites
- Groupe introuvable
- Tête radiée ou fermée

## Dépendances

**À finir avant** : T007, T009, T018
**Bloque** : T021, T029
**Fichiers partagés avec** : `infra/docker-compose.yml` (T004)

## Documentation
- **PRD** : FR-004
- **ARCHI** : Recherche de la tête
