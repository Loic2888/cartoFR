# Recette SC-002 : de la saisie du groupe à l'export CSV en moins de 30 minutes

Guide pour Loïc, écrit le 2026-10-07 (T024). C'est la seule mesure de la
recette du MVP qui demande un humain : les réglages d'un groupe s'écrivent
à la main, et c'est ce temps-là qu'on mesure.

## Le but

PRD, SC-002 : **moins de 30 minutes** entre le moment où l'on tape le nom d'un
groupe et le moment où l'on a son CSV, **réglages écrits à la main compris**.
Trois sessions chronométrées, sur **trois groupes jamais réglés** (ni dans
`config/`, ni dans l'app), de **moins de 200 sociétés**.

Une session réussit si sa durée totale est sous 30 minutes. C2 (spec T024) est
coché quand les trois le sont, et que les trois durées sont dans `rapport.md`.

## Les trois groupes proposés

Choisis le 2026-10-07 : SIREN de la tête lu dans le registre local
(`unites_legales`, société active), taille estimée en lançant le moteur avec un
brouillon minimal (la tête et une marque évidente). Ces brouillons ne sont pas
donnés ici : les réglages, c'est toi qui les écris, c'est ce qu'on chronomètre.
La taille finale dépendra de tes réglages.

| Groupe | Tête au registre | SIREN de la tête | Taille estimée | Pourquoi c'est un bon test |
|---|---|---|---|---|
| Bigard | GROUPE BIGARD | 776221467 | ~46 sociétés, 3 niveaux | Agroalimentaire à **marques connues** (le groupe vend sous plusieurs marques grand public) : il faut trouver ces marques et juger lesquelles sont sûres. |
| Fayat | FAYAT | 595750589 | ~83 sociétés, 4 niveaux | **BTP et industrie** : arbre profond, beaucoup de sociétés de chantier et d'immobilier, des noms d'activité courants. Proche de VINCI en petit. |
| Roullier | COMPAGNIE FINANCIERE ET DE PARTICIPATIONS ROULLIER | 313642548 | ~38 sociétés, 3 niveaux | **Groupe familial** : la tête est une holding dont le nom n'est pas celui des marques ; le nom de famille sert aussi à d'autres sociétés sans lien (exclusions à prévoir). |

Si l'un des trois dépasse 200 sociétés une fois réglé, le remplacer par un
autre groupe jamais réglé, et le noter. Candidats de secours mesurés le même
jour (même méthode) : Charier (SIREN 305319477, ~36 sociétés, BTP).

## Démarrer la pile en local, registre réel en lecture seule

À faire **avant** de lancer le chronomètre. Depuis la racine du dépôt.

1. Créer un fichier de surcharge **hors du dépôt**, par exemple
   `/tmp/cartofr-recette.yml`. Il monte `data/` en **lecture seule** et coupe
   la synchro : sans lui, le worker planifie la synchro du jour dès son
   démarrage (après 02:00), appelle l'INPI et écrit dans le registre.

   ```yaml
   services:
     worker:
       environment:
         CARTOFR_SYNCHRO_HEURE: ""
       volumes:
         - /home/alkemia/cartoFR/data:/app/data:ro
     recherche:
       volumes:
         - /home/alkemia/cartoFR/data:/app/data:ro
   ```

2. Créer `infra/.env` s'il n'existe pas (`bash infra/generer-secrets.sh`).
   Si les ports 80, 443, 3001 ou 8025 sont pris, poser `HTTP_PORT`,
   `HTTPS_PORT`, `STUDIO_PORT`, `MAILPIT_PORT` dans `infra/.env`, et mettre
   `SITE_URL` et `API_EXTERNAL_URL` sur `https://localhost:<HTTPS_PORT>`.

3. Lancer la pile, sous un nom de projet à part :

   ```bash
   docker compose -p cartofr-recette -f infra/docker-compose.yml \
     -f /tmp/cartofr-recette.yml --profile dev up -d --build
   COMPOSE_PROJECT_NAME=cartofr-recette bash infra/appliquer-migrations.sh
   COMPOSE_PROJECT_NAME=cartofr-recette bash infra/appliquer-migrations.sh supabase/seed/reglages_depart.sql
   ```

4. Créer ton compte et l'ajouter à l'organisation Youno (créée par le seed).
   Adresse fictive : les e-mails arrivent dans mailpit, rien ne sort.

   ```bash
   SERVICE=$(grep '^SERVICE_ROLE_KEY=' infra/.env | cut -d= -f2-)
   curl -sk -X POST https://localhost/auth/v1/admin/users \
     -H "apikey: $SERVICE" -H "Authorization: Bearer $SERVICE" \
     -H 'Content-Type: application/json' \
     -d '{"email":"loic@example.com","email_confirm":true}' -o /dev/null -w '%{http_code}\n'
   docker compose -p cartofr-recette -f infra/docker-compose.yml exec -T db psql -U postgres -d postgres -c \
     "insert into public.membres (organisation_id, user_id, role)
      select o.id, u.id, 'membre' from public.organisations o, auth.users u
      where o.nom = 'Youno' and u.email = 'loic@example.com';"
   ```

5. Se connecter : ouvrir https://localhost/connexion (accepter le certificat
   local), saisir `loic@example.com`, ouvrir le lien reçu dans mailpit
   (http://127.0.0.1:8025). On arrive sur l'accueil.

6. Vérifier que tout marche : lancer une fois la carto de LVMH (déjà réglée
   par le seed). Elle doit finir en moins d'une minute environ. Ça réchauffe
   aussi le cache disque du registre : la première carto de la session ne
   paie pas la lecture à froid.

## Une session, pas à pas

Lancer le chronomètre au moment où l'on commence à taper le nom du groupe.
Noter l'heure à chaque étape (une horloge à la seconde suffit).

1. **Début** : *Groupes* → *Nouveau groupe*, taper le nom du groupe.
2. **Tête choisie** : choisir la bonne société de tête dans les résultats,
   *Créer le groupe*.
3. **Réglages validés** : *Réglages*, écrire les marques, sigles, exclusions,
   organigramme ; *Enregistrer le brouillon* ; *Valider la version*. Les
   recherches faites pour écrire les réglages (site du groupe, annuaire)
   comptent dans le temps.
4. **Carto terminée** : sur la fiche du groupe, *Lancer la carto*, attendre
   « Terminée ». Regarder l'arbre. Si une marque ramène des sociétés fausses,
   corriger les réglages, valider une nouvelle version, relancer : c'est
   compté, et c'est noté dans « corrections ».
5. **CSV exporté** : *Exporter (CSV)*, le fichier est téléchargé. Arrêter le
   chronomètre.

Ne pas lancer deux sessions en même temps, ni d'autre calcul lourd sur la
machine pendant la mesure.

## Grille de chronométrage

| | Session 1 | Session 2 | Session 3 |
|---|---|---|---|
| Groupe | | | |
| SIREN de la tête | | | |
| Date | | | |
| Début (saisie du nom) | | | |
| Tête choisie | | | |
| Réglages validés (1ʳᵉ version) | | | |
| Carto terminée (dernière) | | | |
| CSV exporté | | | |
| **Durée totale** | | | |
| Dont réglages (début des réglages → validés) | | | |
| Dont calcul (durée affichée sur la fiche) | | | |
| Nombre de sociétés de la carto | | | |
| Corrections faites (versions de réglages, relances) | | | |
| Sous 30 min ? | | | |
| Gêne ou bug rencontré | | | |

## Après les trois sessions

- Reporter les trois durées dans `rapport.md`, sous la date du jour, avec ce
  qui a pris le plus de temps.
- Cocher C2 dans `specs/01-mvp/T024-recette-mvp.md` si les trois sont sous
  30 minutes. Sinon, ne pas cocher, et noter l'étape qui a dépassé.
- Les CSV exportés restent hors de git (aucun dans le dépôt).
- Arrêter la pile : `docker compose -p cartofr-recette -f infra/docker-compose.yml --profile dev down -v`
  (`-v` efface la base de test, pas `data/`).
