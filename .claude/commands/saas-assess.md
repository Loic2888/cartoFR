---
description: Évalue une idée avant de la construire — cadrage, recherche, définition, mise en forme, décision tracée go / à clarifier / kill
argument-hint: "<l'idée en une ou deux phrases> [slug=<nom-court>]"
---

<objective>
Décider si une idée mérite qu'on y mette du temps, et **laisser une trace de la
décision** — pas seulement un avis.

Cinq étapes, cinq fichiers, un verdict parmi trois. Un `kill` documenté est un
résultat utile : il vaut mieux que l'idée revienne dans six mois avec la raison
de son abandon sous les yeux que sans.

Ça marche sur un repo vide. Il n'y a rien à construire pour évaluer.
</objective>

<critical>
**Les cinq étapes s'arrêtent chacune.** Tu montres ce que l'étape a produit, tu
demandes si on continue. Une évaluation qui déroule d'un trait jusqu'au verdict
n'évalue rien : elle habille une conclusion prise à l'étape 1.

Et **tu peux t'arrêter en cours de route.** Si la recherche démolit l'idée, on
ne fait pas les trois étapes suivantes pour la forme.
</critical>

<context>
Évaluations existantes : !`ls assessments/ 2>/dev/null || echo "aucune"`
</context>

<process>

## Étape 0 — Le slug

Dérive un slug court en `kebab-case` de l'idée, ou prends celui passé en
argument. Tout vit dans `assessments/<slug>/`.

Si le dossier existe déjà, **lis ce qu'il contient et reprends là où c'était
resté.** Ne recommence pas une évaluation faite.

---

## Étape 1 — Intake · `01-intake.md`

Ce qu'on croit savoir, avant d'avoir cherché. Sans ça, la recherche cherche au
hasard.

Pose les questions par deux ou trois, pas toutes d'un coup :

- **Le problème.** Qui le vit, à quelle fréquence, et que fait-il aujourd'hui à
  la place ? *L'alternative actuelle est la donnée la plus importante de toute
  l'évaluation* — s'il n'y en a pas, c'est souvent qu'il n'y a pas de problème.
- **Qui.** Un segment nommable. « Les PME » n'est pas un segment ; « le RevOps
  d'une boîte SaaS de 30 à 80 personnes » en est un.
- **La solution envisagée**, en une phrase.
- **Le pari.** Qu'est-ce qui doit être vrai pour que ça marche ? C'est ce qu'on
  ira vérifier.
- **Le renoncement.** Qu'est-ce qui ferait abandonner ? Fais-le écrire
  **maintenant**, avant les résultats. Après, il sera renégocié.

Écris le fichier, et dedans : **les 3 à 5 hypothèses à tester**, classées par
ce qu'elles coûteraient si elles étaient fausses.

> **Arrêt.** « Voilà ce que je vais aller vérifier. C'est bien ça le pari ? »

---

## Étape 2 — Recherche · `02-research.md`

**Lis `.claude/commands/saas-challenge-idea.md` et applique-le en entier.**
Sa méthode de recherche concurrentielle — 5 à 10 concurrents directs et
indirects, prix, signaux de revenu, saturation du marché, franchise brutale —
est déjà écrite et fait le travail. Ne la réécris pas.

Deux ajouts propres à l'évaluation :

1. **Reprends les hypothèses de l'étape 1, une par une**, et dis pour chacune :
   `confirmée` / `infirmée` / `pas de donnée`. C'est ça le livrable, pas le
   tableau de concurrents.
2. **Cherche aussi la demande, pas seulement l'offre.** Des gens qui décrivent
   le problème sans produit en face : discussions, questions récurrentes,
   bricolages maison. Un marché sans concurrent **et** sans plainte n'est pas
   un marché vierge, c'est un non-problème.

Range le rapport de `saas-challenge-idea` dans `02-research.md`, suivi du
tableau des hypothèses.

> **Arrêt.** Si le score de viabilité est bas ou si l'hypothèse la plus chère
> est infirmée : **propose le `kill` tout de suite**, saute aux étapes 3-4 et va
> directement écrire la décision. On ne met pas en forme une idée morte.

---

## Étape 3 — Définir · `03-define.md`

On sait ce qui existe. On dit maintenant ce que **celle-ci** ferait, et pour
qui, en assumant de laisser des choses dehors.

- **L'utilisateur, resserré** après la recherche. Souvent plus étroit qu'à
  l'étape 1 — c'est bon signe.
- **Le job précis**, formulé du point de vue de l'utilisateur, pas du produit.
- **Ce qui est dedans**, 3 à 5 capacités maximum.
- **Ce qui est dehors**, explicitement, avec la raison. Cette liste-là est la
  plus utile du fichier.
