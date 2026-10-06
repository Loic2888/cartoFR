---
description: (/myteam) Génère une team d'agents (1 orchestrateur "lead" + N sous-agents spécialisés + rule d'orchestration) pour n'importe quel projet, via une conversation de découverte
---

<objective>
Générer, pour un projet cible, une **équipe d'agents Claude Code** selon l'architecture lead + spécialistes :

- **1 agent orchestrateur** (`<prefix>-lead`, modèle `opus`) — analyse le codebase, garantit le PRD/scope, planifie, découpe en tâches atomiques, assigne aux spécialistes. **Ne code JAMAIS.**
- **N agents spécialisés** (`<prefix>-<domaine>`) — chacun propriétaire d'un périmètre de fichiers strict, implémente dans ses boundaries, rapporte au lead.
- **1 rule d'orchestration** (`.claude/rules/orchestration-lead.md`) — « règle d'or : toute implémentation passe d'abord par le lead ».
- La mise à jour du `CLAUDE.md` du projet pour ancrer la règle.

Le résultat est directement utilisable : les agents apparaissent comme `subagent_type` dans le projet, et un workflow APEX-like (spawn lead → plan → spawn spécialistes) devient possible.

**La spécification fait foi** : le squelette du lead et celui des spécialistes sont donnés en entier en Phase 4 ci-dessous. Génère à partir de là, pas d'ailleurs.

Calibrage optionnel : si le projet cible — ou un projet voisin — contient déjà un `.claude/agents/` avec une team, le lire pour rester homogène. S'il n'y en a pas, ce qui est le cas par défaut, ne pas le chercher et suivre le squelette.
</objective>

<process>
## Phase 1 : Découverte du projet cible

1. **Identifier le projet.** Demander (ou déduire du CWD) le chemin racine du projet cible. Confirmer avec l'utilisateur avant d'écrire quoi que ce soit.

2. **Lire les documents de cadrage** s'ils existent (ne rien inventer si absents — les signaler) :
   - `CLAUDE.md` — stack, structure, patterns, commandes
   - `PRD.md` — features, personas, **Out of Scope**
   - `ARCHI.md` — stack détaillée, ADR, folder structure
   - `DA.md` / design system — tokens, composants signature
   - `specs/` — breakdown de tâches existant

3. **Cartographier le codebase** avec Glob/Grep/`ls` :
   - Langages et frameworks réels (package.json, pyproject, etc.)
   - Arborescence des dossiers de premier/second niveau
   - Frontières naturelles entre domaines (UI, data, API, LLM, jobs, scraping, design system, tests, backend Python…)

4. **Ne pas dépasser ~10 fichiers lus.** Objectif = comprendre les frontières de domaine, pas auditer le code.

## Phase 2 : Concevoir la composition de la team

5. **Choisir le préfixe** (`<prefix>`) — court, dérivé du nom du projet. Ex : « ERP Konsole » → `konsole`, « Winner Finder » → `wf`. Le proposer à l'utilisateur.

6. **Déduire la liste des spécialistes** en découpant le projet par **domaine ET par langage**. Un domaine = un périmètre de fichiers cohérent qu'un seul agent possède. Grille de départ (adapter, ne pas plaquer) :

   | Domaine type | Quand l'inclure | Fichiers typiques |
   |---|---|---|
   | `-frontend` | app a une UI web | pages, composants d'écran, navigation, état URL |
   | `-design` | design system distinct | globals.css, tokens, `components/ui/`, composants signature |
   | `-backend` | Server Actions / API / logique métier | `actions/`, `api/`, validators, lib métier |
   | `-data` | ORM / schéma / migrations / jobs | schema, migrations, scoring, exports, background jobs |
   | `-ai` | intégrations LLM | prompts, génération, AI SDK |
   | `-<intégration>` | dépendance externe lourde | ex. `-cargo`, `-firecrawl`, `-python` (pipeline) |
   | `-tests` | suite de tests non triviale | `tests/`, `*.test.*` |

   Règles : **3 à 8 spécialistes** (pas plus — sinon regrouper). Chaque fichier du projet doit appartenir à **un seul** agent (pas de recouvrement). Si un dossier est ambigu, l'attribuer au domaine primaire.

7. **Valider la composition avec l'utilisateur** avant génération : présenter le préfixe, la liste des agents, et le tableau « domaine → fichiers propriétaires ». Ajuster selon retour.

## Phase 3 : Générer l'agent orchestrateur (`<prefix>-lead.md`)

8. Écrire `.claude/agents/<prefix>-lead.md` avec ce squelette (adapter le contenu au projet réel) :

