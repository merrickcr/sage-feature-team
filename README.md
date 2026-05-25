# Sage Feature Team

A multi-agent feature-development workflow for Claude Code. Generic agents
(ProductOwner, TestCreator, Developer, Tester) coordinated by a Skill/Team
Lead. Project-specific knowledge lives in each project's `.sage/` directory.

---

## Quickstart (5 minutes)

From a fresh clone to a live agent team drafting a spec for you.

**1. Install** (one-time per machine):

```bash
pip install -r requirements.txt
python _tools/install_skill.py
```

**2. Kick off a feature.** This repo ships with a ready-to-run example config
(`sage-config.yaml`, pointed at the bundled `examples/static-site-generator`). From the repo
root, in Claude Code:

```
/sage-feature-team "Add a /help command that lists available commands"
```

A team spins up and the **ProductOwner** starts drafting the spec. Watch the
team panel populate -- and once you approve the spec, the parallel
**TestCreator / Developer / Tester** workers join it, one per story:

![Sage team panel: ProductOwner plus parallel per-story workers](docs/img/quickstart-team-panel.png)

**3. Approve the spec.** When the ProductOwner reports the spec is ready, reply
`APPROVED`. A spec, at least one epic, and one YAML file per story land under
`_output/`:

```
_output/add_help_command/
+-- spec.md
+-- epics/EPIC-1.yaml
+-- stories/STORY-1.yaml, STORY-2.yaml, ...
```

![_output tree: spec.md, epics/EPIC-1.yaml, stories/STORY-1.yaml ...](docs/img/quickstart-output-files.png)

That's the on-ramp. From here the team cycles each story through
tests -> code -> validation in parallel until every epic verifies.

