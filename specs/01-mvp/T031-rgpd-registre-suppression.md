# T031 — Écrire le registre des traitements et permettre la suppression d'un compte

**Story** : Transverse · **Phase** : Polish · **Parallèle** : [P]
**Couvre** : R4
**Estimé** : 2 h

## Contexte
Règle produit 4 : effacement possible, aucune donnée personnelle dans les journaux, traitements déclarés.

## Périmètre
Registre des traitements, suppression de son compte par un membre, test qui vérifie que les journaux ne contiennent pas d'e-mail.

## Mise en œuvre

### Fichiers à créer ou modifier
- `docs/registre-traitements.md` — dirigeants (calcul interne), comptes consultants, durées de conservation
- `web/app/(app)/compte/page.tsx`, `web/app/(app)/compte/actions.ts`
- `worker/tests/test_journaux.py`

### Fonctionnement attendu
- Les cartos d'un membre supprimé restent à l'organisation, sans son e-mail

### Technologies
- Supabase Auth

### Motifs d'architecture
—

## Critères de succès
- [ ] **C1** : `docs/registre-traitements.md` couvre les dirigeants stockés et les comptes, avec une durée de conservation pour chacun
- [ ] **C2** : Un membre peut supprimer son compte depuis `web/app/(app)/compte/page.tsx`
- [ ] **C3** : `test_journaux.py` vérifie qu'aucun e-mail ni nom de personne n'apparaît dans les journaux du worker

## Tests et validation

### Vérification manuelle
1. Supprimer un compte de test et vérifier les tables

### Cas limites
- Aucun propre à cette tâche

## Dépendances

**À finir avant** : T009
**Bloque** : —
**Fichiers partagés avec** : aucun

## Documentation
- **PRD** : R4
- **ARCHI** : Contrôle constitutionnel R4
