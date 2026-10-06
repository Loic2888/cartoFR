---
name: routing
type: rule
---

# Rule — Routage des demandes

> Le tableau de routage est dans `CLAUDE.md`, parce qu'il doit être chargé à
> chaque session. Ce fichier-ci porte le **pourquoi** et les **cas limites**.
> Lis-le quand une demande ne tombe pas nettement dans une case.

## Le principe

Une demande arrive sous une forme, pas sous une intention. « Ajoute un bouton »
peut être trois lignes de JSX ou un chantier de six fichiers. Le routage
consiste à trancher **avant** d'agir, une fois, explicitement — pas à
découvrir en cours de route qu'on aurait dû passer par apex.

## Le biais à corriger : le sur-routage

C'est le mode d'échec numéro un d'un routeur. Un workflow en 10 étapes
déclenché pour un renommage de variable coûte du temps, du token et de la
patience — et au bout de trois fois, l'utilisateur désactive le routage.

**En cas de doute, prends la voie la plus légère et propose la plus lourde.**

> « Je le fais directement, c'est deux lignes dans un seul fichier. Dis-moi si
> tu préfères que je passe par apex avec revue et tests. »

L'inverse — partir sur apex et s'apercevoir que c'était trivial — n'est pas
symétrique : le coût est déjà payé.

## Ce qui fait basculer vers apex

Pas le sujet de la demande, mais ces signaux :

- **Plus de 2 ou 3 fichiers** touchés, ou des fichiers dont on ne connaît pas
  encore les dépendances
- **Un comportement à préserver** : il existe des tests, ou le code est en
  production
- **Une incertitude sur le "où"** : il faut chercher avant de pouvoir écrire
- **Un risque de régression** ailleurs que là où on écrit

Un seul de ces signaux suffit. Aucun d'entre eux → voie directe.

## Choisir les flags

Les défauts d'apex sont tous à `false`. Quand tu le déclenches toi-même, tu
choisis, tu n'hérites pas :

| Situation | Flags | Pourquoi |
|---|---|---|
| Bug ou petite feature | `-x -b` | Revue adverse + branche. Le minimum quand on écrit du code. |
| Code couvert par des tests | `+ -t` | Créer et lancer les tests fait partie du travail, pas d'un bonus |
| Chantier multi-domaines | `-m -x -t -b` | Parallélisation, après `/myteam` — apex réutilise alors les agents du projet |
| Session longue à reprendre | `+ -s` | Sauvegarde dans `.claude/output/apex/`, reprise par `-r <task-id>` |
| Plan limité, budget serré | `-e` | Pas de sous-agents. À signaler à l'utilisateur, la qualité baisse. |

`-a` (auto, sans confirmation) ne se met **jamais** de ta propre initiative :
c'est à l'utilisateur de renoncer aux points de contrôle, pas à toi.

## Le pipeline produit, en détail

Les commands ne s'auto-invoquent pas : **lis le fichier et applique-le**.

| Ordre | Fichier | Sortie | Sauter si |
|---|---|---|---|
| 1 | `.claude/commands/saas-assess.md` | `assessments/<slug>/` + verdict go / à clarifier / kill | La décision de build est déjà prise |
| 2 | `.claude/commands/saas-create-prd.md` | `PRD.md` — user stories P1/P2/P3, critères mesurables | Un PRD existe → le lire |
| 3 | `.claude/commands/saas-create-architecture.md` | Architecture technique + principes du projet | Une archi existe → la lire |
| 4 | `.claude/commands/saas-create-tasks.md` | `specs/01-mvp/T0NN-nom.md`, par phases et par story | — |
| 5 | `apex` sur chaque fichier de tâche | Le code | — |
| 6 | `.claude/commands/apex-converge.md` | Verdict Convergé / Non convergé, tâches rouvertes | Rien n'a été implémenté depuis la dernière convergence |

Ne saute jamais une étape en silence : dis laquelle tu sautes et pourquoi.

L'étape 1 applique elle-même `saas-challenge-idea.md` pour sa recherche
concurrentielle. `/saas-challenge-idea` reste appelable seule quand on veut
juste un avis franc, sans les cinq étapes ni la trace écrite.

**L'étape 6 n'est pas une voie de routage.** C'est une mesure : elle relit
`specs/` contre le code, rouvre les tâches non faites en série `T9NN` et rend un
verdict binaire — tous les critères des tâches P1 `fait`, plus typecheck, lint,
tests et build verts, ou bien **non convergé**. Elle n'écrit jamais de code :
corriger est le travail d'`apex`, sur une tâche nommée, dans une session à part.
Trois tours maximum, et aucun reboucle sans progrès entre deux rapports : au 3ᵉ
échec, le problème remonte à l'utilisateur, parce qu'il n'est plus dans
l'exécution mais dans la spec.

Le bon moment pour la lancer : quand la phase US1 est **censée** être finie.
Après chaque tâche, c'est du bruit — les tâches suivantes n'ont pas encore été
écrites.

