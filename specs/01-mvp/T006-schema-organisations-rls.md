# T006 — Créer le schéma de base et le cloisonnement RLS

**Story** : Socle · **Phase** : Foundational · **Parallèle** : [P]
**Couvre** : R7 · FR-003
**Estimé** : 2-3 h

## Contexte
Toutes les stories ont besoin des organisations, des membres et de la file de travaux. Le cloisonnement se pose dès la V0 (règle produit 7).

## Périmètre
Tables `organisations`, `membres`, `travaux`, `etat_registre`, avec leurs politiques RLS et le test « A ne voit pas B ».

## Mise en œuvre

### Fichiers à créer ou modifier
- `supabase/migrations/0001_socle.sql` — tables, index, RLS
- `worker/cartofr/db.py` — connexion psycopg (rôle service)
- `worker/tests/test_rls.py` — deux organisations, deux membres

### Fonctionnement attendu
- Politique RLS : `organisation_id in (select organisation_id from membres where user_id = auth.uid())`
- `travaux` : type, statut, `organisation_id`, paramètres JSON, dates, erreur

### Technologies
- Supabase migrations SQL, psycopg

### Motifs d'architecture
Pas d'ORM (ADR-005).

## Critères de succès
- [x] **C1** : `supabase/migrations/0001_socle.sql` active RLS sur chaque table qui porte `organisation_id`
- [x] **C2** : `worker/tests/test_rls.py` vérifie qu'un membre de A ne lit aucune ligne de B
- [x] **C3** : Aucune colonne de personne physique dans le schéma (principe 6)

## Tests et validation

### Vérification manuelle
1. Appliquer la migration sur le Supabase local, lancer `pytest worker/tests/test_rls.py`

### Cas limites
- Aucun propre à cette tâche

## Dépendances

**À finir avant** : T004
**Bloque** : T008, T009, T018
**Fichiers partagés avec** : `worker/tests/test_rls.py` (T018)

## Documentation
- **PRD** : FR-003, R7
- **ARCHI** : Données §2, ADR-005
