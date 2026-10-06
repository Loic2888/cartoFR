# MEMORY.md — cartoFR

Ce qui a été décidé, et ce qui a déjà fait mal. Pas un journal de bord : le
suivi des tâches vit dans `specs/README.md`, pas ici.

**La règle du tri, avant d'écrire une ligne :**

> *Est-ce que ce sera encore vrai la semaine prochaine, et est-ce que
> quelqu'un d'autre en aurait besoin ?*

Deux oui → ça s'écrit. Un seul non → non. Un fichier de mémoire qui contient
tout ne se lit plus, et une mémoire qu'on ne lit plus ne sert à rien.

**Format d'une entrée** : `- **AAAA-MM-JJ** — <le fait>. <la conséquence pratique>.`

Dates toujours absolues. « La semaine dernière » ne veut plus rien dire dans
six mois.

---

## Décisions techniques

Les choix structurants et **leur pourquoi**. Le pourquoi compte plus que le
choix : sans lui, la décision sera défaite par la première personne qui trouve
qu'elle est bizarre.

Ce qui mérite une entrée : un choix de bibliothèque, un pattern imposé, une
option écartée, une contrainte qui a façonné l'architecture.

Ce qui n'en mérite pas : ce qui est déjà lisible dans `ARCHI.md` ou dans le
code.

- **2026-10-05** — Registre complet en local plutôt qu'appels d'API par carto. L'API INPI plafonne à ~10 000 fiches/jour (VINCI seul en demandait deux jours) ; en local, une carto prend quelques minutes. Les API ne servent plus qu'à la mise à jour.
- **2026-10-06** — Recherche "sociétés dirigées par X" faite sur `data/rne_links/liens.parquet` (1,6 M liens), construit depuis le stock FTP INPI. L'API INPI ne sait pas chercher dans ce sens.
- **2026-10-06** — Règles réglées pour la justesse : les règles souples retrouvaient plus (92/86/87 %) mais avec plus de faux. On a gardé les strictes (90/81/83 %).
- **2026-10-06** — L'adresse seule ne suffit plus à faire entrer une société, même à plus de 85 % du groupe à l'adresse : les fonds domiciliés chez La Française entraient à tort.

<!-- Exemple de ce qu'on attend :
- **2026-01-15** — Rendu côté serveur par défaut, `"use client"` seulement sur
  les composants qui ont besoin d'un état. Choisi parce que les pages de liste
  chargeaient 400 ko de JS pour afficher du texte. Conséquence : toute nouvelle
  page part serveur, et passer client se justifie.
-->

---

## Pièges déjà payés

Ce qui a fait perdre du temps une fois. On l'écrit pour ne pas le repayer.

C'est la section la plus utile du fichier, et la plus souvent vide parce qu'on
oublie de l'alimenter au moment où ça fait mal.

- **2026-10-05** — BODACC : prénoms pris pour des sociétés ("Celine"), noms de famille ("NOM Prénom"), noms plus longs ("MOET HENNESSY INVESTISSEMENTS"). D'où les listes de marques ambiguës et la deuxième preuve exigée.
- **2026-10-05** — Sigle écrit "M H C S" au registre et "MHCS" ailleurs : mettre les deux variantes dans les marques.
- **2026-10-05** — Majorité du groupe à une adresse calculée trop tôt dans la boucle : elle ne joue qu'une fois les mandats ajoutés.
- **2026-10-05** — FTP INPI : il faut le mode passif en ignorant l'IP renvoyée, et des reprises automatiques (`ftp_download.py`). Les navigateurs n'ouvrent plus les liens ftp://.
- **2026-10-06** — `pyright worker` lancé depuis la racine ne vérifie aucun fichier et sort à 0 sans rien afficher : faux vert. Toujours `pyright -p worker`, qui lit `worker/pyproject.toml`.
- **2026-10-06** — Equans (groupe Bouygues) dans les réglages VINCI a fait entrer ~150 fausses sociétés ; "VINCI" et "ASF" doivent toujours exiger une deuxième preuve.

<!-- Exemple :
- **2026-01-22** — Les migrations tournent dans une transaction unique : un
  `ALTER TYPE` sur un enum y échoue toujours. Il faut le sortir dans sa propre
  migration. Deux heures perdues à croire à un problème de droits.
-->

---

## Contraintes externes

Ce qui vient de l'extérieur et qu'on ne choisit pas : limites d'API, quotas,
formats imposés, dépendances qui bougent, contraintes légales.

- **2026-10-06** — Stock RNE : `actif` n'est jamais `false`, il vaut `true` ou vide (244 311 liens vides). Vide = actif, comme le moteur (`coalesce(actif, true)`). Un filtre `actif = true` perd 15 % des liens.

- **2026-10-05** — API INPI : ~10 000 fiches/jour/compte, erreur 429 au-delà, pas de recherche inverse, 10 000 résultats max par requête.
- **2026-10-03** — Licence INPI : les données personnes ne servent pas à la prospection ; `diffusionCommerciale = false` = opposition à la prospection (75 sociétés sur 174 chez LVMH).
- **2026-10-06** — Stock RNE local = photo du 2026-03-04. Tout ce qui a changé depuis manque tant que la synchro quotidienne n'existe pas.
- **2026-10-06** — Caisses locales du Crédit Mutuel (~1 400) : aucun mandat au registre, le moteur ne peut pas les trouver par les liens.

---

## À ne pas refaire

Les fausses bonnes idées déjà essayées, et pourquoi elles ont été abandonnées.
Sans cette section, elles reviennent tous les trois mois.

- **2026-10-03** — Chercher les filiales sur le web société par société (skill v1) : 1 société sur 4 à 1 sur 9 retrouvée.
- **2026-10-03** — Compter sur l'API Basile pour les liens : elle ne les fournit pas.

---

## Comment ce fichier se remplit

Après une tâche significative, tu te poses la question du tri ci-dessus. Si la
réponse est oui, tu ajoutes l'entrée **au moment où c'est frais** — pas plus
tard, parce que plus tard on a oublié le pourquoi et il ne reste que le quoi.

Si une entrée devient fausse, **corrige-la ou supprime-la**. Une mémoire
périmée est pire qu'une mémoire vide : elle est suivie avec la même confiance
qu'une entrée juste.

Une entrée qui dépasse quatre lignes ne va pas ici : condense-la et pointe vers
le fichier qui porte le détail.
