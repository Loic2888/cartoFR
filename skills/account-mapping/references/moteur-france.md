# Moteur France : cartographie sur registre local

Version 2.0.0 du skill, 2026-10-06. Mis au point sur LVMH, VINCI et Crédit Mutuel Alliance Fédérale, contre des cartographies de référence (Basile Advanced et Cargo (référence interne)).

## 1. Pourquoi un registre local

- La recherche web société par société trouve surtout les sociétés connues : 19 sociétés pour LVMH contre 172 chez Basile, 35 pour VINCI Energies contre 126.
- L'API RNE de l'INPI ne permet pas de chercher "les sociétés dirigées par X", et elle est limitée à environ 10 000 fiches par jour : un groupe comme VINCI ne passe pas en une journée.
- L'API Basile ne donne pas les mandats entre sociétés (doc lue le 2026-10-03).
- Avec le stock complet du registre en local, la recherche dans les deux sens prend quelques secondes, sans quota.

## 2. Les données

| Donnée | Source | Comment l'obtenir | Fichier produit |
| --- | --- | --- | --- |
| Toutes les sociétés (nom, adresse, NAF, effectif, statut) | SIRENE (INSEE), gratuit | `StockUniteLegale` et `StockEtablissement` en parquet sur data.gouv.fr (environ 3 Go) | `data/unite_legale.parquet`, `data/etablissement.parquet`, puis `build_sieges.py` donne `data/sieges.parquet` |
| Mandats entre sociétés, dirigeants | Registre national des entreprises (INPI), gratuit | Compte data.inpi.fr, puis demande "SFTP RNE" dans "Mes accès API / SFTP". Les identifiants affichés ouvrent le **FTP simple `www.inpi.net`** (pas le SFTP du port 9222, qui ne contient que des PDF). Fichier `stock_RNE_formalites_NIVEAU1_<date>.zip`, environ 15 Go | `ftp_download.py`, puis `build_links.py` donne `data/rne_links/` |
| Annonces officielles (secours) | BODACC, gratuit | API opendatasoft | `bodacc.py` (mode API seulement) |
| Sociétés dirigées par X (secours) | API Recherche d'entreprises, gratuit | Sans compte | `annuaire.py` (mode API seulement) |

Pièges connus :

- Les navigateurs ne savent plus ouvrir les liens `ftp://` : passer par `ftp_download.py`.
- Le FTP de l'INPI bloque souvent le canal de données. Il faut le mode passif avec l'adresse du serveur principal, un délai maximal et des reprises : `ftp_download.py` le fait, et reprend à l'octet près.
- Le stock est une photo datée (2026-03-04 pour la version utilisée). Les changements plus récents ne sont pas dedans.
- `build_links.py` lit les 165 Go décompressés sans rien écrire de décompressé sur le disque, sur plusieurs cœurs (15 minutes sur 14 cœurs). Il produit : `liens.parquet` (1,6 million de liens), `societes.parquet` (10,5 millions, avec opposition à la prospection et effectif), `personnes.parquet` (13 millions de dirigeants, usage interne seulement).

## 3. Les réglages d'un groupe (`config/<groupe>.json`)

| Clé | Rôle | Exemple |
| --- | --- | --- |
| `groupe`, `tete` | Nom court et SIREN de la tête | `"LVMH"`, `"775670417"` |
| `marques_sures` | Marques propres au groupe : suffisent seules (sauf société civile) | Louis Vuitton, Sephora, TAG Heuer |
| `marques_ambigues` | Prénoms, patronymes, mots courants, lieux : deuxième preuve toujours exigée | Celine, Fred, Zenith, Cheval Blanc |
| `marques_sures_homonymes` | Marques sûres mais aussi prénom ou nom courant : deuxième preuve toujours exigée | SEPHORA, VINCI, ASF |
| `marques_sigles` | Sigles : deuxième preuve seulement si le nom n'est guère que le sigle | LVMH, MHCS |
| `organigramme` | Liste publique des maisons, avec le **nom légal exact** : la plus grande société de ce nom devient tête de maison | "Fresh SAS", "Chateau Cheval Blanc" |
| `exclus`, `exclus_noms` | SIREN et débuts de nom à exclure (actionnaires familiaux, groupe homonyme) | Christian Dior SE, Agache, Aglaé ; Crédit Mutuel Arkéa |
| `familles_exclues` | Noms de famille qui ne comptent jamais comme dirigeant commun | ARNAULT |
| `priorite` | SIREN à préférer comme maison mère à égalité | Moët Hennessy |

Un agent peut proposer ces réglages (site du groupe, rapport annuel). Un humain doit les relire : sur VINCI, la marque Equans (groupe Bouygues) ajoutée par erreur faisait entrer environ 150 fausses sociétés ; sur LVMH, "Fresh" désignait "Fresh and Good" au lieu de Fresh SAS.

