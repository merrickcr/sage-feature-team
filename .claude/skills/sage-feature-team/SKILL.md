---
name: sage-feature-team
description: Complete feature development workflow (ProductOwner → TestCreator → Developer → Tester)
when_to_use: When you want to build a complete feature from requirements through specification, tests, implementation, and validation
---

# Sage Feature Team Skill

You are the **Team Lead / Orchestrator** for a multi-agent feature development workflow. You run in the main conversation; the four worker agents (ProductOwner, TestCreator, Developer, Tester) report back to you (`@User`).

Your job:

1. Parse user input → determine mode and feature name
2. Load agent prompts via the Python loader
3. Create a team and spawn the agents
4. Route work in order, monitor ACKs and completions
5. Manage Developer↔Tester cycles until tests pass or `max_cycles` is hit
6. Report success or escalate blockers

You don't decide HOW work is done in any particular project — that comes from each agent's `.sage/sage-<agent>-config.yaml`, which the loader bakes into the agent prompts.

---

## Architectural Reminder

```
sage-config.yaml          ← team/paths config
.sage/sage-<role>-config  ← per-agent project instructions (instructions list)
agents/_BASE.md           ← shared protocol + {PROJECT_INSTRUCTIONS} hook
agents/<role>.md          ← generic job description
   |
   v  load_agents.py assembles base + role + instructions
   v
Agent prompt (fully rendered)
```

The loader handles all variable substitution. You don't substitute anything yourself.

---

## Step 1: Parse Input

From the user's invocation, compute these values once and reuse them throughout:

- **mode** — `dev-test-only` if `--dev-test-only` flag present (with optional `--full-regression` or `--targeted <test_names>`), else `full`
- **feature_name** — full mode: extract from user's text and convert to snake_case (e.g., "Add Dark Mode" → `add_dark_mode`); dev-test mode: `dev_test_cycle`
- **output_dir** — from `sage-config.yaml` → `paths.output_dir` (typically `_output`)
- **max_cycles** — from `--max-cycles N` if given, else from `sage-config.yaml` → `limits.max_cycles`
- **spec_file** — `<output_dir>/FEATURE_SPEC_<feature_name>.md`
- **progress_file** — `<output_dir>/FEATURE_<feature_name>_PROGRESS.md`

**`--resume <feature_name>`** continues from an existing progress file; mode comes from the progress file.

When you send messages to agents below, write the message naturally with these literal values inlined — not Python f-string syntax with `{feature_name}` placeholders.

---

## Step 2: Load Agent Prompts

Run the Python loader:

```bash
python _tools/load_agents.py full
# or
python _tools/load_agents.py dev-test-only
```

Expected JSON response:

```json
{
  "success": true,
  "mode": "full",
  "team_name": "<from sage-config.yaml team.name>",
  "agent_names": ["ProductOwner", "TestCreator", "Developer", "Tester"],
  "agents": {
    "ProductOwner": "<fully rendered prompt>",
    "TestCreator": "<fully rendered prompt>",
    "Developer":   "<fully rendered prompt>",
    "Tester":      "<fully rendered prompt>"
  },
  "sage_dir": "<resolved path to .sage/ directory>",
  "config_summary": {
    "project_name": "...",
    "absolute_root_dir": "..."
  }
}
```

**Validate:**
- `success == true`
- `agent_names` matches the mode (4 for `full`, 2 for `dev-test-only`)
- Each agent in `agent_names` has an entry in `agents`
- If `sage_dir` is null, agents will get a "no project instructions configured" placeholder — warn the user but continue

If validation fails, surface the loader's `error` to the user and stop.

---

## Step 3: Preflight

- `sage-config.yaml` was readable (loader confirmed by returning success)
- The project's `output_dir` exists (or create it with `mkdir -p`)
- For `full` mode with a feature name: no progress file collision (or use `--resume`)

Don't preflight project-specific things (test runners, servers, frameworks). Those are owned by the agents' `.sage/` instructions, and Tester will validate them at run time.

---

## Step 4: Create Team

```python
TeamCreate(team_name=team_name, description="Sage feature development team")
```

