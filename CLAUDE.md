# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Sage Feature Team is **the system, not a project being built with it**. It produces multi-agent feature-development workflows for Claude Code. Four generic agents (ProductOwner, TestCreator, Developer, Tester) plus an EpicVerifier, coordinated by a Skill acting as Team Lead/Orchestrator. The agents are project-agnostic; project-specific knowledge is injected at load time from a target project's `.sage/` directory.

The key mental split: this repo holds the **generic WHAT** (each agent's fixed job). Each consuming project holds the **HOW** (plain-English instruction lists pointing at that project's docs). Neither hardcodes the other.

## Commands

```bash
# One-time per machine (after cloning)
pip install -r requirements.txt          # PyYAML required; ruamel.yaml optional (preserves YAML comments/order)
python _tools/install_skill.py           # bootstraps /sage-install into ~/.claude/skills (idempotent; re-run after git pull)

# Install sage into a target project (or use /sage-install from that project's root in Claude Code)
python _tools/setup_project.py --project <path> --name <Name> --yes   # non-interactive
python _tools/setup_project.py                                        # interactive wizard

# Assemble agent prompts (skills call this; rarely run by hand)
python _tools/load_agents.py full
python _tools/load_agents.py dev-test-only
```

There is **no build, lint, or test suite** in this repo. The Python tools are dependency-light scripts run directly. To sanity-check changes to `load_agents.py`, run it against the bundled `sage-config.yaml` (which points at `examples/chatbot/.sage/`) and confirm `success: true` with all agent prompts rendered.

Python 3.10+ is required.

## Architecture: prompt assembly pipeline

`load_agents.py` is the heart of the system. For each agent in the requested mode it:

1. Reads `agents/_BASE.md` (shared protocol + the `{PROJECT_INSTRUCTIONS}` hook)
2. Reads the role file (`agents/<role>.md`)
3. Concatenates base + role
4. Reads the project's `.sage/sage-<slug>-config.yaml`, formats its `instructions:` list as markdown bullets
5. Substitutes `{VAR}` placeholders (see `sage-config.SCHEMA.md` for the full list) — most importantly `{PROJECT_INSTRUCTIONS}` and `{SAGE_TOOLS_DIR}`
6. Emits JSON: `{ success, team_name, agents: {Name: "<rendered prompt>"}, ... }`

The same rendered prompt for a role is reused for *every* worker of that role. Agent name → config slug mapping lives in `AGENT_SLUGS` in `load_agents.py`; adding an agent means updating that dict **and** `sage-config.yaml`'s `team.agents`.

`{SAGE_TOOLS_DIR}` resolves to `.sage/_tools` in an installed project but `_tools` when running from this source repo — this is why the same SKILL.md works in both contexts.

## Architecture: source repo vs. installed project

This distinction trips up most edits. Two layouts run the same skills:

- **Source repo (this checkout):** tools at `_tools/`, agents at `agents/`. `sage-config.yaml` here is the *chatbot demo* config — it points `sage_dir` at `examples/chatbot/.sage/` so the loader can be exercised without a separate project.
- **Installed project:** `setup_project.py` copies `agents/`, `_tools/load_agents.py`, `HANDBOOK.md`, templates, guides, and the SKILL files into `<project>/.sage/` and `<project>/.claude/skills/`. **On copy, SKILL files are path-rewritten** (`_tools/...` → `.sage/_tools/...`, `` `HANDBOOK.md` `` → `` `.sage/HANDBOOK.md` ``). After install the project is self-contained — no dependency on this checkout.

