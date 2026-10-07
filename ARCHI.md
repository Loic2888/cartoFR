# Architecture technique — cartoFR

Date : 2026-10-06. Part de `PRD.md`. Le PRD dit le quoi, ce document dit le comment.

> La méthode `saas-create-architecture` cite une référence d'outils (`aiblueprint/ai-coding/tools.md`). Ce fichier n'existe plus (404 le 2026-10-06). Les choix ci-dessous partent de la stack visée dans `CLAUDE.md` et des mesures faites sur le prototype.

## Vue d'ensemble

**Approche** : garder le moteur Python du prototype, qui marche et qui est mesuré, et l'entourer du minimum pour en faire une app. Le registre (lourd, plein de données personnelles) reste à côté du moteur. La base de l'app ne garde que ce qui s'affiche. Un seul serveur, à 20 €/mois au plus.

**Stack en bref**
- Interface : Next.js 16 (App Router) + TypeScript, shadcn/ui (Base UI) + Tailwind
- Base de l'app : Supabase auto-hébergé (Postgres 15, Auth, RLS, PostgREST)
- Registre et moteur : worker Python 3.12, DuckDB sur fichiers locaux
- Hébergement : un VPS Hetzner CX43 (Allemagne, UE), Docker Compose, Caddy pour le HTTPS
- Connexion : lien magique par e-mail, e-mails envoyés par Brevo (France)
- IA (P2) : API Claude, pour proposer les réglages seulement

```
                   ┌──────────────────── VPS Hetzner (UE) ─────────────────────┐
 Consultant ──HTTPS─▶ Caddy ─▶ Next.js ──supabase-js──▶ Supabase (Postgres+Auth)  │
                   │                                         ▲   table travaux     │
                   │                                         │ psycopg             │
                   │   Worker Python (un seul processus) ────┘                    │
                   │     ├─ synchro : API INPI diff, API Sirene ──▶ registre.duckdb │
                   │     └─ moteur  : lit registre.duckdb, écrit la carto          │
                   └───────────────────────────────────────────────────────────────┘
```

## Interface (frontend)

- **Framework : Next.js 16, App Router, TypeScript strict.** (15 prévu au départ ; 16.3 retenu le 2026-10-06 à T002, version courante. Conséquence : `proxy.ts` remplace `middleware.ts`.)
  - **Pourquoi** : stack visée dans CLAUDE.md, rendu serveur par défaut, Server Actions pour les écritures.
  - **Compromis** : plus lourd qu'une page statique, mais la connexion et les formulaires de réglages le justifient.
- **Composants : shadcn/ui + Tailwind.**
  - **Pourquoi** : composants Base UI (shadcn 4) accessibles au clavier, motifs WAI-ARIA, copiés dans le code donc modifiables, mobile-first par défaut avec Tailwind.
  - **Compromis** : pas de composant d'arbre. On écrit un arbre maison selon le motif WAI-ARIA `treeview` (flèches, Entrée, `aria-expanded`).
- **État** : hooks React seulement. Pas de store global.
- **Données serveur** : Server Components qui lisent Supabase. L'état d'une carto en cours se rafraîchit toutes les 3 s tant qu'elle tourne, sans temps réel.
- **État dans l'URL** : groupe et carto ouverts (`/groupes/[id]/cartos/[id]`), dépliage de l'arbre non conservé.
- **Langue** : tout est écrit en français dans le code, sans bibliothèque i18n (une seule langue). Dates au format `jj/mm/aaaa`.

## Serveur (backend)

### Couche API
- **Modèle** : Server Actions pour les écritures (réglages, lancer une carto), lecture directe par Server Components. Pas d'API publique.
- **Validation** : Zod sur chaque Server Action. Les réglages ont un schéma Zod, et le même schéma est vérifié côté Python avec pydantic.
- **Sécurité** : toutes les pages demandent une session. Inscription fermée : un compte n'existe que sur invitation.

### Connexion et droits
- **Fournisseur : Supabase Auth (GoTrue) auto-hébergé.** **Pourquoi** : fourni avec Supabase, et RLS s'appuie directement sur `auth.uid()`.
- **Méthode** : lien magique par e-mail, envoyé en SMTP par Brevo.
- **Droits** : un utilisateur appartient à une organisation. Rôles `membre` (cartographier) et `admin` (inviter, voir les mises à jour). Pas de RBAC plus fin en V1.

### Données
Deux magasins, chacun pour ce qu'il fait bien. C'est la décision centrale (ADR-001).

