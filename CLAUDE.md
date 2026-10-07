# CLAUDE.md — cartoFR

Ce fichier est lu **automatiquement** par Claude Code à chaque démarrage de session
dans ce dossier. Rien à lancer : ce qui est écrit ici s'applique tout seul.

> Garde-le court. Ce qui est long part dans `.claude/rules/` et se lit à la demande.

## Le but

Une app SaaS de cartographie de groupes d'entreprises françaises, d'abord pour
Youno (missions clients), commercialisable ensuite.

1. **Base à jour** : l'app tient sa propre copie du registre (toutes les
   sociétés, tous les liens "société A dirige société B") et la met à jour
   automatiquement avec l'INPI et l'INSEE, **7 jours de retard au plus** sur
   le registre (décidé le 2026-10-06, PRD SC-003) : nouvelles sociétés à
   ajouter, nouveaux liens à créer, liens et sociétés disparus à fermer.
2. **Cartographie** : l'utilisateur donne le nom d'une entreprise, l'app rend
   l'arbre du groupe en France (maison mère, filiales, sous-filiales), avec pour
   chaque lien sa preuve, une confiance A/B/C et si la société est ciblable.
   V1 : une carto qui affiche la date de ses données, 7 jours au plus. Pas d'alertes, pas de
   poussée CRM.

Aujourd'hui le dépôt contient le **prototype** : des scripts Python qui
tournent sur une base locale (DuckDB + parquet). La vision produit est dans
`rapportSaaS.md`, l'historique, les résultats et les décisions dans
`rapport.md`. Les lire avant un gros changement.

## Références

- **PRD** (le quoi) : `PRD.md` · **Architecture** (le comment) : `ARCHI.md` — écrits le 2026-10-06
- **Tâches et convergence** : `specs/README.md` — l'index des tâches, et
  `/apex-converge` pour confronter le code à leurs critères
- **Suivi des tâches** : `<tracker à choisir : ClickUp / GitHub Issues>`
- **Règles détaillées** : `.claude/rules/git-pr.md` · `.claude/rules/tickets.md`
  · `.claude/rules/constitution.md` · `.claude/rules/produit.md` · `.claude/rules/routing.md`
- **Moteur, réglages, pièges** : `skills/account-mapping/references/moteur-france.md`
- **Comment on modifie ce projet** : [`AGENTS.md`](AGENTS.md). **À lire avant d'écrire du code.**
- **Ce qui a été décidé et ce qui a fait mal** : [`MEMORY.md`](MEMORY.md)

## Stack

`Next.js 16 + TypeScript` · `shadcn/ui + Tailwind` · `Supabase auto-hébergé (Postgres, Auth, RLS) + worker Python 3.12 / DuckDB` · `VPS Hetzner CX43, Docker Compose` · région `UE (Allemagne)`

Prototype actuel, à la racine : Python 3.12 · DuckDB · pandas · pyarrow · parquet local.

## Structure

Cible (`ARCHI.md`) :

```
web/                    interface Next.js (pages, Server Actions, arbre)
worker/cartofr/         moteur, registre et synchro, file de travaux (Python)
worker/tests/           pytest : règles du moteur, synchro, RLS, aucun nom de personne
supabase/migrations/    schéma de l'app et politiques RLS
infra/                  docker-compose, Caddy, cron, sauvegardes
config/                 réglages historiques des groupes (données de départ)
```

Prototype, à la racine, jusqu'à ce que le worker atteigne les mêmes scores :

```
engine.py            le moteur de cartographie (boucle jusqu'au point fixe)
brand_scan.py        candidates SIRENE par nom de marque
build_links.py       stock RNE INPI → data/rne_links/ (liens, sociétés, personnes)
build_sieges.py      SIRENE → data/sieges.parquet
inpi.py annuaire.py bodacc.py ftp_download.py   clients des sources, cache dans data/
compare.py to_skill_tables.py debug_*.py         comparaison, export, diagnostic
config/<groupe>.json réglages d'un groupe (tête, marques, exclusions, organigramme)
skills/account-mapping/   le skill v2 (lien .claude/skills/account-mapping)
data/ basile/ out/   hors git : données (19 Go), références, sorties
```

`skills/account-mapping/scripts/moteur_france/` est une **copie** des scripts
de la racine. La racine fait foi : recopier dans le skill après un changement.

## Commandes

Les scripts lisent des chemins relatifs : les lancer depuis la racine.

| Quoi | Commande |
|---|---|
| Installer | `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` |
| Cartographier un groupe | `.venv/bin/python brand_scan.py config/<g>.json && .venv/bin/python engine.py config/<g>.json` |
| Non-régression | `CARTOFR_DATA=data CARTOFR_REFERENCES=basile .venv/bin/python worker/scripts/non_regression.py` : moteur du paquet sur `data/registre.duckdb`, `lvmh`, `vinci` et `cmaf` (scores ci-dessous). L'ancien `compare.py <g>` reste pour le prototype |
| Export skill | `.venv/bin/python to_skill_tables.py config/<g>.json` |
| Reconstruire les tables | `.venv/bin/python build_sieges.py` puis `.venv/bin/python build_links.py data/rne_stock/<stock>.zip` (~15 min) |
| Lint / Typecheck / Tests | `.venv/bin/ruff check worker` · `.venv/bin/pyright -p worker` · `.venv/bin/pytest worker` · `npm --prefix web run lint` · `npm --prefix web run typecheck` · `npm --prefix web test` · `npm --prefix web run build` (détail dans `AGENTS.md`) |

