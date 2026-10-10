# Registre des traitements — cartoFR

Écrit le 2026-10-08 (T031, règle produit 4). Il décrit ce que l'app fait des
données personnelles **aujourd'hui** (V1, usage interne Youno) et ce qui est
prévu (P2). Il se met à jour avec chaque tâche qui ajoute une donnée, un
journal, un sous-traitant ou une durée.

Ce qui n'est pas encore tranché est écrit **« à décider »** et repris dans la
liste de la fin. Rien n'y est inventé : une case vide vaut mieux qu'une durée
fausse. La relecture juridique (licence INPI, RGPD) est prévue avant toute
commercialisation, pas avant l'usage interne (PRD, décidé le 2026-10-06).

## Le responsable

- **Responsable de traitement** : Youno, qui exploite l'app pour ses missions.
  Coordonnées et contact RGPD : à décider.
- **Hébergement** : un VPS Hetzner CX43 en Allemagne (Nuremberg ou
  Falkenstein), UE. Base de l'app, registre, journaux et sauvegardes y sont
  tous (ARCHI, ADR-003).

## Vue d'ensemble

| # | Traitement | Personnes concernées | Données | Durée de conservation | Lieu | Sous-traitants |
|---|---|---|---|---|---|---|
| 1 | Registre des sociétés, calcul des cartos | Dirigeants personnes physiques de sociétés françaises | Nom, prénoms, mois et année de naissance, rôle, dates de mandat | Le temps du registre ; lignes fermées gardées : **à décider** | VPS Hetzner (DE) | Hetzner |
| 2 | Comptes des consultants | Consultants des organisations clientes | Adresse e-mail, dates de connexion, appartenance et rôle | Jusqu'à la suppression du compte ; comptes inactifs : **à décider** | VPS Hetzner (DE) | Hetzner, Brevo |
| 3 | Journaux techniques | Aucune par construction | Aucune donnée personnelle (vérifié par test) | Rotation : 3 fichiers de 10 Mo par service ; journal d'audit GoTrue : **à décider** | VPS Hetzner (DE) | Hetzner |
| 4 | Sauvegardes | Celles des traitements 1 et 2 | Copie du serveur et de la base de l'app | 7 jours glissants (Hetzner) ; `pg_dump` quotidien : **à décider** | Hetzner (DE) | Hetzner |
| 5 | Proposition de réglages par IA (P2) | Aucune : données de sociétés seulement | Nom du groupe ; dénomination, sigle et SIREN de la tête et des plus grosses sociétés du groupe (150 au plus) | Aucune chez le fournisseur du modèle (routage `zdr`) ; chez OpenRouter : **à décider** | OpenRouter puis fournisseur du modèle, États-Unis | OpenRouter, Anthropic |

## 1. Registre des sociétés et calcul des cartos

- **Finalité** : reconstruire l'arbre d'un groupe d'entreprises. Un dirigeant
  personne commun à deux sociétés est un indice qu'elles sont du même groupe
  (holding familiale, dirigeants communs). C'est son seul usage.
- **Base légale** : proposée, intérêt légitime (art. 6.1.f) sur des données
  publiques du registre (RNE, INPI ; SIRENE, INSEE), dans les limites de la
  licence INPI. À valider par la relecture juridique.
- **Données** : table `dirigeants_personnes` du registre DuckDB
  (`registre.duckdb`, sur le worker) : une clé « NOM|PRÉNOMS|AAAA-MM » (nom,
  prénoms, mois et année de naissance), le SIREN de la société, le rôle, les
  dates de début et de fin du mandat. Aussi, le cache des réponses de l'API
  INPI dans `data/`, qui contient les mêmes informations.
- **Ce qui n'en sort jamais** (garde-fou 6, principe 6) : aucun nom de personne
  dans une carto, un export, un journal, une table Postgres ou l'interface.
  Vérifié par `worker/tests/test_aucune_personne.py` (sorties) et
  `worker/tests/test_journaux.py` (journaux), et par l'absence de toute colonne
  de personne dans le schéma Postgres (`worker/tests/test_rls.py`). Les noms de
  famille exclus des réglages ne sont gardés qu'en empreinte HMAC.
