# T014 — Afficher l'état du registre aux admins

**Story** : US1 (P1) · **Phase** : US1 · **Parallèle** : séquentiel
**Couvre** : FR-003
**Estimé** : 1-2 h

## Contexte
Le responsable de la base doit voir tout de suite une mise à jour ratée (persona secondaire).

## Périmètre
Une page admin avec la date des données, le dernier passage, son statut, ses volumes et sa cause en cas d'échec.

## Mise en œuvre

### Fichiers à créer ou modifier
- `web/app/(app)/admin/registre/page.tsx`
- `web/components/etat-registre.tsx`

### Fonctionnement attendu
- Statut écrit en toutes lettres et avec une icône, pas seulement en couleur
- Dates au format jj/mm/aaaa

### Technologies
- Server Components, Supabase

### Motifs d'architecture
Lecture seule.

## Critères de succès
- [ ] **C1** : `web/app/(app)/admin/registre/page.tsx` n'est accessible qu'au rôle admin
- [ ] **C2** : Un échec affiche sa date et sa cause (test Vitest de `etat-registre.tsx`)
- [ ] **C3** : Le statut est porté par un texte, pas seulement par une couleur

## Tests et validation

### Vérification manuelle
1. Afficher la page à 320 px et la parcourir au clavier

### Cas limites
- Aucun propre à cette tâche

## Dépendances

**À finir avant** : T009, T013
**Bloque** : —
**Fichiers partagés avec** : aucun

## Documentation
- **PRD** : FR-003
- **ARCHI** : Surveillance
