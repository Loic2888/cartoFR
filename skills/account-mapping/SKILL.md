---
name: account-mapping
description: Cartographier un groupe d'entreprises ou un compte complexe à partir d'une société racine, en reconstruisant les entités juridiques, filiales et sous-filiales, relations de détention/contrôle, marques, réseaux et présences pays, puis en distinguant le Legal Graph du GTM Graph. Utiliser pour des demandes de cartographie de compte, corporate family tree, recherche de filiales, mapping de groupe, résolution marque vers personne morale, TAM mapping multi-entités ou audit d'exhaustivité d'une cartographie existante. Ne pas utiliser pour retrouver le SIRET d'une liste d'entreprises sans lien de groupe (voir find-siret), ni pour scorer ou prioriser des comptes (voir icp-persona).
metadata:
  version: 2.0.0
---

# Cartographie de compte

Construire un graphe sourcé et récursif. Ne jamais réduire par défaut un groupe complexe à un arbre simple `maison mère -> filiales`.

Sur une mission client, ouvrir d'abord `clients/<slug>/CLAUDE.md` et ranger la cartographie dans `clients/<slug>/04-icp-persona-scoring/` (convention de `clients/CLAUDE.md`). Une cartographie faite pour un client ne sert jamais d'exemple nommé pour un autre (rule `client-isolation`).

## Pour la France : le moteur sur registre local (v2)

Pour le périmètre français, ne pas chercher les filiales sur le web société par société : la recherche web trouve surtout les sociétés connues (de l'ordre d'une sur quatre à une sur neuf sur les cartographies v1). Utiliser le moteur de `scripts/moteur_france/`, qui parcourt une copie locale du registre national (1,6 million de liens "société A dirige société B") et applique des règles de preuve écrites.

Résultats mesurés le 2026-10-06 contre des cartographies de référence : LVMH 90 % des sociétés retrouvées, VINCI 81 %, Crédit Mutuel Alliance Fédérale 83 %, chaque groupe en quelques minutes. Détail des règles et des pièges : `references/moteur-france.md`.

Le web reste utile pour : les filiales étrangères, les pourcentages de détention, le site et la page LinkedIn, et la préparation des réglages (marques, maisons).

## Workflow obligatoire

