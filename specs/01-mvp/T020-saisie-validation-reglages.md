# T020 — Saisir, versionner et valider les réglages

**Story** : US2 (P1) · **Phase** : US2 · **Parallèle** : [P]
**Couvre** : FR-005 · P2
**Estimé** : 3 h

## Contexte
Les réglages font la qualité (Equans : 150 fausses sociétés). Ils sont validés par un humain avant usage (principe 2).

## Périmètre
Écran de réglages (marques sûres et ambiguës, exclusions, familles, organigramme), validation, historique des versions.

## Mise en œuvre

### Fichiers à créer ou modifier
- `web/app/(app)/groupes/[id]/reglages/page.tsx`
- `web/app/(app)/groupes/[id]/reglages/actions.ts`
- `web/lib/reglages/schema.ts` — Zod
- `worker/cartofr/reglages.py` — pydantic, même forme
- `worker/tests/fixtures/reglages/` — exemples partagés
- `worker/tests/test_reglages.py`, `web/lib/reglages/schema.test.ts`

### Fonctionnement attendu
- Familles exclues (garde-fou 6, ARCHI « Familles exclues ») : le nom est saisi une fois, le serveur stocke seulement son empreinte (`familles_exclues_empreintes`, HMAC avec `CARTOFR_CLE_EMPREINTE`, même normalisation que `worker/cartofr/empreinte.py`) ; l'écran affiche le nombre de familles exclues, jamais le nom
- Une validation part toujours de la dernière version (sinon refus)
- Une colonne sur mobile

### Technologies
- Zod, pydantic, Server Actions

### Motifs d'architecture
Le même schéma est vérifié des deux côtés.

## Critères de succès
- [x] **C1** : Les deux schémas acceptent et refusent les mêmes fixtures de `worker/tests/fixtures/reglages/`
- [x] **C2** : Une validation qui ne part pas de la dernière version est refusée (test de `actions.ts`)
- [x] **C3** : Chaque champ de la page a un `<label>`
- [x] **C4** : Chaque version enregistre son auteur et sa date de validation

## Tests et validation

### Vérification manuelle
1. Saisir les réglages d'un groupe neuf à 320 px, au clavier seul

### Cas limites
- Deux consultants modifient le même groupe

## Dépendances

**À finir avant** : T009, T018
**Bloque** : T021, T026
**Fichiers partagés avec** : aucun

## Documentation
- **PRD** : FR-005
- **ARCHI** : Couche API
