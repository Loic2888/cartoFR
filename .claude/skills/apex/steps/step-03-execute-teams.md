---
name: step-03-execute-teams
description: Execute implementation using Claude Code Agent Teams for parallel task execution
prev_step: steps/step-02b-tasks.md
next_step: steps/step-04-validate.md
---

# Step 3t: Execute with Agent Teams

## MANDATORY EXECUTION RULES (READ FIRST):

- 🛑 NEVER implement code yourself - you are the TEAM LEAD
- 🛑 NEVER use Edit, Write tools for implementation
- ✅ ALWAYS delegate implementation to teammates
- ✅ ALWAYS use delegate mode (Shift+Tab) to stay coordination-only
- ✅ ALWAYS keep the team alive after tasks complete
- 📋 YOU ARE A COORDINATOR, not an implementer
- 💬 FOCUS on assigning tasks, monitoring progress, resolving blockers
- 🚫 FORBIDDEN to write any implementation code

## EXECUTION PROTOCOLS:

- 🎯 Create team, assign tasks, monitor completion
- 💾 Log progress to output (if save_mode)
- 📖 Each teammate gets full task context
- 🚫 FORBIDDEN to implement anything yourself

## CONTEXT BOUNDARIES:

- Task breakdown from step-02b is available
- TaskList has all tasks with dependencies
- You have the plan from step-02
- Implementation has NOT started

## YOUR TASK:

Coordinate a team of Claude Code agents to implement all tasks in parallel, acting purely as team lead.

---

<available_state>
From previous steps:

| Variable | Description |
|----------|-------------|
| `{task_description}` | What to implement |
| `{task_id}` | Kebab-case identifier |
| `{auto_mode}` | Skip confirmations |
| `{save_mode}` | Save outputs to files |
| `{teams_mode}` | Should be true |
| `{tasks_mode}` | Should be true |
| `{output_dir}` | Path to output (if save_mode) |
| TaskList | All tasks with dependencies from step-02 |
| Task files | Individual task files from step-02b (if save_mode) |
</available_state>

---

## EXECUTION SEQUENCE:

### 1. Initialize Save Output (if save_mode)

**If `{save_mode}` = true:**

```bash
bash {skill_dir}/scripts/update-progress.sh "{task_id}" "03" "execute-teams" "in_progress"
```

### 2. Analyze Tasks for Team Sizing

Review TaskList and determine team size:

| Tasks | Teammates | Rationale |
|-------|-----------|-----------|
| 1-2 | 1 | Sequential is fine |
| 3-4 | 2 | Small parallel benefit |
| 5-8 | 3-4 | Good parallelism |
| 9+ | 4-6 | Max parallel benefit |

<critical>
NEVER create more than 6 teammates. Group related tasks if needed.
Cap at the number of independent task groups, not total tasks.
</critical>

### 3. Map Skills to Tasks

For each task, check if a matching skill should be suggested:

| Task Type | Suggested Skill |
|-----------|----------------|
| UI/Frontend components | `/frontend-design` |
| API endpoints | - |
| Database/schema | - |
| Tests | - |
| Documentation | - |

Add `skill_hint` to task assignments when relevant.

### 3b. Detect the project's own agents (DO THIS FIRST)

<critical>
Before creating anything, check whether this project already has a dedicated
agent team — created by `/myteam`.

```bash
ls .claude/agents/*.md 2>/dev/null
```

**If `.claude/agents/<prefix>-lead.md` exists**, that team was built FOR this
codebase: its specialists carry real, non-overlapping file boundaries. It beats
any generic executor. Use **Mode A** below and skip TeamCreate entirely.

**If `.claude/agents/` is empty or absent**, use **Mode B**.
</critical>

**Mode A — the project's own agents (preferred, no experimental flag needed)**

1. Read every `.claude/agents/<prefix>-*.md`. For each specialist, extract its
   `<strict_boundaries>` — the list of files it owns.
2. Assign each task from the plan to the specialist that **owns the files the
   task touches**. A task spanning two specialists is split, or assigned to the
   one owning the entry point with the other named as reviewer.
3. Spawn with the Task tool, `subagent_type: "<prefix>-<domain>"` — the real
   agent name, not a generic type.
4. Spawn independent specialists in PARALLEL (one message, several Task calls).
5. If `.claude/rules/orchestration-lead.md` exists, respect it: it may require
   that `<prefix>-lead` plans before any specialist writes. Read it, don't
   assume.

<critical>
NEVER assign a file to a specialist that does not own it. The whole value of
that team is the partition — breaking it produces the conflicts it was designed
to prevent. If no specialist owns a file, say so and ask.
</critical>

**Mode B — generic Agent Teams (fallback)**

Only when the project has no agents of its own. Requires the experimental
feature below; if the flag is not set, do NOT force it — fall back to
`steps/step-03-execute.md` (standard sequential execution) and say why.

### 4. Create Agent Team (Mode B only)

<critical>
IMPORTANT: Claude Code Agent Teams is an EXPERIMENTAL feature, and the
`implementer` subagent type comes with it. It requires
CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 in settings.json — which this kit does
NOT set for you, because enabling an experimental feature is the project
owner's call.

If the flag is not set, Mode B is unavailable. Do not try to work around it:
prefer Mode A, or fall back to standard execution
(`steps/step-03-execute.md`) and tell the user which one you took and why.
</critical>

**Create the team using TeamCreate:**

```
TeamCreate:
  team_name: "apex-{feature_name}"
  description: "APEX: {task_description}"
```

**Spawn teammates using the Task tool with `subagent_type: "implementer"`:**

