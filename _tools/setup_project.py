#!/usr/bin/env python3
"""
Installer for Sage Feature Team into a project.

Run from the source sage-feature-team checkout. Installs everything a project
needs into its `<project>/.sage/` directory plus `<project>/.claude/skills/`.
After install, the project is self-contained — no dependency on the source
checkout.

What it copies (always overwritten on re-run):
  agents/                              -> <project>/.sage/agents/
  _tools/load_agents.py                -> <project>/.sage/_tools/load_agents.py
  _tools/update_story_status.py        -> <project>/.sage/_tools/update_story_status.py
  _tools/verify_ac_map.py              -> <project>/.sage/_tools/verify_ac_map.py
  HANDBOOK.md                          -> <project>/.sage/HANDBOOK.md
  sage-config.SCHEMA.md                -> <project>/.sage/sage-config.SCHEMA.md
  templates/                           -> <project>/.sage/templates/
  guides/                              -> <project>/.sage/guides/
  references/                          -> <project>/.sage/references/
  .claude/skills/sage-feature-team/    -> <project>/.claude/skills/sage-feature-team/
  .claude/skills/sage-dev-test/        -> <project>/.claude/skills/sage-dev-test/
  .claude/skills/sage-po/              -> <project>/.claude/skills/sage-po/
  .claude/skills/sage-test-creator/    -> <project>/.claude/skills/sage-test-creator/
  .claude/skills/sage-developer/       -> <project>/.claude/skills/sage-developer/
  .claude/skills/sage-tester/          -> <project>/.claude/skills/sage-tester/

What it scaffolds (NEVER overwritten on re-run):
  <project>/.sage/sage-product-owner-config.yaml
  <project>/.sage/sage-test-creator-config.yaml
  <project>/.sage/sage-developer-config.yaml
  <project>/.sage/sage-tester-config.yaml
  <project>/sage-config.yaml

SKILL.md files are rewritten on copy so paths reference `.sage/...` (since
inside an installed project, the loader and protocol files live under .sage/
rather than at the repo root).

Usage:
    python setup_project.py
    python setup_project.py --project /path/to/project --name MyProject --yes
"""

import argparse
import os
import re
import shutil
import sys
from pathlib import Path


# Source paths (relative to sage-feature-team root) that are copied verbatim
# into <project>/.sage/. Tuples: (source, dest_under_sage).
SAGE_FILES = [
    ("agents/_BASE.md",                          "agents/_BASE.md"),
    ("agents/product-owner.md",                  "agents/product-owner.md"),
    ("agents/test-creator.md",                   "agents/test-creator.md"),
    ("agents/developer.md",                      "agents/developer.md"),
    ("agents/tester.md",                         "agents/tester.md"),
    ("_tools/load_agents.py",                    "_tools/load_agents.py"),
    ("_tools/update_story_status.py",            "_tools/update_story_status.py"),
    ("_tools/verify_ac_map.py",                  "_tools/verify_ac_map.py"),
    ("HANDBOOK.md",                              "HANDBOOK.md"),
    ("sage-config.SCHEMA.md",                    "sage-config.SCHEMA.md"),
    ("templates/MESSAGE_TEMPLATE.md",            "templates/MESSAGE_TEMPLATE.md"),
    ("templates/PROGRESS_TEMPLATE.md",           "templates/PROGRESS_TEMPLATE.md"),
    ("guides/ORCHESTRATOR_PATTERNS.md",          "guides/ORCHESTRATOR_PATTERNS.md"),
    ("references/ROUTING_REFERENCE.md",          "references/ROUTING_REFERENCE.md"),
]

