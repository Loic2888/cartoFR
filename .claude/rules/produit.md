---
name: produit
type: rule
---

# Règle — Les 8 règles produit, en détail

> Le résumé est dans `CLAUDE.md`, section « 📐 Règles produit ». Ce fichier dit
> ce que chacune veut dire **concrètement**, pour qu'on n'ait pas à
> l'interpréter au moment d'écrire le code.

Elles sont déjà arbitrées : on ne les rediscute pas projet par projet. On les
applique, ou on les supprime explicitement du `CLAUDE.md` du projet avec la
raison.

---

## 1. Français

Tout ce que l'utilisateur voit : libellés, boutons, messages d'erreur, emails
transactionnels, pages légales, états vides.

- **Les messages d'erreur techniques se traduisent.** « Failed to fetch » n'est
  pas un message utilisateur. Dis ce qui s'est passé et quoi faire.
- **Les dates et nombres au format français** : `12/03/2026`, `1 234,56 €`,
  espace insécable avant `€` et `%`.
- Le code, les noms de variables et les commits restent dans la langue
  habituelle du projet. La règle porte sur ce qui est **visible**.

---

## 2. Responsive, mobile-first

- **On écrit le style mobile d'abord**, les media queries montent (`min-width`),
  jamais l'inverse.
- **320 px est le plancher réel.** Pas de débordement horizontal, pas de texte
  coupé, pas de bouton hors écran.
- **Aucune fonctionnalité réservée au desktop.** Un tableau large devient une
  liste de cartes ; il ne disparaît pas.
- **Cibles tactiles : 44 px minimum.** Un lien de 12 px de haut n'est pas
  cliquable au pouce.
- Ce qui se teste en priorité : les formulaires, les tableaux, les modales et
  les menus. C'est là que ça casse.

---

## 3. Accessibilité

Le socle, pas la conformité WCAG intégrale :

- **Contraste AA** — 4,5:1 pour le texte courant, 3:1 pour les grands titres.
  Vaut aussi pour les états `hover`, `disabled` et les textes sur image.
- **Tout au clavier.** Chaque action atteignable et déclenchable sans souris,
  dans un ordre de tabulation logique.
- **Focus visible.** Ne jamais faire `outline: none` sans remplacement.
- **Un label par champ.** Un placeholder n'est pas un label : il disparaît à la
  saisie.
- **Le sens ne passe jamais par la seule couleur.** Un état d'erreur porte une
  icône ou un texte, pas seulement du rouge.
- **Images : `alt` systématique.** Vide (`alt=""`) si l'image est décorative —
  ce qui est une décision, pas un oubli.

---

## 4. RGPD

- **Minimisation.** On ne collecte que ce dont on a besoin maintenant. Un champ
  « au cas où » est une dette juridique.
- **Consentement explicite** pour tout traitement non nécessaire au service.
  Case décochée par défaut ; un bandeau cookies sans refus possible n'est pas
  un consentement.
- **Effacement possible.** Toute donnée personnelle doit pouvoir être supprimée
  ou anonymisée sans casser l'intégrité de la base — à prévoir au moment du
  schéma, pas après.
- **Aucune donnée personnelle dans les logs.** Ni email, ni nom, ni IP, ni
  token, ni corps de requête brut. On journalise des identifiants internes.
- **Durée de conservation décidée** pour chaque type de donnée, et appliquée
  par une tâche, pas par une bonne intention.
- **Un sous-traitant est un transfert de données.** Analytics, support,
  emailing, LLM : à vérifier avant de brancher.

---

## 5. Hébergement et données en UE

- **Base, stockage de fichiers, logs et sauvegardes** en région européenne.
  À vérifier à la création de chaque ressource — c'est un réglage qu'on ne peut
  souvent plus changer après.
- **Les fournisseurs tiers aussi.** Un service hébergé hors UE qui reçoit des
  données personnelles est un transfert, même s'il est gratuit.
- **Un LLM est un sous-traitant.** Ce qu'on lui envoie sort du système : pas de
  donnée personnelle dans un prompt sans avoir tranché la question.

---

## 6. Aucune donnée client réelle en développement

- **Les jeux de test sont générés**, jamais un dump de production.
- Si un dump est absolument nécessaire, il est **anonymisé avant** de quitter
  la production — pas après être arrivé en local.
- Vaut aussi pour les **captures d'écran**, les **fixtures de test** et les
  **exemples de documentation**.

C'est la voie de fuite la plus fréquente et la moins surveillée : personne ne
protège une base de développement.

---

## 7. Isolation multi-tenant

S'applique dès que le produit sert plusieurs clients ou organisations.

- **Le cloisonnement est au niveau de la base**, pas dans le code applicatif.
  RLS Postgres ou équivalent : un client ne peut **techniquement** pas lire les
  données d'un autre, même si une requête est mal écrite.
- **Dès la V0.** Rétrofitter l'isolation sur un schéma existant est un chantier,
  et entre-temps chaque requête est une fuite potentielle.
- **Filtrer en applicatif ne suffit pas.** Un `WHERE tenant_id = ?` oublié une
  seule fois, et tout est visible.
- **À tester explicitement** : un test qui vérifie que le client A ne voit pas
  les données du client B.

Sur un outil mono-utilisateur, cette règle se supprime du `CLAUDE.md` du projet.

---

## 8. Tests sur la logique métier

- **Ce qui calcule ou décide arrive avec ses tests** : calcul de prix, de TVA,
  de dates, règles d'éligibilité, permissions, transitions d'état.
- **Ce qui n'en a pas besoin** : le rendu d'un composant de présentation, un
  passe-plat, une constante.
- **Les cas limites font partie du test**, pas seulement le cas nominal — zéro,
  négatif, vide, `null`, la date de changement d'heure, le dernier jour du mois.
- **Un bug corrigé arrive avec le test qui échouait avant.** Sans ça, il
  reviendra.

La question qui tranche : *si cette fonction se trompe, est-ce que quelqu'un
s'en aperçoit tout de suite ?* Si non, elle a besoin de tests.
