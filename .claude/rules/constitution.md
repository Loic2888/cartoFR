---
name: constitution
type: rule
---

# Rule — La constitution du projet, et son contrôle

> Lis-la quand tu produis ou modifies un document de pipeline (PRD, ARCHI,
> tâches), et quand tu planifies une implémentation dans `apex`.

## Ce qu'est la constitution

Elle n'est pas un fichier de plus. **C'est ce qui est déjà écrit dans le
`CLAUDE.md` du projet**, dans trois sections, et rien d'autre :

| Section de `CLAUDE.md` | Ce qu'elle porte |
|---|---|
| `🥇 Garde-fous` | Ce qui ne se contourne jamais, y compris hors code (branches, PR, secrets) |
| `📐 Règles produit` | Les 8 arbitrages valables pour tout projet — détail dans `produit.md` |
| `⚖️ Principes de ce projet` | Ce qui a été décidé **pour celui-ci**, au moment du PRD et de l'architecture |

Le choix de ne pas créer un `CONSTITUTION.md` séparé est délibéré : `CLAUDE.md`
est le **seul** fichier dont le chargement est garanti à chaque session. Une
constitution que personne ne charge ne contraint personne.

## Le problème qu'elle résout

Sans contrôle, ces règles sont décoratives. On les écrit une fois, puis
l'architecture choisit un hébergeur hors UE, les tâches oublient les tests sur
la logique métier, et personne ne s'en aperçoit avant la revue — ou avant la
production.

Une règle n'est une contrainte que si **quelque chose la relit au moment où on
pourrait la violer**. C'est tout l'objet du contrôle ci-dessous.

## Le contrôle constitutionnel

Il s'insère à **quatre moments**, toujours au même endroit : juste **avant**
d'écrire le livrable, jamais après.

| Où | Quand | Ce qu'on vérifie |
|---|---|---|
| `saas-create-prd` | Avant d'écrire `PRD.md` | Le périmètre est-il compatible avec les règles ? |
| `saas-create-architecture` | Avant d'écrire `ARCHI.md` | Chaque choix technique respecte-t-il la constitution ? |
| `saas-create-tasks` | Avant d'écrire les tâches | Les obligations sont-elles portées par une tâche ? |
| `apex`, étape 02 (plan) | Avant d'écrire du code | Le plan enfreint-il une règle ? |

### Le format, identique partout

```markdown
## Contrôle constitutionnel

| Règle | Verdict | Sur quoi |
|---|---|---|
| Français | ✅ | Tous les libellés et emails sont en français |
| Hébergement UE | ⚠️ | Vercel → région `cdg1` à forcer, tâche T004 |
| Isolation multi-tenant | ⛔ | Le schéma n'a pas de `tenant_id` — bloquant |
| Tests sur la logique métier | ➖ | Aucune logique de calcul à ce stade |
```

Quatre verdicts, pas plus :

- **✅ conforme** — dis sur quoi tu te bases, en quelques mots. Un ✅ sans
  justification ne vaut rien.
- **⚠️ conforme sous condition** — la condition devient une **ligne du
  livrable** : une contrainte dans `ARCHI.md`, une tâche dans `specs/`. Une
  condition qui ne se matérialise nulle part est un ⛔ déguisé.
- **⛔ non conforme** — **tu n'écris pas le livrable.** Tu poses le conflit à
  l'utilisateur et tu attends. Voir ci-dessous.
- **➖ sans objet** — la règle ne s'applique pas à cette étape. Dis pourquoi en
  trois mots. Ce n'est pas la même chose que la supprimer du projet.

### Sur un ⛔

Un conflit se remonte, il ne s'arbitre pas tout seul. Trois issues, c'est à
l'utilisateur de choisir :

1. **Changer le livrable** pour respecter la règle — le cas normal.
2. **Amender la constitution** : la règle était mal calibrée pour ce projet.
   Elle se modifie **dans `CLAUDE.md`**, avec la raison écrite à côté. Une
   règle qu'on contourne en silence est pire que pas de règle : elle apprend à
   la session suivante qu'on peut contourner.
3. **Acter une exception ponctuelle**, tracée à l'endroit du livrable —
   « hébergement hors UE pour ce service tiers, parce que … ».

Ce qui n'est **jamais** une issue : écrire le livrable en espérant que
personne ne relise le tableau.

## Les principes propres au projet

La section `⚖️ Principes de ce projet` de `CLAUDE.md` est vide à
l'installation. Elle se remplit **au moment du PRD et de l'architecture**, avec
ce qui a été tranché et qu'on ne veut plus rediscuter à chaque tâche.

Un bon principe :

- porte sur le **comment**, pas sur le quoi — le quoi est dans le PRD ;
- est **vérifiable** : on peut dire d'un bout de code s'il le respecte ;
- a **coûté quelque chose** : on a écarté une alternative pour l'adopter.

> ✅ « Toute écriture en base passe par une fonction de service, jamais depuis
> un composant. »
> ✅ « Aucune dépendance nouvelle sans alternative en dépendance zéro examinée. »
> ❌ « Le code doit être propre. » — invérifiable, donc décoratif.

Trois à sept principes. Au-delà, plus personne ne les relit, et le contrôle
devient une formalité qu'on remplit sans regarder.

## Ce que le contrôle n'est pas

- **Ce n'est pas une revue de code.** Il regarde des décisions, pas des
  implémentations. La revue, c'est `apex -x`.
- **Ce n'est pas une étape de plus dans le pipeline.** C'est un bloc de dix
  lignes dans un livrable qui existait déjà. S'il commence à coûter une
  conversation, il est mal fait.
- **Ce ne s'applique pas à la voie directe.** Une typo, un renommage, une
  question ne passent par aucun contrôle. Le sur-contrôle se fait désactiver
  aussi vite que le sur-routage — voir `routing.md`.