1. Définir la racine (SIREN de la tête), la date de photographie, les juridictions, les exclusions et règles d'arrêt.
2. **Préparer les réglages du groupe** (`config/<groupe>.json`) : marques sûres, marques ambiguës (prénoms, mots courants, sigles), holdings et familles à exclure, organigramme public avec le nom légal exact de chaque maison. Les faire **valider par un humain** : une seule marque fausse peut ajouter 150 fausses sociétés.
3. Lancer le moteur France (France) et un discovery multi-source à fort recall (international).
4. Résoudre chaque entité en personne morale exacte.
5. Résoudre séparément chaque marque, réseau, offre ou présence pays vers sa ou ses personnes morales.
6. Prouver le parent juridique direct de chaque personne morale (le moteur lit le mandat le plus fort au registre et note la confiance A, B ou C).
7. Descendre récursivement dans les filiales et sous-filiales jusqu'à absence de nouveaux nœuds ou règle d'arrêt explicite (le moteur boucle jusqu'au point fixe).
8. Classifier le Legal Graph et le GTM Graph.
9. Contrôler la couverture contre des sources officielles indépendantes, et **vérifier un échantillon** de 20 à 30 sociétés retenues hors de toute référence.
10. Conserver les éléments encore non résolus dans `entities_to_resolve`, sans les présenter comme des filiales confirmées.

Lire `references/moteur-france.md` avant de lancer le moteur France.
Lire `references/methodology.md` pour les règles détaillées et la hiérarchie des sources.
Lire `references/data-model.md` avant de produire un fichier tabulaire.
Lire `references/completeness.md` avant d'annoncer qu'une cartographie est exhaustive ou terminée.

## Règles non négociables

- Utiliser le web pour les informations contemporaines et sourcer chaque relation importante.
- Distinguer `legal entity`, `brand`, `network`, `offer`, `country presence` et `branch`.
- Une page de marques sert au discovery, jamais seule à prouver un lien capitalistique direct.
- Une présence dans un périmètre de consolidation prouve une relation de consolidation, pas nécessairement le parent juridique direct.
- Ne jamais inventer un parent pour faire rentrer le groupe dans un arbre.
- Supporter les relations multi-parent, joint ventures, associations, affiliations mutualistes et liens institutionnels.
- Pour la France, résoudre en priorité `SIREN`, `SIRET siège`, `adresse du siège`, statut, forme juridique et NAF via RNE/SIRENE/Annuaire des Entreprises lorsque disponibles.
- Pour l'international, utiliser le registre local et le LEI quand disponible.
- Conserver holdings, SCI, SPV et véhicules nécessaires au chemin juridique dans le Legal Graph, même s'ils sont exclus du GTM Graph.
- `targetable` doit être strictement `yes` ou `no`. Utiliser `targetable_reason` pour expliquer la décision. Ne pas utiliser `conditional`.
- La cible GTM par défaut répond à la question : « cette personne morale mérite-t-elle d'exister comme compte ciblable ? ». Une campagne spécifique peut ensuite appliquer ses propres filtres ICP.
- Si une catégorie volontairement exclue comporte beaucoup d'entités sans valeur GTM, l'agréger au parent avec un compteur sourcé plutôt que de créer tous les nœuds.
- **Licence INPI** : les dirigeants personnes physiques servent seulement de preuve pendant le calcul (dirigeants communs). Ne jamais écrire un nom de personne dans une sortie. Marquer les sociétés qui s'opposent à la prospection (`diffusionCommerciale = false`, colonne `opposition_prospection`).
- Un nom de famille, un prénom ou un sigle n'est pas une société : "NOM Prénom" au BODACC est une personne, "SEPHORA" peut être un prénom, "ASF" ou "VINCI" ont des homonymes. Ces marques exigent toujours une deuxième preuve.

## Sorties recommandées

Produire au minimum :

- `companies`
- `relationships`
- `brands`
- `entities_to_resolve`
- `evidence_sources`
- `coverage`

Format par défaut : un dossier de CSV, un fichier par table nommé comme elle (`companies.csv`, `relationships.csv`…), en UTF-8 avec la virgule comme séparateur. Un classeur XLSX avec un onglet par table reste accepté. Renseigner `root_company_id` dans `coverage` : c'est la société racine du cadrage.

`entities_to_resolve` est une file de recherche, pas une partie confirmée du graphe. Une cartographie finalisée ne doit y laisser que des éléments explicitement `excluded`, `not_a_legal_entity`, `duplicate` ou `unresolvable`, avec une raison.

## Contrôle qualité

Avant livraison :

- vérifier l'unicité des identifiants de nœuds ;
- vérifier que tous les `parent_id` et `child_id` confirmés existent dans `companies` ;
- vérifier `targetable in {yes,no}` ;
- vérifier la présence d'une source pour toute relation `confirmed` ;
- vérifier que les marques non juridiques ne sont pas transformées en filiales ;
- compter les nœuds orphelins ;
- compter les marques sans personne morale résolue ;
- mesurer la couverture du périmètre officiel ;
- lister explicitement les branches dont l'expansion récursive n'est pas terminée.

Exécuter `python3 scripts/validate_mapping.py <dossier_csv | fichier.xlsx>` avant livraison et corriger les erreurs bloquantes. Le script lit un dossier de CSV sans dépendance ; un fichier XLSX demande `openpyxl`.

## Lancer le moteur France

Depuis un dossier de travail qui contient une copie de `scripts/moteur_france/` (avec ses dossiers `data/`, `config/`, `out/`). Installation et données : `references/moteur-france.md`.

```bash
python brand_scan.py config/<groupe>.json        # candidates par le nom des marques (base SIRENE)
python engine.py config/<groupe>.json            # boucle complète, écrit out/<groupe>_entites.csv
python to_skill_tables.py config/<groupe>.json   # convertit au format des 6 tables de ce skill
python ../scripts/validate_mapping.py out/<groupe>_skill
python ../scripts/build_hubspot_import.py out/<groupe>_skill
```

Si une cartographie de référence existe (Basile, Cargo), `compare.py` mesure combien de ses sociétés on retrouve et lesquelles on ajoute.

## Import HubSpot

`companies` ne porte pas les parents : ils se calculent depuis `companies` et `relationships`, en retirant ce qui ne sera pas dans HubSpot.

```bash
python3 scripts/build_hubspot_import.py <dossier_csv | fichier.xlsx>
```

Le script refuse une cartographie qui a des erreurs bloquantes, puis écrit deux fichiers :

- `hubspot_import.csv` : une ligne par société à créer, avec `hubspot_level`, `hubspot_parent_count`, `hubspot_primary_parent_id` et `hubspot_notes` ;
- `hubspot_associations.csv` : une ligne par lien société → parent, avec les SIREN des deux côtés, les pourcentages, `primary_parent` et `via` (sociétés non importées sautées).

Règles appliquées :

1. Sont importées les sociétés `targetable = yes`, plus la racine même si elle ne l'est pas, pour que tout le groupe se rattache à une seule tête.
2. Aucune société non exploitable commercialement (holding, SCI, SPV, véhicule) n'est importée. Elle est sautée : sa filiale se rattache à la société importée située au-dessus.
3. Seuls les liens `confirmed` où une société détient ou contrôle l'autre font un parent : `ownership`, `control`, `joint_venture`, `associate`, `branch_of`. Une présence dans les comptes consolidés, une marque exploitée, un service partagé ou un lien institutionnel n'en font pas : la société sort sans parent avec la mention « parent direct à prouver ».
4. Une société détenue par plusieurs sociétés importées a plusieurs parents. Le parent principal (`primary_parent = yes`) a le plus fort `control_pct`, puis le plus fort `ownership_pct`. Sans gagnant net (joint venture 50/50, pourcentages manquants), aucun parent n'est principal.
5. `hubspot_level` vaut 0 sans parent, sinon 1 + le plus haut niveau de ses parents.

Pour importer :

1. Créer ou mettre à jour les sociétés de `hubspot_import.csv` avec le SIREN comme clé, dans une propriété à valeur unique, et non le domaine. À l'import, HubSpot dédoublonne les sociétés sur le domaine : des filiales qui partagent le domaine du groupe seraient fusionnées.
2. Créer les liens de `hubspot_associations.csv`. HubSpot n'accepte qu'un seul lien natif « Parent company » par société : le réserver à `primary_parent = yes`, et porter les autres parents avec un libellé d'association société-société personnalisé (ex. « Actionnaire »), disponible en Pro ou Enterprise et applicable à plusieurs sociétés.
3. Relire avant l'import les sociétés sans parent et les sociétés sans parent principal que le script liste.

Des sociétés importées qui se détiennent mutuellement (participations croisées) bloquent le script : garder le lien majoritaire en `confirmed`, déclasser l'autre, relancer.

## Import Cargo

Pour faire vivre une cartographie dans Cargo (interrogeable en SQL, exposée dans des plays, tenue à jour dans le temps) plutôt que la laisser en export figé : deux data models reliés, un "Comptes" (une ligne par compte racine) et un "Filiales & Entités" (une ligne par entité, tous comptes confondus, avec une auto-relation qui reconstruit l'arbre parent/filiale).

Lire `references/cargo-import.md` avant de pousser une cartographie dans Cargo : schéma des deux modèles, principe "une ligne par compte" (pas de dédoublonnage global d'une entité partagée entre deux comptes), relations à poser et limite connue du CLI sur l'auto-relation, pattern de colonne dénormalisée par play, pièges techniques `defineCustom`.

---

## Related Skills

- **find-siret** : pour résoudre en masse le SIREN et le SIRET siège des entités candidates françaises
- **icp-persona** : pour filtrer ensuite le GTM Graph selon l'ICP d'une campagne
- **basile-b2b-search** : pour trouver des comptes B2B à cartographier
- **enrich-company** : pour enrichir une entité targetable depuis sa page entreprise LinkedIn
- **data-quality-audit** : pour confronter la cartographie aux sociétés déjà présentes dans le CRM du client