## 4. Les règles de preuve (dans `engine.py`)

Codes de rôle RNE, reconstitués en croisant les fiches avec les rôles lus par Basile :

- **Forts** (font entrer seuls) : 73 Président, 30 Gérant, 28 et 29 Gérant et associé indéfiniment responsable, 74 et 75 Associé indéfiniment responsable, 131 Associé commandité.
- **Moyens** (deuxième indice exigé) : 65 Administrateur, 11 Membre, 64 Membre du conseil de surveillance, 51 Président du conseil d'administration.
- **Faibles** : 99 Autre (deux autres indices exigés).
- **Exclus** : 71 et 72 Commissaires aux comptes, et tout rôle inconnu.

Une société entre dans le groupe si :

1. une société du groupe a sur elle un mandat fort ;
2. ou c'est la tête de maison d'une marque de l'organigramme validé ;
3. ou un GIE dont tous les membres sont du groupe ;
4. ou un mandat moyen plus un indice indépendant (marque, adresse du groupe, dirigeant commun qui la dirige), **sauf** si une société extérieure la dirige aussi (président, gérant, associé) : c'est alors une co-entreprise, rangée dans "participations sans contrôle" ;
5. ou un nom de marque sûre, sauf société civile, sauf marque homonyme, et sauf si le nom n'est que la marque, sans salarié connu et sans autre indice ;
6. ou un nom de marque plus un deuxième indice ;
7. ou une adresse du groupe plus un deuxième indice (un dirigeant commun suffit à une adresse du groupe).

Indices :

- **Adresse du groupe** : une adresse exacte où les sociétés du groupe (retenues, ou ayant déjà un indice propre) sont au moins la moitié des sociétés domiciliées, associations et fondations non comptées. Une adresse seule ne suffit jamais : dans une banque, des fonds gérés sont domiciliés chez la société de gestion sans être des filiales.
- **Dirigeants communs** : au moins deux personnes communes avec les sociétés retenues, ou une seule si elle dirige déjà au moins deux sociétés du groupe (cadre du groupe). Ne compte pas pour une société civile au nom ambigu.
- Jamais des filiales : associations, fondations, comités d'entreprise (CSE), sociétés de droit étranger (rangées à part).

Maison mère directe : le mandat le plus fort au registre (fort, puis "Autre", puis moyen ; à égalité la tête, puis `priorite`). Sinon, la tête de maison de sa marque. Sinon, la tête du groupe. Confiance : **A** lien lu au registre, **B** au moins deux indices, **C** à vérifier.

Ciblable : Oui pour la tête, les têtes de maison et les sociétés opérationnelles. Non pour les sociétés civiles, GIE et holdings sans salarié déclaré. Une tranche INSEE "NN" veut dire non renseignée, pas zéro salarié.

## 5. Ce que le moteur ne sait pas encore faire

- **Groupes mutualistes** : les caisses locales (environ 1 400 au Crédit Mutuel Alliance Fédérale) adhèrent à leur fédération sans mandat inscrit au registre. Le moteur n'en trouve presque aucune. Il faut une règle propre (affiliation coopérative) ou les agréger avec un compteur.
- **Filiales étrangères** et **pourcentages de détention** : hors du registre français (LEI GLEIF, rapports annuels).
- **Site web et page LinkedIn** : non calculés par le moteur.
- **Changements depuis la date du stock** : à compléter avec l'API RNE (flux "diff") pour les sociétés retenues.

## 6. Résultats de référence (2026-10-06)

| Groupe | Référence | Retrouvées | En plus (à vérifier) |
| --- | --- | --- | --- |
| LVMH | Basile, 172 sociétés | 90 % (154) | 15 |
| VINCI | Basile, 1 007 sociétés | 81 % (813) | 176 |
| Crédit Mutuel Alliance Fédérale | Cargo (référence interne), 52 SIREN | 83 % (43) | plusieurs centaines (la référence agrège les sous-ensembles) |

Avec des règles plus souples (adresse seule à plus de 85 %, co-entreprises non filtrées), on retrouvait plus de sociétés de la référence (92 %, 86 %, 87 %) mais aussi plus de faux. Les règles ci-dessus privilégient la justesse. Pour le Crédit Mutuel, 4 des 9 manquées sont des associations (fédérations, confédération), écartées volontairement.

Sur un échantillon de 30 sociétés VINCI "en plus", une vingtaine sont très probablement de vraies filiales que la référence n'a pas (Sogea Rhône-Alpes, Cegelec Ouest, Tunzini…), environ six sont douteuses (homonymes "SOGEA", "GTM BATIMENT"), deux sont des co-entreprises (règle 4 ajoutée depuis). La référence elle-même classe parfois de vraies filiales comme "partenaires hors groupe".
