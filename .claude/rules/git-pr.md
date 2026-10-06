# Règle — Git, branches et Pull Requests

S'applique à toute session Claude dans ce projet. Le résumé exécutable est dans
`CLAUDE.md` §Garde-fous ; ce fichier explique **le pourquoi** et traite les cas limites.

## 1. Pourquoi jamais de push direct sur `main`

Un push direct court-circuite trois choses d'un coup : la CI, la relecture, et
le lien entre le code et le ticket qui l'a demandé. Le coût n'est pas le push
lui-même, c'est qu'on ne sait plus, trois mois plus tard, pourquoi cette ligne
existe.

Le hook `.claude/hooks/git-guardrail.py` refuse la commande avant qu'elle
s'exécute. Ce n'est pas une consigne qu'on peut oublier au bout de 40 messages.

## 2. Nommage des branches

Format : `<user>/<id-ticket>-<slug>`

```
✅ loic/42-oauth-refresh-token
✅ loic/PROJ-107-questionnaire-client
❌ fix-bug              (pas d'ID → aucune liaison au ticket)
❌ ma-branche           (pas d'auteur, pas d'ID)
```

**L'ID dans le nom de branche n'est pas décoratif** : c'est lui que le tracker
lit pour faire bouger le statut du ticket tout seul. Sans lui, il faut tout
déplacer à la main, et donc on oublie.

## 3. Commits sémantiques (Conventional Commits)

Format : `type(scope): sujet`

| Type | Quand |
|---|---|
| `feat` | Nouvelle fonctionnalité visible par l'utilisateur |
| `fix` | Correction de bug |
| `refactor` | Réécriture sans changement de comportement |
| `perf` | Optimisation de performance |
| `docs` | Documentation seule |
| `test` | Ajout ou refonte de tests, sans toucher au code prod |
| `style` | Formatage, lint, espaces |
| `chore` | Dépendances, config, outillage, déploiement |
| `build` / `ci` | Chaîne de build, pipeline |
| `revert` | Annulation d'un commit précédent |

Règles : sujet à l'**impératif** (« ajoute », pas « ajouté »), en minuscule,
sans point final, sous ~70 caractères. `!` après le type pour un breaking
change : `feat!: retire l'endpoint v1`.

```
✅ feat(auth): ajoute le refresh de token
✅ fix: corrige le calcul de TVA sur les avoirs
❌ Ajout du refresh token.        (pas de type, majuscule, point final)
❌ wip                            (ne dit rien)
❌ feat: various fixes            (fourre-tout — découpe en plusieurs commits)
```

Référencer le ticket dans le corps ou le sujet : `feat: ajoute X (PROJ-42)`.

## 4. Pull Requests

- Titre de la PR = même convention que les commits. C'est lui qui devient le
  message du squash-merge, donc il finit dans l'historique de `main`.
- Une PR = un sujet. Si la description a besoin d'un « et aussi », c'est deux PR.
- Description : le **pourquoi** et comment tester. Le quoi se lit dans le diff.
- Draft tant que ce n'est pas prêt à relire — ça évite de mobiliser un relecteur
  pour rien.

## 5. Cas limites

| Situation | Quoi faire |
|---|---|
| Commit déjà poussé avec un message non conforme | Le laisser. On ne réécrit pas l'historique d'une branche partagée. Le titre de la PR corrige le tir au squash. |
| Il faut vraiment un `--force` | Uniquement sur sa propre branche, et `--force-with-lease` plutôt que `--force`. |
| Hotfix urgent en prod | Ça reste une branche + une PR. L'urgence justifie une relecture rapide, pas l'absence de relecture. |
| Le hook bloque une commande légitime | Ne le contourne pas en douce. Lis le message, ajuste la commande, ou modifie le hook et dis-le. |
| Un secret a été committé | Le révoquer chez le fournisseur d'abord. Le retirer du code ensuite. Dans cet ordre. |
