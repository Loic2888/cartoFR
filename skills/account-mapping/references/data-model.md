# Modèle de données

## Format

Par défaut, un dossier de CSV : un fichier par table, nommé comme elle (`companies.csv`,
`relationships.csv`, `brands.csv`, `entities_to_resolve.csv`, `evidence_sources.csv`,
`coverage.csv`), en UTF-8 avec la virgule comme séparateur. Un export Excel en français
(point-virgule, BOM) est aussi lu par les scripts. Un classeur XLSX avec un onglet par table reste
accepté.

## Table `companies`

Champs recommandés :

- `company_id`
- `legal_name`
- `brand_name`
- `former_names`
- `siren`
- `siret_hq`
- `hq_address`
- `lei`
- `country`
- `local_registry_id`
- `legal_status`
- `legal_form`
- `naf_code`
- `entity_type`
- `operating_status`
- `targetable` : `yes | no`
- `targetable_reason`
- `domain`
- `domain_scope`
- `local_entities_count` si un niveau est volontairement agrégé
- `resolution_status`
- `identity_confidence`
- `last_verified_at`
- `identity_source_url`
- `opposition_prospection` : `True` si la société s'oppose à la réutilisation de ses données RNE pour la prospection (`diffusionCommerciale = false`)
- `notes`

## Table `relationships`

- `parent_id`
- `child_id`
- `relationship_type`
- `ownership_pct`
- `control_pct`
- `direct_parent_verified`
- `relationship_status`
- `valid_from`
- `valid_to`
- `confidence`
- `source_url`
- `source_date`
- `notes`

## Table `brands`

- `brand_id`
- `brand_name`
- `geography`
- `brand_object_type`
- `legal_entity_id`
- `legal_entity_name`
- `domain`
- `mapping_status`
- `source_url`
- `notes`

Une même marque peut nécessiter une table de liaison séparée si elle est exploitée par plusieurs personnes morales.

## Table `entities_to_resolve`

File de recherche temporaire. Champs recommandés :

- `candidate_id`
- `entity_name`
- `country`
- `discovery_source`
- `official_scope_type`
- `business_segment`
- `control_pct_if_known`
- `resolution_status`
- `next_action`
- `exclusion_reason`
- `notes`

Statuts recommandés : `needs_identity_resolution`, `needs_parent_resolution`, `needs_brand_resolution`, `resolved`, `excluded`, `not_a_legal_entity`, `duplicate`, `unresolvable`.

## Table `evidence_sources`

- `source_id`
- `source_name`
- `url`
- `source_tier`
- `usage`
- `retrieved_at`

## Table `coverage`

Inclure au minimum :

- `root_company_id` : `company_id` de la société racine, lu par `build_hubspot_import.py`
- `mapping_status`
- `recursive_expansion_complete`
- `official_scope_entities_detected`
- `companies_resolved`
- `entities_to_resolve_count`
- `brands_detected`
- `brands_mapped`
- `direct_parent_verified_pct`
- `source_primary_pct`
- `orphan_count`
- `targetable_count`

La table peut être large (une colonne par indicateur, une ligne) ou longue (colonnes
`metric` et `value`, une ligne par indicateur). Les deux sont lues.

## Fichiers dérivés pour HubSpot

Produits par `scripts/build_hubspot_import.py`, jamais à la main. Règles de calcul : section
« Import HubSpot » de `SKILL.md`.

`hubspot_import.csv` reprend les colonnes de `companies` pour les sociétés à importer, et ajoute :

- `hubspot_level` : ordre d'import, 0 d'abord
- `hubspot_parent_count` : nombre de parents dans HubSpot
- `hubspot_primary_parent_id` : le parent qui prend le lien natif « Parent company », vide sans gagnant net
- `hubspot_notes` : racine du groupe, raison de l'absence de parent ou de parent principal

`hubspot_associations.csv` : une ligne par lien société → parent.

- `child_level`, `child_company_id`, `child_legal_name`, `child_siren`
- `parent_company_id`, `parent_legal_name`, `parent_siren`
- `ownership_pct`, `control_pct` : ceux du premier lien (la part que détient la holding sautée, le cas échéant)
- `primary_parent` : `yes | no`
- `via` : sociétés non importées sautées entre l'enfant et ce parent