> Claude lance ces commandes pour se valider. Tant que lint et tests unitaires
> n'existent pas, la seule validation réelle du moteur est la non-régression.

### Scores de non-régression (2026-10-06)

| Groupe | Retrouvées | En plus |
|---|---|---|
| LVMH | 90 % (154/172) | 15 |
| VINCI | 81 % (813/1 007) | 176 |
| Crédit Mutuel Alliance Fédérale | 83 % (43/52) | |

Les règles privilégient la justesse sur le rappel. Un changement du moteur qui
fait baisser un score, ou monter nettement les « en plus », ne se rend pas
sans le dire.

---

## 🧭 Routage

**La demande, d'abord — une seule question :**

1. **C'est petit et je sais déjà où ?** (typo, renommage, import, question sur
   le code, lecture, un réglage de groupe) → **fais-le directement.** Pas de
   workflow, pas d'agent. *C'est le cas le plus fréquent.*
2. **Sinon** → **`apex`**. Bug ou feature : `-x -b`. Code couvert par des
   tests : ajoute `-t`.

Entre les deux, prends la voie légère et **propose** la lourde. Annonce en une
ligne la voie que tu prends.

**Deux préalables :**

- **Il n'y a ni PRD ni specs** (fait le 2026-10-06 : `PRD.md`, `ARCHI.md`, `specs/`) → **`/start`**, qui
  enchaîne évaluation → PRD → architecture → tâches, avec un point d'arrêt
  entre chaque. Puis `apex` sur chaque tâche.
- **Projet gros, plusieurs domaines, et `.claude/agents/` est vide** →
  **`/myteam`**, **une seule fois**, quand il y a du code à partitionner.

**Quand le travail est censé être fini** → **`/apex-converge`** relit `specs/`
contre le code et rend un verdict binaire. Il n'écrit jamais de code.

**Symptôme sans bug identifié** : reproduis d'abord (repro, erreurs réelles,
bug nommé), et seulement alors `apex -x -b "<le bug>"`.

Les commands (`/start`, `/myteam`, `/apex-converge`, `saas-*`) ne
s'auto-invoquent **jamais**. Pour en appliquer une toi-même, **lis son fichier
dans `.claude/commands/` et suis-le en entier**. Seul `apex` est une skill.
Détail : `.claude/rules/routing.md`. Les commands marketing citées par
`/start` et `routing.md` (pricing, domaine, logos, landing…) n'ont
volontairement pas été installées.

## 🥇 Garde-fous — à respecter par toute session Claude

Les points 1 et 3 sont en plus **bloqués en dur** par
`.claude/hooks/git-guardrail.py`, une fois le hook déclaré dans `.claude/settings.json`.

1. **Jamais de push direct sur `main`.** Toute modif de code passe par une **branche + PR**.
2. **1 ticket = 1 branche = 1 PR.** Branche `<user>/<id>-<slug>`.
3. **Commits et titres de PR sémantiques** (Conventional Commits) :
   `type(scope): sujet`, type ∈ `feat` `fix` `docs` `style` `refactor` `perf`
   `test` `chore` `build` `ci` `revert`. Sujet à l'impératif, minuscule, sans point final.
4. **Merge = squash uniquement.** Titre du squash = titre de la PR. Conditions :
   CI verte, approbation non requise (projet solo pour l'instant).
5. **Jamais de secret dans le code.** Lire `.env*` est permis, en ressortir une
   valeur jamais. Le **nom** seul va dans `.env.example`. Détail : [`AGENTS.md`](AGENTS.md) §2.
6. **Le dépôt GitHub est public, et la licence INPI s'applique.**
   - Jamais dans git : `.env`, `data/`, `basile/` (données Basile), `out/`
     (cartographies client), ni aucun dump.
   - Les dirigeants personnes physiques servent seulement de **preuve interne**
     pendant le calcul. Aucun nom de personne dans une sortie, un export, un
     log, une table exposée ou l'interface. *Précisé le 2026-10-07 (T023,
     décision de Loïc)* : la raison sociale officielle d'une société (SIRENE),
     même si elle contient le nom de son fondateur (« Jean Dupont SAS »), est
     une donnée de société, pas un dirigeant tiré du registre : elle s'affiche
     et s'exporte. Ce qui est interdit, c'est de faire sortir une personne de
     `dirigeants_personnes`.
   - Les sociétés avec `diffusionCommerciale = false` sont marquées
     (`opposition_prospection`), jamais cachées ni présentées comme démarchables.

## 📐 Règles produit — non négociables

Le détail de chacune est dans `.claude/rules/produit.md`.