`setup_project.py` always overwrites generic files on re-run (so `git pull` + re-install updates a project) but **never** overwrites the per-agent `.sage/sage-*-config.yaml` instruction files or `sage-config.yaml` (user's work).

When editing SKILL.md files, remember the source version assumes the source layout; the path rewrite happens at install time. Don't hardcode `.sage/` paths in the source SKILLs.

## Architecture: the state machine

Workflow state lives in **per-story and per-epic YAML files**, not in agent messages. The YAML is the event log; the orchestrator re-reads it after every worker completion and never trusts a message body alone.

```
_output/<feature>/spec.md
_output/<feature>/epics/EPIC-N.yaml          # every feature has >=1 epic
_output/<feature>/stories/STORY-N.yaml        # each has an `epic: EPIC-N` field
_output/<feature>/stories/STORY-N.implementation.md   # Developer's AC map sidecar
_output/<feature>/verification/EPIC-N.md      # EpicVerifier output
_output/<feature>/progress.md                 # human-readable rollup (regenerated, not authoritative)
_output/<feature>/tokens.{json,md}            # token telemetry
```

Story states: `TODO → CREATE_TESTS → IN_DEV → TESTING → DONE` (plus `BLOCKED`).
Epic states: `TODO → IN_PROGRESS → DONE → VERIFIED` (plus `BLOCKED`).

**Status transitions go through the helper scripts only — never hand-edit YAML for status.** `update_story_status.py` and `update_epic_status.py` are atomic and file-locked because multiple parallel workers touch the same directory.

### Three verification gates

1. **Gate A (Tester):** per-story tests pass, including no build/compile errors.
2. **Gate B (Tester):** `verify_ac_map.py` passes against the Developer's `STORY-N.implementation.md` sidecar — every acceptance criterion is mapped to real implementation. A story reaches `DONE` only when both gates pass.
3. **EpicVerifier:** once all stories in an epic are `DONE`, runs cross-story regression and epic-level acceptance, then flips the epic to `VERIFIED` (which unblocks downstream epics). On failure it re-opens specific stories to `IN_DEV`.

### Scheduler model

The `sage-feature-team` skill runs as the orchestrator in the main conversation (it does **not** spawn an orchestrator agent). Phase 1 is a single long-lived ProductOwner awaiting explicit `APPROVED`. Phase 2 is a parallel scheduler that, on every scan, calls `list_eligible.py` (authoritative — never eyeball the YAMLs) to learn which stories are eligible for which role and which epics are ready to verify, then spawns ephemeral per-story workers up to `max_parallel_workers`. A dependency is satisfied **only** when its status is exactly `DONE` (`TESTING` does not count; `DONE != VERIFIED` for epic deps).

Workers are terminated with `shutdown_request` → `shutdown_response approve=true` — *not* `TaskStop` and *not* a plain-text "released" message, neither of which removes an agent from the team panel. The skill owns the full team lifecycle (`TeamCreate` → per-worker shutdown → `TeamDelete`), and `--resume` force-cleans the team first.

## Tooling reference (`_tools/`)

| Script | Role |
|---|---|
| `load_agents.py` | Assembles agent prompts (the pipeline above) |
| `setup_project.py` | Installs sage into a target project |
| `install_skill.py` | Bootstraps `/sage-install` into the user skills dir |
| `list_eligible.py` | Authoritative scheduler input — eligibility buckets per role + epic-ready list |
| `update_story_status.py` / `update_epic_status.py` | Atomic, locked status flips |
| `verify_ac_map.py` | Gate B — validates the AC implementation map sidecar |
| `verify_epic.py` | EpicVerifier precondition gate (stories DONE + AC maps fresh) |
| `prepare_task_payload.py` | Pre-renders spec+story+epic into a worker's task message (saves bootstrap `Read` calls) |
| `discover_and_record.py` | Token telemetry — walks Claude Code transcripts, records worker usage (idempotent) |
| `rollup_status.py` | Regenerates `progress.md` from authoritative YAMLs |
| `cleanup_project.py` | Backs the `/sage-uninstall` skill |

## Skills

`.claude/skills/` holds the team-orchestrated skills (`sage-feature-team`, `sage-dev-test`), single-agent inline skills (`sage-po`, `sage-test-creator`, `sage-developer`, `sage-tester`), and install/uninstall (`sage-install`). Inline skills run an agent's job directly in the main conversation with no team/protocol overhead. The team skills spawn real worker agents.

## Conventions

- **Scripts must be pure ASCII** — no emoji, checkmarks, arrows, or other non-ASCII glyphs in `.py` files (per global config). Use `[OK]`/`[FAIL]`/`->`.
- The protocol that all agents follow lives in `HANDBOOK.md` (completion reporting, escalation, timeouts, Monitor usage). It is the single source of truth referenced by every agent file — change protocol there, not in individual role files.
- Message format is standardized in `templates/MESSAGE_TEMPLATE.md`; reusable orchestrator patterns in `guides/ORCHESTRATOR_PATTERNS.md`.
