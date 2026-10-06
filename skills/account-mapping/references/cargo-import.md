# Pousser une cartographie dans Cargo

Une fois la cartographie produite (voir `data-model.md` pour le schéma des 6 tables CSV), ce document explique comment la faire vivre dans Cargo sous forme de deux data models reliés, pour qu'elle soit interrogeable en SQL, exposée dans des plays, et tenue à jour dans le temps plutôt que figée dans un export.

Cette architecture a été rodée sur une mission à 142 comptes cartographiés en plusieurs vagues ; elle est volontairement générique ici (aucun nom de client, de compte ou d'identifiant réel — rule `client-isolation`).

## Principe : 2 modèles, pas 1

Un seul modèle plat ne marche pas : un compte et ses dizaines de filiales n'ont pas la même cardinalité ni les mêmes colonnes utiles. On sépare :

1. **Un modèle "Comptes"** — une ligne par compte racine cartographié.
2. **Un modèle "Filiales & Entités"** — une ligne par entité du graphe (racine comprise), tous comptes confondus.

### Modèle "Comptes"

Une ligne = un compte, construite à partir de la ligne racine de `companies.csv` (celle dont le `company_id` égale le `root_company_id` de `coverage.csv`) :

`account_id, company_id, legal_name, brand_name, siren, siret_hq, hq_address, domain, linkedin_url, naf_code, entity_type, targetable, targetable_reason, mapping_status, identity_confidence, last_verified_at, notes`

`account_id` est le slug technique du compte (ex. le nom de dossier de la cartographie). **Ne jamais le renommer une fois des relations Cargo posées dessus** — voir plus bas.

Si le travail se fait par vagues (priorisation, lots successifs), ajouter une colonne `priority` ou `phase` plutôt que créer un nouveau modèle par vague : un même schéma, une seule source de vérité, filtrable par phase.

### Modèle "Filiales & Entités"

Une ligne par entité de `companies.csv`, pour tous les comptes, avec les colonnes de `companies.csv` plus :

- `record_key` — identifiant composite **unique par compte** (pas forcément unique sur toute la table) : `"<account_id>::<identifiant>"`. L'`<identifiant>` suit une cascade de priorité :
  1. SIRET (ou équivalent établissement) si la valeur est effectivement numérique et au bon format — **vérifier**, ne pas faire confiance à la présence d'une chaîne non vide : une cartographie peut légitimement mettre un texte de type "non récupéré" ou "voir établissements multiples" dans ce champ quand l'identifiant unique n'existe pas, et l'utiliser tel quel casse l'unicité de `record_key` pour toutes les entités concernées.
  2. sinon SIREN (ou équivalent société mère), même vérification de format.
  3. sinon un identifiant interne de repli (`company_id` de la cartographie).
  Une colonne `identifier_type` trace quel niveau a été utilisé.
- `account_id` — clé étrangère vers le modèle Comptes.
- `direct_parent_key` — **auto-référence** vers le `record_key` d'une autre ligne du même modèle : c'est elle qui reconstruit l'arbre parent/filiale à l'intérieur d'un compte. Vide pour l'entité racine du compte (rien au-dessus dans le périmètre cartographié).
- Les attributs de la relation avec le parent direct, aplatis sur la ligne enfant plutôt que dans une table d'arêtes séparée : `relationship_type`, `ownership_pct`, `direct_parent_verified`, `relationship_confidence` (repris de `relationships.csv`, en choisissant si plusieurs liens existent le plus fort : `control` > `ownership` > `cooperative_affiliation` > reste).

**`account_id` et `direct_parent_key` répondent à deux questions différentes**, souvent confondues : `account_id` dit dans quel compte chercher (horizontal, identique pour toutes les entités d'un même compte) ; `direct_parent_key` dit à qui une entité précise est rattachée (vertical, change à chaque ligne, reconstruit l'étage exact de la hiérarchie).

## Principe de modélisation : une ligne par compte, pas de dédoublonnage global

Si une même entité réelle apparaît dans le graphe de plusieurs comptes différents (filiale commune à deux groupes cartographiés séparément), **ne pas la fusionner en une seule ligne globale**. Son rôle ou son `targetable` peut légitimement différer selon le compte (filiale réelle ciblable dans un contexte, simple référence externe non ciblée dans l'autre). Conséquence acceptée : `record_key` est unique par compte, pas forcément unique sur toute la table.

## Relations Cargo à poser

1. **Comptes.account_id → Filiales & Entités.account_id** (1 compte a plusieurs entités). Passe sans problème en CLI (`cargo-ai storage relationship set --dataset-uuid <uuid> --relationships '[...]'`).
2. **Auto-relation sur Filiales & Entités** : `direct_parent_key → record_key` (plusieurs entités peuvent avoir le même parent direct, chaque entité n'a qu'un seul parent). **Le CLI échoue systématiquement sur une relation auto-référente** (même modèle en source et en cible), avec une erreur générique `invalidRelationships`, même en renseignant tous les champs de schéma que l'API réclame (`fromPropertySlug`, `toPropertySlug`, `fromSelectedColumnSlugs`, `toSelectedColumnSlugs`). Les relations croisées entre deux modèles différents, elles, passent bien en CLI — c'est spécifiquement l'auto-référence qui pose problème. Elle ne peut être créée que manuellement dans l'UI Cargo (ouvrir le modèle, section relations, source = le modèle lui-même / colonne "Clé parent direct", cible = le modèle lui-même / colonne "Clé unique", type `n:1`).

Dans l'UI, le sélecteur de colonnes affiche le **libellé** (label), pas le slug technique : si une colonne semble introuvable, vérifier qu'on cherche le bon libellé affiché et pas le nom technique du slug.

**Alternative retenue en pratique** : plutôt que de se battre avec la fiabilité de cette auto-relation (limite CLI ci-dessus, et une relation posée en UI reste modifiable/supprimable par n'importe qui sans qu'on le sache), on peut choisir de **ne pas la poser du tout** et de la remplacer par le pattern de colonne dénormalisée ci-dessous. `direct_parent_key` reste alors une simple colonne texte sur chaque ligne (interrogeable en SQL, ex. `WHERE direct_parent_key = '...'`), sans relation Cargo formelle ni jointure cliquable dans l'UI.

## Colonne dénormalisée "Filiales" sur le modèle Comptes (pattern play) — remplace l'auto-relation

Un play qui, à chaque compte ajouté dans le modèle Comptes, va chercher toutes les entités de ce compte et les écrit en JSON directement sur la ligne du compte, dans une colonne custom (ex. `filiales`, type `any`).

Construction du play (2 nœuds après `start`) :

1. **`modelSearch`** sur le modèle Filiales & Entités, filtre `account_id is {{ nodes.start.account_id }}`, limite large (1000).
2. **`modelCustomColumn`** sur le modèle Comptes, `id = {{ nodes.start._id }}`, mapping `{ columnSlug: "filiales", value: "{{ nodes.modelSearch }}" }`.

Déclencheur du play : segment sur le modèle Comptes, `changeKinds: ["added"]`, schedule `realtime`.

**Ce que ça donne concrètement** : ce n'est pas une reconstruction de l'arbre parent/filiale, c'est **la liste à plat de toutes les entités du compte** (le filtre porte sur `account_id`, pas sur `direct_parent_key`) — racine comprise, tous niveaux confondus, pas seulement les enfants directs. Pour remonter la hiérarchie exacte (qui est filiale de qui), il faut toujours lire `direct_parent_key` ligne par ligne ou en SQL ; le play donne juste "tout ce qui appartient à ce compte", pas "qui est sous qui".

**Limite à connaître** : le déclencheur réagit à l'ajout d'une ligne **Comptes**, pas à un ajout/une modification côté Filiales & Entités. Si de nouvelles entités sont ajoutées plus tard à un compte déjà existant (correction, enrichissement différé), la colonne `filiales` de ce compte ne se rafraîchit pas toute seule — il faut retoucher la ligne Comptes ou relancer le play manuellement pour qu'elle se recalcule.

## Pièges techniques Cargo (vécus, à anticiper)

- **Modèles `defineCustom`** : les colonnes qui comptent pour l'écriture (`record create-bulk`, `record update-bulk`) sont celles déclarées dans le `config.columns` du modèle (`storage model update --config '{...}'`), **pas** celles ajoutées après coup via `storage column create` — celles-là apparaissent préfixées `custom__` en lecture (colonnes, SQL) et sont **rejetées** en écriture bulk avec une erreur "Unknown column". Pour ajouter une colonne qui doit être écrivable en masse, réécrire le `config` du modèle avec l'ancien schéma complet + la nouvelle colonne, pas `storage column create`.
- Le champ `unification` d'un modèle `defineCustom` neuf peut se mettre par défaut à `{"source":"integration"}` sans qu'on l'ait demandé — le nettoyer avec `storage model update --unification null` si besoin.
- `storage record create-bulk` / `update-bulk` : lots de 25 enregistrements, taille testée et sûre sur plusieurs milliers de lignes.
- Les requêtes SQL (`storage query execute`) doivent qualifier la table avec le slug du dataset (`FROM <dataset_slug>.<model_slug>`, ex. `FROM object.mes_comptes`), pas juste le nom du modèle seul.
- Après un import en masse, un `count(*)` peut renvoyer un total partiel avec `"isRefreshing": true` — attendre quelques secondes et refaire la requête avant de considérer le chiffre comme définitif.

## Script de transformation (principe)

Un script qui lit chaque dossier de cartographie (`companies.csv` + `relationships.csv` + `coverage.csv`), construit les deux listes de lignes (Comptes, Filiales & Entités) comme décrit ci-dessus, puis les pousse par lots de 25 via `storage record create-bulk`. Pour une mise à jour incrémentale (nouveaux comptes cartographiés après un premier import), filtrer sur les comptes pas encore présents côté Cargo plutôt que tout réinsérer, et traiter séparément le backfill d'une colonne nouvellement ajoutée (`storage record update-bulk`, par lots de 25, en gardant l'`id` Cargo de chaque ligne existante).