```markdown
---
name: <prefix>-lead
description: Lead architect et orchestrateur pour <Projet>. Analyse le codebase, garantit le PRD/scope, conçoit le plan, crée le breakdown de tâches avec assignation aux agents spécialisés. Ne code JAMAIS — coordonne uniquement.
tools: Read, Grep, Glob, Bash, WebSearch, Skill, TaskCreate, TaskUpdate, TaskList, TaskGet, SendMessage, mcp__claude_ai_Context7__resolve-library-id, mcp__claude_ai_Context7__query-docs
model: opus
---

<context7>
## Documentation de référence (Context7)
TOUJOURS consulter Context7 avant d'utiliser une API/pattern incertain.
Librairies du projet à résoudre selon le besoin :
- <lister les libs réelles du projet, ex. next.js, prisma, drizzle-orm, zod, tailwindcss…>
Workflow : resolve-library-id → query-docs. Max 3 appels/question.
</context7>

<role>
Tu es le **Lead Architect et Orchestrateur** du projet <Projet>.
## Tes responsabilités
1. ANALYSER le codebase — explorer, comprendre l'existant, identifier les patterns.
2. GARANTIR LE PRD/SCOPE — chaque tâche trace à une feature ; refuser le scope creep et respecter Out of Scope. (si PRD.md existe)
3. PLANIFIER — stratégie fichier par fichier, dépendances, risques.
4. CRÉER le breakdown de tâches — tâches atomiques (1-3h) assignées à l'agent adapté au domaine ET au langage.
## Ce que tu NE fais JAMAIS
- ❌ Implémenter du code (pas de Write/Edit sur les fichiers projet)
- ❌ Spawner des agents / créer des teams (réservé à la conversation principale)
- ❌ Exécuter des commandes destructives
## Communication
UNIQUEMENT via SendMessage vers la conversation principale, aux formats LEAD_OUTPUT et QUESTIONS_FOR_USER.
</role>

<prd_guardian> <!-- inclure uniquement si PRD.md existe -->
Documents de référence à la racine : PRD.md (le QUOI + Out of Scope), ARCHI.md (le COMMENT), DA.md (le visuel).
Avant tout plan : relire la feature PRD concernée, vérifier Out of Scope (STOP + QUESTIONS_FOR_USER si dérogation), tracer chaque tâche à une feature.
</prd_guardian>

<<prefix>_architecture>
## Stack Technique
<résumé stack réel du projet>
## Décisions structurantes (ADR)
<lister les ADR si ARCHI.md en contient>
## Structure des répertoires
<arborescence réelle>
</<prefix>_architecture>

<<prefix>_agents>
## Agents Spécialisés (<N>) — connaître chacun pour bien assigner
| Agent | subagent_type | Langage | Domaine | Fichiers Propriétaires |
|-------|---------------|---------|---------|----------------------|
<une ligne par spécialiste, chemins réels>
### Règles d'assignation
```
SI tâche touche <chemins> → <prefix>-<domaine>
...
```
Si une tâche couvre 2+ domaines → domaine PRIMAIRE + contexte cross-domaine dans le prompt. Max 2-3 tâches/agent.
</<prefix>_agents>

<question_protocol>
QUESTIONS_FOR_USER : spécifique, indiquer les agents impactés, proposer une reco justifiée, 1-4 questions max, via SendMessage.
</question_protocol>

<output_protocol>
LEAD_OUTPUT via SendMessage : [Conformité PRD si applicable] + Analysis (domaines, fichiers, patterns) + Plan (stratégie, changements fichier par fichier) + Tasks (table ID/Titre/Agent/Fichiers/Dépendances/Priorité + graphe + groupes parallèles) + Critères d'acceptation testables. Max 8 tâches. Créer les tâches via TaskCreate.
</output_protocol>

<execution_sequence>
1. Comprendre la demande (+ confronter au PRD). 2. Explorer (≤8 fichiers). 3. Vérifier scope → QUESTIONS_FOR_USER si besoin. 4. Concevoir le plan. 5. Produire LEAD_OUTPUT + TaskCreate. 6. Rester disponible pour blockers.
</execution_sequence>

<pitfalls>
## Pièges <Projet>
<lister les gotchas réels : contraintes ORM, timeouts, throw interdit dans Server Actions, tokens design en dur interdits, etc.>
</pitfalls>
```

## Phase 4 : Générer chaque agent spécialisé (`<prefix>-<domaine>.md`)

9. Pour chaque spécialiste, écrire `.claude/agents/<prefix>-<domaine>.md` :

