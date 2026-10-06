---
description: Relit le code réellement écrit contre les specs, rouvre les tâches non faites et rend un verdict Convergé / Non convergé — ne code jamais
argument-hint: "[chemin des specs, défaut specs/01-mvp/]"
---

<objective>
Répondre à une seule question, avec des preuves : **est-ce que ce qui est dans
`specs/` est réellement dans le code ?**

Une case cochée dans `specs/README.md` n'est pas une preuve. Un fichier qui
existe n'est pas une preuve. La preuve, c'est un critère de succès vérifié
contre le code ou contre une commande qui tourne.

À la fin, deux issues possibles et pas une troisième : **Convergé**, ou
**Non convergé** avec la liste des tâches rouvertes.
</objective>

<critical>
**Cette command n'écrit pas une ligne de code.** Elle lit le code, elle écrit
des fichiers de specs. Corriger ce qu'elle trouve est le travail d'`apex`, dans
une session distincte, sur une tâche nommée. Un convergeur qui répare ce qu'il
mesure ne mesure plus rien.
</critical>

<context>
Specs : !`ls specs/01-mvp/ 2>/dev/null || echo "ABSENT"`
Index : !`ls specs/README.md 2>/dev/null || echo "ABSENT"`
Rapports antérieurs : !`ls specs/convergence/ 2>/dev/null || echo "aucun"`
</context>

<process>

## Phase 0 — Préalables

Si `specs/01-mvp/` ou `specs/README.md` manque, **arrête-toi** : il n'y a rien
contre quoi converger. Dis-le, et renvoie vers `/start` (étape 4,
`saas-create-tasks`).

Si `specs/convergence/` contient déjà des rapports, **lis le plus récent**
avant toute chose. Il porte les écarts déjà constatés : c'est lui qui permet de
distinguer un écart neuf d'un écart qui résiste, et c'est ce qui rend le
critère d'arrêt applicable (voir Phase 5).

## Phase 1 — Inventaire

Lis `specs/README.md`, puis **chaque** fichier de `specs/01-mvp/`.

Pour chaque tâche, extrais :

- son **identifiant** (`T0NN`) et son titre ;
- sa **user story** et sa **priorité** (`P1` / `P2` / `P3`) ;
- ses **critères de succès**, un par un, tels qu'ils sont écrits ;
- son **statut déclaré** dans l'index.

Numérote les critères `T0NN-C1`, `T0NN-C2`… C'est cette granularité qui compte :
on ne rouvre pas une tâche entière parce qu'un détail manque, et on ne la
déclare pas faite parce que l'essentiel y est.

## Phase 2 — Confronter au code

**C'est le cœur, et c'est là qu'il faut être lent.**

Lance des agents en parallèle — un par user story, ou un par groupe de 5 à 8
critères. Chacun reçoit la liste brute des critères qui le concernent et
rapporte, **pour chaque critère**, un verdict parmi trois :

| Verdict | Signifie | Preuve exigée |
|---|---|---|
| `fait` | Le comportement existe dans le code | `chemin/fichier.ts:42` — ce que fait ce code |
| `partiel` | Le code existe mais ne couvre pas tout le critère | Le chemin **et** ce qui manque précisément |
| `absent` | Rien dans le code ne réalise ce critère | La recherche menée, pour qu'on puisse la refaire |

**Règles de preuve, non négociables :**

- Un verdict `fait` sans chemin de fichier est un verdict `absent`. Sans
  exception, sans « c'est évidemment là ».
- Un fichier vide, un `TODO`, un `throw new Error("not implemented")` ou un
  composant qui ne rend rien → `absent`, pas `partiel`.
- Un critère qui parle de comportement observable (« l'utilisateur reçoit un
  email de confirmation ») se vérifie sur le chemin complet — l'appel existe
  **et** il est branché. Une fonction jamais appelée → `partiel`.
- Un critère non vérifiable par lecture (« la page charge en moins de 2 s ») →
  verdict `non vérifié`, quatrième cas, qu'on **liste à part** et qu'on ne
  compte ni comme fait ni comme absent. Dis à l'utilisateur comment le mesurer.

Puis fais tourner ce que le projet sait lancer — tableau `## Commandes` de
`CLAUDE.md` : typecheck, lint, tests, build. Note le résultat brut. Un tableau
`Commandes` à moitié faux fait « valider dans le vide » : si une commande
n'existe pas, dis-le, ne l'invente pas.

## Phase 3 — Classer les écarts

Un écart = un critère `absent` ou `partiel`.

Regroupe-les par **cause**, pas par fichier :

1. **Jamais commencé** — la tâche entière est absente.
2. **Commencé, pas fini** — le gros est là, il manque des morceaux nommés.
3. **Fait autrement** — le code résout le besoin par un autre chemin que celui
   spécifié. **Ce n'est pas forcément un écart à corriger** : c'est peut-être
   la spec qui est périmée. Ne tranche pas seul, remonte-le à l'utilisateur.
4. **Régression** — un critère était `fait` au rapport précédent et ne l'est
   plus. À signaler en tête de rapport, c'est le plus grave.

## Phase 4 — Rouvrir les tâches

Pour chaque écart des catégories 1, 2 et 4, écris ou rouvre une tâche.

