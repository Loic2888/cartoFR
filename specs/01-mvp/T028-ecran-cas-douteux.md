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
- [ ] **C1** : Chaque cas affiche sa règle et ses indices
- [ ] **C2** : Une décision enregistre son auteur et sa date
- [ ] **C3** : Les boutons sont utilisables au clavier, avec un libellé explicite

## Tests et validation

### Vérification manuelle
1. Traiter 10 cas VINCI à 320 px

### Cas limites
- Aucun propre à cette tâche

## Dépendances

**À finir avant** : T027
**Bloque** : —
**Fichiers partagés avec** : aucun

## Documentation
- **PRD** : FR-009
- **ARCHI** : —
