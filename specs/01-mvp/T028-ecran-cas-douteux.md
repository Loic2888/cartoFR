# T028 — Lister les cas douteux et décider

**Story** : US4 (P2) · **Phase** : US4 · **Parallèle** : séquentiel
**Couvre** : FR-009
**Estimé** : 2 h

## Contexte
Le consultant tranche vite ce qu'il livre.

## Périmètre
Page de liste des cas, avec indices pour et contre, et boutons « Retenir » ou « Écarter ».

## Mise en œuvre

### Fichiers à créer ou modifier
- `web/app/(app)/groupes/[id]/cartos/[cartoId]/cas/page.tsx`
- `web/app/(app)/groupes/[id]/cartos/[cartoId]/cas/actions.ts`

### Fonctionnement attendu
- Liste de cartes sur mobile
- Décision enregistrée avec auteur et date

### Technologies
- Server Actions

### Motifs d'architecture
—

## Critères de succès
- [x] **C1** : Chaque cas affiche sa règle et ses indices
- [x] **C2** : Une décision enregistre son auteur et sa date
- [x] **C3** : Les boutons sont utilisables au clavier, avec un libellé explicite

## Tests et validation

### Vérification manuelle
1. Traiter 10 cas VINCI à 320 px

### Cas limites
- Aucun propre à cette tâche dans la spec. Traités (2026-10-08) : cas d'une autre organisation ou carto d'un autre groupe introuvable (rien n'est écrit) ; carto pas terminée ; carto sans cas ; compte de l'auteur effacé (« par un compte supprimé »).

### État (2026-10-08)
- C1 à C3 tenus dans le code et testés (`web/lib/cartos/cas.test.ts`, `cas/decision-cas.test.tsx`, `worker/tests/test_rls.py`).
- La vérification manuelle (10 cas VINCI à 320 px) n'a pas été faite : elle demande l'app lancée avec Supabase et une carto VINCI calculée. À faire à la recette.
- Auteur (décidé le 2026-10-08 par Loïc, PRD « avec son nom ») : « par vous », sinon l'e-mail du membre, affiché aux seuls membres de l'organisation de la carto. L'e-mail est lu côté serveur, comme l'écran des membres (T009) : membres sous RLS, puis `auth.users` en service_role pour ces seuls membres (`web/lib/cartos/auteurs.ts`, testé : un membre de B ne lit jamais l'e-mail d'un membre de A). « Un ancien membre » si l'auteur a quitté l'organisation, « un compte supprimé » si son compte est effacé. Aucun e-mail dans les journaux.

## Dépendances

**À finir avant** : T027
**Bloque** : —
**Fichiers partagés avec** : aucun

## Documentation
- **PRD** : FR-009
- **ARCHI** : —
