# T018 — Créer les tables des groupes, réglages et cartos

**Story** : US2 (P1) · **Phase** : US2 · **Parallèle** : [P]
**Couvre** : FR-005 · FR-007 · R7 · P6
**Estimé** : 2 h

## Contexte
Tables propres à US2, cloisonnées comme le socle.

## Périmètre
Tables `groupes`, `reglages` (versionnés), `cartos`, `carto_societes`, `carto_liens`, avec RLS, et les réglages historiques en données de départ.

## Mise en œuvre

### Fichiers à créer ou modifier
- `supabase/migrations/0002_cartos.sql`
- `supabase/seed/reglages_depart.sql` — depuis `config/*.json`
- `worker/tests/test_rls.py` — cas ajoutés pour ces tables

### Fonctionnement attendu
- `reglages.version` + `valide_le` + `valide_par`
- `carto_*` : opposition, non-diffusion, confiance, preuve, ciblable et raison

### Technologies
- Supabase migrations SQL

### Motifs d'architecture
Pas d'ORM, aucune colonne de personne (principe 6).

## Critères de succès
- [ ] **C1** : `0002_cartos.sql` active RLS sur les cinq tables
- [ ] **C2** : `test_rls.py` vérifie A ne voit pas B sur `cartos` et `reglages`
- [ ] **C3** : Aucune colonne de nom de personne dans `0002_cartos.sql`
- [ ] **C4** : Le seed charge les réglages LVMH, VINCI et CMAF comme versions validées

## Tests et validation

### Vérification manuelle
1. Appliquer migration et seed en local

### Cas limites
- Aucun propre à cette tâche

## Dépendances

**À finir avant** : T006
**Bloque** : T019, T020, T021
**Fichiers partagés avec** : `worker/tests/test_rls.py` (T006)

## Documentation
- **PRD** : FR-005, FR-007
- **ARCHI** : Données §2