<critical>
MODE B ONLY. In Mode A you use the project's real agent names
(`<prefix>-<domain>`) and none of this section applies.

In Mode B, always use `subagent_type: "implementer"` for ALL teammates.
The `implementer` agent is the dedicated APEX executor — it knows how to:
- Claim tasks from TaskList via TaskUpdate
- Stay within its assigned file boundaries
- Report via SendMessage (not plain text)
- Handle shutdown requests gracefully
NEVER use `general-purpose` or other agent types.
</critical>

For each teammate, spawn via the Task tool:
- `subagent_type`: `"implementer"` (MANDATORY)
- `team_name`: `"apex-{feature_name}"`
- `name`: `"impl-{group-name}"` (e.g., `impl-backend`, `impl-frontend`)
- `mode`: `"bypassPermissions"`
- `prompt`: Full task context (see template below)

### 5. Spawn Teammates with Assignments (Mode B only)

**Spawn template (one Task call per teammate):**

```
Task:
  subagent_type: "implementer"
  team_name: "apex-{feature_name}"
  name: "impl-{group-name}"
  mode: "bypassPermissions"
  prompt: |
    You are impl-{group-name} in team apex-{feature_name}.

    ## Your Assignment

    **Task:** {task-id} - {task-title}

    ### Objective
    {objective from task file}

    ### Plan
    {implementation steps from task file}

    ### Files to Modify (YOUR boundary — only touch these)
    {file list from task file}

    ### Acceptance Criteria
    {criteria from task file}

    ### Patterns to Follow
    {relevant patterns from step-01 analysis}

    ### Skill Hint
    {skill to invoke, if applicable — e.g., "Use /frontend-design for UI components"}

    ### Dependencies
    {list of completed dependencies and their outputs}

    IMPORTANT: Check TaskList, claim your task, implement, then report via SendMessage.
```

**Spawn rules:**
- Spawn all INDEPENDENT teammates in PARALLEL (single message, multiple Task calls)
- Each teammate gets ALL context (they can't see your conversation)
- Use `mode: "bypassPermissions"` to avoid permission prompt interruptions
- As tasks with dependencies complete, spawn teammates for dependent tasks
- 2-4 teammates for most tasks — more adds overhead, not speed

### 6. Monitor Progress

**While tasks are running:**

Messages from teammates arrive AUTOMATICALLY — no need to poll or check periodically.

1. Wait for teammate messages (completion reports or blocker reports)
2. If a teammate reports a blocker:
   - Analyze the blocker
   - Send guidance via SendMessage
   - If blocker requires another task's output, check TaskList for its status
3. If a teammate reports completion, verify via TaskList that the task is marked `completed`
   (The `implementer` agent marks its own tasks complete — you don't need to do it)
4. As tasks complete, spawn teammates for newly-unblocked dependent tasks

### 7. Handle Completion

**When ALL tasks are complete:**

<critical>
NEVER clean up or dismiss the team.
Keep the team alive for potential follow-up work.
</critical>

**If `{auto_mode}` = true:**
→ Proceed directly to step-04-validate.md

**If `{auto_mode}` = false:**

```yaml
questions:
  - header: "Team Status"
    question: "All tasks complete. What would you like to do?"
    options:
      - label: "Proceed to validation (Recommended)"
        description: "Run typecheck, lint, and verify acceptance criteria"
      - label: "Assign additional tasks"
        description: "Give more work to the team"
      - label: "Message a teammate"
        description: "Send follow-up instructions to a specific teammate"
    multiSelect: false
```

### 8. Complete Save Output (if save_mode)

**If `{save_mode}` = true:**

Append to `{output_dir}/03-execute.md`:

```markdown
## Execution Mode: Agent Teams

**Team size:** {count} teammates
**Tasks completed:** {count}/{total}

### Task Results
| Task | Teammate | Status | Files Changed |
|------|----------|--------|---------------|
| task-01 | impl-backend | ✓ | file1.ts, file2.ts |
| task-02 | impl-frontend | ✓ | file3.ts |

**Team Status:** Active (kept alive for follow-up)

---

## Step Complete

**Status:** ✓ Complete
**Next:** step-04-validate.md
**Timestamp:** {ISO timestamp}
```

```bash
bash {skill_dir}/scripts/update-progress.sh "{task_id}" "03" "execute-teams" "complete"
```

---

## SUCCESS METRICS:

✅ All tasks assigned to teammates
✅ All tasks completed successfully
✅ TaskList updated with completion status
✅ Team kept alive (NOT cleaned up)
✅ NO implementation code written by team lead
✅ Output saved (if save_mode)

## FAILURE MODES:

❌ Team lead writing implementation code
❌ Cleaning up or dismissing the team
❌ Using any agent type other than `implementer` for teammates
❌ Not providing enough context to teammates
❌ Assigning tasks with unmet dependencies
❌ Not monitoring for blockers

## BEST PRACTICES:

- Give each teammate ALL context they need (they can't see your conversation)
- Avoid assigning tasks that modify the same files to different teammates
- Size tasks appropriately - not too large, not too small
- Monitor actively and resolve blockers quickly

---

## NEXT STEP:

After all tasks complete, load `./step-04-validate.md`

<critical>
Remember:
- You are the TEAM LEAD — NEVER implement code yourself
- Mode A first: if `.claude/agents/` holds a team, use it. It knows this codebase.
- `subagent_type: "implementer"` is for Mode B only, and Mode B needs the
  experimental flag
- Keep the team ALIVE after completion
- Each teammate needs FULL context (plan, patterns, file references)
- The `implementer` agent handles TaskList claiming, SendMessage reporting, and file boundaries automatically
</critical>