**1. Le registre — `registre.duckdb` sur le worker, jamais exposé**
| Table | Contenu | Lignes (2026-10-06) |
|---|---|---|
| `societes` | SIREN, dénomination, effectif, état, date de création, opposition à la prospection, non-diffusion INSEE, `debut`, `fin` | 10,5 M |
| `liens` | dirigeante → dirigée (SIREN), rôle, source, `debut`, `fin`, `fin_inconnue`. Sans nom du parent (peut être une personne pour un entrepreneur individuel) ni clé primaire (8 148 doublons du stock gardés) | 1,6 M |
| `dirigeants_personnes` | usage interne au calcul, jamais exporté | 13,1 M |
| `sieges` | SIRENE : siège, adresse, nom, forme juridique, activité, tranche d'effectif (les `etablissements` ne sont pas encore chargés) | 7,8 M |
| `unites_legales` | SIRENE, personnes morales seulement (cj 1000 refusée) : dénominations, sigle, forme juridique, activité, effectif, état. Aucune colonne de personne. Lue par la recherche des marques (T016) | 13,1 M |
| `mises_a_jour` | date, source, volumes ajoutés et fermés, statut | — |

Un lien ou une société qui disparaît reçoit une date `fin`. Il n'y a jamais de `DELETE` (principe 4). Construit par `python -m cartofr.registre.construire` (T007) : 1,4 Go, 27 s, 3 Go de mémoire au plus, le 2026-10-06 ; 2,4 Go, 1 min 12 s, 3,4 Go de mémoire au plus avec `unites_legales` (T016, 2026-10-07).

**2. La base de l'app — Postgres (Supabase), cloisonnée par RLS**
| Table | Contenu |
|---|---|
| `organisations`, `membres` | compte Youno, consultants, rôles |
| `groupes` | tête (SIREN, nom), `organisation_id` |
| `reglages` | versions des réglages (JSON validé), auteur, date, `valide_le` |
| `travaux` | file : type (`carto`, `synchro`), statut, dates, erreur |
| `cartos` | groupe, version de réglages, date des données, durée |
| `carto_societes`, `carto_liens` | résultat : SIREN, nom, niveau, maison mère, preuve, confiance, ciblable et raison, opposition, non-diffusion |
| `etat_registre` | copie de la dernière ligne de `mises_a_jour`, pour l'écran admin |

Chaque table métier porte `organisation_id`, avec une politique RLS `organisation_id in (select organisation_id from membres where user_id = auth.uid())`. Aucun nom de personne physique n'entre dans cette base.

- **Accès** : pas d'ORM. Migrations SQL dans `supabase/migrations/`, types TypeScript générés par `supabase gen types`. Côté Python, `psycopg` en SQL direct.
- **Temps réel** : non. Un rafraîchissement périodique suffit pour une carto qui dure moins d'une minute.

### Le worker
- **Un seul processus Python**, qui prend les travaux un par un dans la table `travaux` (`select … for update skip locked`, interrogée toutes les 5 s). Les cartos et la synchro ne tournent jamais en même temps, donc une carto lit toujours une base cohérente (cas limite du PRD).
- **Le moteur** est `engine.py`, rangé dans un paquet (`worker/cartofr/moteur/`), qui lit `registre.duckdb` au lieu des parquets épars. Mesuré le 2026-10-06 : 49 s et 2,2 Go au plus pour LVMH, 47 s et 2,2 Go pour VINCI (SC-004 : < 5 min).
- **Synchro (US1)**, voir ADR-002 :
  - RNE : API INPI `/api/companies/diff` (fiches complètes modifiées entre deux dates, pagination `searchAfter`), lancée chaque jour pour les changements de la veille.
  - SIRENE : API Sirene de l'INSEE (changements par date de traitement), chaque jour. Fichiers stock mensuels de data.gouv.fr pour un rechargement complet.
  - Chaque passage écrit une ligne dans `mises_a_jour`. Un échec laisse la base dans son état précédent (écriture dans une transaction DuckDB).
