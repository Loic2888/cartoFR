# T004 — Écrire l'infrastructure Docker Compose

**Story** : Socle · **Phase** : Setup · **Parallèle** : [P]
**Couvre** : Garde-fou 5 · R4 · R5
**Estimé** : 2-3 h

## Contexte
Tout tourne sur un seul serveur (ADR-003). Cette tâche décrit les services et permet de tout lancer en local.

## Périmètre
Docker Compose avec `caddy`, `web`, `worker` et Supabase réduit (db, auth, rest, kong, studio), lancé en local.

## Mise en œuvre

### Fichiers à créer ou modifier
- `infra/docker-compose.yml` — services, réseau interne, volumes, `env_file`
- `infra/Caddyfile` — HTTPS et proxy vers `web`
- `infra/web.Dockerfile`, `infra/worker.Dockerfile`
- `infra/supabase/kong.yml` — routes auth et rest seulement
- `.env.example` — noms des variables (Supabase, Brevo SMTP, INPI, INSEE), sans valeur

### Fonctionnement attendu
- Image web : Node 22 (`web/.nvmrc`), `NEXT_TELEMETRY_DISABLED=1`, démarrage par `node server.js` du dossier `standalone` (`next start` ne marche pas avec `output: "standalone"`), en copiant `.next/static`
- SMTP de GoTrue réglé sur Brevo
- Journaux Docker avec rotation `max-size`
- Le worker n'expose aucun port publié

### Technologies
- Docker Compose, Caddy, Supabase auto-hébergé (images officielles)

### Motifs d'architecture
Services réduits pour tenir dans 16 Go (ARCHI, Infrastructure).

## Critères de succès
- [ ] **C1** : `docker compose -f infra/docker-compose.yml up` démarre les services sans erreur
- [ ] **C2** : `infra/docker-compose.yml` ne contient aucune valeur secrète en dur, seulement `env_file`
- [ ] **C3** : `.env.example` liste chaque variable utilisée, sans valeur
- [ ] **C4** : Chaque service déclare `logging.options.max-size`
- [ ] **C5** : Aucun service `realtime`, `storage`, `analytics` ni `functions`

## Tests et validation

### Vérification manuelle
1. Lancer le Compose en local, ouvrir Supabase Studio, envoyer un lien magique de test

### Cas limites
- Aucun propre à cette tâche

## Dépendances

**À finir avant** : T001, T002
**Bloque** : T005, T006, T019
**Fichiers partagés avec** : `infra/docker-compose.yml` (T019)

## Documentation
- **PRD** : —
- **ARCHI** : Infrastructure, ADR-003
