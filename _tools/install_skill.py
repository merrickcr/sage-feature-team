#!/usr/bin/env python3
"""
Bootstrap: copy the /sage-install skill from this repo to the user's
Claude Code user-level skills directory (~/.claude/skills/sage-install/).

This is a one-time setup step a new user runs after cloning the
sage-feature-team repo and installing dependencies. After it runs,
`/sage-install` becomes available in Claude Code from any working
directory, and the user can use it to install sage into their target
projects.

What it does:
  1. Preflight (Python 3.10+, PyYAML required, ruamel.yaml warned)
  2. Reads .claude/skills/sage-install/SKILL.md from this repo
  3. Substitutes the {SAGE_SOURCE_PATH} placeholder with this repo's
     absolute path (so the installed skill knows where to find
     setup_project.py)
  4. Writes the substituted content to:
       ~/.claude/skills/sage-install/SKILL.md
  5. Reports what it did and the next step

Idempotent: re-run safely to upgrade after pulling sage-feature-team.

Usage:
    python _tools/install_skill.py
    python _tools/install_skill.py --user-skills-dir /custom/path  # rare; for testing
    python _tools/install_skill.py --dry-run                       # print what would happen
"""

import argparse
import sys
from pathlib import Path


MIN_PYTHON = (3, 10)
PLACEHOLDER = "{SAGE_SOURCE_PATH}"


def preflight():
    """Same shape as setup_project.py preflight. Hard-fail on Python or pyyaml; warn on ruamel."""
    if sys.version_info < MIN_PYTHON:
        actual = ".".join(str(v) for v in sys.version_info[:3])
        required = ".".join(str(v) for v in MIN_PYTHON)
        print(f"[ERROR] Python {required} or later is required (you have {actual}).")
        print(f"        Install a newer Python and re-run.")
        return False

    try:
        import yaml  # noqa: F401
    except ImportError:
        print("[ERROR] PyYAML is required but not installed.")
        print("        Run: pip install -r requirements.txt")
        print("        (or: pip install pyyaml ruamel.yaml)")
        return False

    try:
        import ruamel.yaml  # noqa: F401
    except ImportError:
        print("[WARN] ruamel.yaml is not installed.")
        print("       Story / epic YAMLs will be rewritten in canonical PyYAML form on")
        print("       every status flip -- comments dropped, field order may reflow.")
        print("       Recommended: pip install ruamel.yaml")
        print()

    return True


def repo_root():
    """Resolve the sage-feature-team repo root (parent of _tools/)."""
    return Path(__file__).parent.parent.resolve()


def source_skill_path(root):
    return root / ".claude" / "skills" / "sage-install" / "SKILL.md"


def default_user_skills_dir():
    return Path.home() / ".claude" / "skills"


def substitute(content, source_path):
    """Replace the {SAGE_SOURCE_PATH} placeholder with the actual repo path."""
    if PLACEHOLDER not in content:
        print(f"[WARN] {PLACEHOLDER} placeholder not found in source SKILL.md.")
        print(f"       The substituted output will be identical to the source.")
        print(f"       If you're seeing this, the placeholder may have been edited out;")
        print(f"       check .claude/skills/sage-install/SKILL.md in the repo.")
    return content.replace(PLACEHOLDER, str(source_path))


def main():
    parser = argparse.ArgumentParser(description="Bootstrap the /sage-install skill into ~/.claude/skills/.")
    parser.add_argument("--user-skills-dir", default=None,
                        help="Override the user skills directory (default: ~/.claude/skills). "
                             "Mainly for testing; you almost never want this.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would happen without writing.")
    args = parser.parse_args()

    print("=" * 70)
    print("Sage Feature Team -- /sage-install Skill Bootstrap")
    print("=" * 70)
    print()

    if not preflight():
        return 1

    root = repo_root()
    src = source_skill_path(root)
    if not src.exists():
        print(f"[ERROR] Source SKILL.md not found at {src}")
        print(f"        This script must run from inside a sage-feature-team checkout.")
        return 1

    user_skills_dir = Path(args.user_skills_dir).expanduser().resolve() if args.user_skills_dir else default_user_skills_dir()
    dest = user_skills_dir / "sage-install" / "SKILL.md"

    print(f"Repo source: {root}")
    print(f"Source skill: {src}")
    print(f"Destination: {dest}")
    print()

    content = src.read_text(encoding="utf-8")
    substituted = substitute(content, root)

    if dest.exists():
        existing = dest.read_text(encoding="utf-8")
        if existing == substituted:
            print("Destination already has the up-to-date content. Nothing to do.")
            print()
            print("Done.")
            return 0
        print("[INFO] Destination exists with different content -- will overwrite (this is the upgrade path).")
    else:
        print("[INFO] Destination doesn't exist yet -- will create.")
    print()

    if args.dry_run:
        print("--- DRY RUN -- not writing ---")
        print(f"Would write {len(substituted):,} chars to {dest}")
        print(f"Placeholder substituted: {PLACEHOLDER!r} -> {str(root)!r}")
        return 0

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(substituted, encoding="utf-8", newline="\n")
    print(f"Wrote {len(substituted):,} chars to {dest}")
    print()
    print("=" * 70)
    print("Done.")
    print("=" * 70)
    print()
    print("Next steps:")
    print("  1. Open Claude Code in any project directory.")
    print("  2. Invoke /sage-install -- it will install sage into that project.")
    print()
    print("If you pull a newer sage-feature-team and want to upgrade the /sage-install")
    print("skill, just re-run this script. Idempotent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
