---
description: Generate implementation task files from PRD and Architecture — sliced by user story, in phases, with parallel markers
---

<objective>
Generate a structured set of implementation task files from existing PRD and Architecture documents.

Create well-scoped, coherent tasks that an AI agent can execute autonomously. Each task represents 1-3 hours of focused work with clear deliverables and success criteria. This comes AFTER PRD and ARCHI - both must exist first.

**The slicing rule**: tasks are grouped by **user story**, not by technical layer.
All the work for the P1 story sits together, so that finishing that group ships
something a user can actually use. A breakdown organised as "all the database
work, then all the API work, then all the UI" delivers nothing until the very
end — and cannot be cut short when time runs out.
</objective>

<context>
Current project: !`ls -la`
Existing specs folder: !`ls specs/ 2>/dev/null || echo "No specs folder"`
Package.json: !`cat package.json 2>/dev/null | head -20 || echo "No package.json"`
</context>

<process>
## Phase 1: Understanding

1. **Ask for project location**:
   > "Where is your project located? Are you starting from scratch or using a boilerplate?"

2. **Explore existing codebase**:
   - Read `package.json` for dependencies
   - Check folder structure (`app/`, `src/`, `components/`)
   - Identify what's already implemented

3. **Document current state**:
   - ✅ Already implemented: [list]
   - 🚧 Partially implemented: [list]
   - ❌ Not yet built: [list]

4. **Ask for PRD location**, then read completely:
   - Extract the **user stories with their P1/P2/P3 priorities**
   - Extract the functional requirements and which story each serves
   - Extract the **measurable success criteria** (SC-xxx) — these become the
     acceptance evidence that `/apex-converge` will check later
   - Note the edge cases and what is out of scope

5. **Ask for ARCHI location**, then read completely:
   - Note all technology choices
   - Understand patterns to follow
   - Identify integration points

## Phase 2: Deep Analysis

6. **Map each user story to implementation work**, story by story:
   - US1 (P1) → what models, UI, API, validation does *this story alone* need?
   - US2 (P2) → same question, assuming US1 is done
   - US3 (P3) → same

7. **Separate the shared work from the story work.** Anything two stories both
   need is not story work — it belongs in Foundational. Keep that layer as thin
   as you can: everything in it blocks everything else.

8. **Identify what can run in parallel.** Two tasks are parallel when they
   touch **no file in common** and neither depends on the other's output. That
   is the only test. "They feel independent" is not the test.

## Phase 3: Verify Before Creating

9. **Confirm checklist complete**:
   - ✅ Codebase understood
   - ✅ Every user story extracted, with its priority
   - ✅ Every functional requirement mapped to a story
   - ✅ All ARCHI decisions understood
   - ✅ Shared work separated from story work
   - ✅ Parallel tasks verified on the file-overlap test
   - ✅ Each success criterion from the PRD is covered by at least one task

**IF ANY MISSING**: Do more analysis first. Do NOT create tasks with gaps.

## Phase 3b: Constitutional Check

10. **Read the project constitution** — `🥇 Garde-fous`, `📐 Règles produit`,
    `⚖️ Principes de ce projet` in `CLAUDE.md` — and check that each obligation
    is **carried by a task**. Method: `.claude/rules/constitution.md`.

    This is the stage where a rule quietly disappears. "Tests on business
    logic", "keyboard navigation", "no real customer data in dev": if no task
    owns them, nobody will write them. Either an existing task's success
    criteria cover the rule, or you add a task.

    The resulting table goes into `specs/README.md`.

## Phase 4: Generate Task Files

11. **Create folder structure**:
    ```bash
    mkdir -p specs/01-mvp
    ```

12. **Phases, in this order.** The phase is what determines execution order;
    priority determines what you can cut.

    | Phase | Contains | Blocks what |
    |---|---|---|
    | **Setup** | Project scaffolding, dependencies, config, CI | Everything |
    | **Foundational** | What two or more stories both need: schema, auth, base layout | All stories |
    | **US1 (P1)** 🎯 | Everything that story needs, and nothing else | Nothing — shippable alone |
    | **US2 (P2)** | Same, for the second story | Nothing |
    | **US3 (P3)** | Same, for the third | Nothing |
    | **Polish** | Error handling, empty states, performance, cross-cutting cleanup | Nothing |

    **The checkpoint rule**: at the end of the US1 phase, the product must be
    demonstrable end to end for that story. If it is not, the split between
    Foundational and US1 is wrong — something the story needs is still sitting
    in a later phase.

13. **Naming**: `specs/01-mvp/T001-kebab-case-name.md`, numbered in execution
    order across all phases. `T9xx` is reserved — it is the series
    `/apex-converge` uses for tasks reopened after a convergence check.

14. **Task file structure**:

