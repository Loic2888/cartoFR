# T002 — Poser l'application Next.js et son outillage

**Story** : Socle · **Phase** : Setup · **Parallèle** : [P]
**Couvre** : —
**Estimé** : 1-2 h

## Contexte
L'interface des consultants. Cette tâche pose le projet vide, en français, mobile-first.

## Périmètre
Projet Next.js 16 dans `web/`, TypeScript strict, Tailwind, shadcn/ui initialisé, ESLint et Vitest.

## Mise en œuvre

### Fichiers à créer ou modifier
- `web/package.json`, `web/tsconfig.json`, `web/eslint.config.mjs`, `web/vitest.config.ts`
- `web/app/layout.tsx` — `<html lang="fr">`, police, styles de base
- `web/app/page.tsx` — page d'accueil provisoire
- `web/components/ui/` — composants shadcn/ui de base (button, input, label, card)
- `web/next.config.ts` — `output: "standalone"`

### Fonctionnement attendu
- Styles écrits mobile d'abord (`min-width` seulement)
- Focus visible conservé sur tous les composants

### Technologies
- Next.js 16 App Router, TypeScript strict, Tailwind, shadcn/ui, ESLint, Vitest

### Motifs d'architecture
Server Components par défaut (ARCHI, Interface).

## Critères de succès
- [x] **C1** : `npm --prefix web run lint` sort en code 0
- [x] **C2** : `npm --prefix web run typecheck` (`tsc --noEmit`) sort en code 0
- [x] **C3** : `npm --prefix web test` passe avec au moins 1 test
- [x] **C4** : `npm --prefix web run build` produit `web/.next/standalone`
- [x] **C5** : `web/app/layout.tsx` déclare `lang="fr"`

## Tests et validation

### Vérification manuelle
1. `npm --prefix web run dev`, ouvrir la page à 320 px de large : pas de défilement horizontal

### Cas limites
- Aucun propre à cette tâche

## Dépendances

**À finir avant** : —
**Bloque** : T003, T004, T009
**Fichiers partagés avec** : aucun

## Documentation
- **PRD** : —
- **ARCHI** : Interface