# SKILL files copied (with path rewrites) into <project>/.claude/skills/.
# Tuples: (source, dest_under_project_root).
SKILL_FILES = [
    (".claude/skills/sage-feature-team/SKILL.md",
     ".claude/skills/sage-feature-team/SKILL.md"),
    (".claude/skills/sage-dev-test/SKILL.md",
     ".claude/skills/sage-dev-test/SKILL.md"),
    (".claude/skills/sage-po/SKILL.md",
     ".claude/skills/sage-po/SKILL.md"),
    (".claude/skills/sage-test-creator/SKILL.md",
     ".claude/skills/sage-test-creator/SKILL.md"),
    (".claude/skills/sage-developer/SKILL.md",
     ".claude/skills/sage-developer/SKILL.md"),
    (".claude/skills/sage-tester/SKILL.md",
     ".claude/skills/sage-tester/SKILL.md"),
]

# Path string substitutions applied to SKILL.md content during copy. The source
# files reference paths relative to the sage-feature-team repo root; the
# installed copy needs them rooted at .sage/.
SKILL_PATH_REWRITES = [
    ("python _tools/load_agents.py",                          "python .sage/_tools/load_agents.py"),
    ("python _tools/update_story_status.py",                  "python .sage/_tools/update_story_status.py"),
    ("python _tools/verify_ac_map.py",                        "python .sage/_tools/verify_ac_map.py"),
    ("`HANDBOOK.md`",                                         "`.sage/HANDBOOK.md`"),
    ("`sage-config.SCHEMA.md`",                               "`.sage/sage-config.SCHEMA.md`"),
    ("`guides/",                                              "`.sage/guides/"),
    ("`references/",                                          "`.sage/references/"),
    ("`templates/",                                           "`.sage/templates/"),
    ("`agents/_BASE.md`",                                     "`.sage/agents/_BASE.md`"),
    ("`agents/developer.md`",                                 "`.sage/agents/developer.md`"),
    ("`agents/tester.md`",                                    "`.sage/agents/tester.md`"),
    ("`agents/product-owner.md`",                             "`.sage/agents/product-owner.md`"),
    ("`agents/test-creator.md`",                              "`.sage/agents/test-creator.md`"),
    ("`_tools/load_agents.py`",                               "`.sage/_tools/load_agents.py`"),
    ("`_tools/update_story_status.py`",                       "`.sage/_tools/update_story_status.py`"),
    ("`_tools/verify_ac_map.py`",                             "`.sage/_tools/verify_ac_map.py`"),
    ("`examples/chatbot/.sage/sage-tester-config.yaml`",      "`.sage/sage-tester-config.yaml`"),
    ("`examples/chatbot/.sage/`",                             "`.sage/`"),
]

AGENT_SLUGS = ["product-owner", "test-creator", "developer", "tester"]


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

def prompt(question, default=None, required=True):
    suffix = f" [{default}]" if default is not None else ""
    while True:
        ans = input(f"{question}{suffix}: ").strip()
        if not ans and default is not None:
            return default
        if ans:
            return ans
        if not required:
            return ""
        print("This field is required.")


def prompt_path(question, default=None):
    while True:
        p = prompt(question, default=default)
        path = Path(p).expanduser()
        if path.exists() and path.is_dir():
            return path.resolve()
        print(f"Not a directory: {p}")


def prompt_yes_no(question, default=True):
    suffix = "Y/n" if default else "y/N"
    while True:
        ans = input(f"{question} [{suffix}]: ").strip().lower()
        if not ans:
            return default
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False


def slugify(name):
    return re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_sage_config(name, abs_root):
    slug = slugify(name)
    # Use single-quoted YAML strings so Windows backslashes pass through
    # literally. (Double-quoted strings interpret \U, \n, etc. as escapes.)
    abs_root_yaml = "'" + str(abs_root).replace("'", "''") + "'"
    return f"""# Sage Feature Team config for {name}
# Generated by setup_project.py

project:
  name: "{name}"
  root_dir: "."
  absolute_root_dir: {abs_root_yaml}

team:
  name: "{slug}-feature-team"
  dev_test_team_name: "{slug}-dev-test-team"
  agents:
    full:
      - name: "ProductOwner"
        file: "agents/product-owner.md"
      - name: "TestCreator"
        file: "agents/test-creator.md"
      - name: "Developer"
        file: "agents/developer.md"
      - name: "Tester"
        file: "agents/tester.md"
    dev_test_only:
      - name: "Developer"
        file: "agents/developer.md"
      - name: "Tester"
        file: "agents/tester.md"

paths:
  output_dir: "_output"
  # sage_dir defaults to <absolute_root_dir>/.sage if omitted
  # sage_dir: ".sage"

limits:
  max_cycles: 5                # per-story dev↔test cycle cap
  max_parallel_workers: 4      # concurrent ephemeral worker cap (parallel scheduler)
  global_timeout_seconds: 3600 # wall-clock kill switch for full-mode feature runs
"""