- **Ce qui sort** : la dénomination officielle d'une société (SIRENE), même si
  elle contient le nom de son fondateur (« Jean Dupont SAS ») : c'est une
  donnée de société (décision du 2026-10-07, T023). Les sociétés qui
  s'opposent à la prospection (`diffusionCommerciale = false`) sont marquées
  `opposition_prospection`, jamais présentées comme démarchables.
- **Durée** : le registre vit tant que l'app vit. Un mandat terminé n'est pas
  effacé mais fermé (date de fin, principe 4) : combien de temps garder un
  mandat fermé, **à décider**.
- **Lieu** : disque du VPS Hetzner (Allemagne), volume du worker seulement.
- **Sous-traitants** : Hetzner (hébergement). L'INPI et l'INSEE sont des
  sources, pas des sous-traitants.
- **Droits des personnes** : opposition et effacement d'un dirigeant dans le
  registre : procédure **à décider** (la synchro le réintroduirait depuis la
  source s'il y figure encore).

## 2. Comptes des consultants

- **Finalité** : donner accès à l'app aux consultants d'une organisation
  cliente, cloisonnés par organisation (RLS).
- **Base légale** : exécution du contrat entre Youno (ou l'organisation
  cliente) et le consultant (art. 6.1.b).
- **Données** : seule l'adresse e-mail est demandée (minimisation : ni nom, ni
  fonction). GoTrue (`auth.users`) garde aussi les dates de création,
  d'invitation et de dernière connexion, et les sessions. La base de l'app
  (`membres`) garde l'organisation et le rôle, avec l'identifiant du compte,
  jamais l'adresse. `groupes.cree_par`, `reglages.cree_par` et
  `reglages.valide_par` gardent l'identifiant de l'auteur, jamais son adresse.
- **Durée** : jusqu'à la suppression du compte. Un compte jamais activé
  (invitation non acceptée) ou inactif depuis longtemps : durée **à décider**,
  et purge à confier à une tâche.
- **Suppression** : un membre supprime lui-même son compte depuis la page
  « Mon compte » (`/compte`), en tapant SUPPRIMER. GoTrue efface la ligne
  `auth.users`, et la base fait le reste (migrations 0001, 0002, 0005) :
  - ses appartenances disparaissent ;
  - ses groupes, réglages et cartos restent à l'organisation, sans aucune
    référence à lui (`cree_par` et `valide_par` passent à nul) ;
  - **dernier administrateur** : s'il était le seul administrateur d'une
    organisation qui a encore des membres, le membre le plus ancien devient
    administrateur (ancienneté d'appartenance, puis identifiant pour
    départager). La suppression n'est donc jamais bloquée, et l'organisation
    n'est jamais laissée sans administrateur. Testé par
    `worker/tests/test_suppression_compte.py` ;
  - **dernier membre** : l'organisation, ses groupes et ses cartos sont gardés,
    sans membre. Seul l'opérateur peut y inviter quelqu'un ou la supprimer.
- **Lieu** : base Postgres du VPS Hetzner (Allemagne).
- **Sous-traitants** : Hetzner (hébergement) ; Brevo (France), qui reçoit
  l'adresse e-mail pour envoyer les liens de connexion et les invitations.
  Durée de conservation des e-mails envoyés chez Brevo : **à vérifier** dans
  son contrat de sous-traitance.

## 3. Journaux techniques

- **Finalité** : exploiter et dépanner l'app (file de travaux, synchro,
  recherche, erreurs).
- **Base légale** : intérêt légitime (sécurité et bon fonctionnement).
- **Données** : aucune donnée personnelle par construction (règle produit 4).
  Le worker ne journalise que des identifiants techniques, des volumes, des
  durées et des noms de classe d'erreur ; la route de recherche ne journalise
  pas la saisie ; Next.js ne journalise que des codes d'erreur. Caddy n'a pas
  de journal d'accès (il contiendrait les adresses IP). Vérifié pour le worker
  par `worker/tests/test_journaux.py` : aucune adresse e-mail ni nom de
  personne du registre de test, journaux au niveau DEBUG.
- **Exception connue** : GoTrue tient un journal d'audit en base
  (`auth.audit_log_entries`) qui peut contenir l'adresse e-mail et l'adresse IP
  des connexions. Il n'est pas lié au compte par clé étrangère : il **reste
  après la suppression du compte**. Purge ou durée de conservation : **à
  décider**. Les journaux du conteneur GoTrue lui-même : contenu **à vérifier**.
