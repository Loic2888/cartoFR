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

**Décision du 2026-10-13 (Loïc) : SC-002 ne sera pas chronométré.** Pas le temps pour les trois sessions. T024 C2 est abandonné, T024 est clos sur C1, C3 et C4. SC-002 (« moins de 30 minutes de la saisie à l'export ») reste **non mesuré** : rien ne prouve qu'il est tenu, rien ne prouve le contraire. Le guide `docs/recette-sc002.md` reste en place si la mesure redevient utile. Indice, pas preuve : le calcul prend moins d'une minute (SC-004), le reste est le temps de saisie et de relecture du consultant.

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

### 2026-10-08, registre des traitements et suppression d'un compte (T031)

- `docs/registre-traitements.md` : cinq traitements (dirigeants en calcul interne, comptes consultants, journaux, sauvegardes, API Claude en P2 avec des données de sociétés seulement), avec finalité, base légale, données, durée, lieu et sous-traitants. Douze points restent « à décider », listés à la fin, dont la durée des mandats fermés, la purge des comptes inactifs et le journal d'audit de GoTrue (`auth.audit_log_entries`), qui garde e-mail et IP après la suppression d'un compte.
- Page « Mon compte » (`/compte`) : un membre supprime son propre compte en tapant SUPPRIMER. GoTrue efface la ligne `auth.users` ; les clés étrangères existantes font le reste : appartenances supprimées, `cree_par` et `valide_par` à nul, cartos gardées par l'organisation. L'e-mail n'était déjà dans aucune table de l'app.
- Règle du dernier administrateur, décidée ici et tenue en base (migration 0005) : s'il ne reste aucun administrateur dans une organisation qui a encore des membres, le membre le plus ancien est promu. Refuser la suppression aurait bloqué un droit RGPD tant qu'aucun écran ne permet de changer un rôle. Dernier membre : l'organisation et ses cartos sont gardées, sans membre.
- Tests : 13 tests base (`test_suppression_compte.py`, dont l'effacement par le rôle de GoTrue), 6 tests des journaux du worker au niveau DEBUG (`test_journaux.py` : recherche, démarrage, travaux carto réussis, refusés et en échec, paramètres hostiles ; aucune adresse e-mail, aucun morceau de nom de dirigeant), 21 tests vitest de la logique de suppression. Worker : 414 réussis, 3 ignorés (registre réel absent). Moteur non touché : pas de non-régression à refaire.

### 2026-10-08, proposition des réglages par l'IA (T025)

- Nouveau type de travail `proposition` (worker) : il lit le groupe, envoie à l'API Claude le nom du groupe, la raison sociale, le sigle et le SIREN de la tête et de ses filiales directes (80 au plus), et rien d'autre. L'IA lit le site et le rapport annuel (recherche web côté Anthropic) et rend, par un outil à schéma strict, des marques, sigles, maisons et débuts de nom à exclure, chacun avec l'URL de sa source. Modèle : `claude-sonnet-5-5`, changeable par `CARTOFR_MODELE_IA`.
- Règle écrite, dans le worker : une marque est ambiguë si au moins une société active au registre, hors de la tête et de toutes les sociétés qu'elle dirige (liens en vigueur, à toute profondeur), a un nom qui commence par elle, avec la normalisation et les formes juridiques de la recherche de candidates du moteur. Sinon elle est sûre. Un élément sans source http(s) est écarté.
- Rien de validé ne se perd en silence (principe 2, décision de Loïc du 2026-10-08) : les valeurs des cinq listes proposées dans la dernière version validée sont reprises dans la revue. Reproposée par l'IA (même valeur, casse, accents et ponctuation ignorés, dans n'importe quelle liste) : un seul élément, celui de l'IA, marqué « déjà validé en <liste> ». Non reproposée : ajoutée, origine `validee`, sans source, gardée par défaut dans le contenu proposé.
- La proposition est une version de `reglages` d'origine `proposition`, sans `valide_le`. La migration `0004_proposition_ia.sql` interdit de la valider telle quelle : le consultant valide la version qui sort de sa revue (T026), avec le nombre de corrections.
- Tests : 24, API simulée, aucun appel réel. Le test C2 confronte tout ce qui part vers l'API aux dirigeants du mini-registre (clé brute, « NOM PRÉNOM », « PRÉNOM NOM ») ; un second vérifie qu'aucune requête des deux modules ne lit `dirigeants_personnes`.
- Moteur inchangé : non-régression sans objet. Dépendance ajoutée au worker : `anthropic` (SDK officiel, 1.12).
- Pas encore fait : un essai avec l'API réelle sur un groupe connu (voir T026, SC-007).

### 2026-10-08, revue de la proposition de l'IA et comptage des corrections (T026)

- Écran des réglages : un bouton « Proposer des réglages » met un travail `proposition` en file (un seul à la fois par groupe) et affiche son état. Quand la dernière version est une proposition, chaque élément montre sa liste, ses homonymes au registre et sa source (lien http(s) seulement), et se garde, se corrige (valeur, liste) ou se rejette. Le consultant peut ajouter ce qui manque.
- « Valider ces réglages » crée une nouvelle version, validée d'un coup, avec `proposition_id` et `corrections`. Une correction : un élément de l'IA rejeté, un élément de l'IA corrigé dont la valeur ou la liste change, un ajout. La proposition elle-même reste non validée. L'historique affiche le nombre de corrections.
- Éléments déjà validés (principe 2) : ceux que l'IA n'a pas reproposés s'affichent marqués « déjà validé », gardés par défaut ; ceux qu'elle repropose s'affichent une fois, avec la liste où ils étaient validés. Décision du 2026-10-08 : rejeter ou modifier un élément déjà validé **n'est pas** une correction. SC-007 mesure les erreurs de l'IA, pas un changement d'avis sur un réglage validé par un humain.
- Next ne décide rien sur le groupe : il compte les choix du consultant (principe 7). Tests : `web/lib/reglages/proposition.test.ts`.
- Limite : si le consultant passe par l'éditeur classique au lieu de la revue, la version enregistrée ne porte pas de compte de corrections. Elle ne compte pas dans SC-007.

**SC-007 : non mesuré le 2026-10-08 (mesure du 2026-10-13 plus bas).** La mesure demande de vraies propositions, donc l'API réelle (clé `OPENROUTER_API_KEY` depuis T037) ; aucune n'a été faite. Rien n'est inventé ici. Protocole :

1. Sur une base de test, créer les groupes LVMH, VINCI et CMAF sans leurs réglages de départ (ou dans une organisation à part).
2. Pour chacun, cliquer « Proposer des réglages » et chronométrer du clic à la validation.
3. Revoir la proposition en prenant `config/<groupe>.json` comme référence : rejeter ce qui n'y est pas et qui est faux, corriger les listes, ajouter ce qui manque et compte (marques, sigles, maisons, exclusions par nom).
4. Relever `corrections` de la version validée (`select version, corrections from reglages where proposition_id is not null`) et la durée.
5. Critère tenu si la moyenne des trois est sous 5 corrections et chaque durée sous 30 minutes. Noter le coût de l'appel (jetons) et le modèle (`CARTOFR_MODELE_IA`).

**2026-10-13, SC-007 mesuré : non tenu, de loin.** Le protocole est rejoué sans clics par `worker/scripts/mesure_sc007.py` : une vraie proposition par groupe (groupe neuf, sans version validée), puis la revue qu'aurait faite un consultant avec `config/<groupe>.json` comme référence, comptée comme l'écran (`appliquerRevue`). Un élément de l'IA absent de `config/` peut être vrai ou faux, et la machine ne le sait pas : d'où une fourchette. `min` le garde, `max` le rejette, `estimé` rejette seulement ceux qu'aucune société du registre ne porte (signal T040). Modèle : `anthropic/claude-haiku-5.5`.

| Groupe | Proposés | Gardés | Liste changée | Doublons | Absents de `config/` (dont sans société) | Ajouts | Corrections min / estimé / max | Coût |
|---|---|---|---|---|---|---|---|---|
| LVMH | 80 | 33 | 14 | 0 | 33 (19) | 38 | **52** / 71 / 85 | 0,054 $ |
| VINCI | 49 | 5 | 20 | 3 | 21 (3) | 56 | **79** / 82 / 100 | 0,073 $ |
| CMAF | 116 | 9 | 23 | 17 | 67 (20) | 23 | **63** / 83 / 130 | 0,066 $ |
| **Moyenne** | | | | | | | **64,7** / 78,7 / 105 | |

- Même l'hypothèse la plus favorable (tout élément absent de `config/` est juste) donne 64,7 corrections en moyenne, contre moins de 5 visés.
- CMAF : cinq essais ont d'abord échoué en 429 « Provider returned error ». C'est le fournisseur derrière OpenRouter qui refusait ; la clé avait encore son crédit et une petite requête passait. Le sixième essai est passé (1,3 min, 7 recherches web). Le script réessaie maintenant trois fois, et enregistre chaque proposition dans `out/sc007/` pour ne pas la repayer.
- Pour LVMH et VINCI, les ajouts pèsent le plus (38 et 56) : l'IA ne retrouve pas les marques qui ne figurent pas sur les pages qu'elle lit, en particulier les marques ambiguës de `config/` (22 et 23 manquent). Ce tirage rappelle moins que celui du 2026-10-10 (80 éléments proposés pour LVMH contre 114). Même constat que T040 : le rappel varie beaucoup d'un essai à l'autre.
- Pour CMAF, c'est le bruit : 17 doublons et 67 éléments absents de `config/`.
- La règle des homonymes coûte ensuite 11 corrections sur LVMH et 16 sur VINCI. Ce sont des marques que la règle range en « ambiguë », parce qu'une société hors du groupe porte un nom qui commence par elles, alors que les réglages validés les tiennent pour sûres. L'humain accepte un risque que la règle refuse. Ce n'est pas une erreur de l'IA, mais l'écran le compte comme une correction.
- La durée (moins de 30 minutes, du clic à la validation) n'est pas mesurée : les chronos sont abandonnés (décision de Loïc du 2026-10-13, voir T024).
- Lecture : la proposition fait gagner du temps (33 éléments justes sur 80 pour LVMH, avec leur source), mais elle ne dispense pas d'une revue complète. L'objectif « moins de 5 corrections » est hors de portée avec cette méthode. Deux suites possibles : revoir la cible SC-007 dans le PRD, ou changer la méthode (plusieurs passes et union des résultats, marques tirées du registre). C'est à Loïc de trancher.
- Coût de la mesure : 0,19 $ pour les trois groupes. Les essais refusés n'ont rien coûté.

## 2026-10-09

### L'IA passe par OpenRouter (T037)

- Décision de Loïc : la proposition des réglages appelle OpenRouter (`POST /api/v1/chat/completions`, format OpenAI) au lieu de l'API Anthropic en direct. Modèle par défaut inchangé : Claude Sonnet 5.5 (`anthropic/claude-sonnet-5.5` chez OpenRouter), changeable par `CARTOFR_MODELE_IA`. Clé : `OPENROUTER_API_KEY`. Le paquet `anthropic` sort des dépendances du worker ; l'appel passe par `httpx`, déjà utilisé pour l'INPI et Sirene.
- La recherche et la lecture web sont les outils serveur d'OpenRouter (`openrouter:web_search`, `openrouter:web_fetch`, 8 utilisations chacun au plus) : OpenRouter les exécute et ne rend au worker que l'appel de la fonction de proposition, à schéma strict. Le reste ne change pas : nettoyage, règle des homonymes, éléments déjà validés gardés, version non validée.
- Confidentialité : chaque requête pose `provider: {zdr: true, data_collection: "deny"}`. Un sous-traitant de plus (OpenRouter, États-Unis) est ajouté au registre des traitements ; sa propre durée de conservation reste à décider. Le routage UE d'OpenRouter est réservé aux comptes entreprise.
- Perdu : le repli automatique d'Anthropic après un refus (`fallbacks`), qui n'existe pas au format OpenAI. Un refus fait échouer le travail avec « L'IA a refusé de faire la proposition. »
- Tests : la requête et le client HTTP sont simulés, aucun appel réel. Le test « aucun nom de dirigeant dans la requête » passe sur le nouveau format ; les erreurs HTTP (401, 402, 429, 5xx, réseau, réponse illisible) donnent un message français sans la clé ni le corps de la réponse dans le journal. Moteur inchangé : non-régression sans objet.
- Ouvert : une proposition réelle (T037 C5, puis la mesure SC-007 de T026) demande une clé OpenRouter dans `.env`.

### Proposition IA recentrée sur les marques, sans modèle par défaut (T038)

- Constat, avec Loïc : l'IA ne rend aucune liste de filiales (sa réponse n'a que marques, sigles, maisons et exclusions) ; le moteur trouve les filiales au registre. Lire un rapport annuel en entier ne servait donc à rien, et c'est ce qui coûtait le plus de jetons. La consigne vise maintenant les pages courtes du site qui listent les marques et les maisons ; le rapport annuel n'est ouvert que si le site ne les donne pas.
- Pas de plafond de taille de page (décision de Loïc) : un plafond couperait la fin des pages, et avec un modèle peu cher une page entière coûte quelques centimes.
- Plus de modèle par défaut (décision de Loïc) : `CARTOFR_MODELE_IA` est obligatoire, sinon le travail échoue sans appeler l'IA. Sonnet 5.5 est écarté (2 $ / 10 $ le million de jetons en entrée / sortie chez OpenRouter). Candidats relevés le 2026-10-09 : Claude Haiku 5.5 (0,10 $ / 0,50 $), DeepSeek V3.2 (0,26 $ / 0,42 $), Mistral Large 4 (0,68 $ / 2,09 $). Les modèles chinois posent la question de l'hébergement (R5) : à examiner avant de choisir. Choix sur l'essai comparatif (T038 C4).
- Chaque proposition journalise modèle, requêtes, jetons, recherches web et coût réel en dollars, même en échec. Des nombres seulement.

