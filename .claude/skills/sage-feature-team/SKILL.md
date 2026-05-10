---
name: sage-feature-team
description: Complete feature development workflow (ProductOwner → parallel TestCreator/Developer/Tester per story)
when_to_use: When you want to build a complete feature from requirements through specification, tests, implementation, and validation — with multiple stories worked in parallel
---

# Sage Feature Team Skill

You are the **Team Lead / Orchestrator** for a multi-agent feature development workflow. You run in the main conversation; worker agents report back to you (`@User`).

The workflow has two phases:

1. **Phase 1 — ProductOwner (single agent, sequential).** A long-lived ProductOwner agent creates the spec and per-story YAML files, iterates on user feedback, and waits for `APPROVED`.
2. **Phase 2 — Parallel scheduler.** Once stories are approved, you become a scheduler. You scan the stories directory and **spawn ephemeral, per-story worker agents** (one per ready story, up to `max_parallel_workers`). Each worker handles one story, reports completion, and is shut down. You re-scan and spawn the next batch until every story is `DONE` or escalated.

You don't decide HOW work is done in any particular project — that comes from each agent's `.sage/sage-<agent>-config.yaml`, which the loader bakes into the agent prompts.

---

## Architectural Reminder

```
sage-config.yaml          ← team/paths/limits config
.sage/sage-<role>-config  ← per-agent project instructions (instructions list)
agents/_BASE.md           ← shared protocol + {PROJECT_INSTRUCTIONS} hook
agents/<role>.md          ← generic job description
   |
   v  load_agents.py assembles base + role + instructions
   v
Agent prompt (fully rendered) — same prompt reused for every worker of that role
```

Stories live as **per-story YAML files**:
```
_output/FEATURE_STORIES_<feature_name>/STORY-1.yaml
_output/FEATURE_STORIES_<feature_name>/STORY-2.yaml
...
```

Each YAML carries its own status. Concurrent workers update their own story file via `_tools/update_story_status.py` (locked, atomic).

---

## Step 1: Parse Input

From the user's invocation, compute these values once and reuse them throughout:

- **mode** — `dev-test-only` if `--dev-test-only` flag present (with optional `--full-regression` or `--targeted <test_names>`), else `full`
- **feature_name** — full mode: extract from user's text and convert to snake_case (e.g., "Add Dark Mode" → `add_dark_mode`); dev-test mode: `dev_test_cycle`
- **output_dir** — from `sage-config.yaml` → `paths.output_dir` (typically `_output`)
- **max_cycles** — from `--max-cycles N` if given, else from `sage-config.yaml` → `limits.max_cycles` (per-story dev↔test cap)
- **max_parallel_workers** — from `sage-config.yaml` → `limits.max_parallel_workers` (default 4)
- **global_timeout_seconds** — from `sage-config.yaml` → `limits.global_timeout_seconds` (default 3600)
- **spec_file** — `<output_dir>/FEATURE_SPEC_<feature_name>.md`
- **stories_dir** — `<output_dir>/FEATURE_STORIES_<feature_name>/`
- **progress_file** — `<output_dir>/FEATURE_<feature_name>_PROGRESS.md`

**`--resume <feature_name>`** continues from existing artifacts.

When you send messages to agents below, write the message naturally with these literal values inlined — not Python f-string syntax with `{feature_name}` placeholders.

---

## Step 2: Load Agent Prompts

```bash
python _tools/load_agents.py full
```

(Or `python .sage/_tools/load_agents.py full` from inside an installed project.)

Expected JSON: `success: true`, `agents` containing rendered prompts for `ProductOwner`, `TestCreator`, `Developer`, `Tester`. Validate as in the previous version of this skill; if `success: false`, surface the error and stop.

You will reuse the rendered `TestCreator`, `Developer`, and `Tester` prompts as the prompt for every per-story worker of that role. The ProductOwner prompt is used once for Phase 1.

---

## Step 3: Preflight

- `sage-config.yaml` was readable (loader confirmed)
- `output_dir` exists (or create it)
- For full mode with a feature name: no spec/stories collision (or use `--resume`)

Don't preflight project-specific things (test runners, servers). Those belong to the agents' `.sage/` instructions.

---

## Step 4: Create Team

```python
TeamCreate(team_name=team_name, description="Sage feature development team")
```

---

## Step 5: Phase 1 — ProductOwner (sequential, single agent)

Skip this whole step in `dev-test-only` mode — go straight to Phase 2 (Step 6) with the existing stories directory.

