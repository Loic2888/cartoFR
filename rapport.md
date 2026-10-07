# Cartographie de compte automatique : rapport

Date : 2026-10-03. Dossier de travail : `zyzx/`.

## Ce qu'on veut faire

- À partir du nom d'un groupe (ex. LVMH, VINCI), retrouver automatiquement toutes ses sociétés en France : la maison mère, les filiales et les sous-filiales.
- Pour chaque société : nom, SIREN, SIRET du siège, site web, page LinkedIn, de qui elle dépend, et si on peut la démarcher (Oui ou Non, avec la raison).
- Chaque lien maison mère vers filiale porte une preuve et une note de confiance : A (lu au registre), B (au moins deux indices), C (à vérifier).
- Ça doit marcher pour tous les secteurs et toutes les formes de groupe : marques connues (LVMH) ou centaines de petites sociétés aux noms neutres (VINCI).
- Périmètre : l'arbre des sociétés seulement. La recherche des personnes à contacter viendra plus tard.

## Pourquoi

- La carto actuelle dans Cargo (workspace Skillup) trouve environ 1 société sur 4 à 1 sur 9 : 19 sociétés pour LVMH contre 172 chez Basile, et 35 pour VINCI Energies contre 126.
- Raison : le skill actuel cherche sur le web, société par société. Basile, lui, a parcouru tout le registre.
- L'API Basile ne donne pas les liens entre sociétés (doc lue le 2026-10-03). Il faut donc les prendre dans les registres publics gratuits.

## Ce qu'on garde, ce qu'on change

- **On garde** la forme du skill account-mapping (repo youno-workspace) : les deux modèles Cargo (Comptes, Filiales et Entités) et les scripts d'import HubSpot et Cargo.
- **On change** le moteur : registres publics à la place de la recherche web, plus les règles de la méthode Basile.

## Plan étape par étape

1. **Récupérer les données publiques.** La base SIRENE de l'INSEE (noms, adresses, activité, statut des 27 millions de sociétés) est en cours de téléchargement. Les mandats entre sociétés viennent du registre INPI, qui demande un compte gratuit. Les annonces officielles viennent du BODACC, accessible sans compte.
2. **Récupérer les fichiers Basile** LVMH et VINCI complets, pour avoir une référence à laquelle comparer.
3. **Préparer le groupe** : société tête, marques classées en sûres ou ambiguës, holdings à exclure. Un agent le propose, un humain valide.
4. **Chercher les candidates par le nom des marques** dans tout le registre, puis écarter les homonymes et les entrepreneurs individuels.
5. **Exiger une deuxième preuve** pour chaque candidate : mandat, annonce officielle, dirigeants communs, adresse du groupe ou domaine du groupe.
6. **Descendre par les mandats** (président, gérant, associé…) et recommencer jusqu'à ce que plus rien ne change.
7. **Désigner la maison mère directe** de chaque société, calculer les niveaux et noter la confiance A, B ou C.
8. **Dire si chaque société est ciblable** : Oui pour les sociétés avec salariés ou chiffre d'affaires, Non pour les holdings vides, SCI et véhicules financiers.
9. **Ajouter le site web et la page LinkedIn.**
10. **Tester sur LVMH et VINCI**, puis mesurer combien de sociétés Basile on retrouve et combien on en ajoute à tort.
11. **Si le test est bon**, mettre à jour le skill account-mapping et l'import Cargo. Rien n'est modifié dans Cargo ni dans youno-workspace avant ça.

## Ce qu'il faut de ta part

- Demander à l'INPI l'accès API et SFTP pour les données RNE (étape 1). Compte : OK. Fichiers Basile : OK.

## Avancement

### 2026-10-03