## 2026-10-10

### Premières propositions réelles, et rappel amélioré (T037 C5, T039)

- Modèle : `anthropic/claude-haiku-5.5` par OpenRouter (choisi par Loïc dans `.env`). Une proposition par groupe, comparée aux réglages validés de `config/` (marques sûres, ambiguës et sigles ; maisons de l'organigramme).
- Avant T039, l'IA ne proposait presque rien de faux mais trop peu : elle n'utilisait que 3 à 6 de ses 16 recherches et lectures, freinée par « préfère peu d'éléments sûrs » et ne connaissant que les filiales directes.
- T039 : consigne d'exhaustivité (parcourir chaque pôle d'activité, rien d'inventé), contexte élargi aux 150 plus grosses sociétés du groupe, 10 recherches et 20 lectures au plus, sortie jusqu'à 64 000 jetons.

| Groupe | Marques de `config/` retrouvées, avant → après | Maisons, avant → après | Éléments proposés, avant → après | Coût, avant → après |
|---|---|---|---|---|
| LVMH | 23/74 → **49/74** | 13/47 → **33/47** | 34 → 114 | 0,029 $ → 0,231 $ |
| VINCI | 18/71 → **26/71** | 15/37 → **23/37** | 25 → 79 | 0,042 $ → 0,046 $ |
| CMAF | 18/52 → **26/52** | 9/13 → 9/13 | 52 → 90 | 0,022 $ → 0,092 $ |

- Les éléments nouveaux (absents de `config/`) sont en grande majorité de vraies sociétés ou marques du groupe : Le Bon Marché, Paris Match, Tiffany & Co., Bvlgari pour LVMH ; Soletanche Bachy, Freyssinet, Spiecapag pour VINCI ; CIC, ACM, Cofidis, AFEDIM pour CMAF. Bruit : pour LVMH, des marques étrangères (domaines viticoles américains…) sans société en France ; la règle des homonymes les range sans effet, mais elles allongent la revue.
- Coût : LVMH monte à 23 centimes, parce que l'IA a ouvert le rapport annuel (658 000 jetons en entrée) malgré la consigne. Les trois groupes coûtent 37 centimes en tout.
- Deux défauts trouvés en mesurant, corrigés : le compteur de recherches lisait un champ qu'OpenRouter n'envoie pas (`server_tool_use_details` est le bon) ; une proposition longue (CMAF) dépassait 16 000 jetons de sortie, l'appel d'outil arrivait coupé et le travail échouait en « illisible » au lieu de « tronquée ».
- Moteur inchangé : non-régression sans objet.

## 2026-10-11

### Bruit de la proposition IA : deux pistes écartées, un signalement retenu (T040)

Objectif : réduire le bruit (marques sans activité en France) et gagner encore en rappel. Une proposition réelle par groupe et par configuration, Claude Haiku 5.5, comparée à `config/`. Marques retrouvées :

| Groupe | T039 (en place) | Consigne « actives en France » + passes par pôle | Consigne « actives en France » seule |
|---|---|---|---|
| LVMH | **49**/74 (0,23 $) | 41/74 (0,41 $) | 26/74 (0,05 $) |
| VINCI | **26**/71 (0,05 $) | 24/71 (0,20 $) | 20/71 (0,06 $) |
| CMAF | 26/52 (0,09 $) | **35**/52 (0,17 $) | 29/52 (0,07 $) |

- La consigne « seulement les marques actives en France » enlève le bruit mais fait baisser le rappel : l'IA écarte aussi de vraies marques dont elle doute. Écartée.
- Les passes par pôle d'activité (repérage des pôles, puis une passe par pôle, 8 au plus) coûtent 2 à 4 fois plus pour un gain qui n'apparaît que sur CMAF. Écartées, non commitées.
- D'un essai à l'autre, le rappel varie beaucoup : il suit surtout la quantité de pages que l'IA choisit de lire. Un écart de quelques marques sur un seul essai ne prouve rien ; une prochaine idée se mesurera sur plusieurs essais par groupe.
- Filtre essayé à sec, sans IA : écarter les marques qu'aucune société active du registre ne porte. Il aurait écarté de vraies marques validées : 6 sur 75 dans LVMH (Veuve Clicquot, Moët & Chandon : leur société s'appelle MHCS ; Maison Francis Kurkdjian…), 6 sur 71 dans VINCI (Graniou ATEM, Lyon Aéroports…), 4 sur 53 dans CMAF (L'Est Républicain, Vosges Matin…). Abandonné.
- Retenu (décision de Loïc) : ces marques restent dans la proposition, signalées « À vérifier : aucune société du registre ne porte ce nom » à la revue. Le consultant garde Veuve Clicquot et rejette un domaine viticole étranger en un clic. Gratuit, sans effet sur le rappel.
- Coût des essais IA depuis le 2026-10-10 : environ 1,70 $.

### Le service recherche lit les cartos avec un rôle en lecture seule (T041)

- Avant : l'export du skill (T029) lisait les cartos avec le rôle `postgres`, qui contourne RLS. L'isolation entre organisations ne tenait que par le filtre écrit dans les requêtes.
- Maintenant : rôle `cartofr_recherche` (migration 0006). Lecture seule par défaut, quatre tables (`groupes`, `reglages`, `cartos`, `carto_societes`), aucun contournement de RLS. Ses politiques ne lui montrent que l'organisation déclarée pour la transaction (`set_config('cartofr.organisation', …)`), et rien sans déclaration. Les requêtes gardent leur filtre : deux barrières.
- Mot de passe hors du code : `RECHERCHE_DB_PASSWORD` dans `infra/.env`, posé par `infra/appliquer-migrations.sh`. Une installation antérieure ajoute la ligne à la main (`infra/README.md`).
- Piège : dans l'image Supabase, `postgres` n'est pas superutilisateur ; il doit être membre du rôle pour le prendre (`set role`). La migration le fait.
- Vérifié : 12 tests (privilèges, rien sans déclaration, seule l'organisation déclarée même si la requête en demande une autre, aucune autre table, aucune écriture, route d'export). Sur une base neuve, une vraie connexion avec le rôle est en lecture seule et ne voit aucune carto sans déclaration. Suite complète : 520 tests réussis.

## 2026-10-13

### Retrait de l'enrichissement : US6 et T030 abandonnées

- Décision de Loïc : cartoFR fait la carto des entreprises françaises, pas l'enrichissement. Le site web et la page LinkedIn servent la prospection, qui est le travail d'un autre outil (HubSpot, Cargo). US6 et FR-011 sont retirées du PRD, T030 est abandonnée, et « Enrichissement » rejoint le hors périmètre. La colonne `domain` de l'export du skill reste vide, comme aujourd'hui : l'outil de prospection la remplit.
- Étude faite avant la décision, gardée pour mémoire. Aucune source gratuite et officielle ne donne le site d'une société française : ni SIRENE, ni l'API Recherche d'entreprises, ni le BODACC. Wikidata couvre 12,5 % des sociétés ciblables de LVMH (13 sur 104). Le reste aurait demandé une recherche web par l'IA, ou un fournisseur payant comme Societeinfo. Le scraping de LinkedIn est interdit par ses conditions d'utilisation.
- Pendant l'étude, une requête envoyée à Wikidata portait par erreur l'adresse e-mail de Loïc dans l'en-tête User-Agent. Une seule requête, sans aucune donnée du projet. L'adresse a été retirée des requêtes suivantes.

### Contrôle hebdomadaire de fraîcheur (T015 C1)

- `worker/scripts/controle_fraicheur.py` tire au hasard 10 changements publiés dans les 7 derniers jours, de J-7 à hier (aujourd'hui n'est pas encore synchronisé) : 5 fiches RNE (API diff INPI) et 5 unités légales SIRENE, hors entrepreneurs individuels. Il rend « Retrouvés : N/10 ».
- Règle « retrouvé » (`cartofr.registre.fraicheur`) : rejouer le changement avec les règles mêmes de la synchro ne modifie aucune ligne. Le rejeu se fait dans une transaction annulée (`synchro_rne.simuler`, `synchro_sirene.simuler_unites`) : le registre n'est jamais modifié. Un écart dit quelles tables auraient bougé (liens ouverts, société fermée…), avec le SIREN de la personne morale, pour vérifier à la main. Aucun nom n'est affiché.
- Tirage : départ à un SIREN tiré au hasard (`searchAfter` pour l'INPI ; plancher `siren:[X TO 999999999]` pour l'INSEE), un même SIREN vérifié une seule fois. Un premier essai tirait le rang SIRENE parmi les 1 000 premiers résultats : il ne voyait que des SIREN en 1xx (secteur public). Corrigé avant le commit. Coût : 5 pages de 20 fiches du quota INPI, 5 requêtes Sirene.
- Limites : la source rend l'état actuel de la société. Un changement survenu après la dernière synchro est compté manquant à tort. À l'inverse, une fiche modifiée sur un champ que le registre ne garde pas compte comme retrouvée : le contrôle mesure que le registre porte l'état actuel de la société, ce qui est l'objet de SC-003.
- Essai sur le registre local, jamais rattrapé depuis le stock du 2026-03-04 : **6/10** retrouvés (graine 13). L'écart est attendu, et il montre que le contrôle voit les retards : liens à ouvrir et à fermer, société à créer, unité légale modifiée. Ce n'est pas la mesure de C2.
- Tests : 15 (`test_fraicheur.py`) : fenêtre, rejeu sans effet sur le registre, fiche appliquée retrouvée, fiche nouvelle, radiation et cessation manquantes, tirages RNE et SIRENE sans toucher au curseur de la synchro, doublons retirés, tirages impossibles comptés manquants. Moteur non touché : non-régression sans objet.
- Reste C2 : rattrapage sur le serveur (T005), puis un premier contrôle à 10/10.

### Retrait du prototype (T032)

- Option validée par Loïc : on ne retire que ce que le paquet `worker/` remplace déjà. Retirés : `engine.py`, `brand_scan.py`, `compare.py`, `to_skill_tables.py`, `debug_addr.py`, `debug_round.py`, `role_codes.py`, `annuaire.py`, `bodacc.py`. Ils restent lisibles dans l'historique git et dans la copie du skill.
- Gardés à la racine : `ftp_download.py`, `inpi.py` (lecture des identifiants, utilisée par `ftp_download.py`), `build_links.py` et `build_sieges.py`. Ils produisent les parquets que `cartofr.registre.construire` charge : sans eux, pas de reconstruction du registre depuis un nouveau stock.
- Le skill `account-mapping` garde sa propre copie du prototype (`skills/account-mapping/scripts/moteur_france/`), pour l'usage hors de l'app. La règle « la racine fait foi, recopier dans le skill » est retirée de `CLAUDE.md` : le moteur qui fait foi est celui de `worker/`.
- C1 : aucun script retiré n'était importé ni appelé par `worker/`, `infra/` ou la CI. C3, non-régression depuis le paquet après le retrait : LVMH 90 % (155/172), 15 en plus ; VINCI 81 % (813/1 007), 176 en plus ; CMAF 83 % (43/52). Mêmes scores que T033. Suite worker : 410 réussis.

## 2026-10-14

### Le moteur dépend des réglages faits à la main ; le périmètre publié du groupe peut les remplacer (T042)

Point de départ : SC-007 non tenu (64,7 corrections au moins par proposition IA). Décision de Loïc : le but est une carto complète produite seule, pas une revue qui fait la moitié du travail. On ne baisse pas la cible : on cherche d'où vient le manque. Toutes les mesures ci-dessous sont locales et en lecture seule sur `data/registre.duckdb`, contre les références Basile. Elles n'affichent que des nombres et des dénominations de sociétés. Les scripts sont jetables (hors dépôt) : T042 en refera un, versionné.

**1. Sans réglages, le moteur ne trouve presque rien.** Moteur du paquet, mêmes groupes :

| Réglages | LVMH (172) | VINCI (1 007) | CMAF (52) |
|---|---|---|---|
| Tête seule, aucune marque | 2 · 0 en plus | 3 · 0 | 1 · 6 |
| Proposition IA brute du 2026-10-13, sans correction | 26 (15 %) · 5 | 27 (3 %) · 5 | 36 · 266 |
| Réglages validés (`config/`) | 155 (90 %) · 15 | 813 (81 %) · 176 | 43 · 529 |

Le registre dit qui **dirige** une société, pas qui la **possède**. Les sociétés entrent par les marques ; dirigeants communs et adresse ne font que confirmer. Le moteur est donc un dictionnaire de marques tenu à la main, et l'IA ne sait pas le refaire.

**2. Le groupe est relié dans le registre, mais on ne sait pas où il commence.** Plafond (sociétés de la référence reliées à la tête par un chemin qui reste dans la référence) : LVMH 131/172 par liens et dirigeants communs, 149 avec l'adresse ; VINCI 794 puis 906 sur 1 007 ; CMAF 48 puis 51 sur 52. Explorer depuis la tête sans savoir quoi suivre échoue : les liens de société seuls donnent 16 %, 1 % et 12 %. Ajouter les sociétés dirigées par un « cadre du groupe » donne 51 % pour LVMH (113 en plus), 4 % pour VINCI et 9 855 sociétés en plus pour CMAF, à cause des administrateurs mutualistes. En remontant les liens depuis chaque société de la référence, 8 sociétés VINCI sur 1 007 arrivent à la tête : le groupe est coupé en blocs (306, 271, 203 sociétés…) dont le sommet est présidé par une personne. Avec la tête et 5 sommets pris dans la référence, les liens seuls donnent 51 % de VINCI (62 en plus) : c'est le recollage des blocs qui manque.

**3. Recollage des blocs par l'IA, sous une règle qui tranche.** Décision de Loïc : l'IA propose, une règle tranche (le principe 1 tient). Une question fermée par sommet (« cette société fait-elle partie du groupe ? URL et citation »). La règle relit la page et exige la citation, le nom ou le SIREN du bloc et le nom du groupe. Lots : 20 sommets vrais et 20 pièges par groupe. Les pièges partagent un dirigeant ou l'adresse avec le groupe et sont absents de la référence.

- Haiku 5.5 répond « inconnu » même pour VINCI Construction France : écarté. Sonnet 5.5 : 80 questions, 5,51 $ (environ 7 centimes la question). Les premiers essais à 6 en parallèle ont pris des 429 du fournisseur, sans frais. Relancé à 2 en parallèle.
- Vrais : l'IA dit oui pour 15/20 (LVMH) et 17/20 (VINCI). La règle recolle 10 et 13 blocs, soit 88 et 590 sociétés, dont 66 et 529 dans la référence. Couverture, avec ce que la tête atteint déjà : environ 55 % et 53 %. Refus de la règle : pages illisibles (PDF, sites qui refusent le robot) et noms de bloc non retrouvés (VINCI Immobilier Promotion, 306 sociétés).
- Pièges : aucune fausse entrée nette. LVMH : un recollage, Paris Match, que la liste consolidée 2024 de LVMH confirme : c'est la référence qui est ancienne. VINCI : les pièges étaient mal choisis, la plupart sont d'anciennes filiales d'Eurovia avec des filiales déjà dans la référence.
- Limite : VINCI a des centaines de sommets distincts. La longue traîne coûterait des dizaines de dollars par carto.
- Au passage, un SIREN inventé (celui de VINCI Construction France) a été donné à Loïc en exemple, puis utilisé dans un essai (3 centimes). Le vrai, vérifié dans le registre, est 380 448 944.

**4. Le périmètre publié du groupe, croisé avec le registre, sans IA.** Les groupes cotés publient la liste de leurs sociétés consolidées. Correspondance par nom normalisé avec SIRENE (un seul porteur, ou homonymes départagés par le registre ou par la commune du siège), puis descente dans les blocs du registre :

| Groupe | Document | Lignes en France | Liste seule | Liste + blocs du registre |
|---|---|---|---|---|
| VINCI | Liste exhaustive des sociétés consolidées 2025 (vinci.com) | 1 139 | 355 (35 %) · 500 en plus | **760 (75 %)** · 736 en plus |
| LVMH | Comptes consolidés 2024, liste p. 67 (AMF), principales sociétés seulement | 232 | 102 (59 %) · 74 en plus | **129 (75 %)** · 131 en plus |
| CMAF | Document d'enregistrement universel 2024 | — | non mesuré | non mesuré |

- VINCI : 844 noms trouvés une fois, 129 homonymes (10 départagés), 145 introuvables (abréviations, sociétés renommées, SCI au nom d'adresse). Sur les 499 sociétés de la liste absentes de la référence, 442 (89 %) sont reliées au groupe par le registre (lien de société, dirigeant commun ou adresse). Pour celles de la référence, la proportion est de 97 % (334/345). La référence Basile sous-compte donc VINCI : 75 % est un minimum.
- LVMH : 150 noms trouvés une fois, 26 départagés par la commune, 39 homonymes, 17 introuvables. Manques typiques : écart de libellé (« MH France – Moët Hennessy France »), sociétés absentes de la liste (Samaritaine, Château d'Esclans, Hublot France).
- CMAF : le site investisseurs de la BFCM répond 403 à tout téléchargement automatique. Pas de contournement. L'app devra accepter un PDF déposé par le consultant.
- Coût : un document par groupe, aucun appel IA, environ 2 minutes de calcul.

**Lecture.** « Périmètre publié + registre » rend 75 % sur VINCI et LVMH sans réglage humain, avec des « en plus » qui sont surtout des oublis de la référence. Les réglages faits à la main restent devant (81 % et 90 %). L'écart se travaille par une correspondance des noms plus souple, sous confirmation du registre, puis par les signaux secondaires (marques sûres, adresse) et par le recollage IA des seuls gros blocs non couverts. Le travail de l'IA change : trouver l'URL du périmètre, plus seulement des marques. Le principe 2 et SC-007 sont à revoir en conséquence : c'est l'objet de T042.

### Lecture du périmètre publié et correspondance avec le registre (T042)

- Nouveau paquet `cartofr.perimetre` :
  - `extraction` lit un PDF (pypdf, ajouté aux dépendances du worker ; il était déjà épinglé à la racine), une page HTML ou un texte. Il garde les sociétés situées en France et en outre-mer, aux deux formats mesurés (VINCI, LVMH).
  - `correspondance` retrouve chaque ligne dans le registre par une règle écrite : porteur unique, puis commune du siège, puis liens du registre, sinon refus avec sa raison.
  - `worker/scripts/mesure_perimetre.py` rejoue la mesure. Les documents restent dans `out/perimetre/`, hors git.
- Revue adverse du jour. Deux vraies erreurs de correspondance étaient possibles sur le format LVMH, où nom et ville ne sont pas séparés :
  - un titre de section (« Vins et Spiritueux ») pouvait être pris pour le nom de la société de la ligne suivante ;
  - une ville de 2 ou 3 mots pouvait raccourcir « Alphamark Parfums Cosmétiques » en « Alphamark », le nom d'une autre société.
- Correction : un nom recollé aux lignes d'avant, ou raccourci par une ville de plusieurs mots, n'est retenu que si le siège SIRENE est dans la ville du document. Autres corrections :
  - une société mise en équivalence ne sert plus à départager des homonymes ;
  - un SIREN retenu pour deux noms différents n'est retenu pour aucun (« conflit ») ;
  - les formes juridiques à points (« S.A.S. ») sont retirées, en tête ou en fin de nom seulement ;
  - les entrepreneurs individuels sont écartés dans la requête elle-même ;
  - le texte des pages HTML est lu sans expression régulière, qui aurait pris un temps quadratique sur une page mal formée ;
  - le CSV des refus ne recopie que la ligne de la société, jamais les lignes d'avant.
- Mesure C3, sur les documents du 2026-10-14 :

| Groupe | Lignes en France | Retenues (unique / commune / registre) | Refusées (homonymes / introuvables / conflit) | Liste seule | Liste + blocs du registre |
|---|---|---|---|---|---|
| VINCI | 1 139 | 865 / 0 / 10 | 124 / 140 / 0 | 362 (36 %) · 514 en plus | **764 (76 %)** · 751 en plus |
| LVMH | 232 | 134 / 34 / 2 | 17 / 45 / 0 | 104 (60 %) · 67 en plus | **128 (74 %)** · 116 en plus |

- Sur LVMH, la règle resserrée retient 170 lignes au lieu de 177. Elle retrouve autant de sociétés de la référence (104), avec 6 en plus de moins. Les 7 lignes perdues étaient donc surtout des fausses correspondances. Avec les blocs, une vraie société est perdue (129 → 128) et 14 sociétés en plus disparaissent.
- Le seuil de C3 (« LVMH 176 retenues ou plus ») comptait ces erreurs. Décision de Loïc : C3 juge désormais les sociétés de la référence retrouvées (VINCI ≥ 760 avec les blocs, LVMH ≥ 102 avec la liste seule), les « en plus » relevés à côté. Tenu : VINCI 764 (751 en plus contre 748), LVMH 104 (67 en plus contre 74).
- Limites connues :
  - la liste VINCI n'a donné aucune ligne en mise en équivalence : sa section B a sans doute un autre format, à voir avec T043 C2 ;
  - un nom coupé sur deux lignes dont le siège n'est pas dans la ville du document se rabat sur la fin du nom, si elle existe seule dans SIRENE ;
  - « SE » et « SA » en tête de nom sont lus comme des formes juridiques.
- Tests : 56 nouveaux (`worker/tests/perimetre/`), sur des textes et mini-registres inventés. Suite worker : 466 réussis. Moteur non touché : non-régression sans objet.

## 2026-10-15

Mesures locales, en lecture seule sur `data/registre.duckdb` (photo du 2026-03-04), contre les références Basile. Elles n'affichent que des nombres et des dénominations de sociétés. Les scripts sont jetables (hors dépôt) : T045 en refera un, versionné.

### Pilote du périmètre publié hors des groupes de référence : Fnac Darty et Edenred

- Documents trouvés par recherche web, rangés dans `out/perimetre/pilote/` (hors git). Correspondance par la règle de T042, sans IA :

| Groupe | Lignes en France | Retenues | Refusées | Tête seule | Liste + blocs du registre |
|---|---|---|---|---|---|
| Fnac Darty | 36 | 28 | 5 homonymes, 3 introuvables | 1 société | 64 sociétés |
| Edenred | 8 | 4 | 4 introuvables | 1 société | 11 sociétés |

- L'extraction de T042 lit 0 ligne sur ces deux documents : elle ne connaît que les formats VINCI et LVMH. Les lignes ont été mises au format à la main pour le pilote. Une partie des refus vient de cette mise au format, pas de la règle (pays resté dans un nom, ligne « dissoute en avril 2025 » prise pour une société).
- Trouver le document prend 5 à 15 minutes par groupe. Pour Bouygues et Eiffage, il faut ouvrir le document d'enregistrement universel.
- Justesse non mesurable : pas de référence pour ces deux groupes.

### Blocs ou arbres : découper le registre en groupes, sans IA (T045)

Idée de Loïc : calculer une fois la carto de tout le pays, pour qu'une demande ne soit plus qu'une lecture. Première étape : découper le registre en groupes propres.

**1. Les blocs ne marchent pas.** Un bloc regroupe toutes les sociétés reliées par un lien actif, dans n'importe quel sens. Avec tous les liens (1,64 M), on obtient 249 625 blocs, dont un bloc géant. Les commissaires aux comptes relient à eux seuls des milliers de sociétés (KPMG 15 387, Deloitte 11 185, PwC 10 570). Aucun réglage n'en sort :

| Liens gardés | Blocs | Plus gros bloc | LVMH, VINCI, CMAF |
|---|---|---|---|
| Rôles forts (président, gérant, associé responsable) | 249 217 | 146 390 | CMAF dans le bloc géant ; VINCI en 26 blocs |
| Idem, sans parent de plus de 500 enfants | 249 458 | 118 127 | idem |
| Idem, sans parent de plus de 100 enfants | 250 433 | 94 971 | VINCI en 35 blocs |
| Président et gérant seuls | 151 327 | 27 509 | LVMH : 32 sociétés sur 172 dans un bloc |
| Tous rôles sauf commissaires aux comptes | 283 017 | 411 478 | les trois groupes dans le même bloc |

Les plus gros parents sont des gérants de défiscalisation : ECOFIP (11 636 sociétés), ECOGESTION (10 454), FINANC'ILE (7 640), ELVEST (7 414).

**2. Les arbres à une mère marchent.** Règle mesurée :
- chaque société reçoit **une seule** mère, parmi ses liens actifs ;
- les commissaires aux comptes (rôles 71, 72, 77) et les parents de plus de 500 enfants sont écartés ;
- la mère est celle du rôle le plus fort : président (73), puis président du conseil (51) et gérant (30), puis gérants associés et commandité (28, 29, 131), associés responsables (74, 75), 53, administrateur et conseil de surveillance (65, 64), membre (11), autre (99) ;
- à rôle égal, le parent qui a le plus d'enfants, puis le plus petit SIREN ;
- on remonte de mère en mère jusqu'au sommet.

Un arbre ne peut pas en fusionner un autre : le plus gros compte 1 334 sociétés, sommet compris (7 760 sans l'écart des parents de plus de 500 enfants).

| Groupe | Arbres touchés par la référence | Plus gros morceaux (sociétés de la référence / taille de l'arbre, sommet) |
|---|---|---|
| LVMH (172) | 109 | 21/26 UFIPAR · 16/22 Moët Hennessy · 10/12 Louis Vuitton Malletier · 10/13 LVMH (la tête) |
| VINCI (1 007) | 395 | 281/351 VINCI Immobilier Promotion · 188/225 VINCI Construction · 30/38 Solarvia · 16/17 Senior Conseil |
| CMAF (52) | 30 | 14/605 Caisse fédérale du Crédit Mutuel de Maine-Anjou et Basse-Normandie · 4/24 CF Crédit Mutuel Océan · 4/321 CR Crédit Mutuel Nord Europe |

**Lecture.**
- Les gros arbres sont propres : 80 à 85 % de leurs sociétés sont dans la référence. Le reste ressemble aux oublis de Basile vus le 2026-10-14, sans vérification.
- Un groupe reste éclaté en beaucoup d'arbres, surtout de petites sociétés dirigées par des personnes. Les recoller est le rôle des listes publiées (T042, T043) : une liste désigne les arbres qui appartiennent au groupe. Un arbre qu'aucune liste ne réclame reste son propre groupe.
- Le mutualisme ne tient pas dans cette règle : les arbres du Crédit Mutuel mêlent plusieurs fédérations, dont Maine-Anjou et Basse-Normandie, hors CMAF. Il demandera un traitement à part.
- L'ordre des rôles est un choix, à tester quand une société a deux mères possibles.
- Une carto du pays calculée sans validation humaine va contre le principe 2. Elle passera par `PRD.md`, `ARCHI.md` et un amendement de `CLAUDE.md`, avec sa raison. T045 ne construit que l'arbre du registre : aucune carto ne s'en sert encore.

### Arbre à une mère du registre (T045)

- Nouveau module `cartofr.registre.arbre` : la règle mesurée ci-dessus, et la table `arbre` de `registre.duckdb` (`siren`, `mere`, `role_mere`, `sommet`, `profondeur`, `boucle`), sans aucun nom. Table dérivée de `liens`, remplacée dans une transaction à chaque calcul. Une ligne `arbre` dans `mises_a_jour` : son `ajoutes` compte les sociétés dont le sommet a changé.
- La synchro nocturne la recalcule après RNE et SIRENE dans deux cas : le RNE a ajouté ou fermé une ligne depuis le dernier calcul réussi, même sur une journée arrêtée par le quota, ou ce calcul n'a jamais réussi. Décision de Loïc : un registre construit avant T045 reçoit son arbre à la première nuit. SIRENE ne déclenche rien : il ne touche jamais `liens`. Un échec du calcul fait échouer le travail, sans défaire la synchro.
- Mesure C5 (`worker/scripts/mesure_arbre.py`, registre du 2026-03-04) : 796 680 sociétés ont une mère, 335 210 arbres de 2 sociétés ou plus, 3 244 sociétés dans une boucle. Plus gros arbre : 1 334 sociétés, sommet compris (la mesure jetable disait 1 333 : elle ne comptait pas le sommet). VINCI Immobilier Promotion 281, VINCI Construction 188, UFIPAR 21 sociétés de la référence : les chiffres du matin, à l'unité.
- Durée : 5 à 7 s pour le calcul. Recalcul complet avec écriture : 7 s sur une table vide, 31 à 43 s sur une table pleine, où l'effacement et la réinsertion de 796 680 lignes indexées dominent. Environ 1 Go de mémoire.
- Compter les enfants distincts plutôt que les lignes de `liens` (doublons du RNE compris) ne change presque rien : VINCI Construction 187 au lieu de 188. On garde le compte de la mesure.
- Revue adverse du jour. Corrigé :
  - une journée RNE arrêtée par le quota ne déclenchait pas le recalcul ;
  - un calcul en échec n'était jamais refait si la nuit suivante ne changeait rien ;
  - SIRENE déclenchait un recalcul complet presque chaque nuit, pour rien ;
  - le sommet d'une boucle était compté à tort parmi les sommets changés ;
  - une interruption laissait la ligne de journal `en_cours`.
- Tests : 54 dans `worker/tests/registre/test_arbre.py`, un de plus dans `worker/tests/jobs/test_synchro.py`. Suite worker avec une base Postgres jetable : 646 réussis, 6 ignorés. Moteur non touché : non-régression sans objet.

## 2026-10-16

### Le périmètre publié entre dans le moteur (T043)

- Nouvel indice du moteur, `perimetre`. `cartographier(..., perimetre=PerimetrePublie(source, lignes))` retrouve les lignes dans le registre par la règle de T042, sur la même connexion, sans réseau.
  - Une société inscrite en intégration globale entre avec sa preuve : « inscrite au périmètre publié du groupe : <document>, ligne « … » (intégration globale, 66 %) ». Ses filiales entrent ensuite par les règles du registre.
  - Confiance A si un mandat au registre la rattache à une société du groupe, B sinon. Jamais C.
  - Une société inscrite en mise en équivalence (ou autre méthode) n'entre pas, même présidée par le groupe. Décision de Loïc : le document l'emporte. Elle est rangée en participation sans contrôle (avec ses mandats, forts compris) et dans les cas douteux. Le consultant peut la retenir ; l'inscription ne compte alors pas comme indice de confiance.
  - Les exclusions des réglages, les décisions du consultant et la règle des associations s'appliquent avant le périmètre. Une société étrangère inscrite va dans les sociétés étrangères. Sans document, le moteur ne change pas.
- Mesure par le moteur, non-régression (`worker/scripts/non_regression.py --perimetre out/perimetre`, documents du 2026-10-14) :

| Groupe | Réglages validés seuls | Réglages validés + périmètre (C3) | Tête seule + périmètre (C4) |
|---|---|---|---|
| LVMH (172) | 155 (90 %) · 15 en plus | **166 (97 %)** · 69 en plus, dont 60 inscrites | **142 (83 %)** · 67 en plus, dont 60 inscrites |
| VINCI (1 007) | 813 (81 %) · 176 en plus | **861 (86 %)** · 679 en plus, dont 513 inscrites | **836 (83 %)** · 620 en plus, dont 513 inscrites |
| CMAF (52) | 43 (83 %) | 43, pas de document | 1, pas de document |

- Les « en plus » sont de deux sortes :
  - les sociétés que le document du groupe inscrit lui-même en intégration globale (« inscrites ») : 60 sur LVMH, 513 sur VINCI. Le 2026-10-14, 89 % des sociétés de la liste VINCI absentes de la référence étaient reliées au groupe par le registre : ce sont surtout des oublis de la référence Basile ;
  - les autres (9 et 166 avec les réglages, 7 et 107 sans) sont entrées par les règles du registre, sous une société du groupe : mandat fort surtout. Non vérifiées une à une.
- Le moteur fait mieux que la mesure jetable du 2026-10-14 (75 %, liste + blocs) : ses autres règles (adresse du groupe, dirigeants communs, mandat et indice indépendant) ajoutent des sociétés que la descente brute ne voit pas. Variante mesurée à part (script jetable) : liste + sous-arbres de l'arbre à une mère (T045), LVMH 130 (76 %) · 85 en plus, VINCI 727 (72 %) · 855 en plus. Elle ne fait pas mieux que les blocs ni que le moteur : on garde les règles du moteur.
- Une colonne « reliés au groupe par le registre seul » a été essayée puis retirée : depuis la tête seule, le registre n'atteint presque aucun « en plus » (0 et 1), pour la raison connue du 2026-10-14 (le groupe est coupé en blocs).
- Durée : une carto avec périmètre prend 75 s tête seule et 165 à 180 s avec les réglages (75 à 135 s sans périmètre, selon la charge de la machine). La correspondance relit tous les noms de SIRENE, comme la recherche des marques : les deux lectures pourraient être fusionnées. Mémoire au plus : 3,0 Go au lieu de 2,0. Reste sous les 5 minutes de SC-004.
- Revue adverse du jour. Corrigé :
  - le mode « tête seule » plantait : le moteur lit chaque liste des réglages ;
  - une inscription sans contrôle comptait comme un indice et pouvait monter une société retenue par le consultant de C en B ;
  - une participation sans contrôle perdait le mandat fort qui la reliait au groupe ;
  - le taux s'écrivait « 33,3333 % ».
  Gardés tels quels, notés : une association inscrite au périmètre disparaît sans être rangée en cas douteux (comme pour une marque) ; une mauvaise correspondance de T042 fait entrer une société et ses filiales (les « en plus » n'ont plus de plafond avec le périmètre, ils sont comptés) ; les sociétés exclues servent encore à départager des homonymes dans T042.
- Tests : 13 dans `worker/tests/moteur/test_perimetre_moteur.py`, sur des mini-registres inventés. Suite worker : 533 réussis sans base Postgres (132 ignorés, aucun ne touche le moteur).

### Carto du pays : réponses de Loïc pour la mise à jour du PRD

À reprendre dans `PRD.md`, `ARCHI.md` et l'amendement du principe 2 :
- un arbre du registre qu'aucune liste publiée ne réclame reste son propre groupe : c'est une carto acceptable ;
- le mutualisme (les arbres du Crédit Mutuel mêlent plusieurs fédérations) reçoit un traitement à part, dans la V1 ;
- les documents de périmètre sont cherchés par Loïc lui-même, avec son forfait Claude Code : aucune recherche par OpenRouter, donc aucun coût IA récurrent à plafonner. T044 C3 (l'IA de l'app cherche l'URL du périmètre) est à revoir en conséquence.

### PRD de la carto du pays et amendement du principe 2

Décisions de Loïc, portées dans `PRD.md` et `CLAUDE.md` :
- la carto du pays devient le parcours principal (US7, P1). Le consultant lit une carto déjà calculée (US2 réécrite). Les réglages écrits à la main deviennent des corrections facultatives (US8, P2). La proposition par l'IA passe en P3 ;
- tout le pays est cartographié avant la mise en ligne : 100 % des sociétés actives dans une carto, et un document pour 100 % des groupes cotés à Paris qui publient leur liste (SC-008) ;
- chaque carto a 7 jours de retard au plus sur la base (SC-009) ;
- le principe 2 est amendé : une carto existe sans validation humaine ; une correction est versionnée, datée, et son effet est affiché ;
- SC-001 se mesure désormais sans aucune correction, avec les mêmes cibles qu'avant (90, 81 et 83 %). Au 2026-10-16 : LVMH 83 %, VINCI 83 %, CMAF 2 %. SC-007 est retiré, SC-002 devient un temps de lecture (moins de 10 s).

Restent ouverts : la règle du traitement mutualiste, et le volume des cartos du pays dans la base de l'app (environ 800 000 sociétés ont une mère), à trancher dans `ARCHI.md`.

### Architecture de la carto du pays

- Mesure : une carto tête seule + périmètre prend 75 s, mais le moteur lui-même n'en prend que 2 à 3 (LVMH 2 s, VINCI 3 s). La correspondance d'un document en prend 26 à 29, presque tout en lecture des 13 M de noms de SIRENE ; la recherche des marques relit ces noms même sans aucune marque.
- Conséquence (`ARCHI.md`, ADR-007) : un seul passage sur les noms pour tous les documents, puis le moteur groupe par groupe. Tout le pays se recalcule chaque nuit, en moins d'une heure estimée pour quelques centaines de groupes.
- La carto du pays vit dans `pays.duckdb`, sur le worker, à côté du registre (ADR-006). L'interface lit un groupe par la route interne `/groupe`. Postgres ne garde que les corrections, les décisions et les cartos corrigées de chaque organisation.
- Les documents se déposent par une commande du worker, en lot. Le champ de réglage prévu par T044 est abandonné.
- À écrire dans une tâche : la règle de départage d'une société réclamée par deux groupes, dont les groupes imbriqués (un groupe dont la tête est inscrite dans le document d'un autre).

### Dépôt des documents en lot, correspondance en un seul passage (T046)

- Nouvelle commande `python -m cartofr.perimetre.deposer <tête> <fichier>` ou `--dossier <dossier>` (avec `index.csv` : `tete,fichier`). Chaque document est copié dans `data/perimetre/` sous un nom neuf (`<tête>-<horodatage UTC>`), jamais écrasé ni effacé, et enregistré dans la table `documents_perimetre` du registre. Un nouveau dépôt pour la même tête ferme le précédent ; un document identique ne change rien. Les anciens fichiers restent dans `data/perimetre/`, pas dans un sous-dossier `ancien/` comme l'écrivait la spec : un nom horodaté suffit à ne rien écraser.
- `correspondre_plusieurs` lit les noms de SIRENE une seule fois pour tous les documents. Mesure (C3), LVMH et VINCI ensemble : 39 s groupés contre 70 s un par un, résultat identique ligne par ligne. La lecture des noms coûte 31 à 36 s selon la charge ; chaque document ensuite 0,1 à 0,2 s. Quelques centaines de documents tiennent donc en une à deux minutes. Les documents du pilote (Fnac Darty, Edenred) ne donnent toujours aucune ligne à l'extraction : ils n'ont pas servi à la mesure.
- La recherche des marques sort tout de suite quand le groupe n'a aucune marque, sans relire les noms. Non-régression avec les réglages de `config/` inchangée : LVMH 155/172, VINCI 813/1 007, CMAF 43/52.
- Revue adverse du jour. Corrigé :
  - un document qui ne donne aucune ligne (PDF scanné, format inconnu) remplaçait le bon document en vigueur : il est refusé, rien n'est écrit ;
  - `construire --remplacer` effaçait l'historique des dépôts : la reconstruction recopie `documents_perimetre` de l'ancien registre (le test a aussi trouvé que DuckDB refuse un paramètre dans `attach`) ;
  - le registre restait verrouillé en écriture pendant toute la correspondance (25 à 40 s) : la correspondance se fait en lecture, l'écriture ne dure que la transaction finale ;
  - une tête absente du registre était acceptée ; un index d'Excel (marque d'ordre des octets), un index mal formé, en cp1252 ou au point-virgule, un PDF abîmé sortaient en trace Python : tous refusés avec un message en français ;
  - un `commit` raté laissait des copies orphelines ; une copie interrompue n'était pas retirée ; les noms horodatés pouvaient se heurter au changement d'heure (UTC désormais) ; le nom du fichier d'origine n'est plus affiché.
- Tests : 21 dans `worker/tests/perimetre/test_deposer.py`, sur des documents et registres inventés. Suite worker : 553 réussis sans base Postgres.

### Départage d'une société réclamée par deux groupes (T047)

- Nouveau paquet `cartofr.pays`, fonction pure `departager(reclamations, groupes)`. Règle : un groupe dont la tête est inscrite dans le document d'un autre devient son sous-groupe et garde sa carto (décision de Loïc : chercher LVMH rend LVMH, filiale de Christian Dior) ; une société réclamée par les deux va au sous-groupe, le plus proche d'elle. Hors emboîtement : inscription avant descente ; entre inscriptions, taux, puis taille, puis plus petite tête ; entre descentes, niveau, puis plus petite tête ; un arbre non réclamé perd toujours.
- Écrite par un agent, relue : les parents se calculaient en comparant chaque tête à chaque autre, soit de l'ordre de 10^11 tours pour les 335 000 groupes du pays. Corrigé : parents calculés depuis les seuls documents ; test à 100 000 arbres en 1,5 s.
- Choix faits sans la spec, confirmés par Loïc le 2026-10-17 : quand plusieurs documents inscrivent la même tête, le parent est le document le plus proche (A inscrit B et C, B inscrit C : C sous B) ; une boucle de plusieurs groupes se casse à sa plus petite tête ; les arbres sont écartés avant l'emboîtement, et l'emboîtement passe avant les autres règles (une descente dans B bat une inscription de A si B est sous A).
- Tests : 31 dans `worker/tests/pays/test_departage.py`, dont 720 permutations de six réclamations et 300 graphes d'inscriptions tirés au hasard, sans boucle de parents.

## 2026-10-18

### La carto d'une société descend, elle ne remonte pas

Décision de Loïc. La carto d'une société, c'est cette société et tout ce qui descend d'elle : ses filiales, puis leurs filiales. On ne remonte jamais à sa mère ou à ses actionnaires pour prendre leurs autres filiales.

- Avant : `PRD.md` (US7, FR-012) et `ARCHI.md` rangeaient chaque société dans l'arbre entier de son sommet (T045). Chercher une filiale rendait aussi ses sœurs, et les filiales du holding qui la préside.
- Après : chaque société garde au plus une mère (document du groupe, sinon arbre du registre). La lecture (`/groupe?siren=`) part de la société cherchée et descend. Une société inscrite au document d'un groupe y entre avec ses filiales, sans les autres filiales de sa mère au registre.
- La carto d'une filiale nomme sa mère directe au-dessus de l'arbre, avec un lien vers la carto de la mère, sans ses autres filiales (décision de Loïc, même jour). Une mère entrepreneur individuel n'est pas affichée (garde-fou 6).
- S'accorde avec les groupes emboîtés (2026-10-16, T047) : le rangement d'une société dans un seul groupe ne change pas, seule la lecture change. La carto de la tête d'un groupe reste le groupe entier. T048 (C1) et T050 (route `/groupe`, page) sont réécrites en ce sens.
- Aucun code à changer : la table `arbre` porte déjà la mère de chaque société, et le moteur (T043) descend depuis la tête et les sociétés inscrites. Les scores de LVMH et VINCI (83 %, 2026-10-16) viennent du moteur : ils ne bougent pas.

### Carto du pays calculée chaque nuit (T048)

- Nouveau paquet `cartofr.pays.calcul` et travail `pays` : arbre, documents en vigueur retrouvés en un seul passage, moteur tête seule + périmètre par groupe à document, départage (T047), groupes des arbres, puis `pays.duckdb` écrit à côté et renommé. Une ligne `pays` dans `mises_a_jour` (`ajoutes` : sociétés rangées, `fermes` : groupes).
- Règle appliquée (décision de Loïc du jour) : un groupe est la descente depuis sa tête. Une société dont la mère est un entrepreneur individuel, une société fermée ou une société prise par un groupe à document est la tête de son propre groupe. Les sociétés d'une même personne ne sont plus regroupées (PRD, cas limite, mis à jour).
- Planification : un travail `pays` après chaque synchro terminée, et au plus tard 7 jours après le dernier calcul réussi ; un calcul en échec est réessayé une fois par jour ; un travail resté `en_cours` plus de 6 h (processus mort) ne bloque plus.
- Le moteur accepte des correspondances déjà calculées (`cartographier(..., correspondances=)`) : sans cela, chaque groupe relisait les 13 M de noms (30 s par groupe). Non-régression inchangée : LVMH 155/172, VINCI 813/1 007, CMAF 43/52.
- Mesure sur le registre réel, LVMH et VINCI déposés (`worker/scripts/mesure_pays.py`) : 114 s au total, 2,3 Go de mémoire au plus. 288 449 groupes de 2 sociétés ou plus, 937 396 sociétés dans ces groupes (12,0 % des 7 827 096 sociétés actives), les autres seules ; aucune ligne hors des sociétés actives. C4 : les cartos de LVMH (209 sociétés, 142/172 de la référence) et de VINCI (1 456, 836/1 007) sont identiques à celles de `non_regression.py --perimetre --sans-reglages`.
- 288 449 groupes contre 335 210 arbres de T045 : les sociétés d'un entrepreneur individuel ou d'une mère fermée ne sont plus réunies, et celles qui restent seules ne forment plus de groupe.
- Revue adverse du jour. Corrigé :
  - le départage pouvait ranger la tête d'un groupe à document dans un autre groupe (deux documents qui s'inscrivent l'un l'autre, ou deux documents qui inscrivent la même tête) : groupe sans tête et mères en boucle. La tête reste désormais dans son groupe ;
  - un travail `pays` resté `en_cours` après la mort du processus bloquait toute planification future ;
  - la preuve de la tête d'un sous-groupe nommait le mauvais groupe quand sa mère directe était prise par un troisième ;
  - un PDF abîmé pouvait faire échouer toute la carto (pypdf lève d'autres erreurs que `PyPdfError`) : il est compté en échec ;
  - la ligne du journal pouvait rester `en_cours` si le registre était occupé à la fin ; un vieux WAL de `pays.duckdb` aurait été rejoué sur le nouveau fichier ; la mesure affichait 100 % de sociétés rangées sans le mesurer.
- Tests : 24 dans `worker/tests/pays/test_calcul.py` et 6 dans `test_planification.py`, sur des registres et documents inventés. Suite worker : 740 réussis.
- Limite : le travail `pays` tient la file pendant son calcul ; une carto lancée par un consultant attend derrière lui (2 min aujourd'hui, à mesurer quand des centaines de documents seront déposés, T052).
