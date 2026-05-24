---
name: sage-install
description: Install Sage Feature Team into the current project (.sage/ + .claude/skills/ + sage-config.yaml)
when_to_use: When the user wants to install Sage Feature Team into the current working directory. The project becomes self-contained -- no dependency on the source sage-feature-team checkout.
---

# /sage-install

Wraps `_tools/setup_project.py` from the user's local sage-feature-team checkout. Installs everything a project needs to use Sage agents into the current working directory:

- Team workflows: `/sage-feature-team`, `/sage-dev-test`
- Per-agent inline skills: `/sage-po`, `/sage-test-creator`, `/sage-developer`, `/sage-tester`

---

## Prerequisites (verify before running this skill)

The installer has a preflight that hard-errors if anything below is missing, so the user will see a clear message. But to avoid the failed-then-retry loop, check up front:

1. **Python 3.10 or later** is on PATH (`python --version`).
2. **PyYAML installed** in that Python env. **ruamel.yaml recommended** (preserves comments/field order on YAML edits). One-time install from the source repo:
   ```bash
   pip install -r <SAGE_SOURCE>/requirements.txt
   ```
   Where `<SAGE_SOURCE>` is the user's sage-feature-team checkout (see "Source location" below).

If you ALREADY ran this on a prior `/sage-install` for any project, the deps are installed globally (or per-user) and cover every sage-using project on this machine -- skip step 2.

**Virtualenv caveat:** sage tools run with whatever python is on PATH at workflow time. If the target project uses a venv, install the deps in THAT venv too (the installer copies `requirements.txt` into `.sage/requirements.txt` for exactly this purpose -- after install, the user can `pip install -r .sage/requirements.txt` inside their venv).

If the user explicitly says "I haven't installed deps yet" or this looks like their first time installing sage anywhere, tell them to run the pip install command above before invoking the skill. Otherwise proceed; preflight will catch it.

---

## Source location (edit if you move sage-feature-team)

```
SAGE_SOURCE = "{SAGE_SOURCE_PATH}"
```

If the user has moved or renamed the source checkout, ask them where it is and update `SAGE_SOURCE` for this run. Don't assume it's still in the default location if the path doesn't exist -- verify first.

