---
description: Lance un nouveau produit de bout en bout — enchaîne validation de l'idée, PRD, architecture et découpage en tâches, avec un point d'arrêt entre chaque étape
argument-hint: "<nom ou pitch du produit>"
---

<objective>
Conduire les 4 étapes du pipeline produit **dans l'ordre**, en s'arrêtant entre
chacune pour validation. Chaque étape mange la sortie de la précédente : sauter
un maillon, c'est deviner au maillon suivant.

Tu es le **chef d'orchestre**, pas l'exécutant. Chaque étape a déjà sa méthode
écrite dans son propre fichier — tu la lis et tu l'appliques intégralement.
</objective>

<critical>
**Une command ne peut pas en invoquer une autre.** Pour chaque étape :
**lis le fichier `.claude/commands/<nom>.md` et applique-le en entier.**
Ne résume pas sa méthode, ne l'improvise pas — ces fichiers font 130 à 300
lignes chacun, et c'est là qu'est la valeur.
</critical>

<process>

## Étape 0 — Cadrer, avant de lancer quoi que ce soit

Ne démarre pas sur un pitch d'une ligne. Établis d'abord :

1. **Que veut-on construire, pour qui ?** Une à deux phrases.
2. **Qu'est-ce qui existe déjà ?** Cherche `PRD.md`, `ARCHI.md`,
   `specs/`, un `README` fourni. Ce qui existe se lit, ne se réécrit pas.
3. **Quel est le point d'entrée ?** Selon ce que tu as trouvé, on ne commence
   pas forcément à l'étape 1 — voir le tableau ci-dessous.

| Ce qui existe déjà | Commence à |
|---|---|
| Rien, juste une idée | Étape 1 |
| Un `assessments/<slug>/05-decision.md` en **go** | Étape 2 — l'idée vient d'être validée, ne la rejuge pas |
| La décision de build est prise, l'idée n'est pas à challenger | Étape 2 |
| Un `PRD.md` | Étape 3 (lis le PRD, ne le réécris pas) |
| Un PRD **et** une architecture | Étape 4 |
| Un `specs/README.md` déjà peuplé | Le pipeline est déjà passé — ne rien refaire, dire où on en est. Si le code a avancé depuis, la bonne command est `/apex-converge`, pas celle-ci. |

Annonce le point d'entrée et ce que tu sautes, avec la raison. Attends l'accord.

## Étapes 1 à 4 — le pipeline

| # | Fichier à lire et appliquer | Produit |
|---|---|---|
| 1 | `.claude/commands/saas-assess.md` | `assessments/<slug>/01→05`, verdict **go / à clarifier / kill** |
| 2 | `.claude/commands/saas-create-prd.md` | `PRD.md` — user stories P1/P2/P3, critères mesurables |
| 3 | `.claude/commands/saas-create-architecture.md` | `ARCHI.md` + les principes du projet |
| 4 | `.claude/commands/saas-create-tasks.md` | `specs/01-mvp/T0NN-nom.md` + l'index `specs/README.md` |

L'étape 1 applique elle-même `saas-challenge-idea.md` pour sa phase de
recherche concurrentielle : ne la lance pas en plus, tu ferais le travail deux
fois. Si l'utilisateur veut seulement un avis franc sur son idée, sans les cinq
étapes ni la trace écrite, `/saas-challenge-idea` seule suffit — mais alors on
n'est plus dans `/start`.

**Entre chaque étape, tu t'arrêtes.** Tu montres ce qui a été produit, en trois
lignes, puis tu demandes : on continue, on corrige, on s'arrête là ?

Deux étapes sont **interactives par construction** et posent leurs propres
questions — ne les court-circuite pas :

- L'étape 1 évalue l'idée en cinq temps, avec un arrêt entre chacun, et rend un
  verdict. Sur **kill** ou **à clarifier**, **dis-le et arrête-toi** : écrire un
  PRD pour une idée que l'étape précédente vient d'écarter n'a aucun sens. Seul
  un **go** ouvre l'étape 2.
- L'étape 2 refuse d'écrire le PRD tant que ses 5 zones d'information ne sont
  pas couvertes, et refuse un critère de succès qu'on ne peut pas mesurer.
  C'est voulu. Laisse-la poser ses questions.
- Les étapes 2, 3 et 4 passent chacune un **contrôle constitutionnel** avant
  d'écrire leur livrable (`.claude/rules/constitution.md`). Un verdict ⛔
  arrête l'étape : le conflit remonte à l'utilisateur, il ne s'arbitre pas.

## Étape 4b — Remplir CLAUDE.md, tout de suite

Dès que `ARCHI.md` existe, **tu remplis toi-même** les sections que
l'utilisateur ne peut pas connaître avant : c'est toi qui viens de les décider.

