# infra — lancer cartoFR en Docker Compose

Un seul serveur, quatre blocs (ARCHI, Infrastructure ; ADR-003) :
`caddy` (HTTPS), `web` (Next.js), `worker` (Python) et Supabase réduit
(`db`, `auth`, `rest`, `kong`, `meta`, `studio`). En local, `mailpit` reçoit
les e-mails (profil `dev`).

## Prérequis

- Docker avec Compose 2.24 ou plus (`docker compose version`).
- `python3` (pour générer les secrets).
- Environ 3 Go de mémoire libre.

## Démarrer en local

Depuis la racine du dépôt :

```bash
bash infra/generer-secrets.sh        # une seule fois : crée infra/.env (hors git)
docker compose -f infra/docker-compose.yml --profile dev up -d --build
docker compose -f infra/docker-compose.yml --profile dev ps
```

Le premier build télécharge les polices de l'interface : il faut le réseau.

| Quoi | Adresse |
|---|---|
| L'app | https://localhost (certificat local : accepter l'alerte, ou `curl -k`) |
| Supabase Studio | http://127.0.0.1:3001 |
| Boîte mail locale (mailpit) | http://127.0.0.1:8025 |

Studio et mailpit n'écoutent que sur `127.0.0.1`. Sur le serveur, on passe par
un tunnel SSH : `ssh -L 3001:127.0.0.1:3001 <serveur>`.

## Envoyer un lien magique de test

L'inscription est fermée : un lien magique vers une adresse inconnue est
refusé. On crée d'abord l'utilisateur avec la clé `service_role`. Les clés sont
lues dans `infra/.env` sans être affichées. Adresse fictive seulement.

```bash
SERVICE=$(grep '^SERVICE_ROLE_KEY=' infra/.env | cut -d= -f2-)
ANON=$(grep '^ANON_KEY=' infra/.env | cut -d= -f2-)

# 1. Refusé : l'adresse n'existe pas encore
curl -sk -X POST https://localhost/auth/v1/magiclink \
  -H "apikey: $ANON" -H 'Content-Type: application/json' \
  -d '{"email":"test@example.com"}'

# 2. Créer l'utilisateur (comme le fera une invitation)
curl -sk -X POST https://localhost/auth/v1/admin/users \
  -H "apikey: $SERVICE" -H "Authorization: Bearer $SERVICE" \
  -H 'Content-Type: application/json' \
  -d '{"email":"test@example.com","email_confirm":true}' -o /dev/null -w '%{http_code}\n'

# 3. Le lien magique part, et arrive dans mailpit
curl -sk -X POST https://localhost/auth/v1/magiclink \
  -H "apikey: $ANON" -H 'Content-Type: application/json' \
  -d '{"email":"test@example.com"}'
curl -s http://127.0.0.1:8025/api/v1/messages | python3 -m json.tool | grep -m1 Subject
```

## Arrêter

```bash
docker compose -f infra/docker-compose.yml --profile dev down     # garde les données
```

`down -v` efface aussi la base : à ne faire que sur une base de test.

## En production

- `infra/.env` : `DOMAINE`, `SITE_URL` et `API_EXTERNAL_URL` sur le vrai nom de
  domaine, et SMTP sur Brevo (`smtp-relay.brevo.com`, port 587, identifiants
  du compte Brevo).
- Lancer sans le profil `dev` : `docker compose -f infra/docker-compose.yml up -d --build`.
- Ne jamais changer `POSTGRES_PASSWORD` ou `JWT_SECRET` après la création de
  la base sans changer aussi les rôles et les clés.
- Le worker lit les identifiants INPI et INSEE dans le `.env` de la racine.
