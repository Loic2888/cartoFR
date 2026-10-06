# Une app SaaS de cartographie de groupe : comment la construire

Date : 2026-10-05. Base : le prototype de `zyzx/` (voir `rapport.md`).

## 1. Ce que fait l'app, en une phrase

L'utilisateur tape le nom ou le SIREN d'un groupe. L'app rend l'arbre de toutes ses sociétés en France : maison mère, filiales, sous-filiales, avec pour chacune son SIREN, son SIRET, son site, sa page LinkedIn, la preuve du lien, une note de confiance (A, B, C) et si on peut la démarcher.

## 2. Ce que le prototype a déjà prouvé

- **La méthode marche.** Sur LVMH, on retrouve 158 des 172 sociétés de Basile (92 %), avec 16 en plus à vérifier, en quelques heures et uniquement avec des données publiques gratuites.
- **Le même programme sert pour tous les groupes.** Seul un petit fichier de réglages change : les marques, les holdings à exclure, la liste publique des maisons.
- **Il faut une validation humaine** de ce fichier de réglages : une erreur (par exemple "Fresh and Good" au lieu de Fresh SAS) fait entrer de fausses sociétés.
- **Lire les registres société par société ne passe pas à l'échelle.** L'INPI limite à environ 10 000 fiches par jour et par compte : un seul groupe comme VINCI prend deux jours.

C'est ce dernier point qui décide de l'architecture.

## 3. L'idée centrale : avoir sa propre copie du registre

Le prototype interroge les sources à chaque cartographie. Une app ne peut pas faire ça : avec dix clients le même jour, le quota INPI est épuisé avant midi.

À la place, l'app tient **sa propre base de toutes les sociétés françaises et de tous les liens entre elles**, mise à jour chaque jour. Une cartographie devient alors un simple parcours de cette base, en quelques secondes, sans aucun appel extérieur.

### Les sources à copier

| Source | Ce qu'elle donne | Comment la récupérer | Mise à jour |
| --- | --- | --- | --- |
| SIRENE (INSEE) | Toutes les sociétés : nom, adresse, activité, effectif, statut | Fichiers complets gratuits sur data.gouv.fr (déjà téléchargés dans le prototype) | Mensuelle, plus une API pour les changements du jour |
| RNE (INPI) | Les dirigeants de chaque société, dont les sociétés qui en dirigent d'autres, avec leur rôle | Registre complet par SFTP (accès à débloquer), puis l'API "diff" de l'INPI pour les changements du jour | Quotidienne |
| BODACC | Les annonces officielles (nominations, départs, fusions), utiles pour l'historique | Export complet gratuit (opendatasoft) | Quotidienne |
| Annuaire des entreprises (État) | Recherche "sociétés dirigées par X", déjà utilisée par le prototype | API gratuite ; à vérifier s'il existe un export complet | Quotidienne |
| Sites web et LinkedIn | Domaine et page de chaque société | Recherche web et fournisseur de données (Basile, Cargo) | À la demande |

**Le point bloquant à lever en premier : l'accès SFTP au registre INPI complet.** Sans lui, il faudrait reconstruire le registre fiche par fiche, au rythme de 10 000 par jour, soit des années pour 7,8 millions de sociétés actives. Avec lui, tout le reste est simple. Si le SFTP reste refusé, plan B : un fournisseur qui revend le registre complet avec les mandats (Pappers, par exemple), à chiffrer.

### Le cœur de la base : la table des liens

Une seule table fait tout le travail : **une ligne par lien "société A dirige société B"**, avec le rôle (président, gérant, associé, administrateur…), la source, la date et si le lien est encore actif. Pour toute la France, c'est de l'ordre de quelques millions de lignes : une base classique (PostgreSQL) le gère sans difficulté.

Avec cette table, "toutes les sociétés que LVMH dirige, puis celles qu'elles dirigent, et ainsi de suite" devient une seule requête, au lieu de milliers d'appels d'API.

## 4. Comment l'app fait une cartographie

1. **L'utilisateur donne le groupe** (nom ou SIREN de la tête).
2. **Un agent IA prépare les réglages** : il lit le site du groupe et son rapport annuel, puis propose la liste des marques (sûres ou ambiguës), les maisons avec leur nom légal exact, et les holdings familiales à exclure.
3. **L'utilisateur valide les réglages** à l'écran : il coche, corrige, ajoute. C'est l'étape qui fait passer la qualité de 77 % à 92 % dans le prototype : elle doit être simple et rapide.
4. **Le moteur tourne sur la base locale** : marques, deuxième preuve, descente par les mandats, adresses du groupe, boucle jusqu'à ce que plus rien ne bouge. Quelques secondes à quelques minutes.
5. **Le moteur pose les cas douteux à part** (confiance C, sociétés étrangères, participations sans contrôle). L'agent IA peut préparer pour chacun une fiche "pour ou contre" lisible.
6. **L'utilisateur voit le résultat** : l'arbre dépliable, la liste des sociétés, la preuve de chaque lien en clair.
7. **L'utilisateur exporte** : CSV, import HubSpot (les scripts existent déjà dans le skill account-mapping), ou poussée dans Cargo (deux modèles Comptes et Filiales et Entités).

### Ce que l'IA fait, et ce qu'elle ne fait pas

- **L'IA fait** : proposer les réglages, résumer les cas douteux, expliquer une preuve, chercher le site et la page LinkedIn.
- **L'IA ne fait pas** : décider qu'une société est une filiale. Ça reste des règles écrites et vérifiables (celles du prototype). Une décision de l'IA ne serait ni reproductible, ni explicable à un client.

