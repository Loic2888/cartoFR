# T009 — Mettre en place la connexion par lien magique et le gabarit

**Story** : Socle · **Phase** : Foundational · **Parallèle** : [P]
**Couvre** : R1 · R2 · R3 · R4
**Estimé** : 2-3 h

## Contexte
Toutes les pages demandent une session. Inscription fermée : un compte n'existe que sur invitation.

## Périmètre
Page de connexion, retour du lien, protection des pages, gabarit mobile, invitation d'un membre par un admin, messages d'erreur traduits.

## Mise en œuvre

### Fichiers à créer ou modifier
- `web/app/connexion/page.tsx`
- `web/app/auth/callback/route.ts`
- `web/lib/supabase/server.ts`, `web/lib/supabase/client.ts`
- `web/middleware.ts`
- `web/app/(app)/layout.tsx` — en-tête et navigation, mobile d'abord
- `web/app/(app)/admin/membres/page.tsx` et `actions.ts` — invitation
- `web/lib/erreurs.ts` — erreurs Supabase traduites en français
- `infra/docker-compose.yml` — `GOTRUE_DISABLE_SIGNUP=true`

### Fonctionnement attendu
- Un label par champ
- Seul l'e-mail est demandé (minimisation RGPD)

### Technologies
- Supabase Auth (GoTrue) via `@supabase/ssr`, Brevo SMTP, Zod

### Motifs d'architecture
Server Actions pour les écritures.

## Critères de succès
- [ ] **C1** : `web/middleware.ts` redirige vers `/connexion` toute page sans session
- [ ] **C2** : Les inscriptions libres sont désactivées dans la configuration GoTrue de `infra/`
- [ ] **C3** : `web/lib/erreurs.ts` traduit les codes d'erreur d'auth, testé par Vitest
- [ ] **C4** : Le champ e-mail de `web/app/connexion/page.tsx` a un `<label>` associé

## Tests et validation

### Vérification manuelle
1. Se connecter par lien magique en local, puis inviter un second membre

### Cas limites
- Lien expiré : message en français et nouvel envoi proposé

## Dépendances

**À finir avant** : T002, T006
**Bloque** : T014, T019, T020, T031
**Fichiers partagés avec** : `infra/docker-compose.yml` (T004, T019)

## Documentation
- **PRD** : —
- **ARCHI** : Connexion et droits
