# T022 — Afficher l'arbre du groupe avec ses preuves

**Story** : US2 (P1) · **Phase** : US2 · **Parallèle** : [P]
**Couvre** : FR-007 · R2 · R3
**Estimé** : 3 h

## Contexte
Ce que le consultant regarde et défend devant le client.

## Périmètre
Page de carto : arbre dépliable (liste indentée sous 640 px), preuve de chaque lien, confiance, ciblable, opposition, non-diffusion, date des données.

## Mise en œuvre

### Fichiers à créer ou modifier
- `web/app/(app)/groupes/[id]/cartos/[cartoId]/page.tsx`
- `web/components/arbre/arbre.tsx`, `noeud.tsx`, `preuve.tsx`
- `web/components/arbre/arbre.test.tsx`

### Fonctionnement attendu
- Motif WAI-ARIA `treeview` : flèches, Entrée, `aria-expanded`
- Confiance écrite (« A — lu au registre »), pas seulement en couleur
- Rafraîchissement toutes les 3 s tant que la carto tourne

### Technologies
- shadcn/ui, Tailwind

### Motifs d'architecture
Affichage seulement : aucune règle du moteur dans `web/` (principe 7).

## Critères de succès
- [ ] **C1** : `arbre.test.tsx` vérifie la navigation au clavier (flèches, Entrée)
- [ ] **C2** : `arbre.tsx` porte `role="tree"`, et chaque nœud `role="treeitem"` et `aria-expanded`
- [ ] **C3** : Chaque nœud affiche confiance, ciblable et opposition en texte
- [ ] **C4** : La page affiche la date des données de la carto

## Tests et validation

### Vérification manuelle
1. Ouvrir la carto VINCI (environ 1 000 sociétés) à 320 px et au clavier

### Cas limites
- Carto réduite à la tête

## Dépendances

**À finir avant** : T021
**Bloque** : T024, T028
**Fichiers partagés avec** : aucun

## Documentation
- **PRD** : FR-007
- **ARCHI** : Interface
