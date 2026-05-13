#!/usr/bin/env python3
"""
Uninstaller for Sage Feature Team.

Removes the generic files that setup_project.py installed (agents, _tools,
HANDBOOK, templates, guides, SKILL files) while PRESERVING user data:
  - .sage/sage-product-owner-config.yaml
  - .sage/sage-test-creator-config.yaml
  - .sage/sage-developer-config.yaml
  - .sage/sage-tester-config.yaml
  - sage-config.yaml

This is the inverse of setup_project.py. Re-running setup_project.py after
cleanup_project.py restores everything that was deleted (the preserved
configs are left in place and not overwritten).

What it removes (always):
  <project>/.sage/agents/
  <project>/.sage/_tools/
  <project>/.sage/HANDBOOK.md
  <project>/.sage/sage-config.SCHEMA.md
  <project>/.sage/templates/
  <project>/.sage/guides/
  <project>/.claude/skills/sage-feature-team/
  <project>/.claude/skills/sage-dev-test/
  <project>/.claude/skills/sage-po/
  <project>/.claude/skills/sage-test-creator/
  <project>/.claude/skills/sage-developer/
  <project>/.claude/skills/sage-tester/

What it preserves (NEVER touched):
  <project>/.sage/sage-product-owner-config.yaml
  <project>/.sage/sage-test-creator-config.yaml
  <project>/.sage/sage-developer-config.yaml
  <project>/.sage/sage-tester-config.yaml
  <project>/sage-config.yaml

What it touches conditionally:
  <project>/_output/                      preserved by default; removed with --remove-output

After running, empty .sage/.claude/skills/ and .claude/ directories are
also removed unless they contain unrelated files.

Usage:
    python cleanup_project.py
    python cleanup_project.py --project /path/to/project --yes
    python cleanup_project.py --project ... --yes --dry-run
    python cleanup_project.py --project ... --yes --remove-output
"""

import argparse
import os
import shutil
import sys
from pathlib import Path


# Directories under <project>/.sage/ that get removed wholesale.
SAGE_DIRS_TO_REMOVE = [
    "agents",
    "_tools",
    "templates",
    "guides",
]

# Files directly under <project>/.sage/ that get removed.
SAGE_FILES_TO_REMOVE = [
    "HANDBOOK.md",
    "sage-config.SCHEMA.md",
]

# Skill subdirectories under <project>/.claude/skills/ to remove.
SKILL_DIRS_TO_REMOVE = [
    "sage-feature-team",
    "sage-dev-test",
    "sage-po",
    "sage-test-creator",
    "sage-developer",
    "sage-tester",
]

# These are NEVER removed -- they're project-specific user data.
PRESERVED_SAGE_CONFIGS = [
    "sage-product-owner-config.yaml",
    "sage-test-creator-config.yaml",
    "sage-developer-config.yaml",
    "sage-tester-config.yaml",
]


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


def remove_dir(path, dry_run, log):
    if not path.exists():
        return
    if dry_run:
        log.append(f"  WOULD REMOVE  {path}/")
    else:
        shutil.rmtree(path)
        log.append(f"  removed       {path}/")


def remove_file(path, dry_run, log):
    if not path.exists():
        return
    if dry_run:
        log.append(f"  WOULD REMOVE  {path}")
    else:
        path.unlink()
        log.append(f"  removed       {path}")


def remove_empty_dir(path, dry_run, log):
    """Remove the directory only if it's empty after we've stripped sage stuff."""
    if not path.exists() or not path.is_dir():
        return
    try:
        # rmdir only succeeds on empty directories
        if dry_run:
            if not any(path.iterdir()):
                log.append(f"  WOULD REMOVE  {path}/  (now empty)")
        else:
            if not any(path.iterdir()):
                path.rmdir()
                log.append(f"  removed       {path}/  (was empty)")
    except OSError:
        pass


