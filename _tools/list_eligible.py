#!/usr/bin/env python3
"""
List which stories are eligible for which role, based on story status and
dependency satisfaction. Mechanical replacement for the scheduler's
ad-hoc eligibility logic.

A story's `dependencies:` list is satisfied ONLY when every dep resolves
to a story file with `status: DONE`. Any other status (`TESTING`,
`IN_DEV`, `BLOCKED`, `TODO`, `CREATE_TESTS`) does NOT count -- including
TESTING, which can still re-cycle back to IN_DEV.

CLI:
    python _tools/list_eligible.py --feature add_dark_mode

Output (JSON on stdout):
    {
      "success": true,
      "feature": "add_dark_mode",
      "stories_dir": "_output/add_dark_mode/stories",
      "TestCreator":     ["STORY-2"],           // TODO with deps all DONE
      "Developer":       ["STORY-4", "STORY-5"], // IN_DEV with deps all DONE
      "Tester":          ["STORY-1"],            // TESTING with deps all DONE
      "in_progress":     ["STORY-7"],            // CREATE_TESTS (TestCreator owns it)
      "blocked_on_deps": {
        "STORY-3": ["STORY-1 (TESTING, needs DONE)"]
      },
      "blocked":         ["STORY-6"],            // status BLOCKED
      "done":            [],
      "all_statuses":    {"STORY-1": "TESTING", "STORY-2": "TODO", ...}
    }

Exit codes:
    0  success (even if no stories are eligible -- that's a valid scheduler state)
    1  error (feature dir missing, YAML parse failure, etc.)
"""

import argparse
import json
import re
import sys
from pathlib import Path

import yaml


SAGE_ROLE_FOR_STATUS = {
    "TODO":         "TestCreator",
    "IN_DEV":       "Developer",
    "TESTING":      "Tester",
    "CREATE_TESTS": None,   # in-flight: TestCreator owns it
    "DONE":         None,
    "BLOCKED":      None,
}


def find_sage_config():
    cur = Path.cwd()
    for _ in range(10):
        c = cur / "sage-config.yaml"
        if c.exists():
            return c
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def load_config():
    p = find_sage_config()
    if p is None:
        return {}
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_output_dir(config):
    return Path((config.get("paths") or {}).get("output_dir", "_output"))


def _story_sort_key(s):
    m = re.match(r"^STORY-(\d+)$", str(s))
    if m:
        return (0, int(m.group(1)))
    return (1, str(s))


def load_all_stories(stories_dir):
    """Return {story_id: parsed_yaml_dict} for every STORY-*.yaml in the dir."""
    stories = {}
    for yaml_path in stories_dir.glob("STORY-*.yaml"):
        try:
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        except Exception as e:
            raise RuntimeError(f"YAML parse failed for {yaml_path}: {e}")
        if not isinstance(data, dict):
            raise RuntimeError(f"{yaml_path} did not contain a YAML mapping")
        sid = data.get("id")
        if not sid:
            raise RuntimeError(f"{yaml_path} has no 'id' field")
        if sid != yaml_path.stem:
            # Non-fatal: warn via stderr but trust the yaml `id` field as canonical
            print(f"[warn] filename {yaml_path.name} doesn't match id {sid!r}", file=sys.stderr)
        stories[sid] = data
    return stories


def deps_status(story, all_statuses):
    """Return list of dep descriptions that aren't DONE. Empty list means all deps satisfied."""
    unmet = []
    deps = story.get("dependencies") or []
    if not isinstance(deps, list):
        return [f"<malformed dependencies field: {deps!r}>"]
    for dep_id in deps:
        if dep_id not in all_statuses:
            unmet.append(f"{dep_id} (not found)")
        elif all_statuses[dep_id] != "DONE":
            unmet.append(f"{dep_id} ({all_statuses[dep_id]}, needs DONE)")
    return unmet


def classify(feature, stories_dir):
    stories = load_all_stories(stories_dir)
    all_statuses = {sid: s.get("status") for sid, s in stories.items()}

    result = {
        "success": True,
        "feature": feature,
        "stories_dir": str(stories_dir),
        "TestCreator": [],
        "Developer": [],
        "Tester": [],
        "in_progress": [],
        "blocked_on_deps": {},
        "blocked": [],
        "done": [],
        "all_statuses": all_statuses,
    }

    for sid in sorted(stories.keys(), key=_story_sort_key):
        story = stories[sid]
        status = story.get("status")

        if status == "DONE":
            result["done"].append(sid)
            continue
        if status == "BLOCKED":
            result["blocked"].append(sid)
            continue
        if status == "CREATE_TESTS":
            # TestCreator is presumed to own this story -- not eligible to spawn fresh.
            # If the scheduler determines it was stranded (e.g., after interrupt),
            # the orchestrator can manually flip back to TODO and re-trigger.
            result["in_progress"].append(sid)
            continue

        role = SAGE_ROLE_FOR_STATUS.get(status)
        if role is None:
            # Unknown / unexpected status -- surface for visibility but do not
            # mark eligible.
            result["blocked_on_deps"][sid] = [f"<unexpected status: {status!r}>"]
            continue

        unmet = deps_status(story, all_statuses)
        if unmet:
            result["blocked_on_deps"][sid] = unmet
            continue

        result[role].append(sid)

    return result


def main():
    parser = argparse.ArgumentParser(description="List which stories are eligible for which role, based on status + dependency satisfaction.")
    parser.add_argument("--feature", required=True, help="Feature name (snake_case). Reads from <output_dir>/<feature>/stories/.")
    args = parser.parse_args()

    config = load_config()
    output_dir = get_output_dir(config)
    stories_dir = output_dir / args.feature / "stories"

    if not stories_dir.is_dir():
        print(json.dumps({
            "success": False,
            "error": f"stories directory not found: {stories_dir}",
            "feature": args.feature,
        }))
        sys.exit(1)

    try:
        result = classify(args.feature, stories_dir)
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "feature": args.feature,
            "stories_dir": str(stories_dir),
        }))
        sys.exit(1)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