(If you're reading the canonical copy in the sage-feature-team repo itself, `{SAGE_SOURCE_PATH}` is an unsubstituted placeholder; run `python _tools/install_skill.py` from the repo to write a substituted copy to your user-level skills directory.)

---

## Workflow

### Step 1: Verify source exists

Run:
```bash
test -f "<SAGE_SOURCE>/_tools/setup_project.py" && echo OK || echo MISSING
```

If MISSING, tell the user the source path doesn't have an installer at the expected location, ask them where their sage-feature-team checkout is, and use that path for the rest of the run.

### Step 2: Determine target project

**Project root** = current working directory (`pwd`) by default.

If the user invoked the skill with an argument like `/sage-install /path/to/somewhere`, use that path instead. Otherwise use cwd.

**Project name** = basename of the project root by default (e.g., cwd is `~/StudioProjects/Breadcrumbs` -> name is `Breadcrumbs`).

Ask the user to confirm both values before running. Example:

> I'm about to install Sage into:
> - **Project root:** `<resolved absolute path>`
> - **Project name:** `<basename>` (used in team names like `<name>-feature-team`)
>
> Want to change either before I run the installer? (Press enter to proceed.)

### Step 3: Refuse to install into the source itself

If the resolved project root is the same as `SAGE_SOURCE`, refuse:

> That's the sage-feature-team source itself -- installing into it would be circular. Pick a different project directory.

### Step 4: Run the installer

```bash
python "<SAGE_SOURCE>/_tools/setup_project.py" \
    --project "<project_root>" \
    --name "<project_name>" \
    --yes
```

Show the installer's output to the user verbatim. The installer prints:
- A summary of what will be installed
- A line per copied/scaffolded/preserved file
- A verification result (`OK: loaded N agents` or `[WARN] verification failed: ...`)

### Step 5: Report and next steps

If the installer exited 0, summarize for the user:

> Installed into `<project_root>`. The project now has:
> - `.sage/requirements.txt` -- Python deps manifest (pyyaml + ruamel.yaml). If this project uses a virtualenv or gets handed to CI / a collaborator with a different Python env, install with `pip install -r .sage/requirements.txt` in that env.
> - `.sage/agents/` -- 6 agent role files (_BASE + 5 roles: ProductOwner, TestCreator, Developer, Tester, EpicVerifier)
> - `.sage/_tools/` -- 11 helper scripts:
>   - `load_agents.py` (renders agent prompts)
>   - `update_story_status.py` (atomic, locked story status flips)
>   - `update_epic_status.py` (atomic, locked epic status flips: TODO/IN_PROGRESS/DONE/VERIFIED/BLOCKED)
>   - `verify_ac_map.py` (Tester's Gate B: per-story AC implementation map check)
>   - `verify_epic.py` (EpicVerifier preconditions: all stories DONE + AC maps still verify)
>   - `list_eligible.py` (scheduler entry point: per-role eligibility + epic_ready_to_verify)
>   - `rollup_status.py` (read-only renderer: feature/epic/story tree to `progress.md`)
>   - `prepare_task_payload.py` (renders spec + story YAMLs + optional epic for embedding in worker task messages, avoiding bootstrap Read calls)
>   - `extract_token_usage.py` (parses Agent JSONL transcripts for token usage)
>   - `record_worker_usage.py` (writes per-worker token entries)
>   - `discover_and_record.py` (idempotent token discovery, called per scheduling scan)
> - `.sage/HANDBOOK.md`, `templates/`, `guides/` -- protocol details and reusable patterns
> - `.claude/skills/` with 6 skills: `sage-feature-team`, `sage-dev-test`, `sage-po`, `sage-test-creator`, `sage-developer`, `sage-tester`
> - 5 skeleton instruction configs in `.sage/sage-*-config.yaml` (one per agent role, including epic-verifier)
> - `sage-config.yaml` in the project root (with `max_cycles`, `max_parallel_workers`, `global_timeout_seconds` limits, plus a commented-out `pricing:` block for cost reporting overrides)
>
> Next: edit each `.sage/sage-*-config.yaml` to fill in the `instructions:` list with project-specific guidance (point at your project's docs). Then run one of:
> - `/sage-feature-team "Your feature"` -- full team workflow (writes `_output/FEATURE_<name>_TOKENS.md` live as workers finish)
> - `/sage-dev-test` -- ad-hoc test/fix cycle
> - `/sage-po "Your feature"`, `/sage-test-creator`, `/sage-developer`, `/sage-tester` -- invoke a single agent inline

If the installer exited non-zero, surface the failure and don't claim success. Common cases:
- Exit 1: source file missing, or user cancelled, or invalid project path
- Exit 2: install succeeded but post-install verification (loader rendering all 4 agents) failed -- investigate the printed error message

---

## Idempotency

The installer is safe to re-run. On re-run:
- Generic files (agents, `_tools/` scripts, HANDBOOK, templates, guides, references, SKILLs) are **overwritten** -- this is how you upgrade an installed project after pulling sage-feature-team.
- User data (the four `sage-*-config.yaml` instruction files and `sage-config.yaml`) is **preserved** -- your project-specific instructions never get clobbered.

So `/sage-install` is also the "upgrade" command. If the user asks "how do I update Sage in this project?", the answer is just to re-run this skill.

---

## Upgrading this skill itself

If you pull a new version of sage-feature-team, the `/sage-install` skill itself may have been updated. To pull that update into your user-level skills directory, re-run the bootstrap from the source repo:

```bash
cd <SAGE_SOURCE>
python _tools/install_skill.py
```

This overwrites `~/.claude/skills/sage-install/SKILL.md` with the latest version from the repo. Safe to run repeatedly; the bootstrap is idempotent.

---

## What this skill does NOT do

- Doesn't install sage-feature-team itself -- that's a separate `git clone` of the source repo.
- Doesn't push, commit, or modify git in any way.
- Doesn't fill in the instruction lists for the user -- that's project-specific work the user does after install.
- Doesn't run `/sage-feature-team` -- install only. The user invokes the workflow skills themselves once install is done.