def cleanup(project_root, remove_output, dry_run):
    log = []
    sage_dir = project_root / ".sage"
    skills_dir = project_root / ".claude" / "skills"
    claude_dir = project_root / ".claude"
    output_dir = project_root / "_output"

    log.append(f"Target project: {project_root}")
    log.append("")

    # ---- .sage/ ----
    if sage_dir.exists():
        for sub in SAGE_DIRS_TO_REMOVE:
            remove_dir(sage_dir / sub, dry_run, log)
        for f in SAGE_FILES_TO_REMOVE:
            remove_file(sage_dir / f, dry_run, log)
        # List what was preserved (informational)
        preserved = [(sage_dir / cfg) for cfg in PRESERVED_SAGE_CONFIGS if (sage_dir / cfg).exists()]
        for p in preserved:
            log.append(f"  preserved     {p}")
        # If .sage/ ends up empty (no preserved configs), remove the dir
        remove_empty_dir(sage_dir, dry_run, log)
    else:
        log.append(f"  (.sage/ not present at {sage_dir})")

    # ---- .claude/skills/sage-*/ ----
    if skills_dir.exists():
        for sub in SKILL_DIRS_TO_REMOVE:
            remove_dir(skills_dir / sub, dry_run, log)
        # Remove skills/ and .claude/ only if they're now empty
        remove_empty_dir(skills_dir, dry_run, log)
        remove_empty_dir(claude_dir, dry_run, log)
    else:
        log.append(f"  (.claude/skills/ not present at {skills_dir})")

    # ---- sage-config.yaml (preserved) ----
    sage_config = project_root / "sage-config.yaml"
    if sage_config.exists():
        log.append(f"  preserved     {sage_config}")

    # ---- _output/ (preserved by default, removed with --remove-output) ----
    if output_dir.exists():
        if remove_output:
            remove_dir(output_dir, dry_run, log)
        else:
            log.append(f"  preserved     {output_dir}/  (use --remove-output to delete)")

    return log


def main():
    parser = argparse.ArgumentParser(description="Uninstall Sage Feature Team from a project (preserves user configs).")
    parser.add_argument("--project", help="Absolute path to the project root", default=None)
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    parser.add_argument("--dry-run", action="store_true", help="List what would be removed without deleting")
    parser.add_argument("--remove-output", action="store_true", help="Also remove _output/ (feature specs, stories, progress, tokens). DESTRUCTIVE.")
    args = parser.parse_args()

    print("=" * 70)
    print("Sage Feature Team -- Project Uninstaller")
    print("=" * 70)
    print()

    if args.project:
        project_root = Path(args.project).expanduser().resolve()
        if not project_root.is_dir():
            print(f"[ERROR] {project_root} is not a directory")
            return 1
    else:
        project_root = prompt_path("Project root directory", default=os.getcwd())

    # Refuse to nuke the sage-feature-team source itself.
    here = Path(__file__).parent.parent.resolve()
    if project_root == here:
        print()
        print("[ERROR] Project root is the same as the sage-feature-team source.")
        print("        Refusing to uninstall from the source repo.")
        return 1

    print()
    print(f"Uninstalling Sage from: {project_root}")
    print()
    print("Will REMOVE:")
    for sub in SAGE_DIRS_TO_REMOVE:
        print(f"  .sage/{sub}/")
    for f in SAGE_FILES_TO_REMOVE:
        print(f"  .sage/{f}")
    for sub in SKILL_DIRS_TO_REMOVE:
        print(f"  .claude/skills/{sub}/")
    if args.remove_output:
        print(f"  _output/  (because --remove-output)")
    print()
    print("Will PRESERVE:")
    for cfg in PRESERVED_SAGE_CONFIGS:
        print(f"  .sage/{cfg}")
    print(f"  sage-config.yaml")
    if not args.remove_output:
        print(f"  _output/  (feature artifacts; pass --remove-output to wipe)")
    print()

    if args.dry_run:
        print("[DRY-RUN] No files will be touched.")
        print()

    if not args.yes and not args.dry_run:
        if not prompt_yes_no("Proceed?", default=False):
            print("Cancelled.")
            return 1

    print()
    print("Uninstalling..." if not args.dry_run else "Dry run...")
    log = cleanup(project_root, args.remove_output, args.dry_run)
    for line in log:
        print(line)

    print()
    print("=" * 70)
    print("Done." if not args.dry_run else "Dry run complete (no changes).")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