- **Recherche de la tête (US2)** : le worker expose une seule route HTTP interne, `GET /recherche?q=` (nom ou SIREN, 20 résultats au plus : SIREN, nom, ville, statut). Elle lit `registre.duckdb` en lecture seule, n'est joignable que depuis le conteneur `web` (réseau Docker, aucun port publié) et ne rend jamais de personne. Ajoutée le 2026-10-06 au découpage des tâches : sans elle, l'interface ne peut pas chercher dans le registre.
- **Planification** (T013, 2026-10-07) : la boucle du worker insère elle-même un travail `synchro` chaque nuit, une seule fois par jour, à `CARTOFR_SYNCHRO_HEURE` (heure de Paris) ; pas de cron (le conteneur n'en a pas). Sans cette variable, aucune synchro ne tourne : elle est posée dans le compose. Chaque passage lit au plus `CARTOFR_SYNCHRO_JOURS_MAX` jours par source (7), dans l'ordre, jusqu'à J-`CARTOFR_SYNCHRO_DECALAGE` (2 en production : un jour appliqué n'est jamais relu, une publication tardive serait perdue). Le dernier jour appliqué par source est gardé dans `data/synchro/jours.json` (à remplacer par une colonne `jour` de `mises_a_jour`).

### Familles exclues : masquées par empreinte (garde-fou 6)
Décidé le 2026-10-07. Le réglage `familles_exclues` contient des noms de famille (la famille qui contrôle le groupe, dont les holdings personnelles ne doivent pas entrer dans la carto). Ces noms ne s'écrivent jamais en clair dans la base de l'app ni à l'écran.
- **Stockage** : `reglages.contenu.familles_exclues_empreintes`, liste de HMAC-SHA256 de `upper(trim(nom))` avec la clé serveur `CARTOFR_CLE_EMPREINTE` (`worker/cartofr/empreinte.py`). Une contrainte SQL refuse la clé `familles_exclues` en clair.
- **Saisie (T020)** : le consultant tape le nom une fois ; le serveur calcule l'empreinte ; l'écran affiche « N famille(s) exclue(s) », jamais le nom.
- **Moteur (T021)** : compare l'empreinte du nom de chaque dirigeant à la liste. La non-régression, qui lit `config/*.json` côté worker, garde les noms.
- **Pourquoi un HMAC et pas un SHA-256** : un nom de famille connu se retrouve en une seconde en essayant des noms. Sans la clé, non.
- **Écarté** : amender le garde-fou ; garder ce réglage hors de l'app (plus modifiable depuis l'interface).
- **Limite** : `config/*.json` et le seed, publics dans git, contiennent encore le nom, comme avant.

### IA (P2, US3)
- **SDK** : `anthropic` (Python), dans le worker. Modèle choisi au moment de US3.
- **Usage** : lire le site et le rapport annuel du groupe (recherche web), proposer les marques, les maisons et les exclusions, chacune avec sa source.
- **Ce qui part** : le nom du groupe et des noms de sociétés publics. Jamais un nom de personne. La proposition est enregistrée comme `reglages` non validés (principe 1).
- US3 n'oriente aucun choix de cette architecture : elle s'ajoute comme un type de travail en plus.

## Infrastructure

- **Plateforme : un VPS Hetzner CX43** (8 vCPU, 16 Go de RAM, 160 Go de disque, Nuremberg ou Falkenstein). Docker Compose avec quatre services : `caddy`, `web` (Next.js `standalone`), `worker`, et `supabase` (db, auth, rest, kong, studio seulement ; sans realtime, storage, analytics ni edge functions, pour économiser la mémoire).
  - **Pourquoi** : budget plafonné à 20 €/mois, tout en UE, et un seul endroit à surveiller.
  - **Compromis** : pas de haute disponibilité. Si le serveur tombe, l'app est arrêtée jusqu'à la restauration. C'est acceptable pour un outil interne.
