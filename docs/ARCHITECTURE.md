# Architecture

This doc covers the *what* and *why* of sage's design. For the user-facing
on-ramp, see [README.md](../README.md). For the agent protocol (how workers
communicate, complete tasks, escalate, time out, use Monitor), see
[HANDBOOK.md](../HANDBOOK.md). For the per-project config file fields, see
[sage-config.SCHEMA.md](../sage-config.SCHEMA.md).

---

## Core idea

Each agent has **one fixed job** and **one generic instruction file**:

| Agent | Job | File |
|---|---|---|
| ProductOwner | Write a feature spec; break it into epics + per-story YAMLs | [`agents/product-owner.md`](../agents/product-owner.md) |
| TestCreator | Write tests against a story's acceptance criteria | [`agents/test-creator.md`](../agents/test-creator.md) |
| Developer | Make tests pass without breaking others; map each AC to its implementation | [`agents/developer.md`](../agents/developer.md) |
| Tester | Run tests, verify AC implementation map, decide DONE vs IN_DEV | [`agents/tester.md`](../agents/tester.md) |
| EpicVerifier | Cross-story regression + AC re-check once every story in an epic is DONE | [`agents/epic-verifier.md`](../agents/epic-verifier.md) |

Each project tells these agents **how** to do their job for that project via a
`.sage/sage-<agent>-config.yaml` file containing a list of plain-English
instructions. The instructions point at project markdown docs that the agent
reads at runtime.

The split is load-bearing: the **generic WHAT** lives in this repo
(`agents/`); the **project-specific HOW** lives in each consuming project's
`.sage/`. Neither hardcodes the other. A new project is one
`/sage-install` run plus a few minutes of editing five YAML files.

```
sage-feature-team/                       <- this repo (the system)
+-- agents/
|   +-- _BASE.md                         <- shared protocol + {PROJECT_INSTRUCTIONS} hook
|   +-- product-owner.md                 <- generic job
|   +-- test-creator.md                  <- generic job
|   +-- developer.md                     <- generic job
|   +-- tester.md                        <- generic job
|   \-- epic-verifier.md                 <- generic job
+-- _tools/
|   +-- load_agents.py                   <- assembles agent prompts
|   \-- setup_project.py                 <- scaffolds .sage/ in a new project
+-- HANDBOOK.md                          <- protocol details (completion reporting, escalation)
+-- sage-config.yaml                     <- demo team/path config (points at the example below)
\-- examples/static-site-generator/      <- self-contained reference example

<your-project>/                          <- e.g. ~/StudioProjects/Breadcrumbs
+-- sage-config.yaml                     <- created by the installer
\-- .sage/
    +-- sage-product-owner-config.yaml   <- project's PO instructions
    +-- sage-test-creator-config.yaml    <- project's TestCreator instructions
    +-- sage-developer-config.yaml       <- project's Developer instructions
    +-- sage-tester-config.yaml          <- project's Tester instructions
    \-- sage-epic-verifier-config.yaml   <- project's EpicVerifier instructions
```

---

## How a run works

1. User invokes `/sage-feature-team "Add dark mode"`.
2. The skill reads `sage-config.yaml` and calls `_tools/load_agents.py`.
3. The loader:
   - Reads `agents/_BASE.md` + each role file.
   - Finds the project's `.sage/` directory (defaults to `<project_root>/.sage/`).
   - Reads `.sage/sage-<agent>-config.yaml` for each agent.
   - Substitutes the instructions list into `{PROJECT_INSTRUCTIONS}` in `_BASE.md`.
   - Substitutes `{SAGE_TOOLS_DIR}` (becomes `_tools` in source, `.sage/_tools` in installed projects).
4. The skill creates a team and spawns the agents with their fully-rendered prompts.
5. Each agent reads its referenced project files (test guides, code conventions, etc.) using `Read` when relevant.
6. The skill routes work through ProductOwner → (parallel) TestCreator → Developer ↔ Tester → EpicVerifier until every epic verifies or `max_cycles` exhausts.

Two modes:

- **full** -- all five agents (spec → tests → code → validation → epic verification).
- **dev-test-only** -- Developer + Tester only (tests already exist; fix and verify).