- **Durée** : journaux Docker en rotation, 3 fichiers de 10 Mo par service
  (`infra/docker-compose.yml`). La durée réelle dépend du volume.
- **Lieu** : VPS Hetzner (Allemagne). Aucun service de journaux externe (pas de
  Sentry en V1).

## 4. Sauvegardes

- **Finalité** : restaurer l'app après une panne ou une erreur.
- **Base légale** : intérêt légitime (continuité du service).
- **Données** : sauvegardes Hetzner du serveur entier (base de l'app, comptes
  GoTrue, registre et son cache), et un `pg_dump` quotidien de la base de
  l'app, gardé sur le serveur (prévu par ARCHI ; script pas encore écrit
  dans `infra/` au 2026-10-08).
- **Durée** : 7 jours glissants pour les sauvegardes Hetzner. Pour les
  `pg_dump` : **à décider** (aucune rotation écrite à ce jour). Un compte
  supprimé reste donc dans les sauvegardes jusqu'à leur expiration ; il n'est
  pas restauré, sauf restauration complète de la base, auquel cas les
  suppressions des derniers jours sont à rejouer (procédure **à décider**).
- **Lieu** : Hetzner, Allemagne.
- **Sous-traitants** : Hetzner.

## 5. Proposition de réglages par IA (P2)

- **Finalité** : proposer les marques et exclusions d'un groupe, que l'humain
  valide ensuite (principes 1 et 2).
- **Base légale** : intérêt légitime ; aucune donnée personnelle envoyée.
- **Données envoyées** : données de sociétés publiques seulement : le nom du
  groupe, et la dénomination, le sigle et le SIREN de la tête et des plus
  grosses sociétés du groupe au registre (150 au plus, T039). **Jamais un
  nom de personne**, ni dirigeant,
  ni consultant (condition R5 de l'architecture ; vérifié par
  `worker/tests/ia/test_proposition.py`).
- **Passage** : OpenRouter (passerelle), qui transmet au fournisseur du modèle
  (Anthropic par défaut) et exécute lui-même la recherche et la lecture web.
  Décidé le 2026-10-09 (T037).
- **Durée** : chaque requête exige un fournisseur sans conservation ni
  collecte (`provider.zdr`, `data_collection: deny`). La conservation chez
  OpenRouter lui-même : **à décider** (à lire dans ses conditions et à régler
  dans les paramètres de confidentialité du compte).
- **Lieu** : OpenRouter et Anthropic, États-Unis : transfert hors UE,
  acceptable seulement parce qu'aucune donnée personnelle n'y part. Le routage
  UE d'OpenRouter est réservé aux comptes entreprise.
- **Sous-traitants** : OpenRouter, Anthropic (ou le fournisseur du modèle
  choisi par `CARTOFR_MODELE_IA`).

## Hors de l'app : le prototype

Les scripts de la racine (prototype) tournent sur un poste de développement,
avec `data/` (registre et cache INPI, mêmes dirigeants que le traitement 1),
`out/` (cartos faites pour des clients) et `basile/` (références Basile). Rien
de cela n'entre dans git. Lieu du poste, durée de conservation de `out/` et de
`basile/` : **à décider**.

## À décider

1. Coordonnées du responsable de traitement et contact RGPD.
2. Base légale du traitement 1 (intérêt légitime proposé), à valider par la
   relecture juridique.
3. Durée de conservation des mandats fermés dans `dirigeants_personnes`.
4. Procédure d'opposition et d'effacement d'un dirigeant dans le registre.
5. Durée de conservation des comptes jamais activés ou inactifs, et la tâche
   qui les purge.
6. Durée de conservation du journal d'audit GoTrue (`auth.audit_log_entries`),
   et sa purge à la suppression d'un compte.
7. Contenu des journaux du conteneur GoTrue (à vérifier).
8. Durée de conservation des e-mails envoyés chez Brevo (à vérifier dans son
   contrat).
9. Rotation des `pg_dump` quotidiens, et la procédure qui rejoue les
   suppressions de comptes après une restauration.
10. Durée de conservation chez OpenRouter (P2) et réglage de confidentialité du compte
    (journalisation des requêtes désactivée, ZDR au niveau du compte).
11. Ce que deviennent l'organisation et ses cartos à la fin d'un contrat
    client, et après le départ de son dernier membre.
12. Lieu et durées du poste de développement du prototype (`data/`, `out/`,
    `basile/`).
