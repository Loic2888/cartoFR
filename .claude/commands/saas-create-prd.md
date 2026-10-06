---
description: Create a lean Product Requirements Document through interactive discovery — prioritized user stories (P1/P2/P3) and measurable success criteria
---

<objective>
Create a focused Product Requirements Document (PRD) for an MVP through iterative conversation.

Guide the user through defining product vision, user personas, prioritized user stories, and measurable success criteria. Keep the PRD minimal and focused on essential features that solve real problems. This is the FOUNDATION - the PRD comes FIRST, then ARCHI, then implementation.

Two things make this PRD usable downstream, and both are non-negotiable:
**every user story carries a priority**, and **every success criterion is measurable**.
Without the priorities, task breakdown cannot slice the MVP. Without measurable
criteria, `/apex-converge` has nothing to check the code against.
</objective>

<process>
## Phase 1: Information Discovery

1. **Do NOT write anything until you have answers to ALL 5 areas below**

Ask questions progressively (2-3 at a time, not all at once) until you have complete clarity:

### Area 1: Problem & Vision
- What problem does this product solve?
- Who experiences this problem most acutely?
- What makes this solution unique or different?
- What does success look like?

### Area 2: Target Users
- Who are the primary users? (1-3 personas max)
- What are their key characteristics? (role, context, pain points)
- What motivates them to use this product?
- What would make them stop using it?

### Area 3: User Stories & Priorities
- What is the ONE journey this product must support end to end? → that is **P1**
- What 1-2 journeys support it but could ship a week later? → **P2**
- What is desirable but would not block a launch? → **P3**
- For each: who does what, and what do they get out of it?
- What happens when it goes wrong? (empty state, wrong input, no network, no permission)

**The P1 story is the MVP.** If two stories are both "absolutely P1", the scope
is not an MVP yet — help the user cut. Three P1 stories is a ceiling, not a target.

### Area 4: Measurable Success Criteria
- How will you measure if this product is working?
- For each metric: what is the **target number**, and **how is it measured**?
- What user behavior indicates success?
- What business metric matters most?

Push back on anything that cannot be measured. "Users love it" is not a
criterion; "60% of users who create an account complete an import within 7 days"
is. Reject vague goals like "increase engagement" — ask *engagement measured how,
from what baseline, to what target, by when*.

### Area 5: Constraints & Scope
- What technical constraints exist?
- What timeline are you working with?
- What resources are available?
- What are you explicitly NOT building in v1?

## Phase 2: Verify Completeness

2. **Before generating PRD**, confirm you have:

- ✅ Core problem clearly defined with specific user experiencing it
- ✅ 1-3 specific personas with roles, pain points, motivations
- ✅ Exactly one (at most three) **P1** user story, plus P2/P3 stories
- ✅ Edge cases named for the P1 story
- ✅ Success criteria that are **measurable**: target value + measurement method
- ✅ Clear list of what is NOT being built in v1
- ✅ Timeline and constraints understood

**IF ANY MISSING**: Ask more questions first. Do NOT generate PRD with gaps.

## Phase 3: Constitutional Check

3. **Read the project constitution** — the `🥇 Garde-fous`, `📐 Règles produit`
and `⚖️ Principes de ce projet` sections of `CLAUDE.md` — and check the scope
you are about to write against it. Method and verdicts:
`.claude/rules/constitution.md`.

At PRD stage the relevant ones are usually: French-language interface, GDPR and
data minimisation, EU hosting, no real customer data in development,
multi-tenant isolation.

Put the resulting table **in the PRD**, in a `## Constitutional Check` section.
A ⛔ means you stop and raise the conflict — you do not write the PRD around it.

## Phase 4: Generate PRD

4. **Create PRD.md** with this structure:

```markdown
# Product Requirements Document: [Product Name]

## Product Vision

**Problem Statement**
[2-3 sentences describing the core problem]

**Solution**
[2-3 sentences describing how this product solves it]

## Target Users

### Primary Persona: [Name]
- **Role**: [User role/context]
- **Pain Points**:
  - [Pain point 1]
  - [Pain point 2]
- **Motivations**: [What drives them]
- **Goals**: [What they want to accomplish]

### Secondary Persona: [Name] (if applicable)
- **Role**: [User role/context]
- **Pain Points**: [Key challenges]
- **Motivations**: [What drives adoption]

## User Scenarios

### User Story 1 — [Short title] (Priority: P1) 🎯 MVP
**As a** [persona], **I want to** [action], **so that** [outcome].

**Why this priority**: [what breaks if this ships late]
**Independently testable**: [how you would verify this story alone, with nothing else built]

**Acceptance scenarios**
1. **Given** [initial state], **when** [action], **then** [observable outcome]
2. **Given** [initial state], **when** [action], **then** [observable outcome]

### User Story 2 — [Short title] (Priority: P2)
[same structure]

### User Story 3 — [Short title] (Priority: P3)
[same structure]

### Edge Cases
- What happens when [boundary condition]?
- What happens when [the user has no data / no permission / no network]?
- What happens when [two users act at the same time]?

## Requirements

### Functional Requirements
- **FR-001**: The system MUST [specific capability] — *covers US1*
- **FR-002**: The system MUST [specific capability] — *covers US1*
- **FR-003**: The system MUST [specific capability] — *covers US2*

Every FR names the story it serves. An FR that serves no story is out of scope;
a story with no FR is not specified yet.

### Key Entities (if the feature involves data)
- **[Entity]**: [what it represents, its key attributes, what it relates to]

## Success Criteria

### Measurable Outcomes
- **SC-001**: [Metric] reaches [target] — measured by [method], baseline [value]
- **SC-002**: [Behaviour] happens for [X%] of [population] within [timeframe]
- **SC-003**: [Business outcome] — measured by [method]

Each criterion states **what**, **how much**, and **how it is measured**.
Criteria describe outcomes, not implementations: "search returns results in
under 1 second" is a criterion, "use an Elasticsearch index" is not.

## Out of Scope (v1)

Explicitly NOT building in MVP:
- [Feature/capability 1] — [why it waits]
- [Feature/capability 2] — [why it waits]

## Assumptions

Things taken as true without proof, which would change the product if false:
- [Assumption 1]
- [Assumption 2]

## Open Questions
- [Question 1 needing resolution]
- [Question 2 requiring validation]

## Constitutional Check
[the table from Phase 3]

## Timeline & Milestones
- **MVP Completion**: [Target timeframe]
- **First User Testing**: [Target]
- **Launch**: [Target]
```

## Phase 5: Save and Next Steps

5. **Save PRD.md** in project directory

6. **Suggest next steps**:
   > "PRD created. Next: `/saas-create-architecture` to design the technical
   > architecture from it. Then `/saas-create-tasks`, which will slice the work
   > by user story — which is why the P1/P2/P3 priorities above matter."
</process>

<constraints>
**DISCOVERY RULES**:
- NEVER write PRD until ALL 5 information areas are covered
- Ask 2-3 questions at a time, not all at once
- Dig deeper based on responses - don't accept vague answers
- Push for specific metrics, not goals like "increase engagement"

**PRIORITIES**:
- One P1 story is the target, three is the ceiling
- Each story must be **independently testable** — if US2 cannot be verified
  without US3 being built, they are one story, not two
- Priority reflects *what breaks if it ships late*, not what is exciting

**MEASURABILITY**:
- Every success criterion has a target value and a measurement method
- Criteria are technology-agnostic: they describe what the user or the business
  gets, never how the code does it
- A criterion nobody can measure is deleted, not softened

**MVP FOCUS**:
- Maximum 3-5 must-have functional requirements per P1 story
- If user lists 10 features, help them prioritize
- "Out of Scope" section is critical - define boundaries clearly

**OUTPUT RULES**:
- Target 2-3 pages max, not a 20-page spec
- Be specific and actionable, not vague

**CONVERSATION STYLE**:
- Keep it conversational, not interrogation
- Adapt questions based on their industry/context
- Help users think through trade-offs
</constraints>

<success_criteria>
- All 5 information areas have complete answers
- 1-3 specific personas defined with pain points
- User stories carry P1/P2/P3 priorities, and each is independently testable
- Each story has Given/When/Then acceptance scenarios
- Edge cases named for the P1 story
- Every success criterion has a target value and a measurement method
- Functional requirements each name the story they serve
- Out of Scope section explicitly defines boundaries, with reasons
- Constitutional check present, with no unresolved ⛔
- PRD saved as PRD.md in project directory
</success_criteria>
