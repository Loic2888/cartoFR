# Méthodologie de cartographie d'un groupe d'entreprises

## 1. Modèle conceptuel

Utiliser un graphe, pas un arbre. Une personne morale peut avoir plusieurs détenteurs, appartenir à un sous-groupe métier, exploiter plusieurs marques et être reliée à d'autres entités par des liens non capitalistiques.

Construire deux vues :

- **Legal Graph** : toutes les personnes morales et relations utiles à la compréhension juridique du groupe.
- **GTM Graph** : sous-ensemble des personnes morales réellement utiles comme comptes commerciaux.

## 2. PASS 0 - cadrage

Définir :

1. société ou groupe racine ;
2. date de photographie ;
3. profondeur souhaitée ;
4. juridictions couvertes ;
5. catégories explicitement exclues ;
6. règles d'arrêt ;
7. définition de `targetable`.

## 3. PASS 1 - discovery à fort recall

Pour le périmètre français, le discovery se fait d'abord avec le moteur sur registre local (`references/moteur-france.md`) : il parcourt tous les mandats entre sociétés, ce que la recherche web ne peut pas faire. Les sources ci-dessous complètent (international, marques, organigramme).

Croiser :

1. page officielle marques/métiers ;
2. rapport annuel ;
3. comptes consolidés et composition du périmètre ;
4. organigrammes officiels ;
5. rapports des sous-groupes et filiales ;
6. listes de groupe TVA ou documents fiscaux publics ;
7. régulateurs sectoriels ;
8. sites officiels des filiales ;
9. registres nationaux ;
10. GLEIF Level 2 pour l'international ;
11. agrégateurs seulement pour discovery/cross-check.

Produire deux files : `candidate_entities` et `candidate_brands`.

## 4. PASS 2 - résolution d'identité

Pour chaque personne morale candidate, chercher :

- `legal_name`
- `siren` en France
- `siret_hq`
- `hq_address`
- `lei`
- `country`
- `local_registry_id`
- `legal_status`
- `legal_form`
- `naf_code`
- alias et anciens noms

L'adresse française doit correspondre au siège rattaché au SIRET siège lors de la vérification.

## 5. PASS 3 - marque vers personne morale

Pour chaque marque/objet commercial :

1. classifier l'objet ;
2. déterminer s'il possède une personnalité morale ;
3. sinon, identifier l'entité qui l'exploite ;
4. conserver son domaine séparément ;
5. autoriser une marque à pointer vers plusieurs entités si nécessaire.

Types recommandés : `legal_entity`, `brand`, `brand_group`, `network`, `internal_network`, `offer_network`, `product_range`, `country_presence`, `joint_venture_brand`.

## 6. PASS 4 - parent direct

Pour chaque personne morale, traiter la question indépendamment : « qui la détient directement ? »

Ordre de preuve :

1. comptes annuels/consolidés de la société ou du parent ;
2. RNE, statuts et actes ;
3. rapport financier de la filiale ;
4. régulateur ;
5. GLEIF Level 2 ;
6. publication officielle du groupe ;
7. agrégateur en contrôle secondaire.

Séparer `ownership`, `control`, `consolidation`, `joint_venture`, `associate`, `branch_of`, `cooperative_affiliation`, `institutional_link`, `shared_service`, `brand_operated_by`.

## 7. PASS 5 - expansion récursive

Pour chaque personne morale résolue :

1. chercher ses filiales ;
2. résoudre leur identité ;
3. prouver leur parent direct ;
4. chercher les filiales de ces filiales ;
5. répéter jusqu'à absence de nouveau nœud ou règle d'arrêt.

Ne pas considérer une branche « faite » parce que sa marque principale a été trouvée.

## 8. PASS 6 - classification GTM

Classifier `entity_type`, par exemple :

- `operating_company`
- `holding`
- `holding_operating_group`
- `shared_service`
- `regional_bank`
- `real_estate_vehicle`
- `sci`
- `spv`
- `securitization_vehicle`
- `investment_fund`
- `association`
- `foundation`
- `branch`
- `local_cooperative`
- `unknown`

Puis attribuer :

- `targetable = yes` : entité qui mérite de pouvoir exister comme compte GTM autonome, avec activité, collaborateurs, fonctions de décision ou opérations propres.
- `targetable = no` : nœud purement structurel, véhicule, association institutionnelle, nœud virtuel ou entité sans intérêt de ciblage autonome.

Toujours renseigner `targetable_reason`.

## 9. PASS 7 - couverture

Comparer la sortie avec plusieurs univers officiels : périmètre de consolidation, marques, organigramme, régulateurs, registres.

Mesurer :

- candidats résolus ;
- identifiants légaux trouvés ;
- adresses siège trouvées ;
- parents directs vérifiés ;
- relations sourcées ;
- marques rattachées ;
- orphelins ;
- conflits ;
- nœuds targetables ;
- branches récursives complètes/incomplètes.

## 10. Hiérarchie des sources

### Tier A - preuve primaire
RNE/SIRENE/registres, comptes et rapports annuels, actes/statuts, régulateurs, GLEIF Level 2.

### Tier B - preuve groupe
Pages institutionnelles, pages marques/métiers, annuaires filiales, communiqués financiers.

### Tier C - discovery/cross-check
Pappers, OpenCorporates, bases commerciales, moteurs de recherche.

Une source Tier C ne doit pas seule créer une relation capitalistique `confirmed` lorsqu'une source primaire est accessible.