For the visual version of the full pipeline, see
[How it flows](../README.md#how-it-flows) in the README, or the standalone
diagram at [docs/img/architecture.svg](img/architecture.svg).

---

## State machine

Workflow state lives in **per-story and per-epic YAML files**, not in agent
messages. The YAML is the event log; the orchestrator re-reads it after every
worker completion and never trusts a message body alone.

```
_output/<feature>/
  spec.md
  epics/EPIC-N.yaml                      # every feature has >=1 epic
  stories/STORY-N.yaml                   # each has an 'epic: EPIC-N' field
  stories/STORY-N.implementation.md      # Developer's AC map sidecar
  verification/EPIC-N.md                 # EpicVerifier output per epic
  progress.md                            # human-readable rollup (regenerated)
  tokens.{json,md}                       # token telemetry
```

Story states: `TODO → CREATE_TESTS → IN_DEV → TESTING → DONE` (plus `BLOCKED`).
Epic states: `TODO → IN_PROGRESS → DONE → VERIFIED` (plus `BLOCKED`).

**Status transitions go through the helper scripts only -- never hand-edit
YAML for status.** `update_story_status.py` and `update_epic_status.py` are
atomic and file-locked because multiple parallel workers touch the same
directory.

### Three verification gates

A story does not reach `DONE` -- and an epic does not reach `VERIFIED` --
until all three gates pass:

1. **Gate A: per-story tests pass.** Run by Tester after each Developer cycle.
   The test selector is story-scoped (`pytest -m STORY-N`, `JUnit @Tag`, etc.)
   so parallel Testers don't fight over shared fixtures.
2. **Gate B: AC implementation map verifies.** The Developer writes a sidecar
   `STORY-N.implementation.md` listing every acceptance criterion and the file
   paths that satisfy it. `verify_ac_map.py` checks the sidecar's shape and
   bans deferral words (`deferred`, `future`, `TODO`, `placeholder`, etc.).
   This catches the failure mode where tests pass but the feature wasn't
   actually wired up.
3. **Gate C: cross-story epic regression.** Once every story in an epic is
   `DONE`, EpicVerifier runs the full story-tagged regression for that epic
   plus any optional epic-level acceptance check. Catches regressions that
   per-story Testers cannot see.

A failure at any gate re-opens the relevant story (or stories) to `IN_DEV`
with the failure reason preserved for the next Developer cycle. Downstream
epics with `depends_on:` only unblock at `VERIFIED`, not `DONE`.

### Scheduler model

The orchestrator runs in two phases:

- **Phase 1 (sequential):** a single long-lived ProductOwner agent awaits the
  user's explicit `APPROVED`.
- **Phase 2 (parallel):** a scheduler scans the stories directory on every
  loop, calls `list_eligible.py` (mechanical, deterministic), and spawns
  ephemeral per-story workers up to `max_parallel_workers`. Workers are
  named `<Role>-<STORY-N>` for first attempts and `<Role>-<STORY-N>-cN` on
  re-cycles. On completion they're terminated via `shutdown_request`.

Eligibility is mechanical, not LLM-judged. A dependency is satisfied **only**
when its status is exactly `DONE` (or `VERIFIED` for epic-level
`depends_on:`). `TESTING` does not count -- a story in `TESTING` can still
re-cycle back to `IN_DEV`.

---

## Files

### Top-level

| Path | Purpose |
|---|---|
| [`HANDBOOK.md`](../HANDBOOK.md) | Full protocol details (completion reporting, escalation, Monitor usage, timeouts) |
| [`sage-config.yaml`](../sage-config.yaml) | The demo driver config (points at the static-site-generator example) |
| [`sage-config.SCHEMA.md`](../sage-config.SCHEMA.md) | Field reference for `sage-config.yaml` |
| [`agents/_BASE.md`](../agents/_BASE.md) | Shared protocol + the `{PROJECT_INSTRUCTIONS}` hook |
| [`agents/<role>.md`](../agents/) | Generic job description per agent |

### Tooling (`_tools/`)

User-facing scripts:

| Script | Role |
|---|---|
| [`setup_project.py`](../_tools/setup_project.py) | Installs sage into a target project |
| [`install_skill.py`](../_tools/install_skill.py) | Bootstraps `/sage-install` into the user skills dir |
| [`cleanup_project.py`](../_tools/cleanup_project.py) | Backs the `/sage-uninstall` skill |

Internal scripts (called by the skills and agents):

| Script | Role |
|---|---|
| [`load_agents.py`](../_tools/load_agents.py) | Assembles agent prompts (the pipeline above) |
| [`list_eligible.py`](../_tools/list_eligible.py) | Authoritative scheduler input (eligibility buckets per role + epic-ready list) |
| [`update_story_status.py`](../_tools/update_story_status.py) | Atomic, file-locked story status flips |
| [`update_epic_status.py`](../_tools/update_epic_status.py) | Atomic, file-locked epic status flips |
| [`verify_ac_map.py`](../_tools/verify_ac_map.py) | Gate B: validates the AC implementation map sidecar |
| [`verify_epic.py`](../_tools/verify_epic.py) | EpicVerifier precondition gate (stories DONE + AC maps fresh) |
| [`prepare_task_payload.py`](../_tools/prepare_task_payload.py) | Pre-renders spec+story+epic into a worker's task message |
| [`discover_and_record.py`](../_tools/discover_and_record.py) | Token telemetry from Claude Code transcripts |
| [`rollup_status.py`](../_tools/rollup_status.py) | Regenerates `progress.md` from authoritative YAMLs |

See [`_tools/README.md`](../_tools/README.md) for tool-level docs.

### Templates and guides

| Path | Purpose |
|---|---|
| [`templates/MESSAGE_TEMPLATE.md`](../templates/MESSAGE_TEMPLATE.md) | Standard SendMessage format |
| [`templates/PROGRESS_TEMPLATE.md`](../templates/PROGRESS_TEMPLATE.md) | Progress file template |
| [`templates/COMPLETION_MESSAGES.md`](../templates/COMPLETION_MESSAGES.md) | Per-role completion message templates |
| [`templates/AC_MAP_FORMAT.md`](../templates/AC_MAP_FORMAT.md) | Developer's AC implementation map format |
| [`guides/ORCHESTRATOR_PATTERNS.md`](../guides/ORCHESTRATOR_PATTERNS.md) | Reusable Skill/Team Lead patterns |

### Skills

| Skill | What it does |
|---|---|
| [`.claude/skills/sage-feature-team/SKILL.md`](../.claude/skills/sage-feature-team/SKILL.md) | Full team workflow (all 5 agents) |
| [`.claude/skills/sage-dev-test/SKILL.md`](../.claude/skills/sage-dev-test/SKILL.md) | Dev/test cycles only (Developer + Tester team) |
| [`.claude/skills/sage-po/SKILL.md`](../.claude/skills/sage-po/SKILL.md) | Inline ProductOwner -- create spec + stories |
| [`.claude/skills/sage-test-creator/SKILL.md`](../.claude/skills/sage-test-creator/SKILL.md) | Inline TestCreator -- write tests for the next ready story |
| [`.claude/skills/sage-developer/SKILL.md`](../.claude/skills/sage-developer/SKILL.md) | Inline Developer -- implement code for the next IN_DEV story |
| [`.claude/skills/sage-tester/SKILL.md`](../.claude/skills/sage-tester/SKILL.md) | Inline Tester -- validate tests for the next TESTING story (or `--full` regression) |
| [`.claude/skills/sage-install/SKILL.md`](../.claude/skills/sage-install/SKILL.md) | Install sage into a target project |

### Example

[`examples/static-site-generator/`](../examples/static-site-generator/) is a
self-contained reference: the implementation sage produced (in `src/`,
`tests/`, `content/`, `pyproject.toml`) plus the full run artifacts under
`_output/`, including spec, epics, stories, verification reports, and token
telemetry.

---

## Adding a new agent

1. Create `agents/<new-role>.md` (generic job description).
2. Add an entry to `team.agents.full` (and `dev_test_only` if applicable) in
   `sage-config.yaml`.
3. Add the agent to `AGENT_SLUGS` in `_tools/load_agents.py` so its config
   file slug is known.
4. Update the routing logic in
   [`.claude/skills/sage-feature-team/SKILL.md`](../.claude/skills/sage-feature-team/SKILL.md).
5. Each project then creates `.sage/sage-<new-role>-config.yaml` to give it
   project-specific guidance.

The `{PROJECT_INSTRUCTIONS}` hook is in `_BASE.md` -- every agent gets it
automatically.

---

## Going deeper

- [HANDBOOK.md](../HANDBOOK.md) -- the agent protocol in full: completion reporting, escalation, Monitor usage, timeouts, the SendMessage discipline.
- [sage-config.SCHEMA.md](../sage-config.SCHEMA.md) -- every field in `sage-config.yaml` explained.
- [guides/ORCHESTRATOR_PATTERNS.md](../guides/ORCHESTRATOR_PATTERNS.md) -- reusable patterns for the skill that acts as Team Lead.
- [examples/static-site-generator/](../examples/static-site-generator/) -- a real run end-to-end with all artifacts on disk.