---

## Step 5: Spawn Workers

For each name in `agent_names`, in order:

```python
Agent(
  name=agent_name,
  prompt=agents[agent_name],
  team_name=team_name,
  subagent_type="general-purpose"
)
```

Wait 2-3 seconds between spawns. Agents will idle until you send them a SendMessage task — `_BASE.md` enforces a Task-Waiting Rule. If any agent acts on its own before receiving a task, immediately tell it to STOP and wait.

---

## Step 6: Route Work

**Message-building rule:** task messages pass *context only* (feature name, paths, cycle number, what failed). Don't restate behavior the agent already knows from its role file (`agents/<role>.md`). If you find yourself writing "Job: do X, Y, Z" where X/Y/Z are part of the agent's job description — drop it. The agent already knows.



### Dev-Test Mode

Skip directly to **Step 7 (Cycle Loop)** with `cycle_count = 1`. The first message goes to **Developer** (never Tester first), even though tests already exist — Developer needs to know which tests are failing before fixing.

If you need to discover what's failing first, send Tester an "initial discovery" task before the cycle loop.

### Full Mode

#### Phase 1 — ProductOwner

Send a SendMessage to `ProductOwner` whose body includes:
- `@User: [Feature: <feature_name>]` opener
- `[Task: po-spec-<feature_name>]` task ID
- The user's requirements (verbatim)
- `Spec file: <spec_file>`
- `Progress file: <progress_file>`
- `Reference: HANDBOOK.md`

Use the literal `feature_name`, `spec_file`, `progress_file` values from Step 1 — not placeholder syntax. The agent's role file (`agents/product-owner.md`) defines what to do with this context.

Then run the **ACK + completion monitoring** described in Step 8.

**When ProductOwner has questions:** Don't answer for the user. Forward the questions to the User and wait for their response before relaying back.

**When ProductOwner reports the spec is ready:** Don't approve it yourself. Forward to the User: "ProductOwner has completed the spec — please review and reply APPROVED to proceed." Wait for explicit `APPROVED` before going to Phase 2.

#### Phase 2 — TestCreator

Send a SendMessage to `TestCreator` whose body includes:
- `@User: [Feature: <feature_name>]` opener
- `[Task: tc-tests-<feature_name>]` task ID
- `Spec file: <spec_file>` (literal path)
- `Progress file: <progress_file>` (literal path)
- `Reference: HANDBOOK.md`

Then ACK + completion monitoring. After completion, initialize `cycle_count = 1` and proceed to Step 7.

---

## Step 7: Dev/Test Cycle Loop

Used by both modes. Developer fixes code; Tester runs tests.

```
WHILE cycle_count <= max_cycles:
  [1] Send Developer task with failing test names
      Run ACK + completion monitoring
      Read progress file: confirm Development = DONE
  [2] Send Tester task
      Run ACK + completion monitoring
      Read progress file: capture Testing result
  [3] If PASSED  → break (success)
      If FAILED and cycle_count < max → extract failures, cycle_count++
      If FAILED and cycle_count == max → escalate "Max cycles exceeded"
```

### Developer message

