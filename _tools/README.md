# `_tools/`

Python tools that back the sage skills and agents. Some are user-facing
(you run them by hand to install or maintain sage); most are internal
(skills and agents call them; you generally don't).

If you're hunting for "which tool does X?", the
[ARCHITECTURE.md file reference](../docs/ARCHITECTURE.md#files) is the
canonical list. This README is the directory-local index.

---

## User-facing scripts

You run these. They have proper CLI surface, exit codes, and `--help`.

| Script | What it does |
|---|---|
| `setup_project.py` | Install sage into a target project. Copies `agents/`, the internal `_tools/` scripts, `HANDBOOK.md`, templates, guides, and the SKILL files; rewrites SKILL paths from the source repo's `_tools/...` to the installed `.sage/_tools/...`; scaffolds the per-agent instruction configs and `sage-config.yaml`. Generic files refresh on re-run; per-agent YAML configs and `sage-config.yaml` are preserved. |
| `install_skill.py` | Bootstrap `/sage-install` into your Claude Code user-level skills directory (`~/.claude/skills/sage-install/`). Run once per machine after cloning sage-feature-team; re-run after a `git pull` (idempotent). |
| `cleanup_project.py` | Backs the `/sage-uninstall` skill. Removes the sage scaffolding from a project. |

## Internal scripts

The skills and agents call these. You can run them by hand for debugging,
but they're not part of the user-facing API.

| Script | Role |
|---|---|
| `load_agents.py` | Assembles each agent's rendered prompt for a given mode (`full` or `dev-test-only`). Reads `_BASE.md` + the role file + the project's `.sage/sage-<role>-config.yaml`, substitutes `{PROJECT_INSTRUCTIONS}` and other variables, optionally writes a copy of each rendered prompt to `.sage/.rendered/`. The pipeline is documented below. |
| `list_eligible.py` | Authoritative scheduler input. Returns JSON buckets per role (`po`, `test_creator`, `developer`, `tester`) plus an `epic_ready_to_verify` list. The orchestrator calls this on every loop and never eyeballs YAMLs to decide what to spawn. |
| `update_story_status.py` | Atomic, file-locked story status flip. The only legitimate path to change a story's `status:` field. Validates transitions against a whitelist (`TODO → CREATE_TESTS → IN_DEV → TESTING → DONE`, plus `BLOCKED` as escape hatch). |
| `update_epic_status.py` | Same as above for epic status (`TODO → IN_PROGRESS → DONE → VERIFIED`, plus `BLOCKED`). Only the EpicVerifier should flip an epic to `VERIFIED`. |
| `verify_ac_map.py` | **Gate B.** Validates the Developer's `STORY-N.implementation.md` sidecar: one `## ACx` heading per AC, every section has at least one path-shaped line, no banned deferral words (`deferred`, `future`, `TODO`, `placeholder`, etc.). Returns JSON; non-zero exit on failure. |
| `verify_epic.py` | EpicVerifier precondition gate: all stories in the epic are `DONE` and every story's AC map still verifies. Does **not** run tests -- that's the EpicVerifier worker's job after this passes. |
| `prepare_task_payload.py` | Pre-renders the spec + story YAML + epic YAML + relevant AC context into a worker's task message so the worker doesn't burn 3-5 `Read` tool calls on bootstrap. Cache_create optimization. |
| `discover_and_record.py` | Token telemetry. Walks Claude Code transcript files under `~/.claude/projects/<slug>/<session>/subagents/`, records per-worker usage to `_output/<feature>/tokens.{json,md}`, deduplicates raw captures (multiple snapshots of the same growing conversation) into logical workers. Idempotent. Calls `extract_token_usage.py` + `record_worker_usage.py` internally. |
| `extract_token_usage.py` | Parses one Claude Code transcript JSONL file and returns the cumulative token usage (input / output / cache_create / cache_read). Used internally by `record_worker_usage.py`; called from the orchestrator pipeline rather than directly. |
| `record_worker_usage.py` | Writes one worker's token entry to `_output/<feature>/tokens.json` and re-renders `tokens.md`. Called by `discover_and_record.py` for team-mode workers, and called directly by each inline skill (`/sage-po`, `/sage-developer`, `/sage-tester`, etc.) with `--inline` to record their own usage since they don't show up in the subagent transcript walk. |
| `rollup_status.py` | Regenerates `_output/<feature>/progress.md` from the authoritative story/epic YAMLs. The progress file is a convenience view; the YAMLs remain the source of truth. |

---

## `load_agents.py` in detail

This is the heart of the prompt-assembly pipeline. Every skill that spawns
agents calls it.

```bash
python _tools/load_agents.py full
python _tools/load_agents.py dev-test-only
```

### What it does

1. Find `sage-config.yaml` (cwd -> script parent -> walk up the tree).
2. Validate it (`project`, `team`, required fields).
3. Find the project's `.sage/` directory:
   - `paths.sage_dir` if set
   - else `<absolute_root_dir>/.sage`
   - else `<root_dir>/.sage`
   - else `./.sage`
4. For each agent in the requested mode:
   - Read `agents/_BASE.md` (shared protocol + `{PROJECT_INSTRUCTIONS}` hook).
   - Read the role file (e.g. `agents/tester.md`).
   - Concatenate base + role.
   - Read `.sage/sage-<agent-slug>-config.yaml` for that agent.
   - Format its `instructions:` list as a markdown bullet list.
   - Substitute `{PROJECT_INSTRUCTIONS}` and other variables.
5. Optionally persist the rendered prompts to `.sage/.rendered/<AgentName>.md`
   for inspection (the cache is gitignored; regenerated on every call).
6. Print JSON to stdout, exit 0 on success, 1 on failure.

### Output JSON

```json
{
  "success": true,
  "mode": "full",
  "team_name": "<from team.name or team.dev_test_team_name>",
  "agent_names": ["ProductOwner", "TestCreator", "Developer", "Tester", "EpicVerifier"],
  "agents": {
    "ProductOwner": "<fully rendered prompt>",
    "TestCreator":  "<fully rendered prompt>",
    "Developer":    "<fully rendered prompt>",
    "Tester":       "<fully rendered prompt>",
    "EpicVerifier": "<fully rendered prompt>"
  },
  "sage_dir": "<resolved path or null>",
  "config_summary": {
    "project_name": "...",
    "absolute_root_dir": "..."
  }
}
```

On failure:

```json
{ "success": false, "error": "<message>", "error_type": "<exception name>" }
```

### Variables substituted into prompts

| Placeholder | Source |
|---|---|
| `{AGENT_NAME}` | Agent class name (`Tester`) |
| `{AGENT_NAME_SLUG}` | Slug for the config file (`tester`) |
| `{PROJECT_NAME}` | `project.name` |
| `{PROJECT_ROOT}` | `project.absolute_root_dir` |
| `{TEAM_NAME}` | `team.name` |
| `{DEV_TEST_TEAM_NAME}` | `team.dev_test_team_name` |
| `{OUTPUT_DIR}` | `paths.output_dir` |
| `{SAGE_TOOLS_DIR}` | `_tools` in the source repo, `.sage/_tools` in installed projects |
| `{PROJECT_INSTRUCTIONS}` | Bulleted list from `.sage/sage-<slug>-config.yaml` |

`{PROJECT_INSTRUCTIONS}` is the only hook that's project-specific. It lives
in `agents/_BASE.md`, so every agent inherits it without needing its own
role file edit.

### Empty / missing instruction config

If `.sage/sage-<slug>-config.yaml` is missing or has `instructions: []`,
the loader substitutes a placeholder:

```
_No project-specific instructions configured._

_Create `.sage/sage-<agent>-config.yaml` with an `instructions:` list to
give this agent project-specific guidance._
```

The agent will run but with no project-specific knowledge -- fine for
ad-hoc testing, useless for real work.

### Agent slug mapping

Defined in `AGENT_SLUGS` in `load_agents.py`:

| Agent name | Config file |
|---|---|
| `ProductOwner` | `sage-product-owner-config.yaml` |
| `TestCreator`  | `sage-test-creator-config.yaml`  |
| `Developer`    | `sage-developer-config.yaml`     |
| `Tester`       | `sage-tester-config.yaml`        |
| `EpicVerifier` | `sage-epic-verifier-config.yaml` |

Adding a new agent? Add it here AND to `team.agents.full` (and
`dev_test_only` if applicable) in `sage-config.yaml`.

---

## `setup_project.py` in detail

Full installer. After it runs, the target project is self-contained -- it
has its own copy of every file sage needs, and does NOT depend on the
source sage-feature-team checkout.

```bash
# Interactive wizard
python ~/claudeProjects/sage-feature-team/_tools/setup_project.py

# Non-interactive (CI / scripts)
python ~/claudeProjects/sage-feature-team/_tools/setup_project.py \
    --project ~/StudioProjects/Breadcrumbs \
    --name Breadcrumbs \
    --yes
```

The `/sage-install` skill in Claude Code wraps this same script; either path
produces the same result.

### What it copies (always overwrites on re-run)

| Source (sage-feature-team root) | Dest (`<project>/`) |
|---|---|
| `agents/` | `.sage/agents/` |
| `_tools/` (all internal scripts) | `.sage/_tools/` |
| `HANDBOOK.md` | `.sage/HANDBOOK.md` |
| `sage-config.SCHEMA.md` | `.sage/sage-config.SCHEMA.md` |
| `requirements.txt` | `.sage/requirements.txt` |
| `templates/` | `.sage/templates/` |
| `guides/` | `.sage/guides/` |
| `.claude/skills/sage-feature-team/SKILL.md` | `.claude/skills/sage-feature-team/SKILL.md` |
| `.claude/skills/sage-dev-test/SKILL.md` | `.claude/skills/sage-dev-test/SKILL.md` |
| `.claude/skills/sage-po/SKILL.md` | `.claude/skills/sage-po/SKILL.md` |
| `.claude/skills/sage-test-creator/SKILL.md` | `.claude/skills/sage-test-creator/SKILL.md` |
| `.claude/skills/sage-developer/SKILL.md` | `.claude/skills/sage-developer/SKILL.md` |
| `.claude/skills/sage-tester/SKILL.md` | `.claude/skills/sage-tester/SKILL.md` |

SKILL files are rewritten on copy: paths like `_tools/load_agents.py`
become `.sage/_tools/load_agents.py`, and references like ``
`HANDBOOK.md` `` become `` `.sage/HANDBOOK.md` ``. The source SKILLs
assume the sage-feature-team layout; installed SKILLs assume the project
layout.

### What it scaffolds (NEVER overwrites on re-run)

- `<project>/.sage/sage-product-owner-config.yaml`
- `<project>/.sage/sage-test-creator-config.yaml`
- `<project>/.sage/sage-developer-config.yaml`
- `<project>/.sage/sage-tester-config.yaml`
- `<project>/.sage/sage-epic-verifier-config.yaml`
- `<project>/sage-config.yaml`

Re-running the installer is safe: generic files refresh (so you can update
an installed project by re-running after pulling sage-feature-team), but
the user's per-agent instructions and team config are preserved.

### What it doesn't do

- Doesn't probe the project for language/framework -- that knowledge lives
  in the user's instruction lists.
- Doesn't preflight test commands or servers -- Tester does that at
  runtime per its instructions.
- Doesn't write or copy any project markdown -- the user creates those,
  organized however they like.

### Verification

After install, the wizard runs the installed loader
(`<project>/.sage/_tools/load_agents.py full`) and prints OK if all
agents render cleanly. If verification fails, the install completed but
something is wrong (corrupt config, missing source file, etc.) -- exit
code 2.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `sage-config.yaml not found` | No config in cwd, sage-feature-team root, or any parent dir | Run `setup_project.py` from your project root |
| `Agent file not found: agents/X.md` | `team.agents.full` references a missing role file | Check the `file:` path in `sage-config.yaml` matches an actual file in `agents/` |
| `_No project-specific instructions configured._` appears in agent prompt | `.sage/sage-<agent>-config.yaml` missing or has empty `instructions: []` | Edit the file to add real instructions |
| `instructions must be a list` | YAML scalar where a list was expected | Use the bullet list form: `instructions:\n  - "..."\n  - "..."` |
| Loader runs but worker uses stale prompt | `.sage/.rendered/` is cached and another process is reading it | Cache is regenerated on every loader call; if stale, delete `.sage/.rendered/` and re-run |
| Worker can't find a helper script (e.g. `verify_ac_map.py`) | Path resolution: `{SAGE_TOOLS_DIR}` resolved to `_tools` in source vs `.sage/_tools` in installed projects | Confirm whether you're running in source-mode or installed-mode; the rendered prompt should match |

---

## Layout

```
_tools/
+-- README.md                  <- this file
+-- setup_project.py           <- USER-FACING: install sage into a project
+-- install_skill.py           <- USER-FACING: bootstrap /sage-install
+-- cleanup_project.py         <- USER-FACING: backs /sage-uninstall
+-- load_agents.py             <- internal: assemble rendered agent prompts
+-- list_eligible.py           <- internal: scheduler eligibility buckets
+-- update_story_status.py     <- internal: atomic story status flip
+-- update_epic_status.py      <- internal: atomic epic status flip
+-- verify_ac_map.py           <- internal: Gate B (AC implementation map check)
+-- verify_epic.py             <- internal: EpicVerifier precondition gate
+-- prepare_task_payload.py    <- internal: pre-render task message
+-- discover_and_record.py     <- internal: token telemetry from transcripts
+-- extract_token_usage.py     <- internal: parse one transcript's usage (used by record_worker_usage)
+-- record_worker_usage.py     <- internal: write one worker's tokens entry (called by discover_and_record, also by inline skills)
\-- rollup_status.py           <- internal: regenerate progress.md
```