| | Règle |
|---|---|
| 1 | **Français.** Interface, messages d'erreur, emails, contenu. Rien d'anglais visible par l'utilisateur. |
| 2 | **Responsive, mobile-first.** De 320 px au desktop. Aucune fonctionnalité réservée au grand écran. |
| 3 | **Accessibilité.** Contraste AA, navigation clavier complète, label sur chaque champ, focus visible. |
| 4 | **RGPD.** Minimisation, consentement explicite, effacement possible. Aucune donnée personnelle dans les logs. |
| 5 | **Hébergement UE.** Base, stockage, logs et sauvegardes en région européenne. |
| 6 | **Aucune donnée client réelle en dev.** Les données publiques du registre (SIRENE, RNE) ne sont pas des données client ; les cartographies faites pour un client et les fichiers Basile, si. |
| 7 | **Isolation multi-tenant.** Cloisonnement au niveau base (RLS) dès la V0 : l'app sert Youno d'abord, mais sa commercialisation n'est pas exclue. |
| 8 | **Tests sur la logique métier.** Toute règle du moteur qui décide (filiale ou non, maison mère, confiance, ciblable) arrive avec ses tests. |

## ⚖️ Principes de ce projet

Les principes 1 à 5 ont été tranchés par le prototype (voir `rapport.md`), les
principes 6 et 7 par `ARCHI.md` (2026-10-06).

| | Principe |
|---|---|
| 1 | **L'IA ne décide jamais qu'une société est une filiale.** Elle propose les réglages et explique les cas douteux ; la décision vient de règles écrites, reproductibles, et chaque lien retenu porte sa preuve. |
| 2 | **Les réglages d'un groupe sont validés par un humain** avant d'être utilisés. Une seule marque fausse peut ajouter 150 fausses sociétés (Equans dans VINCI). |
| 3 | **Une cartographie ne fait aucun appel extérieur** : elle lit la base locale. Les API (INPI, Annuaire, BODACC) servent à la mise à jour de la base, pas au calcul d'une carto. |
| 4 | **Un lien n'est jamais effacé, il est fermé** : chaque lien et chaque société portent une date de début et de fin, pour savoir ce qui a changé et quand. |
| 5 | **Pas de régression silencieuse** : tout changement du moteur est mesuré sur LVMH, VINCI et CMAF avant d'être rendu. |
| 6 | **Le registre ne quitte pas le worker.** La base de l'app ne reçoit que les sociétés et liens retenus dans une carto, jamais une ligne de dirigeant personne : aucune table Postgres n'a de colonne de personne physique. |
| 7 | **La logique métier vit dans le paquet Python, testée par `pytest`.** Next.js affiche, valide la saisie et met en file ; il ne décide jamais si une société entre dans un groupe. Aucune règle du moteur dans `web/`. |

### Le contrôle constitutionnel

Garde-fous, règles produit et principes forment la **constitution du projet**.
Elle est **relue comme contrainte** avant d'écrire un PRD, une architecture,
des tâches, et à l'étape *plan* d'`apex`. Quatre verdicts : ✅ conforme ·
⚠️ conforme sous condition (la condition devient une ligne du livrable) ·
⛔ non conforme, **on n'écrit pas**, le conflit remonte à l'utilisateur ·
➖ sans objet. Amender est permis, ici, avec la raison ; contourner ne l'est
pas. Méthode : `.claude/rules/constitution.md`.

### Workflow standard d'une tâche

```
Ticket → git switch -c <user>/<id>-<slug> → code → commit sémantique
   → git push -u origin <branche> → PR vers main → CI verte → merge squash → ticket Done
```

Pas de PR nécessaire pour : lecture, exploration, question, modif locale non poussée.

---

## Autonomie — ce qu'elle implique

Trois obligations, détaillées dans [`AGENTS.md`](AGENTS.md) :

1. **Se relire.** Une tâche est finie quand les commandes de validation sont
   vertes, pas quand le code est écrit. Puis relire son diff en cherchant ce
   qui casse ailleurs.
2. **Regarder avant de supprimer.** Ouvrir le contenu, annoncer ce qui
   disparaît, dans le doute ne pas supprimer. Vaut double pour `data/` :
   19 Go qui ont pris des jours à télécharger.
3. **Ne jamais toucher à `main`.** Rien n'est poussé sans demande explicite
   dans le message courant.

## Ce que Claude ne fait jamais ici

- ❌ `git push --force` sur une branche partagée
- ❌ Commit d'un fichier `.env`, d'une clé, d'un fichier de `data/`, `basile/` ou `out/`
- ❌ Écrire un nom de dirigeant personne physique hors du calcul interne
- ❌ Dépasser le quota INPI (~10 000 fiches/jour) en lançant le moteur en mode API sans le dire
- ❌ Inventer un ID (SIREN, ticket, compte). En cas de doute : laisser vide et demander.

## Conventions

- Python 3.12, scripts courts, DuckDB et pandas sur parquet, docstring en tête
  de fichier (but, usage, entrées, sorties).
- Rapports et docs en français simple, avec des phrases courtes et des chiffres datés.
- Une décision ou un résultat important s'ajoute à `rapport.md`, sous la date du jour.