### 5a. Spawn ProductOwner

```python
Agent(
  name="ProductOwner",
  prompt=agents["ProductOwner"],
  team_name=team_name,
  subagent_type="general-purpose"
)
```

Wait 2-3 seconds. The agent idles until you SendMessage it.

### 5b. Send the spec task

SendMessage to `ProductOwner`:
- `@User: [Feature: <feature_name>]` opener
- `[Task: po-spec-<feature_name>]`
- The user's requirements (verbatim)
- `Spec file: <spec_file>`
- `Stories dir: <stories_dir>`
- `Progress file: <progress_file>`
- `Reference: HANDBOOK.md`

Run **ACK + completion monitoring** (Step 8).

### 5c. Forward questions to the User; require explicit APPROVED

- When ProductOwner asks questions: forward them to the User; relay the answer back. Don't answer for the user.
- When ProductOwner reports the spec is ready: forward to the User: "ProductOwner has completed the spec — please review and reply APPROVED to proceed." Wait for explicit `APPROVED`.

### 5d. Shut down ProductOwner

After ProductOwner's completion handshake, you don't need it anymore. Stop the agent task to free its slot:

```python
TaskStop(name="ProductOwner")   # or TaskList → TaskStop by id
```

If `TaskStop` isn't available or fails, leave the idle agent alone — it won't act again without a task. Move on.

---

## Step 6: Phase 2 — Parallel Scheduler

You now own a scheduling loop. You read the stories directory, spawn per-story workers, wait for any to complete, and re-scan. The loop ends when every story is `DONE` (or escalated as terminal `BLOCKED`/cycle-exhausted), or the global timeout fires.

### 6a. Initialize state

In your own working memory (no need to write to disk), maintain:

```
in_flight       = {}   # STORY-N -> {role, agent_name, started_at, cycle_n}
cycle_count     = {}   # STORY-N -> int (Developer→Tester rounds completed; counts when Tester re-flips to IN_DEV)
escalated       = set()  # STORY-Ns that hit max_cycles or are unrecoverable
start_time      = now()
```

### 6b. Scheduling rule (per scan)

Read every YAML in `stories_dir`. For each story, compute eligibility:

| Story status | Deps all DONE? | In flight? | Escalated? | Action |
|---|---|---|---|---|
| TODO         | yes | no | no | Eligible for **TestCreator** worker |
| CREATE_TESTS | —   | — | — | Already in flight (a TestCreator owns it) — skip |
| IN_DEV       | yes | no | no | Eligible for **Developer** worker |
| TESTING      | yes | no | no | Eligible for **Tester** worker (story-scoped) |
| DONE         | —   | — | — | Done — skip |
| BLOCKED      | —   | — | — | Skip (annotate; user can resolve) |

Sort eligible stories by ID (lowest STORY-N first). Skip any story whose ID is in `in_flight` or `escalated`.

Available slots = `max_parallel_workers - len(in_flight)`. Spawn `min(slots, len(eligible))` workers.

If `len(in_flight) == 0` AND no eligible stories AND not every story is `DONE`: **deadlock**. Escalate (Step 6f).

### 6c. Spawn a per-story worker

Worker name pattern: `<Role>-<STORY-N>` (e.g., `TestCreator-STORY-3`, `Developer-STORY-7`, `Tester-STORY-2`). Names must be unique within the team — if a worker for the same story+role was previously spawned and shut down, append a `-cN` suffix where N is the cycle count for that story (e.g., `Developer-STORY-3-c2`).

```python
Agent(
  name=worker_name,
  prompt=agents[role],         # rendered prompt for the role; same for every worker of that role
  team_name=team_name,
  subagent_type="general-purpose"
)
# wait ~2s
SendMessage(to=worker_name, summary="...", message=<task message>)
```

Track `in_flight[STORY-N] = {role, agent_name: worker_name, started_at: now(), cycle_n: cycle_count[STORY-N]}`.

### 6d. Per-role task message templates

All worker task messages should be self-contained — workers don't share state with each other. Always pass the story id, paths, and references explicitly.

#### TestCreator worker (for a TODO story)

SendMessage:
- `@User: [Feature: <feature_name>] (Story: <STORY-N>)` opener
- `[Task: tc-<STORY-N>-<feature_name>]`
- `Target story: <STORY-N>` (this is your single target — no auto-discovery)
- `Stories dir: <stories_dir>`
- `Spec file: <spec_file>`
- `Progress file: <progress_file>`
- `Reference: HANDBOOK.md`

#### Developer worker (for an IN_DEV story)