- **Jamais commencé** → la tâche existante est simplement remise à `[ ]` dans
  l'index. On n'en crée pas une nouvelle.
- **Commencé, pas fini** → nouvelle tâche `specs/01-mvp/T9NN-<slug>.md`, au
  format habituel, avec en plus :

  ```markdown
  **Origine** : convergence 2026-09-17 — écart sur T012-C3
  **Périmètre** : uniquement ce qui manque, listé ci-dessous. Ne pas
  réimplémenter ce qui est déjà en place.
  ```

  La série `T9NN` est réservée aux tâches nées d'une convergence : on voit d'un
  coup d'œil ce qui est du plan initial et ce qui est du rattrapage.
- **Fait autrement** → **aucune tâche**. Une ligne dans le rapport, une question
  à l'utilisateur : on aligne le code sur la spec, ou la spec sur le code ?

Puis **remets `specs/README.md` d'aplomb** : les cases cochées doivent refléter
les verdicts, pas les intentions. C'est souvent la modification la plus utile de
toute la command.

## Phase 5 — Verdict et critère d'arrêt

Écris `specs/convergence/<AAAA-MM-JJ>-convergence.md` :

```markdown
# Convergence — <AAAA-MM-JJ>

**Verdict : Convergé** | **Non convergé — <n> tâches rouvertes**
**Tour n° <n>** (rapports précédents : <liste ou « aucun »>)

## Régressions
<en tête, ou « aucune »>

## Couverture

| Priorité | Critères | fait | partiel | absent | non vérifié |
|---|---|---|---|---|---|
| P1 (MVP) | 24 | 21 | 2 | 1 | 0 |
| P2 | … | | | | |

## Validation projet
typecheck : ✅ · lint : ✅ · tests : ❌ 3 en échec · build : ✅

## Écarts, par cause
### Jamais commencé
- **T014** — …
### Commencé, pas fini
- **T012-C3** → rouvert en `T901-webhook-retry.md` — …
### Fait autrement — décision à prendre
- **T008-C2** — la spec dit Zod, le code valide dans le handler. Question : …

## Non vérifiables par lecture
- **T003-C4** « moins de 2 s au chargement » — à mesurer avec …

## Prochaine action
<une seule phrase>
```

**Le verdict est mécanique, il ne se négocie pas :**

> **Convergé** = tous les critères des tâches **P1** sont `fait`,
> **et** typecheck, lint, tests et build sont verts.

P2 et P3 non faits n'empêchent pas la convergence du MVP — ils sont comptés,
listés, et c'est tout. Un seul critère P1 `partiel` suffit à dire **Non
convergé** : il n'y a pas de « convergé à 95 % ».

**Le critère d'arrêt de la boucle**, lui, protège d'un autre échec — tourner en
rond :

- **Trois tours maximum.** Au 3ᵉ rapport consécutif non convergé, tu
  **t'arrêtes et tu remontes le problème à l'utilisateur** au lieu de rouvrir
  une quatrième fois. Trois échecs sur le même écart ne sont pas un problème
  d'exécution, c'est un problème de spec ou d'architecture.
- **Un écart qui revient deux fois à l'identique** ne se rouvre pas une
  troisième fois automatiquement : il remonte, avec les deux rapports en
  regard.
- **Aucun progrès entre deux tours** (mêmes compteurs) → arrêt immédiat, même
  si on est au tour 1. Reboucler sans progression consomme du budget sans rien
  produire.

## Phase 6 — Restituer

Trois lignes maximum dans la conversation :

```
Non convergé — 4 tâches rouvertes (tour 2/3).
  P1 : 21/24 critères faits · 1 régression sur T007
  Rapport : specs/convergence/2026-09-17-convergence.md
  Prochaine action : apex -x -b sur T901-webhook-retry
```

Puis **arrête-toi.** N'enchaîne pas sur `apex` de ta propre initiative : lancer
l'implémentation est une décision de l'utilisateur, prise en regardant le
rapport.

</process>

<constraints>
- **Aucune écriture de code.** Ni correctif, ni « pendant que j'y suis ». Les
  seuls fichiers modifiés sont sous `specs/`.
- **Aucune preuve = absent.** La charge de la preuve est sur le code, pas sur
  le doute.
- **Ne jamais cocher une case par optimisme.** L'index de specs devient faux, et
  un index faux est pire que pas d'index : il éteint la vigilance.
- **Ne pas réécrire les specs d'origine.** On ajoute des tâches `T9NN`, on
  corrige des cases. Réécrire une spec pour qu'elle colle au code, c'est
  supprimer l'écart au lieu de le traiter.
- **Pas de push, pas de PR, pas de branche.**
</constraints>

<success_criteria>
- Chaque critère de chaque tâche P1 a un verdict, et chaque `fait` porte un
  chemin de fichier.
- Les commandes du projet ont été lancées, résultats bruts dans le rapport.
- Les écarts sont classés par cause, pas listés en vrac.
- Les tâches rouvertes existent réellement, en série `T9NN`, avec leur origine
  et un périmètre limité à ce qui manque.
- `specs/README.md` reflète la réalité constatée.
- Le rapport est daté, numéroté en tours, et porte un verdict binaire.
- Le critère d'arrêt a été appliqué : pas de 4ᵉ tour, pas de reboucle sans
  progrès.
</success_criteria>
