# Install

The full install is two phases:

```
# 1. Once per machine -- clone sage-feature-team and install its deps + the /sage-install skill
cd sage-feature-team
pip install -r requirements.txt
python _tools/install_skill.py

# 2. Once per project -- in Claude Code, cd to YOUR project and invoke
/sage-install
```

That's the whole install path. Phase 1 makes `/sage-install` available across
your machine; phase 2 scaffolds sage into a specific project repo (the agent
role files, helper scripts, handbook, templates, and the six sage skills,
all under `.sage/` and `.claude/skills/` in that project).

After phase 2 you'll edit each `.sage/sage-<role>-config.yaml` in your
project to add your project-specific instructions (test conventions, file
layout, docs to consult). Then `/sage-feature-team "<feature description>"`
from your project root is the working invocation.

For just trying sage against the bundled `examples/static-site-generator/`
without installing anywhere else, phase 1 alone is enough -- the bundled
example is already set up. The
[Quickstart](../README.md#quickstart-5-minutes) in the README covers that
path.

The rest of this doc walks each phase in detail and covers the dependency
story, the manual-install path (without `/sage-install`), what to do when
something doesn't preflight, and the full what-gets-installed-where tree.

---

## Prerequisites

- **Python 3.10 or later** (older versions are not supported).
- **PyYAML** (required) and **ruamel.yaml** (optional but strongly recommended
  -- without ruamel, story and epic YAML edits will lose comments and may
  reflow field order on every status flip).
- **Claude Code** with skills support.

## Phase 1: First-time setup (one-time per machine)

After cloning this repo:

```bash
cd sage-feature-team

# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Bootstrap the /sage-install skill into your Claude Code user-level skills directory
python _tools/install_skill.py
```

`/sage-install` is now available in Claude Code from any directory.

What each step did:

- **Step 1** installs PyYAML + ruamel.yaml into your Python env. One-time per
  Python env; covers every sage-using project on this machine.
- **Step 2** copies `.claude/skills/sage-install/SKILL.md` into
  `~/.claude/skills/sage-install/SKILL.md`, with the source-repo path
  substituted in. Re-run it any time you `git pull` an update to
  sage-feature-team (it's idempotent).

## Phase 2: Install sage into a project (per-project)

In Claude Code, `cd` to your target project's root and invoke:

```
/sage-install
```

This wraps `_tools/setup_project.py` and scaffolds `.sage/`,
`.claude/skills/`, and `sage-config.yaml` into the project. The installer
preflights deps and Python version with friendly error messages if anything's
missing.

After it completes, edit each `.sage/sage-<role>-config.yaml` with your
project-specific instructions -- one bullet per instruction, ideally pointing
at a project markdown file:

```yaml
instructions:
  - "When running tests, follow docs/run_gradle_tests.md."
  - "Test files go in app/src/test/java/, naming pattern <Feature>Test.kt."
  - "If a test references the emulator, see docs/start_emulator.md first."
```

See [`examples/static-site-generator/.sage/`](../examples/static-site-generator/.sage/)
for filled-in reference configs.

Then run `/sage-feature-team "feature description"` from your project root.

## Manual install (without /sage-install)

If you'd rather skip the skill wrapper and run the installer directly:

```bash
cd ~/StudioProjects/Breadcrumbs
python ~/claudeProjects/sage-feature-team/_tools/setup_project.py
```

The wizard asks for project name + root path, then writes the same files
`/sage-install` would.

For non-interactive install (CI, scripts):

```bash
python _tools/setup_project.py --project /path/to/project --name MyProject --yes
```

---

## Diagnostic notes

- **PyYAML missing or Python too old.** `setup_project.py` fails fast with a
  clear message. Install PyYAML (`pip install pyyaml --break-system-packages`)
  or upgrade Python.
- **Only ruamel.yaml missing.** The installer warns and continues.
  Functionality is unaffected, but YAML edits will lose comments and may
  reflow field order on every status flip. Install ruamel
  (`pip install ruamel.yaml`) to preserve those.
- **Virtualenv caveat.** Sage tools run with whatever Python is on PATH at
  workflow time. The `pip install -r requirements.txt` above is one-time per
  Python env. If your target project uses a venv, install the deps in that
  venv too. The installer copies `requirements.txt` into each installed
  project's `.sage/` directory, so once a project is installed you can
  `pip install -r .sage/requirements.txt` in any env -- venv or global --
  without needing the source sage-feature-team repo nearby.
- **Updating sage in installed projects.** Re-running `/sage-install` against
  an installed project overwrites the generic framework files (agents/, the
  internal tools under `_tools/`, the handbook, the templates, the inline
  skills) but **never** the per-agent `.sage/sage-*-config.yaml` instruction
  files or your `sage-config.yaml`. Framework updates are mechanical; your
  project-specific HOW stays yours.
- **`/sage-install` permission errors on Windows.** If the skill copy step
  fails because a previous `~/.claude/skills/sage-install/SKILL.md` is open
  in another editor, close it and re-run. The installer is idempotent.

---

## What gets installed where

After `/sage-install` runs against your project, you'll see:

```
<your-project>/
  sage-config.yaml              # team + paths for your project
  .sage/
    sage-product-owner-config.yaml   # PO instructions for this project
    sage-test-creator-config.yaml    # TestCreator instructions
    sage-developer-config.yaml       # Developer instructions
    sage-tester-config.yaml          # Tester instructions
    sage-epic-verifier-config.yaml   # EpicVerifier instructions
    agents/                          # generic role files (copied)
    _tools/                          # helper scripts (copied)
    templates/                       # message + progress templates
    guides/                          # orchestrator patterns
    HANDBOOK.md                      # protocol details
    requirements.txt                 # pip install -r this if you use a venv
  .claude/skills/
    sage-feature-team/SKILL.md       # full team workflow
    sage-dev-test/SKILL.md           # Developer + Tester only
    sage-po/SKILL.md                 # inline ProductOwner
    sage-test-creator/SKILL.md       # inline TestCreator
    sage-developer/SKILL.md          # inline Developer
    sage-tester/SKILL.md             # inline Tester
```

The path rewrites happen at install time: SKILL files that reference
`_tools/...` in the source repo are rewritten to `.sage/_tools/...` in the
installed copy. After install your project is self-contained -- it doesn't
need the source sage-feature-team checkout nearby.

For the meaning of every field in `sage-config.yaml`, see
[sage-config.SCHEMA.md](../sage-config.SCHEMA.md).
