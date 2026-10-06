# Règle — Tickets et suivi

S'applique automatiquement à toute interaction impliquant le tracker de ce projet.

> **À adapter avant usage.** Ce fichier est écrit pour un tracker branché en MCP
> (Linear, ClickUp, Jira, GitHub Issues…). Remplace les `<…>` par tes valeurs
> réelles, et **supprime les sections qui ne s'appliquent pas**. Une règle jamais
> utilisée finit par être fausse.

## 1. Périmètre — un seul projet depuis ce dossier

- Tracker : `<Linear / ClickUp / Jira / GitHub Issues>`
- Projet / board : `<nom exact>` · URL : `<url>`
- **Ne jamais créer de ticket dans un autre projet depuis ce dossier.**

Le cloisonnement par dossier est ce qui évite qu'un ticket de test atterrisse
dans le backlog d'un client.

## 2. Assignation par défaut

- Si aucun assigné n'est précisé → `<toi / personne>`.
- Vérifier que la personne **existe et a un siège** dans l'outil avant d'assigner.

Quelqu'un peut demander une tâche sans pouvoir la porter : il n'a pas de compte.
Dans ce cas, on le cite dans la description, on ne l'assigne pas. **Un ID inventé
est plus dangereux qu'un champ vide** : il passe la relecture sans alerter, puis
l'appel API échoue plus loin — ou réussit sur la mauvaise personne.

## 3. Labels

Un label **Type** + un label **Domaine** par ticket.

- **Type** — aligné sur le préfixe de commit : `feat` `fix` `refactor` `perf`
  `docs` `test` `style` `chore`. Un ticket et le commit qui le clôt portent le
  même type : c'est ce qui rend l'historique lisible dans les deux sens.
- **Domaine** — `<liste tes domaines : API, UI, Data, Infra…>`
- **Flags** optionnels : `blocked` · `needs-spec` · `tech-debt` · `good-first-issue`

La **priorité** se gère avec le champ natif du tracker, jamais en label.
En cas de doute sur le type : `feat` pour un livrable, `chore` pour de l'infra.

## 4. Statuts — synchronisation au fil de l'eau

| Événement | Statut |
|---|---|
| L'utilisateur mentionne un ticket (« on bosse sur PROJ-45 ») | **In Progress** |
| PR ouverte | **In Review** |
| PR mergée | **Done** |
| Travail partiel | reste **In Progress** |

Si le tracker est branché sur le repo et que le nom de branche porte l'ID, ces
transitions sont automatiques — on ne touche à rien. Sinon, Claude les applique
via le MCP au moment où l'événement arrive, pas en fin de session.

## 5. Ce qu'on écrit dans un ticket

- Titre : même convention que les commits (`type: sujet à l'impératif`).
- Le **problème** et le **résultat attendu**. Pas la solution technique, sauf si
  elle est imposée.
- Les critères d'acceptation, sous forme de cases à cocher vérifiables.
- Aucun secret, aucune donnée client réelle, aucun extrait de base de production.