- Étape 1 : base SIRENE téléchargée (30,1 millions de sociétés, dont 7,8 millions de personnes morales actives avec un siège actif). Le compte INPI se connecte, mais il refuse l'accès par programme ("accès impossible pour API") : il faut demander l'accès API et SFTP dans l'espace personnel INPI.
- Étape 2 : fichiers Basile récupérés dans `basile/` (LVMH : 172 sociétés, 232 liens ; VINCI : 1 007 sociétés, 1 514 liens).
- Étape 4, premier test sur LVMH (`brand_scan.py`) : 4 414 candidates par le nom, dont 114 sur des marques sûres. On retrouve 80 des 172 sociétés Basile (47 %), sans encore trier les homonymes.
- Les 92 sociétés manquées viennent des mandats (environ 37, il faut l'INPI) et de l'adresse du groupe (38 au 24 rue Jean Goujon).
- Règle de l'adresse : au 24 rue Jean Goujon, seules 14 des 69 sociétés portent une marque sûre. La règle "groupe majoritaire à l'adresse" ne joue donc qu'une fois les mandats ajoutés. Les deux étapes doivent tourner ensemble, en boucle.
- Accès INPI accordé le 2026-10-03 : l'API marche (fiche complète d'une société à partir de son SIREN). Elle ne permet pas de chercher "les sociétés dirigées par X" : pas de recherche dans ce sens, et au plus 10 000 résultats par requête, avec un quota par jour.
- SFTP INPI (registre complet, `registre-national-entreprises.inpi.fr:9222`) : connexion refusée avec le mot de passe du compte. D'après l'INPI, un mot de passe propre au SFTP se crée via un e-mail envoyé après l'acceptation de la licence.
- BODACC : la recherche plein texte marche sans compte (118 annonces citent "LVMH MOET HENNESSY"). C'est une piste de secours pour la recherche dans ce sens.
- Licence INPI, à respecter : les données personnes (dirigeants) ne doivent pas servir à la prospection, et les sociétés avec `diffusionCommerciale = false` s'opposent à la prospection. Décision : les noms de dirigeants servent seulement de preuve interne, ils ne sortent jamais dans les fichiers livrés. Les sociétés opposées seront marquées.

### 2026-10-05