> **Note:** the example config targets a sample app, so the spec-and-stories
> step above runs anywhere. To point these same agents at *your own* codebase
> and run the full build, see [Installing sage into a project](#installing-sage-into-a-project)
> below. Just want the spec without spawning a team? Run `/sage-po "..."` -- the
> ProductOwner inline, no team panel.

---

## Prerequisites

- **Python 3.10 or later** (older versions are not supported)
- **PyYAML** (required) and **ruamel.yaml** (optional but strongly recommended)

## First-time setup (one-time per machine)

After cloning this repo:

```bash
cd sage-feature-team

# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Bootstrap the /sage-install skill into your Claude Code user-level skills directory
python _tools/install_skill.py
```

That's it. `/sage-install` is now available in Claude Code from any directory.

What each step did:
- Step 1: installs pyyaml + ruamel.yaml into your Python env. One-time per Python env; covers every sage-using project on this machine.
- Step 2: copies `.claude/skills/sage-install/SKILL.md` into `~/.claude/skills/sage-install/SKILL.md`, with the source-repo path substituted in. Re-run this anytime you `git pull` an update to sage-feature-team (it's idempotent).

## Installing sage into a project

In Claude Code, `cd` to your target project's root and invoke:

```
/sage-install
```

This wraps `_tools/setup_project.py` and scaffolds `.sage/`, `.claude/skills/`, and `sage-config.yaml` into the project. The installer preflights deps and Python version with friendly error messages if anything's missing. After it completes, edit `.sage/sage-<role>-config.yaml` with your project-specific instructions, then run `/sage-feature-team "feature description"`.

## Diagnostic notes

- The `setup_project.py` preflight fails fast with a clear message if PyYAML is missing or Python is too old. If only `ruamel.yaml` is missing it warns -- functionality is unaffected, but story / epic YAML edits will lose comments and may reflow field order on every status flip.
- **Virtualenv caveat:** Sage tools run with whatever Python is on PATH at workflow time. The `pip install` above is one-time-per-Python-env. If a target project uses a venv, install the deps in that venv too. The installer copies `requirements.txt` into each installed project's `.sage/` directory, so once a project is installed you can `pip install -r .sage/requirements.txt` in any env (venv or global) without needing the source sage-feature-team repo nearby.

---

## Core Idea

Each agent has **one fixed job** and **one generic instruction file**:

| Agent | Job | File |
|---|---|---|
| ProductOwner | Write a feature spec | `agents/product-owner.md` |
| TestCreator | Write tests for the spec | `agents/test-creator.md` |
| Developer | Make tests pass without breaking others | `agents/developer.md` |
| Tester | Run tests, report pass/fail | `agents/tester.md` |

Each project tells these agents **how** to do their job for that project via a
`.sage/sage-<agent>-config.yaml` file containing a list of plain-English
instructions. The instructions point at project markdown docs that the agent
reads at runtime.

```
sage-feature-team/                       <- this repo (the system)
+-- agents/
|   +-- _BASE.md                         <- shared protocol + {PROJECT_INSTRUCTIONS} hook
|   +-- product-owner.md                 <- generic job
|   +-- test-creator.md                  <- generic job
|   +-- developer.md                     <- generic job
|   \-- tester.md                        <- generic job
+-- _tools/
|   +-- load_agents.py                   <- assembles agent prompts
|   \-- setup_project.py                 <- scaffolds .sage/ in a new project
+-- HANDBOOK.md                          <- protocol details (completion reporting, escalation, etc.)
+-- sage-config.yaml                     <- team/path config (points at the example below)
\-- examples/static-site-generator/      <- self-contained reference example

<your-project>/                          <- e.g. ~/StudioProjects/Breadcrumbs
+-- sage-config.yaml                     <- created by setup wizard
\-- .sage/
    +-- sage-product-owner-config.yaml   <- project's instructions for ProductOwner
    +-- sage-test-creator-config.yaml    <- project's instructions for TestCreator
    +-- sage-developer-config.yaml       <- project's instructions for Developer
    \-- sage-tester-config.yaml          <- project's instructions for Tester
```

---

## How a Run Works

1. User invokes `/sage-feature-team "Add dark mode"`
2. Skill reads `sage-config.yaml` and calls `_tools/load_agents.py`
3. Loader:
   - Reads `agents/_BASE.md` + each role file
   - Finds the project's `.sage/` directory (defaults to `<project_root>/.sage/`)
   - Reads `.sage/sage-<agent>-config.yaml` for each agent
   - Substitutes the instructions list into `{PROJECT_INSTRUCTIONS}` in `_BASE.md`
4. Skill creates a team and spawns the four agents with their fully-rendered prompts
5. Each agent reads its referenced project files (test guides, code conventions, etc.) using the Read tool when relevant
6. Skill routes work through ProductOwner -> TestCreator -> Developer <-> Tester until tests pass or max cycles hit

Two modes:
- **full** -- all four agents (spec -> tests -> code -> validation)
- **dev-test-only** -- Developer + Tester (tests already exist; fix and verify)

---

## Setup for a New Project

```bash
cd ~/StudioProjects/Breadcrumbs
python ~/claudeProjects/sage-feature-team/_tools/setup_project.py
```

The wizard asks for project name + root path, then writes:
- `sage-config.yaml` (team name, paths)
- `.sage/sage-product-owner-config.yaml` (skeleton)
- `.sage/sage-test-creator-config.yaml` (skeleton)
- `.sage/sage-developer-config.yaml` (skeleton)
- `.sage/sage-tester-config.yaml` (skeleton)

Then edit each `.sage/sage-*-config.yaml` to fill in the `instructions:` list.
Each instruction is a one-line English statement, ideally pointing at a project
markdown file:

```yaml
instructions:
  - "When running tests, follow docs/run_gradle_tests.md."
  - "Test files go in app/src/test/java/, naming pattern <Feature>Test.kt."
  - "If a test references the emulator, see docs/start_emulator.md first."
```

See `examples/static-site-generator/.sage/` for filled-in reference configs.

---

## Files

| Path | Purpose |
|---|---|
| `agents/_BASE.md` | Shared protocol + the `{PROJECT_INSTRUCTIONS}` hook |
| `agents/<role>.md` | Generic job description per agent |
| `HANDBOOK.md` | Full protocol details (completion reporting model, escalation, Monitor) |
| `sage-config.yaml` | This repo's demo team/paths config (points at the static-site-generator example) |
| `sage-config.SCHEMA.md` | Field reference for `sage-config.yaml` |
| `_tools/load_agents.py` | Assembles agent prompts; finds `.sage/`; substitutes vars |
| `_tools/setup_project.py` | Setup wizard for new projects |
| `_tools/README.md` | Tool-level docs |
| `templates/MESSAGE_TEMPLATE.md` | Standard SendMessage format |
| `templates/PROGRESS_TEMPLATE.md` | Progress file template |
| `guides/ORCHESTRATOR_PATTERNS.md` | Reusable Skill/Team Lead patterns |
| `examples/static-site-generator/` | Self-contained reference example (`.sage/` + docs + `sage-config.yaml`) |
| `.claude/skills/sage-feature-team/SKILL.md` | Full team workflow (PO -> TestCreator -> Developer <-> Tester) |
| `.claude/skills/sage-dev-test/SKILL.md` | Dev/test cycles only (Developer + Tester team) |
| `.claude/skills/sage-po/SKILL.md` | Single-agent inline: ProductOwner -- create spec + stories |
| `.claude/skills/sage-test-creator/SKILL.md` | Single-agent inline: TestCreator -- write tests for the next ready story |
| `.claude/skills/sage-developer/SKILL.md` | Single-agent inline: Developer -- implement code for the next IN_DEV story |
| `.claude/skills/sage-tester/SKILL.md` | Single-agent inline: Tester -- validate tests for the next TESTING story (or `--full` regression) |

---

## Per-Agent Skills (Inline)

In addition to the team-orchestrated skills, each agent can be invoked individually
inline (no team, no protocol overhead -- the main conversation acts as the agent):

| Skill | Picks up | Override |
|---|---|---|
| `/sage-po "<feature description>"` | n/a -- creates a new spec + stories file | `--feature <name>` to set feature_name explicitly |
| `/sage-test-creator [STORY-N]` | Next story at `TODO` whose dependencies are all `DONE` | Pass `STORY-N` to target a specific story |
| `/sage-developer [STORY-N]` | Next story at `IN_DEV` | Pass `STORY-N` to target a specific story |
| `/sage-tester [STORY-N] [--full]` | Next story at `TESTING` (story-scoped tests) | `STORY-N` to target a specific story; `--full` for regression |

All four also accept `--feature <feature_name>` if multiple feature folders
exist under `_output/`. Otherwise, the feature is auto-detected (single match)
or the skill asks the user (multiple matches).

---

## Adding a New Agent

1. Create `agents/<new-role>.md` (generic job description)
2. Add an entry to `team.agents.full` (and `dev_test_only` if applicable) in `sage-config.yaml`
3. Add the agent to `AGENT_SLUGS` in `_tools/load_agents.py` so its config file slug is known
4. Update the routing logic in `.claude/skills/sage-feature-team/SKILL.md`
5. Each project then creates `.sage/sage-<new-role>-config.yaml` to give it project-specific guidance

The hook (`{PROJECT_INSTRUCTIONS}`) is in `_BASE.md` -- every agent gets it automatically.