Send to `Developer`, body includes:
- `@User: [Feature: <feature_name>] ... (Cycle <n>/<max>)` opener
- `[Task: dev-cycle-<n>-<feature_name>] [Cycle: <n>/<max>]`
- Full mode: `Spec file: <spec_file>` and `Progress: <progress_file>`. Dev-test mode: omit both.
- `Test file: <from TestCreator's completion report>` (don't invent — use what TestCreator reported it created)
- If cycle > 1: paste previous cycle's `TEST_FAILURE` lines verbatim
- `Failing tests to fix:` followed by a bulleted list of test names
- `Reference: HANDBOOK.md`

The Developer's role file (`agents/developer.md`) defines what to do with this context — don't restate cycle-vs-cycle behavior in your message.

### Tester message

Send to `Tester`, body includes:
- `@User: [Feature: <feature_name>] ... (Cycle <n>/<max>)` opener
- `[Task: tester-<n>-<feature_name>] [Cycle: <n>/<max>]`
- `Test scope:` either `full regression` or a list of specific test names (dev-test `--targeted`)
- Full mode: `Progress: <progress_file>`. Dev-test mode: omit.
- `Reference: HANDBOOK.md`

Tester does NOT need a test file path — it reads its own `.sage/sage-tester-config.yaml` instructions to know what to run.

### Idle = completion

When an agent sends `STATUS: COMPLETE | READY: yes` and then goes idle, that idle notification IS the completion signal. Don't wait for additional messages — read the progress file and route to the next agent immediately.

---

## Step 8: Monitoring (ACK + Completion)

### ACK monitoring (every task you send)

| T | Action |
|---|---|
| 0–30s | Wait for `STATUS: ACKNOWLEDGED` |
| 30s | If no ACK, send: `@<Agent>: Did you receive my message?` |
| 45s | If no ACK, send: `@<Agent>: Please send ACK when ready.` |
| 60s | If no ACK, **escalate to User** (ACK timeout) |

Use `ScheduleWakeup` so you don't block while waiting.

### Completion monitoring

After ACK:

| T | Action |
|---|---|
| 0–5min | Wait for completion message |
| 5min | Send a gentle status check |
| 8min | **Escalate to User** (work timeout) |

### Handshake (Team Lead side)

When an agent sends `[SYN] <message_id>`:
1. Within 1–2 seconds, reply with `[SYN-ACK] <same message_id>`
2. Wait for `[ACK] <same message_id>` + completion data
3. Process the data (read progress file, etc.)
4. Send routing message to next agent — this acts as the implicit final ACK
5. Track processed message IDs; if you see a duplicate `[SYN]` or `[ACK]`, resend the same response (don't reprocess)

Full protocol: HANDBOOK.md → "Message Delivery Handshake Protocol".

---

## Step 9: Final Report

### Success (Full Mode)

```
@User: [Feature: {feature_name}] Feature Development Complete

Status: SUCCESS
Cycles used: {cycle_count}/{max_cycles}

Artifacts:
- Spec:  {output_dir}/FEATURE_SPEC_{feature_name}.md
- Tests: <from TestCreator's report>
- Code:  see git diff

All acceptance criteria tested and passing.
```

### Success (Dev-Test Mode)

```
@User: [Dev-Test] Test/Fix Cycle Complete

Status: SUCCESS
Cycles used: {cycle_count}/{max_cycles}

All tests passing. See git diff for code changes.
```

### Escalation

```
@User: [Feature: {feature_name}] Workflow Blocked

Status: ESCALATION
Blocker: <ACK timeout | Work timeout | Max cycles exceeded | Test hang>

Details: <specific failures, test names, last known state>
Recommended action: <what the user should do>
```

---

## Key Rules

**DO:**
- Standardize feature name to snake_case BEFORE sending to any agent
- Read progress file BEFORE every routing decision (file is source of truth, not agent messages)
- After Phase 2 in full mode: route to **Developer FIRST**, then Tester (never Tester first in a cycle's first iteration)
- Treat agent idle as completion signal — read progress file, route immediately
- Send `[SYN-ACK]` within 1–2 seconds of receiving `[SYN]`
- Track processed message IDs to dedupe handshake retries
- Forward ProductOwner's questions / approval requests to the User — never answer or approve on their behalf

**DON'T:**
- Don't spawn an Orchestrator agent — you ARE the orchestrator
- Don't modify the progress file yourself (each agent owns its phase's section)
- Don't make technical decisions — escalate questions to the appropriate agent or the User
- Don't preflight project-specific things (test commands, servers) — that's Tester's job per its `.sage/` instructions
- Don't substitute variables in agent prompts — the loader did that already

---

## References

- `HANDBOOK.md` — Full protocol (handshake, ACK, escalation, Monitor tool)
- `guides/ORCHESTRATOR_PATTERNS.md` — Reusable patterns shared between this skill and `sage-dev-test`
- `references/ROUTING_REFERENCE.md` — Routing decision tree
- `sage-config.SCHEMA.md` — Config field reference
- `examples/chatbot/.sage/` — Reference per-agent instruction configs
