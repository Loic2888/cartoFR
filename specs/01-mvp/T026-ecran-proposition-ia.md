# T026 — Afficher la proposition et mesurer les corrections

**Story** : US3 (P2) · **Phase** : US3 · **Parallèle** : séquentiel
**Couvre** : FR-008 · SC-007
**Estimé** : 2 h

## Contexte
Le consultant accepte, corrige ou rejette chaque élément proposé.

## Périmètre
Bouton « Proposer », affichage des sources, acceptation élément par élément, comptage des corrections.

## Mise en œuvre

### Fichiers à créer ou modifier
- `web/app/(app)/groupes/[id]/reglages/proposition.tsx`
- `web/app/(app)/groupes/[id]/reglages/page.tsx`
- `rapport.md` — mesure SC-007

### Fonctionnement attendu
- Les corrections sont comptées à la validation

### Technologies
- Server Actions

### Motifs d'architecture
—

## Critères de succès
- [x] **C1** : Chaque élément proposé affiche sa source
- [x] **C2** : Le nombre de corrections est enregistré à la validation
- [ ] **C3** : `rapport.md` donne la moyenne des corrections sur LVMH, VINCI et CMAF (SC-007) — *ouvert le 2026-10-08 : demande l'API réelle ; protocole écrit dans `rapport.md`, mesure non faite*

## Tests et validation

### Vérification manuelle
1. Proposer puis valider sur un groupe neuf, chronométré — *ouvert : demande l'API réelle*

### Cas limites
- Aucun propre à cette tâche

## Dépendances

**À finir avant** : T025
**Bloque** : —
**Fichiers partagés avec** : `web/app/(app)/groupes/[id]/reglages/page.tsx` (T020)

## Documentation
- **PRD** : FR-008, SC-007
- **ARCHI** : IA (P2)