def render_agent_skeleton(slug):
    title = slug.replace("-", " ").title()
    return f"""# {title} instructions for this project
#
# Each line below is a project-specific instruction. The agent reads these
# at startup and uses Read tool to fetch any referenced files at runtime.
#
# Examples of good instructions:
#   - "When running tests, follow docs/run_tests.md exactly."
#   - "Read docs/coding_conventions.md before writing any code."
#   - "Test files go in tests/<area>/test_<feature>.py — never anywhere else."
#   - "Specs use the template in docs/spec_template.md."
#
# Keep instructions short and concrete. Point at files for detail.

instructions: []
"""


def rewrite_skill_paths(content):
    for old, new in SKILL_PATH_REWRITES:
        content = content.replace(old, new)
    return content


# ---------------------------------------------------------------------------
# File operations
# ---------------------------------------------------------------------------

def copy_file(src, dest, transform=None):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if transform is None:
        shutil.copyfile(src, dest)
    else:
        content = src.read_text(encoding="utf-8")
        dest.write_text(transform(content), encoding="utf-8")


def install_files(source_root, project_root):
    """Copy generic files (always overwrites) and SKILLs (with path rewrites)."""
    sage_dir = project_root / ".sage"
    copied = []

    for src_rel, dest_rel in SAGE_FILES:
        src = source_root / src_rel
        if not src.exists():
            raise FileNotFoundError(f"Source file missing: {src}")
        dest = sage_dir / dest_rel
        copy_file(src, dest)
        copied.append(dest.relative_to(project_root))

    for src_rel, dest_rel in SKILL_FILES:
        src = source_root / src_rel
        if not src.exists():
            raise FileNotFoundError(f"Source file missing: {src}")
        dest = project_root / dest_rel
        copy_file(src, dest, transform=rewrite_skill_paths)
        copied.append(dest.relative_to(project_root))

    return copied


def scaffold_skeletons(project_root, project_name, abs_root):
    """Write skeleton configs and sage-config.yaml. Never overwrites existing."""
    sage_dir = project_root / ".sage"
    sage_dir.mkdir(parents=True, exist_ok=True)
    written = []
    skipped = []

    for slug in AGENT_SLUGS:
        f = sage_dir / f"sage-{slug}-config.yaml"
        if f.exists():
            skipped.append(f.relative_to(project_root))
            continue
        f.write_text(render_agent_skeleton(slug), encoding="utf-8")
        written.append(f.relative_to(project_root))

    config_path = project_root / "sage-config.yaml"
    if config_path.exists():
        skipped.append(config_path.relative_to(project_root))
    else:
        config_path.write_text(render_sage_config(project_name, str(abs_root)), encoding="utf-8")
        written.append(config_path.relative_to(project_root))

    return written, skipped