Un doc de spec fourni par l'utilisateur entre à l'étape 2 ou 3, **pas à
l'étape 5** — développer sans PRD ni architecture, c'est deviner. Et un doc
n'est pas une spec tant que les critères d'acceptation ne sont pas écrits.

Attention à la stack : `saas-create-architecture` et
`saas-implement-landing-page` supposent du Next.js et shadcn/ui. Sur une autre
stack, prends la méthode et ignore les choix techniques qu'elles imposent.

Les autres commands ne sont pas dans le pipeline, appelle-les à la demande :
`saas-define-pricing`, `saas-find-domain-name`, `saas-create-headline`,
`saas-create-landing-copywritting`, `saas-implement-landing-page`,
`saas-create-logos`, `saas-create-legals-docs`.

## Le diagnostic, en détail

Il n'y a pas de skill de diagnostic dans ce kit — n'improvise pas de workflow.
Établis les faits dans cet ordre, et arrête-toi dès que le bug est nommé :

1. **Demande la reproduction** si elle manque : quoi, attendu, obtenu.
2. **Lis les erreurs réelles** — logs, sortie de test, console. Jamais deviner.
3. **Reproduis**, ou dis explicitement que tu n'y arrives pas.
4. Bug nommé et reproduit → `apex -x -b "<le bug>"`.

Tant que le symptôme n'est pas reproduit, tu diagnostiques. Tu ne corriges pas.
Proposer un correctif sur un bug non reproduit, c'est deviner deux fois : sur
la cause, puis sur la solution.

## Cas limites

**La demande contient déjà une solution.** « Remplace ce useState par un
useReducer » — l'utilisateur a déjà tranché. Voie directe, sauf si tu vois que
la solution proposée casse quelque chose : dis-le en une phrase, puis fais ce
qui est demandé.

**Bug reproduit en une ligne.** Une typo dans une condition, un `<` au lieu de
`<=` : c'est un bug, mais c'est trivial. Voie directe.

**Demande de refactoring.** Presque toujours apex : par définition, ça touche
du code qui marche déjà, donc le risque de régression est le sujet même.

**« Fais ce que tu veux / améliore ça ».** Aucune voie. Demande ce qui gêne
concrètement avant de router quoi que ce soit — un routeur ne peut pas trancher
une demande sans critère de succès.

**Le doc de spec est fourni mais vague.** Entre à l'étape 2 du pipeline (PRD),
pas à l'étape 5. Un doc n'est pas une spec tant que les critères d'acceptation
ne sont pas écrits.

**Un projet a déjà une team d'agents** (`.claude/agents/<prefix>-*.md` existe).
Alors la règle d'or du projet s'applique et prime sur ce routage : toute
implémentation passe par `<prefix>-lead`. Voir
`.claude/rules/orchestration-lead.md`.

Deux façons de les mettre au travail, et il faut savoir laquelle on prend :

- **Directement.** C'est la voie normale. La règle d'orchestration est ancrée
  dans `CLAUDE.md`, donc la session principale spawne `<prefix>-lead`, qui
  spawne ses spécialistes. Aucune skill supplémentaire n'est nécessaire.
- **Via `apex -m`.** apex détecte `.claude/agents/`, lit les
  `strict_boundaries` de chaque spécialiste et assigne chaque tâche à celui qui
  possède les fichiers concernés. À prendre quand on veut aussi les étapes
  d'apex — plan, validation, revue adverse — autour de la parallélisation.

Sans agents dans le projet, `apex -m` retombe sur les Agent Teams génériques,
qui demandent `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`. Ce kit ne pose pas ce
drapeau : activer une fonctionnalité expérimentale est la décision du
propriétaire du projet. Sans lui, exécution séquentielle normale.

## Le contrôle constitutionnel, et quand il ne s'applique pas

Les étapes 2, 3, 4 du pipeline et l'étape *plan* d'`apex` relisent la
constitution du projet — garde-fous, règles produit, principes du projet — avant
d'écrire leur livrable. Méthode : `.claude/rules/constitution.md`.

**La voie directe n'y passe pas.** Une typo, un renommage, un import, une
question : aucun contrôle. Le sur-contrôle se fait désactiver exactement comme
le sur-routage, et pour la même raison — dix lignes de tableau pour corriger un
libellé, et au bout de trois fois l'utilisateur coupe.

## Ce que le routage ne fait jamais

- **Il ne dispense d'aucun garde-fou.** Les six règles de `CLAUDE.md`
  s'appliquent quelle que soit la voie, y compris directe.
- **Il ne se substitue pas à une question.** Si la demande est ambiguë sur ce
  qui compte — le périmètre, le comportement attendu — demande. Router une
  demande mal comprise produit vite beaucoup de code faux.
- **Il n'est pas silencieux.** Dis en une ligne quelle voie tu prends, surtout
  quand tu lances apex : l'utilisateur doit pouvoir t'arrêter avant les dix
  étapes, pas après.
