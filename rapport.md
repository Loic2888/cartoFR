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

### 2026-10-07, marque sûre et mandat « Autre » (T033)

- Défaut trouvé par T017 : dans `decide`, la branche du mandat faible (« Autre », code 99) rendait `None` dès qu'il manquait le second indice, avant les règles de la marque sûre et de l'adresse. Un mandat « Autre » servait donc de veto. Correction : cette branche ne décide plus que l'entrée (« mandat 'Autre' et deux indices ») ; sinon la société passe aux règles suivantes, comme sans ce mandat. Rien d'autre ne change dans le moteur.
- Tests : `test_marque_sure_et_mandat_autre` passe sans `xfail` ; ajoutés « adresse du groupe + un dirigeant commun + Autre » (entre par « adresse du groupe et second indice ») et « Autre + marque ambiguë seule » (reste refusée).
- Non-régression, même registre, avant → après :

| Groupe | Retrouvées | En plus | Même mère |
|---|---|---|---|
| LVMH | 154/172 → **155/172** | 15 → 15 | 70 % → 71 % |
| VINCI | 813/1 007 → 813/1 007 | 176 → 176 | 63 % → 63 % |
| CMAF | 43/52 → 43/52 | 529 → 529 (non mesuré) | — |

- Un seul SIREN entre, dans LVMH : `444653489` (marque sûre, et mandat « Autre » d'une société du groupe). Il est dans la référence Basile : c'est la société retrouvée en plus. Aucun SIREN ne sort ; VINCI et CMAF ont exactement les mêmes sociétés, maisons mères et réponses « ciblable ».
- Deux maisons mères changent dans LVMH. `444653489` devient la tête de sa maison (plus grand effectif), donc `514035633` se rattache à elle (« même maison »). `318571064`, qui porte le mandat « Autre » vers `444653489`, forme alors une boucle avec elle ; la boucle est coupée et `318571064` est rattachée à la tête (« boucle de mandats coupée », confiance C), avec un niveau incohérent, défaut déjà suivi par T036.

### 2026-10-08, comités au nom accentué (T034)

- Défaut trouvé par T017 : dans `decide`, le filtre des comités, amicales et associations comparait le nom SIRENE brut, mis en majuscules, à `CSE|COMITE|AMICALE|ASSOCIATION`. Un nom écrit « COMITÉ … » n'était pas reconnu et entrait par son mandat. Correction : le nom passe par `norm` (majuscules, accents retirés, ponctuation en espaces) avant le filtre. La règle reste la même : un mot entier, en tête du nom. Rien d'autre ne change dans le moteur.
- Tests : le cas « COMITÉ SOCIAL ET ÉCONOMIQUE » passe sans `xfail` ; ajoutés « Comité d'Établissement » (casse mixte et accents) et « comite-d-entreprise » (minuscules et tirets), tous exclus. Nouveau test témoin : trois noms proches mais qui ne sont pas des comités (« COMITÉVA », « SOCIÉTÉ DES COMITÉS », « Éditions Amicalement ») entrent toujours par leur mandat.
- Portée sur tout le registre : 11 sièges hors forme juridique 9 (associations, fondations) sont nouvellement filtrés par leur nom, sur 244 431 qui le sont en tout. Aucun n'est dans LVMH, VINCI ou CMAF.
- Non-régression, même registre, avant → après :

| Groupe | Retrouvées | En plus | Même mère |
|---|---|---|---|
| LVMH | 155/172 → 155/172 | 15 → 15 | 71 % → 71 % |
| VINCI | 813/1 007 → 813/1 007 | 176 → 176 | 63 % → 63 % |
| CMAF | 43/52 → 43/52 | 529 → 529 (non mesuré) | — |

- Aucun écart : les trois cartos ont exactement les mêmes SIREN, maisons mères et réponses « ciblable » avant et après (170, 989 et 572 sociétés). La correction protège les groupes à venir, elle ne change pas les trois groupes de référence.

### 2026-10-08, point fixe sans limite silencieuse (T035)

- Défaut trouvé par T017 : la boucle du moteur s'arrêtait après `MAX_TOURS = 8` tours, même si le point fixe n'était pas atteint. Une chaîne de 9 mandats sous la tête perdait son 9ᵉ niveau, sans rien dire. Correction : la boucle va jusqu'au point fixe, avec une garde haute de 50 tours. Si la garde est atteinte avant le point fixe, la carto porte un avertissement en français (`Carto.avertissements`), repris par le travail `carto` dans `cartos.avertissement`, déjà affiché tel quel par l'app. Rien d'autre ne change dans le moteur.
- Tests : `test_point_fixe_atteint_au_dela_de_huit_niveaux` passe sans `xfail` (9 niveaux, 10 tours, aucun avertissement). Ajoutés : garde ramenée à 3 tours sur la même chaîne (le 4ᵉ niveau manque et la carto le signale) ; garde de 4 tours pour un point fixe atteint au 4ᵉ tour (aucun avertissement) ; l'avertissement du moteur arrive dans le texte de `cartos.avertissement`.
- Non-régression, même registre, avant → après :

| Groupe | Retrouvées | En plus | Même mère | Tours |
|---|---|---|---|---|
| LVMH | 155/172 → 155/172 | 15 → 15 | 71 % → 71 % | 5 → 5 |
| VINCI | 813/1 007 → 813/1 007 | 176 → 176 | 63 % → 63 % | 7 → 7 |
| CMAF | 43/52 → 43/52 | 529 → 529 (non mesuré) | — | 6 → 6 |

- Aucun écart : les trois groupes ont exactement les mêmes SIREN, maisons mères et niveaux avant et après. Les trois atteignaient déjà leur point fixe sous 8 tours (VINCI : 6 tours qui ajoutent des sociétés, puis 1 qui constate que rien ne change). La garde de 8 ne coupait donc rien sur nos groupes de référence ; elle aurait coupé un groupe plus profond, sans le dire.

### 2026-10-08, niveau cohérent avec la maison mère après une boucle coupée (T036)

- Défaut trouvé à l'essai de T022 : dans `build`, la fonction récursive `lvl` coupait une boucle de mandats croisés (A → B → A) en rattachant A à la tête avec le niveau 1, puis l'appel qui avait commencé par A reprenait la main et écrasait ce niveau par `niveau(B) + 1`, soit 3. La maison mère disait « tête », le niveau disait 3, et toute la descendance de A était décalée de 2.
- Correction : deux passes. D'abord les rattachements : les boucles sont coupées, sur la même société qu'avant (la première de la boucle atteinte en remontant). Ensuite les niveaux, sur des rattachements fixés : niveau = niveau de la maison mère + 1, tête à 0. Rien d'autre ne change dans le moteur.
- Tests : `test_boucle_de_mandats_coupee_niveau_coherent` (boucle A → B → A sous la marque, plus une filiale de A) et `test_niveau_egal_niveau_de_la_maison_mere_plus_un` (invariant sur une carto complète : mandats sur trois niveaux, tête de maison d'une marque, boucle coupée et sa descendance). Les deux échouaient avant la correction.
- Non-régression, même registre, avant → après :

| Groupe | Retrouvées | En plus | Même mère |
|---|---|---|---|
| LVMH | 155/172 → 155/172 | 15 → 15 | 71 % → 71 % |
| VINCI | 813/1 007 → 813/1 007 | 176 → 176 | 63 % → 63 % |
| CMAF | 43/52 → 43/52 | 529 → 529 (non mesuré) | — |

- Niveaux corrigés : 28 sociétés dans LVMH (3 boucles coupées, dont `318571064`, et leur descendance), 19 dans VINCI (4 boucles), 10 dans CMAF (1 boucle). Chaque niveau baisse de 2. Avant, 6, 8 et 2 sociétés violaient la règle « niveau = niveau de la mère + 1 » ; après, aucune.
- Mêmes sociétés, mêmes maisons mères, mêmes preuves, confiances, réponses « ciblable » et comptes de rattachement dans les trois groupes : seule la colonne niveau bouge.

### 2026-10-08, cas douteux et décisions du consultant (T027)

- Le moteur range maintenant les cas douteux (`Carto.cas`), au lieu de les laisser noyés dans l'arbre. Quatre sortes : confiance C (un seul indice, rattachement déduit), co-entreprise (retenue, mais une société hors du groupe y tient un mandat fort ou moyen), participation sans contrôle, société étrangère. Chaque cas porte la règle qui l'a placé là et ses indices pour et contre, en textes du moteur : rôle, marque, nombre de sociétés à une adresse, nombre de dirigeants en commun. Jamais un nom de personne ; une entité extérieure absente de SIRENE (entrepreneur individuel, société cessée) n'est pas désignée.
- Les décisions du consultant (`decisions`, migration `0003_cas_douteux.sql`) sont reprises à la carto suivante du même groupe. La plus récente l'emporte (`decisions_en_vigueur`). « Écarter » fait sortir une société que les règles retiennent, et donc les sociétés qui n'entraient que par elle ; le cas garde la règle qui l'aurait fait entrer. « Retenir » fait entrer une société que le moteur voit encore liée au groupe ; une décision sur une société disparue, ou qui n'a plus aucun indice, est sans objet. Une société décidée reste dans la liste (type « décision ») pour qu'on puisse revenir dessus. Les règles du moteur ne changent pas (principe 1).
- Non-régression, même registre, avant → après (sans décision, comme la non-régression) :

| Groupe | Retrouvées | En plus | Même mère |
|---|---|---|---|
| LVMH | 155/172 → 155/172 | 15 → 15 | 71 % → 71 % |
| VINCI | 813/1 007 → 813/1 007 | 176 → 176 | 63 % → 63 % |
| CMAF | 43/52 → 43/52 | 529 → 529 (non mesuré) | — |

- Aucun écart : sociétés, liens, participations, sociétés étrangères et tours identiques champ par champ dans les trois groupes. Le premier passage CMAF de la non-régression a échoué sur une erreur interne de DuckDB dans la recherche des marques (code non modifié, machine chargée) ; relancé seul, il passe.
- Cas douteux par groupe :

| Groupe | Cas | Dans la carto | Hors carto | Confiance C | Co-entreprise | Participation | Étrangère |
|---|---|---|---|---|---|---|---|
| LVMH | 80 | 27 | 53 | 14 | 13 | 35 | 18 |
| VINCI | 569 | 484 | 85 | 173 | 314 | 56 | 29 |
| CMAF | 353 | 207 | 146 | 19 | 190 | 129 | 17 |

  Un cas peut avoir deux sortes. Chaque cas a au moins un indice pour et un indice contre.
- Piège payé : une première version recopiait la marque dans l'indice (« marque sûre : … »). Le test SC-005 sur le registre réel a trouvé dans LVMH un nom complet de dirigeant dans ce texte : une marque de maison peut être le nom de son fondateur, porté aussi par un dirigeant. L'indice dit maintenant « Porte une marque sûre du groupe », sans la marque ; le nom de la société, affiché à côté, la montre déjà. Après correction, SC-005 : 0 personne trouvée dans le texte du moteur, pour les trois groupes.
- Le PRD (US4) attendait les 176 sociétés « en plus » de VINCI dans la liste : 93 y sont. Les 83 autres sont retenues en confiance B (75) ou A (8), sans mandat extérieur : le moteur n'a pas de raison de douter d'elles. Les y mettre voudrait dire classer « douteuse » toute confiance B ; c'est une décision produit, pas prise ici.

### 2026-10-08, export pour HubSpot ou Cargo (T029)

- Nouveau bouton « Exporter pour HubSpot ou Cargo (zip) » sur une carto terminée : un zip des 6 tables du skill account-mapping (`companies`, `relationships`, `brands`, `entities_to_resolve`, `evidence_sources`, `coverage`) et un `LISEZMOI.txt`. Aucune poussée vers un CRM : le client importe lui-même.
- Les tables sont construites par le worker (`cartofr/exports/skill.py`, repris de `to_skill_tables.py`) depuis la carto **enregistrée** dans la base de l'app : ni registre, ni appel extérieur. Route interne `GET /export/skill/<carto>?organisation=` du service `recherche`, relayée par la route web `export-skill`, qui lit la carto avec la session de l'utilisateur (RLS) : la carto d'une autre organisation rend 404, et le worker filtre aussi par organisation.
- Écarts avec `to_skill_tables.py` : SIRET et adresse du siège, NAF et forme juridique restent vides (la base de l'app ne les garde pas) ; `entities_to_resolve` est vide (participations et sociétés étrangères ne sont pas enregistrées) ; colonne `non_diffusible` ajoutée ; dates = date des données de la carto, pas le jour de l'export. `to_skill_tables.py` n'écrivait aucun dirigeant : aucun champ n'a été vidé.
- Validation du skill (`validate_mapping.py`) sur les exports du registre réel : 0 erreur pour LVMH (170 sociétés), VINCI (989) et CMAF (572). Aucun nom complet de dirigeant dans le texte exporté (2 376, 3 824 et 19 030 dirigeants confrontés). Homonymies dans une dénomination SIRENE ou une marque de l'organigramme validé : LVMH 1, VINCI 2, CMAF 0 (marques au nom d'un fondateur, décision T023).