- SFTP INPI toujours refusé (aucun e-mail reçu). On s'en passe : la recherche "sociétés dirigées par X" passe par l'API Recherche d'entreprises (gratuite, sans compte), qui donne le SIREN des sociétés dirigeantes, et par le BODACC. Chaque lien est ensuite vérifié sur la fiche INPI de la société.
- Moteur complet en place (`engine.py`) : marques, deuxième preuve, mandats, adresses du groupe, organigramme public, maison mère, niveaux, confiance A/B/C, ciblable. La boucle tourne jusqu'à ce que plus rien ne change (5 à 6 tours).
- Pièges rencontrés et corrigés : prénoms pris pour des sociétés au BODACC ("Celine"), noms de famille ("NOM Prénom"), noms plus longs ("MOET HENNESSY INVESTISSEMENTS"), sigle écrit "M H C S" au registre et "MHCS" ailleurs, majorité à l'adresse du groupe calculée trop tôt, expiration de la connexion INPI.
- **Résultat LVMH : 174 sociétés, dont 158 des 172 de Basile (92 %).** 16 en plus, à vérifier : certaines semblent réelles (Champagne de Mansin, Société Viticole de Reims, Chamfipar), d'autres sont douteuses (LC Investissements, Toiltech Holding). Même maison mère directe que Basile : 71 %. Même réponse ciblable : 91 %.
- Ce que l'humain doit valider dans la config : la liste des marques (sûres ou ambiguës), les holdings et familles à exclure, et l'organigramme public (nom légal exact de chaque maison). Pour TAG Heuer, Krug et Veuve Clicquot, le nom légal reste à trouver.
- Point légal : 75 des 174 sociétés LVMH ont `diffusionCommerciale = false` au registre (elles s'opposent à la réutilisation de leurs données INPI pour la prospection). La colonne `opposition_prospection` le marque.
- VINCI lancé (1 007 sociétés chez Basile, plusieurs heures de lecture INPI).
- VINCI arrêté le 2026-10-05 à 14h27 : quota quotidien INPI atteint (erreur 429 "quota dépassé", après environ 10 000 fiches lues sur deux jours). Le tour 1 était fini (476 sociétés retenues), le tour 2 était en cours. Les 10 001 fiches déjà lues sont gardées en cache, donc la reprise ne relit rien. À relancer quand le quota est revenu : `.venv/bin/python engine.py config/vinci.json`.
- Conséquence pour la suite : environ 10 000 fiches INPI par jour. Un groupe comme LVMH (environ 4 000 fiches) tient en une journée ; un groupe comme VINCI en demande deux. Pistes pour réduire : ne lire que les candidates qui ont déjà un indice, et garder le cache d'un groupe à l'autre.
- 2026-10-05, soir : accès FTP RNE obtenu (serveur `www.inpi.net`, FTP simple, identifiants dans `.env`, les navigateurs ne savent plus ouvrir les liens ftp://). Il contient le registre complet des formalités en JSON (`stock_RNE_formalites_NIVEAU1_20260304_1400.zip`, 15 Go, photo du 2026-03-04) et les comptes annuels (4 Go). Le serveur est capricieux : il faut le mode passif avec `--ftp-skip-pasv-ip`, et des reprises automatiques. Téléchargement en cours dans `data/rne_stock/`.
- Suite prévue : construire depuis ce stock la table de tous les liens "société A dirige société B" pour toute la France. La recherche "sociétés dirigées par X" se fera alors en local, sans quota. L'API INPI ne servira plus qu'à vérifier l'état actuel (depuis mars 2026) des sociétés retenues.
- 2026-10-05, fin de soirée : téléchargement du stock à environ 3 Go sur 14 Go. Pour le reprendre là où il s'est arrêté (après un redémarrage, par exemple) : `cd zyzx && nohup .venv/bin/python -u ftp_download.py stock_RNE_formalites_NIVEAU1_20260304_1400.zip > data/rne_stock/dl.log 2>&1 &`. Le fichier `data/rne_stock/<nom>.zip.ok` apparaît quand c'est fini.

### 2026-10-06

- Stock RNE téléchargé en entier (14,4 Go, 5 470 fichiers JSON, 165 Go une fois décompressés, photo du 2026-03-04).
- Tables nationales construites (`build_links.py`, 15 minutes sur 14 cœurs) dans `data/rne_links/` : 1 644 581 liens "société dirige société", 10,5 millions de sociétés (avec opposition à la prospection et effectif), 13,1 millions de dirigeants personnes (usage interne, comme preuve seulement).
- `engine.py` a maintenant un mode local (par défaut quand les tables existent) : plus d'API INPI, plus d'Annuaire, plus de BODACC, plus de quota. Une cartographie prend quelques minutes.
- **LVMH, mode local : 173 sociétés, 158 des 172 de Basile (92 %)**, 15 en plus, même réponse ciblable 91 %. Même qualité qu'avec les API, en quelques minutes au lieu de plusieurs heures.
- **VINCI, mode local : 1 069 sociétés, 868 des 1 007 de Basile (86 %)**, 201 en plus, 139 manquées. Même maison mère directe : 64 %.
  - Erreurs de réglages trouvées et corrigées : Equans (groupe Bouygues, pas VINCI) faisait entrer environ 150 fausses sociétés ; "VINCI" et "ASF" doivent toujours demander une deuxième preuve (Le Vinci Audit, Access Security First…).
  - Parmi les 201 en plus, beaucoup ont un mandat inscrit au registre et semblent réelles (Spiecapag Régions France, Botte Fondations, Terrasol, SCCV de VINCI Immobilier) : à vérifier sur un échantillon.
  - Les 139 manquées sont surtout des mandats "Autre" (46) et "Membre" (32) que Basile accepte plus largement que nos règles.
- Règle ajoutée : un GIE dont tous les membres sont du groupe entre dans le groupe (règle Basile).
- Leçon principale : la qualité dépend d'abord des réglages (marques, homonymes, organigramme). Une seule marque fausse (Equans) a ajouté 150 fausses sociétés. La relecture humaine des réglages n'est pas optionnelle.

### 2026-10-06, après-midi

- **Échantillon VINCI vérifié** (30 sociétés "en plus", contrôlées dans l'annuaire public) : une vingtaine très probablement de vraies filiales absentes de Basile (Sogea Rhône-Alpes, Cegelec Ouest, Tunzini, Faceo FM Sud Est…), environ six douteuses (homonymes "SOGEA", "GTM BATIMENT" sans salarié), deux co-entreprises avec EQIOM. Basile classe lui-même plusieurs vraies filiales VINCI comme "partenaires hors groupe" (27 de nos sociétés en plus).
- **Crédit Mutuel Alliance Fédérale testé** contre la carto Cargo (68 lignes, 52 SIREN) : 83 % des SIREN retrouvés. Limite de fond : les caisses locales (environ 1 400) n'ont pas de mandat au registre, le moteur n'en trouve presque aucune.
- **Règles ajoutées** : co-entreprise (une société extérieure la dirige aussi) rangée en participation ; nom réduit à la marque sans salarié ni autre indice : deuxième preuve exigée ; GIE dont tous les membres sont du groupe : retenu ; comités d'entreprise exclus. **Règle retirée** : l'adresse seule (même à plus de 85 %) ne suffit plus (fonds domiciliés chez La Française).
- **Résultats finaux** : LVMH 90 % (154/172, 15 en plus), VINCI 81 % (813/1 007, 176 en plus), Crédit Mutuel 83 % (43/52). Les règles privilégient la justesse : avec les règles souples, on retrouvait plus (92 %, 86 %, 87 %) mais avec plus de faux.
- **Skill account-mapping copié et mis à jour dans `zyzx/skills/account-mapping/` (version 2.0.0)**, sans toucher à youno-workspace : nouveau `references/moteur-france.md` (données, réglages, règles, limites, résultats), moteur dans `scripts/moteur_france/`, `to_skill_tables.py` pour produire les 6 tables du skill. Validation et import HubSpot du skill testés sur les trois groupes : 0 erreur.

### 2026-10-06, soir

- **Quota de l'API diff de l'INPI mesuré (T010).** Lecture complète du lundi 2026-10-05 avec `worker/scripts/mesure_quota_diff.py`, 100 fiches par page (le maximum).
- Résultat : **39 131 fiches lues, journée complète, aucune erreur 429.** Une fiche est l'état complet d'une société (un SIREN), qui peut regrouper plusieurs formalités. 392 pages, 394 requêtes (les pages, la page vide de fin et le comptage), 6 min 48 s.
- Le volume d'un jour est donc d'environ 39 000 fiches, le double des 15 000 à 20 000 annoncés par l'INPI. Le lundi rattrape peut-être le week-end : un jour de milieu de semaine reste à mesurer.
- Le quota observé le 2026-10-05 (environ 10 000 fiches par jour) comptait des requêtes d'une fiche chacune. Avec `/diff`, une requête rend 100 fiches : une journée coûte environ 400 requêtes. L'hypothèse, non vérifiée, est que le quota compte les requêtes.
- `/diff/count` ne donne pas le total d'une journée : il répond seulement « plus de 10 000 ». Les en-têtes `pagination-count` et `pagination-max-page` sont vides.
- Décision : la mise à jour quotidienne passe par l'API diff (ADR-002 confirmé). Le rattrapage depuis le stock du 2026-03-04 peut passer par `/diff`, étalé avec reprise sur curseur.

### 2026-10-07

- Moteur rangé dans le paquet `cartofr.moteur` (T016) et branché sur `data/registre.duckdb`. Le mode API (INPI, Annuaire, BODACC) est supprimé : une carto ne fait plus aucun appel extérieur.
- Non-régression du moteur porté, sur les mêmes données que le prototype : LVMH 154/172 (15 en plus), VINCI 813/1 007 (176 en plus), CMAF 43/52. Exactement les scores du 2026-10-06.
- Même ensemble de SIREN que le prototype pour les trois groupes (169, 989 et 572). Quelques maisons mères directes changent (8 LVMH, 38 VINCI, 1 CMAF) : le prototype dépendait d'un tri instable, le portage trie de façon stable. Contre Basile, même mère directe : 108/154 au lieu de 105/154 pour LVMH, 513/813 pour VINCI.
- Une carto prend environ 45 s, dont 35 s pour normaliser les noms. Le registre passe à 2,4 Go avec la table `unites_legales`.

### 2026-10-07, après-midi (T021)

- Une carto se lance depuis l'app : bouton « Lancer la carto » sur la fiche du groupe, travail `carto` dans la file du worker, résultat écrit dans `cartos`, `carto_societes` et `carto_liens`.
- Le moteur exclut les familles par empreinte (`familles_exclues_empreintes`), comme les réglages lus en base. Non-régression avec les empreintes : LVMH 154/172 (15 en plus), VINCI 813/1 007 (176 en plus), CMAF 43/52. Sociétés, liens, participations et sociétés étrangères identiques, champ par champ, à la carto aux noms en clair, pour les trois groupes.
- Seul écart mesuré sur tout le registre : une variante du nom exclu de LVMH, écrite avec des blancs au bord (5 mandats), est exclue par l'empreinte et ne l'était pas en clair. Sans effet sur la carto LVMH.
- Carto LVMH lancée de bout en bout depuis l'interface sur le registre réel : 169 sociétés (les mêmes SIREN que la non-régression), 115 liens, 51 s de calcul. Date des données : 04/03/2026 (le stock), signalée en avertissement tant que la synchro n'a pas rattrapé.

### 2026-10-07, recette du MVP (T024)

Pile Docker Compose complète en local (projet `cartofr-t024`), registre réel monté en lecture seule, synchro coupée (aucun appel INPI). Un membre fictif de l'organisation Youno, connecté par lien magique depuis la page de connexion. Les cartos sont lancées depuis l'interface (Chromium sans écran), une à la fois, sur les réglages de départ validés. Machine : 16 cœurs, 15 Go de mémoire (6 Go libres), une vingtaine de conteneurs d'autres projets au repos ; charge moyenne de 0,7 à 1,2 avant chaque mesure, montée à 5–10 par la carto elle-même. Aucune limite de CPU ni de mémoire sur le conteneur `worker`.

**SC-001, scores obtenus depuis l'app** (`non_regression.py --depuis-postgres --organisation Youno`, cartos lues dans `carto_societes`) :

| Groupe | Retrouvées | En plus | Seuil | Même mère | Sociétés | Liens | Calcul (worker) | Du clic à « Voir l'arbre » |
|---|---|---|---|---|---|---|---|---|
| LVMH | 90 % (154/172) | 15 | ≥ 154/172, ≤ 16 | 70 % | 169 | 115 | 53,1 s | 57 s |
| VINCI | 81 % (813/1 007) | 176 | ≥ 813/1 007, ≤ 193 | 63 % | 989 | 1 084 | 53,1 s | 57 s |
| CMAF | 83 % (43/52) | (529, non mesuré) | ≥ 43/52 | — | 572 | 756 | 41,5 s | 48 s |

- Exactement les scores du prototype (2026-10-06) et du moteur porté : les trois groupes passent leurs seuils.
- Le moteur lancé en direct (`non_regression.py` sans option, même registre) donne les mêmes chiffres (54 s, 60 s, 44 s ; 2,0 Go au plus). Comparaison ligne à ligne app / moteur direct : mêmes SIREN (169, 989, 572), même maison mère et même « ciblable » pour chaque société, mêmes liens (115, 1 084, 756), pour les trois groupes.
- Le « clic à l'arbre » ajoute 4 à 6 s au calcul : prise du travail par la file (sondage toutes les 5 s) et rafraîchissement de la page (toutes les 3 s).

**SC-004, VINCI sous 5 minutes : tenu.** Mesuré seul (charge 0,95 au départ, rien d'autre en cours) : **45,4 s** de calcul dans le worker (`cartos.duree_ms`), 51 s du clic à l'arbre. La première mesure, juste après LVMH, donnait 53,1 s. Même score dans les deux cas (813/1 007, 176 en plus). Marge : six fois sous la cible.

**Contrôle à 320 px et au clavier des écrans de US2 (C4)**, avec Chromium à 320 × 640 px : connexion, liste des groupes, nouveau groupe (vide, avec 20 résultats, sans résultat), fiche d'un groupe (réglé, et neuf sans réglages validés), réglages (validés, et brouillon vide), carto en cours, arbre (LVMH 169 sociétés, VINCI 989 sociétés tout déplié, 6 niveaux), lien d'export.

- Aucun défilement horizontal, sur aucun écran ; à 6 niveaux de profondeur, la carte la plus étroite de VINCI fait encore 213 px, sans débordement.
- Tous les éléments interactifs atteints au Tab, chacun avec un focus visible (anneau). L'arbre suit le motif ARIA « tree » : un seul arrêt de tabulation, flèches pour se déplacer ; les 169 et 989 sociétés sont atteintes aux flèches avec l'anneau ; « Voir la preuve » s'atteint au Tab et s'ouvre à Entrée. « Exporter (CSV) » s'atteint au Tab, Entrée télécharge `cartofr-lvmh-2026-03-04.csv` (BOM, 169 sociétés).
- Chaque champ a son label (aucun champ sans label). Aucun texte anglais visible (recherche de Loading, Submit, Error, undefined, null, NaN et d'une trentaine d'autres mots). Contraste AA tenu partout (aucun texte sous 4,5:1). Aucune erreur dans la console.
- Seul défaut, mineur : après *Enregistrer le brouillon* au clavier, le focus retombe au début de la page (observé), parce que le bouton se désactive pendant l'envoi ; *Valider la version* et *Lancer la carto* ont le même motif dans le code, non observé (`disabled={enCours}`, dans `web/app/(app)/groupes/[id]/reglages/editeur-reglages.tsx` et `web/app/(app)/groupes/[id]/cartos/lancer-carto.tsx`). Rien n'est bloqué, mais il faut retabuler. Non corrigé ici.
- Captures d'écran regardées (connexion, recherche, fiche, réglages, carto en cours, arbre déplié).

**SC-002 : à mesurer par Loïc, guide dans `docs/recette-sc002.md`.** Trois groupes jamais réglés y sont proposés (Bigard, Fayat, Roullier ; 38 à 83 sociétés avec un brouillon minimal).