1. **`## Stack`** — une seule ligne, dérivée d'`ARCHI.md` :
   `` `framework + langage` · `UI` · `base de données` · `hébergement` · région `xx` ``
2. **`## Structure`** — l'arborescence de premier niveau, **5 à 10 lignes max**,
   un commentaire court par dossier. Pas l'arbre complet.
3. **`## ⚖️ Principes de ce projet`** — recopie les 3 à 7 principes que
   l'étape 3 a arrêtés, dans la section `Project Principles` d'`ARCHI.md`. Ils
   deviennent la partie « propre au projet » de la constitution, celle que le
   contrôle constitutionnel relira à chaque étape et à chaque plan d'`apex`.
   Un principe invérifiable (« le code doit être propre ») ne se recopie pas :
   il ne contraint rien.
4. **Le titre** de `CLAUDE.md`, `AGENTS.md` et `MEMORY.md` si le
   `<NOM DU PROJET>` y traîne encore.
5. **Les chemins sensibles**, en bas de `CLAUDE.md` : remplace le placeholder
   par les vrais — dossier de migrations, fichiers de configuration de
   production.

Puis **relis la section « 📐 Règles produit »** de `CLAUDE.md` et signale à
l'utilisateur toute règle qui ne s'applique manifestement pas au projet qu'on
vient de spécifier — l'isolation multi-tenant sur un outil mono-utilisateur,
par exemple. **Tu ne la supprimes pas toi-même** : tu la signales, c'est sa
décision.

<critical>
Ne touche PAS au tableau `## Commandes`. Il n'y a pas encore de manifeste à
lire ; `install.sh` le détectera quand le projet sera scaffoldé.
</critical>

## Étape 5 — la suite, sans la faire

Quand les 4 étapes sont passées, **arrête-toi** et restitue :

```
Pipeline terminé.

  assessments/<slug>/ verdict go, 5 étapes tracées
  PRD.md              <n> user stories · P1 : <titre> · <n> critères mesurables
  ARCHI.md            <stack retenue> · <n> principes de projet
  specs/01-mvp/       <n> tâches, <n> phases, MVP = Setup + Foundational + US1
  specs/README.md     l'index, les dépendances et la couverture du PRD
  CLAUDE.md           Stack, Structure et Principes remplis

Ensuite :
  1. apex sur la 1re tâche de la phase Setup, puis on descend les phases.
  2. Puis relance install.sh : le tableau Commandes se détectera enfin,
     et sans lui la validation d'apex ne lance rien.
  3. Projet à plusieurs domaines ? `/myteam`, une seule fois — mais
     seulement après, il lui faut du code à partitionner.
  4. Quand la phase US1 est censée être finie : `/apex-converge`, qui
     confronte le code aux critères plutôt qu'aux cases cochées.
```

**N'enchaîne pas sur l'implémentation de ta propre initiative.** Le pipeline
produit des documents ; écrire le code est une décision distincte, qui se prend
en regardant les tâches.

</process>

<constraints>
- **Ordre strict.** Aucune étape ne se saute en silence. Sauter se dit, avec
  la raison, et se fait valider.
- **Applique les fichiers, ne les résume pas.** Chaque command porte une
  méthode détaillée ; la remplacer par ton improvisation, c'est perdre tout
  l'intérêt du pipeline.
- **Attention à la stack.** `saas-create-architecture` et
  `saas-implement-landing-page` supposent Next.js et shadcn/ui. Sur une autre
  stack, prends la méthode et écarte les choix techniques imposés — en le
  disant.
- **Les satellites ne sont pas dans le pipeline** : `saas-define-pricing`,
  `saas-find-domain-name`, `saas-create-headline`,
  `saas-create-landing-copywritting`, `saas-implement-landing-page`,
  `saas-create-logos`, `saas-create-legals-docs`. Mentionne-les à la fin si
  c'est pertinent, ne les lance jamais tout seul.
- **Pas de push, pas de PR.** Ce pipeline écrit des fichiers, rien d'autre.
</constraints>

<success_criteria>
- Point d'entrée annoncé et validé avant de commencer.
- Les 4 étapes appliquées depuis leurs fichiers, dans l'ordre.
- Un point d'arrêt entre chaque, avec ce qui a été produit.
- `PRD.md`, `ARCHI.md` et `specs/01-mvp/` existent réellement à la fin.
- Chaque étape a passé son contrôle constitutionnel, sans ⛔ non résolu.
- `CLAUDE.md` : Stack, Structure et `⚖️ Principes de ce projet` remplis, titres
  corrigés dans les trois fichiers, tableau `Commandes` laissé intact.
- Toute règle produit manifestement inapplicable a été signalée, pas supprimée.
- Restitution finale + prochaines étapes, sans avoir commencé à coder.
</success_criteria>