## 5. Ce que l'app peut vendre en plus d'une carto figée

- **Le suivi dans le temps.** La base est mise à jour chaque jour : l'app peut prévenir quand un groupe suivi crée une filiale, en rachète une, change de dirigeant ou ferme une société. C'est un signal commercial (nouvelle entité, nouveau décideur).
- **La mise à jour du CRM.** Pousser les nouvelles filiales et les liens dans HubSpot ou Cargo sans refaire d'import.
- **La carto en masse.** Cartographier d'un coup toute une liste de comptes cibles (par exemple les 143 comptes Skillup), au lieu d'un groupe à la fois.

## 6. Les règles légales à respecter

Ce n'est pas un détail : une app qui redistribue ces données devient un "rediffuseur", avec des obligations.

- **Licence INPI.** Les données sur les personnes (dirigeants) ne doivent pas servir à la prospection. L'app s'en sert uniquement comme preuve pendant le calcul (dirigeants communs) et ne les affiche jamais. À faire relire par un juriste.
- **Opposition à la prospection.** Le registre marque les sociétés qui refusent que leurs données servent à la prospection (`diffusionCommerciale`). Sur LVMH, c'est 75 sociétés sur 174. L'app doit les marquer clairement, et le contrat client doit dire comment les traiter.
- **Sociétés non diffusibles (INSEE).** Certaines sociétés ne peuvent pas être redistribuées par un tiers. L'app doit les filtrer.
- **RGPD.** Même sans afficher les noms, la base contient des données personnelles (dirigeants) : registre des traitements, durée de conservation, sécurité, information.

## 7. Architecture technique proposée

| Brique | Rôle | Choix proposé |
| --- | --- | --- |
| Base de données | Sociétés, liens, adresses, historique | PostgreSQL (liens et résultats) et DuckDB ou Parquet pour les gros fichiers de chargement |
| Chargement quotidien | Télécharger SIRENE, RNE, BODACC, mettre à jour la table des liens | Tâches planifiées en Python (le code du prototype est déjà en Python) |
| Moteur | Les règles de cartographie | Le `engine.py` du prototype, réécrit pour lire la base locale au lieu des API |
| Agent IA | Proposer les réglages, résumer les cas douteux | API Claude, avec recherche web |
| File de travaux | Lancer les cartos en arrière-plan, une par client | File de tâches simple (par exemple une table "travaux" dans PostgreSQL au début) |
| Interface | Saisie, validation des réglages, arbre, exports | Application web (par exemple Next.js), avec connexion par compte |
| Exports | CSV, HubSpot, Cargo | Scripts du skill account-mapping, puis connecteurs directs |

Le volume reste modeste : environ 30 millions de sociétés dans SIRENE, dont 7,8 millions actives, et quelques millions de liens. Un seul serveur suffit pour démarrer.

## 8. Plan de construction, étape par étape

1. **Débloquer l'accès SFTP au registre INPI** ou, à défaut, chiffrer un fournisseur du registre complet. Sans cette étape, rien d'autre ne passe à l'échelle.
2. **Construire la base locale** : charger SIRENE et le registre complet, construire la table des liens, puis la mise à jour quotidienne.
3. **Brancher le moteur du prototype sur la base locale**, et vérifier qu'on retrouve au moins les résultats du prototype sur LVMH (92 % de Basile) et VINCI.
4. **Écrire l'agent qui propose les réglages**, et mesurer combien de corrections un humain doit faire par groupe.
5. **Faire l'interface minimale** : saisie du groupe, validation des réglages, arbre, export CSV.
6. **Ajouter les exports HubSpot et Cargo** (le code existe déjà en partie).
7. **Tester sur 10 groupes de formes différentes** (marques connues, BTP, banque mutualiste, groupe familial, filiale de groupe étranger) avec un client pilote, en comparant à une carto faite à la main.
8. **Ajouter le suivi dans le temps** (alertes nouvelles filiales).
9. **Valider le cadre légal** avec un juriste avant toute ouverture à des clients externes.

## 9. Les risques

- **Accès aux données.** Si l'INPI ne donne pas le SFTP, il faut un fournisseur payant, ce qui change l'économie du produit.
- **Groupes étrangers.** Les registres français ne voient que les filiales immatriculées en France. Pour les filiales étrangères, il faudrait le LEI (base GLEIF, gratuite) et les rapports annuels : c'est une deuxième étape.
- **Pourcentages de détention.** Le registre dit qui dirige, pas qui possède combien. Les pourcentages ne se trouvent que dans les comptes et rapports annuels : à traiter plus tard, avec l'IA.
- **Concurrence.** Basile fait déjà ce travail à la main ("Basile Advanced"), et des acteurs comme Pappers ont des vues de liens entre sociétés. L'avantage à viser : la validation rapide des réglages, la preuve de chaque lien en clair, et le suivi dans le temps branché au CRM.
- **Qualité sur les cas difficiles.** Holdings familiales, participations croisées, sociétés civiles personnelles de cadres : les règles du prototype les gèrent, mais il faudra une file "à vérifier" visible pour l'utilisateur.

## 10. Questions à trancher

- **Pour qui** : un outil interne Youno pour les missions clients, ou un produit vendu à des équipes commerciales ?
- **Données de contact** : rester sur l'arbre des sociétés, ou ajouter ensuite les décideurs (via Basile ou Cargo), avec les contraintes légales que ça implique ?
- **Fournisseur de données** : tout reconstruire à partir des sources publiques, ou acheter le registre complet pour aller plus vite ?