- **La différence qui tient.** Pas « plus simple » ni « plus moderne » : une
  chose qu'un concurrent identifié à l'étape 2 ne peut pas faire, et pourquoi
  il ne peut pas.
- **Les critères de succès**, mesurables, avec cible et méthode de mesure —
  même format qu'un PRD, pour qu'ils se transmettent tels quels ensuite.

> **Arrêt.** « Voilà le périmètre. Ce qui est dehors est-il vraiment dehors ? »

---

## Étape 4 — Mettre en forme · `04-shape.md`

Ce que ça coûte, et ce qui pourrait faire capoter. Pas de conception technique
ici — c'est le travail de `saas-create-architecture`, et il est prématuré.

- **La forme la plus petite qui prouve quelque chose.** Souvent pas un produit :
  une page, un script, un service rendu à la main. Dis-la.
- **L'ordre de grandeur de l'effort** pour cette forme-là : jours, semaines,
  mois. Un ordre de grandeur, pas une estimation — on n'en sait pas assez.
- **Les risques**, classés par ce qu'ils coûtent × leur probabilité. Nomme le
  risque qui tue le projet s'il se réalise.
- **Les inconnues qui restent**, et pour chacune : **ce qui les lèverait.**
  C'est ce qui alimente un verdict « à clarifier ».
- **Ce qu'on ne saura qu'en construisant.** Il y en a toujours. L'admettre
  évite de faire durer l'évaluation pour se rassurer.

> **Arrêt.** « Voilà ce que ça engage. On tranche ? »

---

## Étape 5 — Décider · `05-decision.md`

Un verdict, **un seul**, et il est écrit en haut du fichier :

| Verdict | Quand | Ce qui suit |
|---|---|---|
| **go** | Le pari tient, l'inconnue restante ne bloque pas le démarrage | `/start` — l'intake et la définition alimentent directement le PRD |
| **à clarifier** | Une inconnue nommée empêche de trancher | La façon de la lever, et **qui** la lève. Pas « creuser le marché » : une action datée. |
| **kill** | Le pari ne tient pas | On archive, et **on écrit ce qui devrait changer** pour rouvrir le dossier |

Le fichier :

```markdown
# Décision — <idée> · <AAAA-MM-JJ>

**Verdict : go | à clarifier | kill**

## Pourquoi
<trois à cinq lignes, et elles renvoient aux fichiers 01 à 04>

## Ce qui a changé d'avis
<ce qu'on croyait à l'étape 1 et qui s'est révélé faux — souvent le plus utile>

## Le renoncement, revisité
<le critère d'abandon écrit à l'étape 1 : atteint, ou pas ? réponse franche>

## La suite
<une action, un responsable, une échéance — ou « archivé »>

## Ce qui ferait rouvrir le dossier
<pour un kill ou un à clarifier : le signal concret qui justifierait d'y revenir>
```

**« à clarifier » n'est pas un demi-oui.** C'est un arrêt, avec une chose
précise à aller chercher. Si la chose n'est pas nommable, ce n'est pas « à
clarifier », c'est « kill ».

Un **go** ne lance rien : il se passe à `/start`, qui commencera à l'étape 2 —
l'idée vient d'être validée bien plus sérieusement que ne le ferait son
étape 1.

</process>

<constraints>
- **Un arrêt entre chaque étape.** Sans exception.
- **La recherche avant la définition.** Définir avant d'avoir cherché produit
  une idée qui se défend elle-même.
- **Aucun chiffre sans source.** Un concurrent, un prix, une levée : d'où ça
  vient. Un chiffre inventé dans une évaluation contamine tout ce qui suit.
- **Ne pas repousser le verdict.** Une évaluation qui s'allonge est une
  évaluation qui n'ose pas conclure. Cinq étapes, puis on tranche.
- **Ne pas enchaîner sur `/start`** de ta propre initiative, même sur un `go`.
- **Pas de push, pas de PR.** Cette command écrit cinq fichiers markdown.
</constraints>

<success_criteria>
- `assessments/<slug>/` contient les cinq fichiers, dans l'ordre.
- Les hypothèses de l'étape 1 sont reprises et tranchées à l'étape 2.
- Le critère d'abandon a été écrit **avant** les résultats, et relu à l'étape 5.
- Ce qui est hors périmètre est écrit, avec la raison.
- Le verdict est l'un des trois, et il est justifié par des lignes des fichiers
  précédents.
- Un `à clarifier` nomme l'inconnue et l'action qui la lève.
- Un `kill` dit ce qui ferait rouvrir le dossier.
</success_criteria>
