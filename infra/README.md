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

## Appliquer les migrations

Le schéma de l'app est dans `supabase/migrations/`, un fichier SQL par étape,
joué dans l'ordre des noms. La stack lancée, depuis la racine :

```bash
bash infra/appliquer-migrations.sh                                  # toutes (base neuve)
bash infra/appliquer-migrations.sh supabase/migrations/0002_x.sql   # seulement les nouvelles
```

Chaque fichier passe dans une seule transaction : une erreur n'applique rien
de ce fichier. Il n'y a pas de suivi des migrations jouées : rejouer une
migration échoue (« already exists ») sans rien changer.

Puis les données de départ (`supabase/seed/`) : les réglages historiques de
LVMH, VINCI et CMAF, en version 1 validée de l'organisation Youno. Le seed se
rejoue sans effet. Il est généré depuis `config/*.json` : après un changement
de config, relancer `.venv/bin/python worker/scripts/generer_seed_reglages.py`.

```bash
bash infra/appliquer-migrations.sh supabase/seed/reglages_depart.sql
```

Tester le cloisonnement RLS (`worker/tests/test_rls.py`) demande une URL vers
cette base avec le rôle `postgres`. Le port de `db` n'est pas publié : le plus
simple est une base jetable, comme en CI.

```bash
docker run -d --name cartofr-test-db -e POSTGRES_PASSWORD=test-local \
  -p 127.0.0.1:55432:5432 supabase/postgres:15.8.1.060
for f in supabase/migrations/*.sql supabase/seed/*.sql; do
  docker exec -i cartofr-test-db psql -U postgres -v ON_ERROR_STOP=1 -q -1 -f - < "$f"
done
DATABASE_URL=postgresql://postgres:test-local@127.0.0.1:55432/postgres .venv/bin/pytest worker -rs
docker rm -f cartofr-test-db
```

Sans `DATABASE_URL`, le test est ignoré en local et échoue en CI.

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

## Se connecter à l'app et inviter (T009)

L'app ne crée aucun compte seule : le premier admin se crée à la main, une
fois par organisation. Les suivants sont invités depuis la page Membres.

```bash
# 1. Le compte (étape 2 ci-dessus), puis l'organisation et le rôle admin
docker compose -f infra/docker-compose.yml exec -T db psql -U postgres -d postgres -c \
  "with o as (insert into public.organisations (nom) values ('Youno') returning id)
   insert into public.membres (organisation_id, user_id, role)
   select o.id, u.id, 'admin' from o, auth.users u where u.email = 'test@example.com';"
```

2. Ouvrir https://localhost/connexion, saisir l'adresse : le lien arrive dans
   mailpit, en français. L'ouvrir connecte et mène à l'accueil.
3. Menu **Membres** (admins seulement) : saisir l'adresse à inviter. L'e-mail
   d'invitation arrive dans mailpit ; son lien connecte le nouveau membre.

Le texte des e-mails vient de `web/public/modeles-email/`, que GoTrue lit sur
`http://web:3000` à chaque envoi. Si `web` ne répond pas, GoTrue envoie ses
modèles anglais par défaut : vérifier `web` avant de chercher ailleurs.
`SITE_URL` doit être l'adresse publique de l'app : les liens des e-mails la
reprennent.

Les variables de `web` sont lues au démarrage du conteneur, pas au build
(aucune `NEXT_PUBLIC_`) : une même image sert partout. `SUPABASE_SERVICE_ROLE_KEY`
n'est lue que côté serveur (`web/lib/supabase/admin.ts`, `server-only`).

Si le port 8025 de mailpit est pris : `MAILPIT_PORT` dans `infra/.env`.

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