SendMessage:
- `@User: [Feature: <feature_name>] (Story: <STORY-N>, Cycle: <cycle_n>/<max_cycles>)` opener
- `[Task: dev-<STORY-N>-c<cycle_n>-<feature_name>]`
- `Target story: <STORY-N>`
- `Stories dir: <stories_dir>`
- `Spec file: <spec_file>`
- `Progress file: <progress_file>`
- If `cycle_n > 1`: paste the previous Tester run's `TEST_FAILURE` lines for this story verbatim
- `Reference: HANDBOOK.md`

#### Tester worker (for a TESTING story — story-scoped)

SendMessage:
- `@User: [Feature: <feature_name>] (Story: <STORY-N>)` opener
- `[Task: tester-<STORY-N>-c<cycle_n>-<feature_name>]`
- `Target story: <STORY-N>`
- `Test scope: story <STORY-N>` (LITERAL — Tester role file uses this to construct a story-scoped selector and to know it must only flip this story)
- `Stories dir: <stories_dir>`
- `Progress file: <progress_file>`
- `Reference: HANDBOOK.md`

The Tester role file has the story-scoped selector logic: it reads the project's tagging convention from `.sage/sage-test-creator-config.yaml` and runs only that story's tests. Multiple Tester workers can run concurrently as long as the project's test isolation allows it.

### 6e. Wait for ANY worker to complete; reschedule

After spawning a batch, you wait. Don't block on a specific worker — wait on the team and act on whichever completes first.

For each completion (handshake `[ACK]+DATA` from a worker):

1. **Run the standard handshake** (Step 8 / `HANDBOOK.md`): reply `[SYN-ACK]`, accept `[ACK]+DATA`, send a routing message that acts as the implicit final ACK. The routing message can simply be: `@<worker>: Acknowledged. You are released — shutting down.`
2. **Re-read the completed story's YAML** to learn its new status (the worker already flipped it via `update_story_status.py`).
3. **Update bookkeeping:**
   - If the worker was Tester and the story is now `IN_DEV` (tests failed): `cycle_count[STORY-N] += 1`. If `cycle_count[STORY-N] > max_cycles`: add to `escalated` and report a per-story escalation (Step 6f).
   - If the worker was Tester and the story is now `DONE`: nothing more to do for this story.
   - If the worker was TestCreator and the story is now `IN_DEV`: ready for Developer next scan.
   - If the worker was Developer and the story is now `TESTING`: ready for Tester next scan.