def verify_install(project_root):
    """Run the installed loader against the new sage-config.yaml.

    Returns (ok, message). On error, message contains the loader's complaint.
    """
    loader = project_root / ".sage" / "_tools" / "load_agents.py"
    config = project_root / "sage-config.yaml"
    if not loader.exists():
        return False, f"loader not found at {loader}"
    if not config.exists():
        return False, f"sage-config.yaml not found at {config}"

    import json
    import subprocess
    try:
        result = subprocess.run(
            [sys.executable, str(loader), "full"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        return False, "loader timed out (>15s)"
    if result.returncode != 0:
        return False, f"loader failed (exit {result.returncode}): {result.stderr.strip() or result.stdout.strip()}"
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        return False, f"loader output was not valid JSON: {e}"
    if not data.get("success"):
        return False, f"loader returned success=false: {data.get('error')}"
    agent_count = len(data.get("agents", {}))
    return True, f"loaded {agent_count} agents in mode={data.get('mode')}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Install Sage Feature Team into a project.")
    parser.add_argument("--project", help="Absolute path to the project root", default=None)
    parser.add_argument("--name", help="Project name (used in team names)", default=None)
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    source_root = Path(__file__).parent.parent.resolve()

    print("=" * 70)
    print("Sage Feature Team — Project Installer")
    print("=" * 70)
    print(f"Source: {source_root}")
    print()

    # Project name
    if args.name:
        project_name = args.name
    else:
        project_name = prompt("Project name (e.g., 'Breadcrumbs')")

    # Project root
    if args.project:
        project_root = Path(args.project).expanduser().resolve()
        if not project_root.is_dir():
            print(f"[ERROR] {project_root} is not a directory")
            return 1
    else:
        project_root = prompt_path("Project root directory", default=os.getcwd())

    if project_root == source_root:
        print()
        print("[ERROR] Project root is the same as the sage-feature-team source.")
        print("        Run the installer from a separate project directory.")
        return 1

    sage_dir = project_root / ".sage"
    print()
    print(f"Project name: {project_name}")
    print(f"Project root: {project_root}")
    print()
    print("Will install into:")
    print(f"  {sage_dir}/                   (agents, loader, HANDBOOK, templates, guides, references)")
    print(f"  {project_root}/.claude/skills/  (sage-feature-team, sage-dev-test, sage-po, sage-test-creator, sage-developer, sage-tester)")
    print(f"  {project_root}/sage-config.yaml")
    print()
    print("Skeleton configs (never overwritten on re-run):")
    for slug in AGENT_SLUGS:
        print(f"  {sage_dir}/sage-{slug}-config.yaml")
    print()

    if sage_dir.exists():
        print("[WARN] .sage/ already exists. Generic files (agents, loader, HANDBOOK,")
        print("       templates, guides, references, SKILLs) will be OVERWRITTEN.")
        print("       Skeleton configs and sage-config.yaml will be PRESERVED.")
        print()

    if not args.yes:
        if not prompt_yes_no("Proceed?", default=True):
            print("Cancelled.")
            return 1

    # Install
    print()
    print("Installing...")
    try:
        copied = install_files(source_root, project_root)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        return 1

    for path in copied:
        print(f"  copied   {path}")

    # Scaffold
    written, skipped = scaffold_skeletons(project_root, project_name, project_root)
    for path in written:
        print(f"  wrote    {path}")
    for path in skipped:
        print(f"  preserved {path}  (already exists)")

    # Verify
    print()
    print("Verifying install...")
    ok, msg = verify_install(project_root)
    if ok:
        print(f"  OK: {msg}")
    else:
        print(f"  [WARN] verification failed: {msg}")
        print(f"         Install completed but the loader couldn't render agents.")
        print(f"         Check {project_root / 'sage-config.yaml'} and re-run with --yes.")
        return 2

    # Done
    print()
    print("=" * 70)
    print("Done.")
    print("=" * 70)
    print()
    print("Next steps:")
    print(f"  1. Edit each {sage_dir.name}/sage-*-config.yaml — fill in `instructions:`")
    print(f"     with project-specific guidance (point at your project's docs).")
    print(f"  2. From the project root, run one of:")
    print(f"       /sage-feature-team \"Your feature\"   — full team workflow")
    print(f"       /sage-dev-test                       — ad-hoc test/fix cycle (Developer + Tester)")
    print(f"       /sage-po \"Your feature\"             — single agent: create spec + stories")
    print(f"       /sage-test-creator [STORY-N]         — single agent: write tests for a story")
    print(f"       /sage-developer    [STORY-N]         — single agent: implement code for a story")
    print(f"       /sage-tester       [STORY-N]         — single agent: validate a story's tests")
    return 0


if __name__ == "__main__":
    sys.exit(main())