- **Mémoire estimée** : Supabase réduit environ 2 Go, Next.js environ 0,3 Go, moteur 2,2 Go au plus. Environ 5 Go en pointe sur 16. La construction complète des tables depuis un stock (`build_links.py`) tourne avec 4 processus au lieu de 14 : environ 1 h, une fois par an au plus.
- **Disque** : registre environ 5 Go, stock RNE zippé 15 Go (gardé tant qu'un rechargement est probable), Postgres moins de 1 Go. Environ 25 Go sur 160.
- **Région** : une seule, Allemagne (UE).
- **Tâches de fond** : le worker ci-dessus. Pas de Redis, pas de Celery.
- **Sauvegardes** : sauvegardes Hetzner du serveur (7 jours glissants, en UE), plus un `pg_dump` quotidien de la base de l'app dans le serveur. Le registre se reconstruit depuis les sources : il n'a pas besoin d'être sauvegardé.
- **Surveillance** : la table `mises_a_jour`, affichée sur l'écran admin (FR-003). Journaux Docker avec rotation (`max-size`), sans aucune donnée personnelle. Pas de Sentry en V1.
- **CI** : GitHub Actions sur chaque PR (lint, typecheck, tests). Elle n'utilise que du code et des données de test, jamais le registre. Déploiement manuel : `git pull && docker compose up -d --build` sur le serveur.

## Services en plus

- **E-mail** : Brevo, en SMTP pour les liens magiques. Gratuit jusqu'à 300 e-mails par jour.
- **Stockage de fichiers** : non. Les CSV sont générés à la demande.
- **Paiement** : non (usage interne).

## Contrôle constitutionnel

| Règle | Verdict | Sur quoi |
|---|---|---|
| G1-G4 Branches, PR, commits, squash | ✅ | Le hook `git-guardrail.py` est actif. La CI GitHub Actions est la condition de merge |
| G5 Aucun secret dans le code | ⚠️ | Les identifiants INPI, INSEE, Brevo et Supabase sont dans `.env` sur le serveur, et seuls les noms vont dans `.env.example`. **Contrainte** : le `docker-compose.yml` lit `env_file`, jamais une valeur en dur |
| G6 Licence INPI, dépôt public | ✅ | `dirigeants_personnes` ne quitte jamais `registre.duckdb`. La base de l'app n'a aucune colonne de personne. `data/` est hors git |
| R1 Français | ✅ | Interface entièrement en français, sans i18n. Les messages d'erreur Supabase sont traduits dans une table de correspondance |
| R2 Responsive | ⚠️ | **Contrainte** : l'arbre devient une liste indentée et dépliable sous 640 px, et l'écran de réglages est en une colonne. Vérification à 320 px dans les tâches de US2 |
| R3 Accessibilité | ⚠️ | **Contrainte** : arbre maison au motif WAI-ARIA `treeview`, confiance A/B/C écrite en toutes lettres (pas seulement en couleur), shadcn/ui pour le reste |
| R4 RGPD | ⚠️ | Dirigeants stockés pour le calcul seulement, sur le worker. **Contraintes** : registre des traitements à rédiger (tâche) ; aucune donnée personnelle dans les journaux ; comptes consultants limités à l'e-mail ; suppression d'un compte possible |
| R5 Hébergement UE | ⚠️ | VPS, Postgres, journaux et sauvegardes chez Hetzner en Allemagne ✅. Brevo en France ✅. GitHub Actions ne voit que du code ✅. **Condition** : l'API Claude (P2, Anthropic, États-Unis) ne reçoit que des données de sociétés publiques, jamais un nom de personne |
| R6 Aucune donnée client réelle en dev | ⚠️ | **Contrainte** : les tests utilisent des extraits du registre public. Les références Basile servent seulement à la non-régression locale (`compare.py`), hors git et hors de l'app |
| R7 Isolation multi-tenant | ✅ | `organisation_id` + RLS sur chaque table métier. Le worker écrit en rôle service, mais copie l'`organisation_id` du travail. Un test vérifie qu'un membre de A ne voit rien de B |
| R8 Tests sur la logique métier | ✅ | Toute la logique (moteur, synchro, fermeture des liens) est dans le paquet Python, testée par `pytest`. Next.js ne décide rien |
| P1 L'IA ne décide pas | ✅ | Les propositions de l'IA sont des `reglages` sans `valide_le` |
| P2 Réglages validés | ✅ | Le worker refuse un travail `carto` dont la version de réglages n'est pas validée |
| P3 Aucun appel extérieur pendant une carto | ✅ | Le moteur ne lit que `registre.duckdb`. Les API ne servent qu'au travail `synchro` |
| P4 Fermer, jamais effacer | ✅ | Colonnes `debut` et `fin`, aucun `DELETE` dans la synchro, avec un test dédié |
| P5 Pas de régression silencieuse | ✅ | `compare.py` sur LVMH, VINCI et CMAF avant toute PR qui touche le moteur |

Aucun ⛔.

## Principes du projet

Tranchés ici, et à ne pas rediscuter à chaque tâche. Ils s'ajoutent aux cinq principes de `CLAUDE.md` :

6. **Le registre ne quitte pas le worker.** La base de l'app ne reçoit que des sociétés et des liens retenus dans une carto, jamais une ligne de `dirigeants_personnes`. Vérifiable : aucune table Postgres n'a de colonne de personne physique. Alternative écartée : tout mettre dans Supabase.
7. **La logique métier vit dans le paquet Python, testée par `pytest`.** Next.js affiche, valide la saisie (Zod) et met en file. Il ne décide jamais si une société entre dans un groupe. Vérifiable : aucune règle du moteur dans `web/`. Alternative écartée : réécrire le moteur en TypeScript ou en SQL.

## Décisions d'architecture (ADR)

### ADR-001 : le registre en DuckDB sur le worker, l'app dans Postgres
- **Contexte** : le registre fait 10,5 M sociétés, 1,6 M liens et 13,1 M dirigeants personnes. Le moteur du prototype est écrit en DuckDB et pandas.
- **Décision** : le registre reste dans un fichier DuckDB sur le worker. Postgres (Supabase) ne garde que les comptes, les réglages, la file de travaux et les cartos.
- **Alternatives** : tout dans Postgres (une seule base, mais 15 à 25 Go, moteur à réécrire en SQL, et données personnelles dans la base exposée).
- **Raison** : le moteur tourne presque tel quel (mesuré à moins de 1 min), les dirigeants restent isolés (licence INPI), et Postgres reste petit.
- **Conséquences** : deux magasins à garder cohérents, mais le seul pont est le worker. L'interface n'interroge le registre que par la route interne `/recherche` du worker. Une exploration libre du registre n'est pas un besoin de la V1.

### ADR-002 : mise à jour par API, au jour le jour, rechargement complet en secours
- **Contexte** : fraîcheur visée de 7 jours (SC-003). Le stock RNE local date du 2026-03-04. Il y a 15 000 à 20 000 formalités par jour. Le quota INPI observé est d'environ 10 000 fiches par jour, mais il n'est pas documenté pour `/diff`.
- **Décision** : chaque nuit, le worker lit `/api/companies/diff` pour la veille et l'API Sirene pour les changements SIRENE. Si le quota coupe, le passage reprend le lendemain où il s'est arrêté. La marge de 7 jours absorbe les retards. Un rattrapage initial (de mars à aujourd'hui) passe par un nouveau stock FTP, ou par `/diff` étalé sur plusieurs jours.
- **Alternatives** : recharger le stock FTP complet chaque semaine (15 Go à télécharger, 1 h de calcul, et le serveur FTP est capricieux) ; un fournisseur payant (Pappers), hors budget.
- **Raison** : volume quotidien faible, et la reprise est simple avec le curseur `searchAfter`.
- **Conséquences** : **première tâche de US1, mesurer le quota réel de `/diff`**. Si le quota ne permet pas de suivre 20 000 formalités par jour sur une semaine, on bascule sur le rechargement FTP hebdomadaire, et la décision est réécrite ici.
- **Mesure (2026-10-06, T010)** : le lundi 2026-10-05 a été lu en entier, sans erreur 429 : 39 131 fiches de société, 392 pages de 100, 394 requêtes, 6 min 48 s. Le volume réel est donc d'environ 39 000 fiches par jour, pas 15 000 à 20 000 (le lundi rattrape peut-être le week-end). `/diff/count` ne donne pas le total au-delà de 10 000. Le quota de 10 000 observé le 2026-10-05 portait sur des requêtes d'une fiche ; avec `/diff`, une journée coûte environ 400 requêtes.
- **Décision après mesure : la voie API est retenue.** Une journée se lit en moins de 7 minutes et bien en dessous du quota. Une semaine de retard (environ 2 800 requêtes) tient dans une seule journée de quota, si le quota compte les requêtes ; même sinon, la reprise sur curseur étale la lecture sur les jours suivants. Le rechargement FTP hebdomadaire reste le secours, pas la règle.
- **Ce que cela implique pour T011** : lire `/diff` avec `pageSize=100` et le client `cartofr.registre.inpi_diff` (reprise par `searchAfter`, arrêt propre au 429) ; prévoir environ 40 000 fiches par passage, et ne garder des fiches que ce qui sert au registre ; le rattrapage depuis le stock du 2026-03-04 peut passer par `/diff`, période par période, en surveillant le premier 429.

### ADR-003 : un seul VPS Hetzner, Supabase auto-hébergé
- **Contexte** : budget plafonné à 20 €/mois, hébergement UE, un seul développeur.
- **Décision** : Hetzner CX43 (15,99 € + 0,50 € d'IPv4 + 3,20 € de sauvegardes, soit 19,69 €/mois HT), Docker Compose, Supabase réduit à db, auth, rest, kong et studio.
- **Alternatives** : Supabase Cloud Paris (25 $/mois en Pro, au-dessus du budget à lui seul) ; Scaleway ou OVH en France (60 à 90 € pour le même gabarit) ; Vercel pour l'interface (journaux hors UE).
- **Raison** : le seul gabarit à 16 Go de RAM sous 20 €. Les mesures montrent qu'on n'a pas besoin de 32 Go.
- **Conséquences** : mises à jour de Supabase, sauvegardes et HTTPS à notre charge. Aucune haute disponibilité.

### ADR-004 : la file de travaux est une table Postgres, et un seul worker
- **Contexte** : cartos de moins de 1 min, synchro nocturne, quelques consultants.
- **Décision** : table `travaux` lue par `for update skip locked`, un seul processus, un travail à la fois.
- **Alternatives** : Redis + Celery/RQ (un service de plus, de la mémoire en plus) ; Inngest ou Trigger.dev (services externes, hors UE).
- **Raison** : zéro dépendance en plus. Et comme cartos et synchro ne se chevauchent jamais, une carto lit toujours une base cohérente.
- **Conséquences** : une carto attend la fin de la synchro si elle tombe pendant (quelques minutes la nuit). À revoir si l'app est commercialisée.

### ADR-005 : pas d'ORM
- **Décision** : migrations SQL Supabase, types générés pour TypeScript, `psycopg` en Python.
- **Alternatives** : Prisma ou Drizzle, qui ne savent pas exprimer les politiques RLS et ne servent pas le Python.
- **Raison** : RLS s'écrit en SQL de toute façon, et le schéma est petit (une dizaine de tables).

## Arborescence

```
web/                    Next.js : pages, Server Actions, composants (arbre)
worker/
  cartofr/moteur/       moteur de cartographie (depuis engine.py, brand_scan.py)
  cartofr/registre/     construction et synchro du registre (depuis build_*.py, inpi.py)
  cartofr/travaux.py    boucle de la file de travaux
  tests/                pytest : règles du moteur, synchro, RLS, aucun nom de personne
supabase/migrations/    schéma de l'app et politiques RLS
infra/                  docker-compose.yml, Caddyfile, scripts de migration et de sauvegarde
config/                 réglages historiques (LVMH, VINCI, CMAF), importés comme données de départ
skills/account-mapping/ le skill, inchangé (export P3)
```

Les scripts de la racine (`engine.py`, `build_links.py`…) restent en place tant que le worker n'a pas atteint les mêmes scores. Ils sont ensuite retirés dans une PR dédiée.

## Coûts

### Par mois
- VPS Hetzner CX43 + IPv4 : 16,49 € HT
- Sauvegardes Hetzner (+20 %) : 3,20 € HT
- Supabase auto-hébergé : 0 €
- Brevo : 0 € (moins de 300 e-mails par jour)
- API INPI, API Sirene, data.gouv : 0 €
- API Claude (P2) : quelques euros, selon le nombre de propositions
- **Total : 19,69 € HT/mois** (environ 23,60 € TTC), plus l'IA à partir de P2

### Limites gratuites
- Brevo : 300 e-mails par jour.
- API INPI : environ 10 000 fiches par jour observées (quota de `/diff` à mesurer).
- API Sirene : 30 requêtes par minute.

## Ordre de construction

### Phase 1 — Fondation
1. Dépôt : `web/`, `worker/`, `infra/`. Lint (ruff, eslint), typecheck (tsc, pyright), pytest et vitest, CI GitHub Actions.
2. VPS Hetzner, Docker Compose, Supabase réduit, Caddy, Brevo, sauvegardes.
3. Schéma de l'app, RLS, et le test « A ne voit pas B ».
4. Paquet `cartofr` : le moteur sorti des scripts, et `registre.duckdb` construit depuis les parquets actuels. Non-régression : mêmes scores que le prototype.

### Phase 2 — P1
1. US1 : mesurer le quota de `/diff`, synchro RNE et SIRENE, fermeture des liens, table `mises_a_jour`, écran admin.
2. US2 : connexion par lien magique, choix de la tête, saisie et validation des réglages, file de travaux, arbre, export CSV.

### Phase 3 — P2 et P3
1. US3 : proposition des réglages par l'IA.
2. US4 : liste des cas douteux et décisions mémorisées.
3. US5 et US6 : export des 6 tables du skill, puis domaine et LinkedIn.