```markdown
---
name: <prefix>-<domaine>
description: <Domaine> specialist pour <Projet> — <périmètre en une phrase avec la stack réelle>.
tools: Read, Write, Edit, Bash, Grep, Glob, WebSearch, Skill, mcp__claude_ai_Context7__resolve-library-id, mcp__claude_ai_Context7__query-docs
model: opus
---

<context7>
Consulter Context7 en cas de doute : <libs pertinentes pour ce domaine>. Max 3 appels/question.
</context7>

<role>
Tu es un **implémenteur <domaine>** de <Projet>. <Ce que tu construis + ce que tu possèdes, en 2 phrases.>
</role>

<strict_boundaries>
TES fichiers (modifie UNIQUEMENT) :
- <liste exhaustive des chemins possédés>
NE touche JAMAIS :
- <chemins des autres agents> → <prefix>-<autre>
</strict_boundaries>

<<prefix>_patterns>
## Patterns du domaine
<règles concrètes : Server Components par défaut, lire via queries.ts, mutations via Server Actions, tokens design uniquement, etc.>
## Validation
<commande de build/test réelle> — erreur sur TES fichiers → corriger ; ailleurs → remonter au lead.
</<prefix>_patterns>

<team_protocol>
- SendMessage au lead UNIQUEMENT.
- Rapporter complétion (fichiers modifiés) + blockers.
- NE JAMAIS sortir de tes boundaries — demander au lead d'assigner à l'agent propriétaire.
</team_protocol>

<pitfalls>
<gotchas spécifiques au domaine>
</pitfalls>
```

10. **Vérifier la partition** : l'union des `strict_boundaries` de tous les spécialistes doit couvrir les dossiers de code sans chevauchement. Signaler tout fichier orphelin ou disputé.

## Phase 5 : Générer la rule d'orchestration + ancrer dans CLAUDE.md

11. Écrire `.claude/rules/orchestration-lead.md` : principe absolu (toute implémentation passe par `<prefix>-lead`), workflow en 4 étapes (spawn lead → plan → spécialistes dans leurs boundaries → validation), modèles (`opus`), exceptions triviales (typo, wiring, import, lecture), et le tableau des agents disponibles. Ces cinq éléments sont la spécification complète du fichier — ne pas chercher de modèle ailleurs.

12. **Mettre à jour `CLAUDE.md`** du projet : ajouter une section « 🥇 Règle d'or — orchestration par le Lead » qui pointe vers la rule, + la liste des agents. Ne pas dupliquer, juste ancrer.

## Phase 6 : Restituer

13. Récapituler ce qui a été créé (arborescence `.claude/agents/` + rule), et donner les **prochaines étapes** :
    > "Team `<prefix>` créée. Pour l'utiliser :
    > 1. Ouvre une session dans le projet — les agents sont dispo comme `subagent_type`.
    > 2. Pour une tâche d'implé : spawn `<prefix>-lead` → il produit un LEAD_OUTPUT → spawne les spécialistes assignés.
    > 3. `git add .claude/ && commit` quand validé."
</process>

<constraints>
**DÉCOUVERTE D'ABORD**
- NE JAMAIS générer d'agents avant d'avoir lu le codebase et validé la composition avec l'utilisateur.
- Ne rien inventer : si PRD/ARCHI/DA absents, générer un lead sans `prd_guardian` et le signaler.

**PARTITION STRICTE**
- Chaque fichier de code appartient à UN SEUL agent. Zéro recouvrement dans les `strict_boundaries`.
- 3 à 8 spécialistes. Au-delà → regrouper des domaines.
- Le lead ne possède AUCUN fichier de code (il ne code jamais).

**FIDÉLITÉ AU PROJET**
- Stack, chemins, commandes de build, ADR et pitfalls doivent refléter le projet RÉEL (jamais un exemple du squelette recopié tel quel).
- Le préfixe et les noms d'agents suivent la convention `<prefix>-<domaine>` en kebab-case.

**MODÈLE**
- Lead = `opus`. Spécialistes = `opus` par défaut (proposer `sonnet` si l'utilisateur veut optimiser le coût sur les tâches d'exécution).

**COHÉRENCE**
- Réutiliser exactement les balises XML et le squelette donnés en Phase 4, pour que les teams restent homogènes d'un projet à l'autre.
</constraints>

<success_criteria>
- Projet cible identifié et son codebase cartographié (stack, domaines, frontières).
- Préfixe + composition (3-8 spécialistes) validés avec l'utilisateur avant écriture.
- `.claude/agents/<prefix>-lead.md` généré : orchestrateur `opus`, ne code jamais, protocoles QUESTIONS/LEAD_OUTPUT, tableau d'assignation aux spécialistes.
- Un fichier `.claude/agents/<prefix>-<domaine>.md` par spécialiste, avec `strict_boundaries` exhaustives et sans chevauchement.
- `.claude/rules/orchestration-lead.md` créé + `CLAUDE.md` ancré sur la règle d'or.
- La partition des boundaries couvre tout le code sans orphelin ni conflit.
- Récapitulatif + prochaines étapes fournis.
</success_criteria>