4. **Shut down the worker** to free the slot:
   ```python
   TaskStop(name=worker_name)
   ```
   (If TaskStop is unavailable, the idle worker won't act again — moving on is fine.)
5. **Remove from `in_flight`** and re-run the scheduling rule (6b) to pick up newly eligible stories.

### 6f. Per-story escalation

When a story hits `max_cycles` (Developer↔Tester loops without success) or a worker reports an unrecoverable BLOCKER:

- Add it to `escalated`
- Mark its YAML `BLOCKED` via the helper (with a reason):
  ```bash
  python _tools/update_story_status.py STORY-N BLOCKED \
      --stories-dir <stories_dir> --reason "max_cycles exceeded after <n> rounds"
  ```
- Report to the User: `@User: [Feature: <feature_name>] STORY-N escalated — <reason>. Continuing other stories.`
- Continue the scheduler — one stuck story doesn't stop the rest

### 6g. Global wall-clock kill switch

At the top of every scan, check `now() - start_time >= global_timeout_seconds`. If hit:

- Stop spawning new workers
- Wait briefly (one more tick) for in-flight workers to complete naturally
- Then `TaskStop` any still-running workers
- Mark every still-non-DONE story as `BLOCKED` with reason `global_timeout`
- Jump to Step 7 (Final Report) with `Status: GLOBAL_TIMEOUT`

### 6h. Loop exit

The scheduler loop exits cleanly when:
- Every story in `stories_dir` is `status: DONE` → success
- OR every remaining non-DONE story is in `escalated` → partial success (some stories escalated)
- OR the global timeout fired → escalation

---

## Step 7: Final Report

### Success (Full Mode, all stories DONE)

```
@User: [Feature: <feature_name>] Feature Development Complete

Status: SUCCESS
Stories: <N> total, all DONE
Cycles used (per story): STORY-1=1, STORY-2=2, ...
Wall clock: <elapsed>s

Artifacts:
- Spec:        <spec_file>
- Stories dir: <stories_dir>
- Tests:       see git diff
- Code:        see git diff
```

### Partial Success (some stories escalated)

```
@User: [Feature: <feature_name>] Feature Development Partially Complete

Status: PARTIAL
Stories DONE:      STORY-1, STORY-3, ...
Stories ESCALATED: STORY-2 (max_cycles), STORY-5 (BLOCKED: ...)

See <stories_dir> for blocked_reason on each escalated story.
```

### Global Timeout

```
@User: [Feature: <feature_name>] Workflow Hit Global Timeout

Status: GLOBAL_TIMEOUT after <global_timeout_seconds>s
Stories DONE: ...
Stories left: ...
```

### Dev-Test Mode

(Phase 1 skipped; Phase 2 still applies but works against the existing stories directory. If no stories directory exists, fall back to the legacy `/sage-dev-test` flow — recommend the user invoke that skill instead.)

---

## Step 8: Monitoring (ACK + Completion + Handshake)

### ACK monitoring (every task you send)

| T | Action |
|---|---|
| 0–30s | Wait for `STATUS: ACKNOWLEDGED` |
| 30s | If no ACK, send: `@<worker>: Did you receive my message?` |
| 45s | If no ACK, send: `@<worker>: Please send ACK when ready.` |
| 60s | If no ACK, **escalate**: shut down the worker, mark its story `BLOCKED` with reason `ack_timeout`, continue scheduling |

Use `ScheduleWakeup` so you don't block while waiting; or use `Monitor` on the team to receive worker messages reactively.

### Completion monitoring

After ACK:

| T | Action |
|---|---|
| 0–`timeout_work_hard`s (default 480s = 8min) | Wait for completion |
| `timeout_work_hard / 2` | Send a gentle status check |
| `timeout_work_hard` | **Escalate**: shut down the worker, mark its story `BLOCKED` with reason `work_timeout`, continue scheduling |

### Handshake (Team Lead side)

When a worker sends `[SYN] <message_id>`:
1. Within 1–2s, reply `[SYN-ACK] <same message_id>`
2. Wait for `[ACK] <same message_id>` + completion data
3. Process the data (re-read story YAML)
4. Send the routing/release message — this acts as the implicit final ACK and tells the worker it's released
5. `TaskStop` the worker to free the slot
6. Track processed message IDs; on duplicate `[SYN]` or `[ACK]`, resend the same response (don't reprocess)

Full protocol: `HANDBOOK.md` → "Message Delivery Handshake Protocol".

---

## Key Rules

**DO:**
- Standardize feature name to snake_case BEFORE sending to any agent
- Phase 1: ProductOwner is single, sequential, long-lived — wait for explicit `APPROVED` before Phase 2
- Phase 2: Re-read the stories directory before every scheduling decision (YAML files are source of truth, not agent messages)
- Spawn per-story workers up to `max_parallel_workers`; never exceed the cap
- Use the role name + story id for worker names (`TestCreator-STORY-3`); add `-cN` suffix on re-cycles to keep names unique
- Tester workers always run **story-scoped** in this skill (`Test scope: story STORY-N`) so multiple Testers can run in parallel
- After each worker completes, `TaskStop` it to free the slot
- Track per-story cycle counts independently — one stuck story doesn't drain the budget for others
- Forward ProductOwner's questions / approval requests to the User — never answer or approve on their behalf
- Always invoke status flips through `_tools/update_story_status.py`; never edit story YAMLs directly

**DON'T:**
- Don't spawn an Orchestrator agent — you ARE the orchestrator
- Don't keep workers alive between stories — spawn fresh per story so you can use natural shutdown for rate-limiting
- Don't run a Tester worker with `Test scope: full regression` from this skill — full regression is for `/sage-dev-test` and the inline `/sage-tester --full`. The parallel scheduler relies on per-story scoping for safe concurrency.
- Don't preflight project-specific things (test commands, servers) — that's each worker's job per its `.sage/` instructions
- Don't substitute variables in agent prompts — the loader did that already

---

## References

- `HANDBOOK.md` — Full protocol (handshake, ACK, escalation, Monitor tool)
- `guides/ORCHESTRATOR_PATTERNS.md` — Reusable Skill/Team Lead patterns
- `references/ROUTING_REFERENCE.md` — Routing decision tree
- `sage-config.SCHEMA.md` — Config field reference (including `max_parallel_workers`, `global_timeout_seconds`)
- `_tools/update_story_status.py` — Atomic, locked story-status updater used by all workers
- `examples/chatbot/.sage/` — Reference per-agent instruction configs