```markdown
# T001 — [Action-Oriented Title]

**Story**: US1 (P1) · **Phase**: Foundational · **Parallel**: [P] | sequential
**Covers**: FR-001, FR-002 · SC-001
**Estimated**: 1-3 hours

## Context
[Which user story this serves, and what it unblocks]

## Scope
[Specific deliverables for this task]

## Implementation Details

### Files to Create/Modify
- `path/to/file.ts` - [Purpose]

### Key Functionality
- [What the code should do]

### Technologies Used
- [From ARCHI with how it's used]

### Architectural Patterns
[Patterns from ARCHI to follow]

## Success Criteria
- [ ] **C1**: [Testable outcome — observable, not "the code is written"]
- [ ] **C2**: [Testable outcome]
- [ ] **C3**: [Testable outcome]

Each criterion must be checkable by reading the code or running a command.
`/apex-converge` will confront every one of them with the codebase and demand a
file path as evidence — a criterion like "the module is clean" cannot be
verified and will come back as a gap.

## Testing & Validation

### Manual Testing Steps
1. [Step]
2. [Step]

### Edge Cases
- [Edge case from the PRD, if this task owns it]

## Dependencies

**Must complete first**: T00X
**Blocks**: T00Y
**Shares files with**: [tasks that touch the same files — these can never be [P]]

## Related Documentation
- **PRD**: [story and FR references]
- **ARCHI**: [Reference]
```

15. **Create README overview** at `specs/README.md`:

```markdown
# Implementation Tasks Overview

## Project Summary
**From PRD**: [Summary]
**Tech Stack**: [From ARCHI]
**Current State**: [What exists]

## How to read this
- `[P]` = can run in parallel with other `[P]` tasks in the same phase
  (no shared files, no mutual dependency)
- Phases run in order. Within a phase, `[P]` tasks may run at once.
- **MVP = Setup + Foundational + US1.** Everything after is additive.

## Phase 1: Setup
- [ ] `T001` [P] - [Description]
- [ ] `T002` [P] - [Description]

## Phase 2: Foundational (blocks all stories)
- [ ] `T003` - [Description]
- [ ] `T004` [P] - [Description]

## Phase 3: US1 — [Story title] (P1) 🎯 MVP
- [ ] `T005` - [Description]
- [ ] `T006` [P] - [Description]

**Checkpoint**: at the end of this phase, [what a user can do end to end].

## Phase 4: US2 — [Story title] (P2)
- [ ] `T007` [P] - [Description]

## Phase 5: US3 — [Story title] (P3)
- [ ] `T008` - [Description]

## Phase 6: Polish
- [ ] `T009` [P] - [Description]

## Dependency Map
[Which task blocks which — text graph is fine]

## Parallel Opportunities
- Phase 2: T004 alongside T003? No — both touch `schema.prisma`
- Phase 3: T006 and T007 touch no common file → parallel

## PRD Coverage
| Story | Priority | Tasks | Success criteria covered |
|---|---|---|---|
| US1 | P1 | T005, T006 | SC-001, SC-002 |
| US2 | P2 | T007 | SC-003 |

Every FR and every SC from the PRD appears in this table. One that does not is
either out of scope — say so — or a task you forgot.

## Constitutional Check
[the table from Phase 3b]

## Total Estimated Time: [X-Y hours]
```
</process>

<constraints>
**SLICING**:
- Group by user story, never by technical layer
- Foundational holds only what **two or more** stories need. When in doubt, it
  belongs to the story, not to Foundational — an over-fed Foundational phase
  delays every demo
- Each story phase must be independently shippable and independently testable

**PARALLEL MARKERS**:
- `[P]` only when the tasks share **no file** and have no dependency between them
- Two tasks editing the same file are never `[P]`, however unrelated they look
- List shared files explicitly in each task — this is what lets `apex -m`
  hand tasks to the agent that owns those files

**TASK SIZING**:

❌ **Too Small**: "Add TypeScript type" · "Create button component" · "Add validation to field"

❌ **Too Large**: "Implement complete auth system" · "Build entire dashboard"

✅ **Just Right** (1-3 hours):
- "Create user authentication flow with email/password and session management"
- "Build dashboard layout with navigation and responsive design"
- "Implement checkout with Stripe integration and webhooks"

**OUTPUT FORMAT**:
- NEVER create a single document with all tasks
- ALWAYS create individual files in `specs/01-mvp/`, named `T0NN-slug.md`
- ALWAYS create `specs/README.md` overview
- Never use the `T9xx` range — it belongs to `/apex-converge`

**QUALITY**:
- Every task names its story, its phase, and what it covers
- Every success criterion is checkable against code or a command
- Every task has explicit dependencies and its shared-file list
</constraints>

<output>
**Created files**:
- `specs/README.md` - Overview, phases, parallel opportunities, PRD coverage
- `specs/01-mvp/T001-*.md` … - Individual task files

**Next step (suggest to the user)**:
> "Tasks created. Next:
> - `apex -x -b` on the first Setup task, and work down the phases.
> - `/myteam` if the project spans several domains — it generates the agent
>   team, and `apex -m` will then use the `[P]` markers and the shared-file
>   lists to run tasks in parallel.
> - `/apex-converge` once you think the MVP is done, to check the code against
>   these criteria rather than against the checkboxes."
</output>

<success_criteria>
- Every user story from the PRD has its own phase, in priority order
- Foundational contains only genuinely shared work
- The US1 phase ends on a stated, demonstrable checkpoint
- `[P]` markers verified on the file-overlap test, with shared files listed
- Every FR and SC from the PRD appears in the coverage table
- Each task is 1-3 hours, with verifiable success criteria
- Individual files created as `specs/01-mvp/T0NN-*.md`, none in the T9xx range
- README created with phases, dependency map and constitutional check
- No orphan tasks (everything connected to a story)
</success_criteria>
