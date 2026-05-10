#!/usr/bin/env python3
"""
Verify a story's AC implementation map sidecar (the artifact the Developer
writes to prove every AC is wired into production code).

Sidecar path:  _output/FEATURE_STORIES_<feature>/STORY-N.implementation.md
Sidecar shape (Markdown -- written by Developer at the end of every cycle):

    # STORY-N Implementation Map

    Last updated: 2026-05-10T15:42:00Z by Developer (cycle 2)

    ## AC1 ("modal surface presented")
    Implemented in:
    - app/src/main/java/.../SummaryDialog.kt:42 (composable)
    - app/src/main/java/.../WorkoutScreen.kt:118 (call site)

    ## AC2 ("share button")
    Implemented in:
    - app/src/main/java/.../ShareButton.kt:15

    ## AC3 ("dismiss")
    Implemented in:
    - app/src/main/java/.../SummaryDialog.kt:71 (onDismiss callback)

The Tester calls this script before flipping a story TESTING -> DONE. If it
fails, the Tester flips the story back to IN_DEV instead.

CLI:
    python _tools/verify_ac_map.py STORY-3 --stories-dir _output/FEATURE_STORIES_add_dark_mode

Output (JSON, single object on stdout):
    {"success": true,  "story": "STORY-3", "ac_count": 3, "covered": ["AC1","AC2","AC3"]}
    {"success": false, "story": "STORY-3", "error": "...", "missing_ac": [...], "banned_word_hits": [...]}

Exit codes:
    0  success
    1  verification failed (missing sidecar, missing AC, banned word, no impl path)
    2  invocation error (bad args, story file missing, YAML parse failure)

Banned words (case-insensitive) in any AC section indicate the Developer is
trying to roll the deferral forward instead of actually implementing:
    deferred, defer, future story, later story, next pass, next cycle,
    next pr, todo, fixme, will be done, to be implemented, punt, stub,
    placeholder, pending, skipped (the literal word in an impl context),
    not implemented, not yet, postponed
"""

import argparse
import json
import re
import sys
from pathlib import Path


BANNED_PATTERNS = [
    r"\bdeferred\b",
    r"\bdefer(?:s|ring)?\b",
    r"\bfuture\s+story\b",
    r"\blater\s+story\b",
    r"\bnext\s+pass\b",
    r"\bnext\s+cycle\b",
    r"\bnext\s+pr\b",
    r"\btodo\b",
    r"\bfixme\b",
    r"\bwill\s+be\s+(?:done|implemented|added|wired)\b",
    r"\bto\s+be\s+implemented\b",
    r"\bpunt(?:ed|ing)?\b",
    r"\bplaceholder\b",
    r"\bpending\b",
    r"\bnot\s+implemented\b",
    r"\bnot\s+yet\b",
    r"\bpostponed\b",
]

# Heading like: "## AC1" or "## AC1 (anything)" or "## AC1: anything"
AC_HEADING_RE = re.compile(r"^##\s+(AC\d+)\b", re.MULTILINE)

# A "looks like a file path" line under "Implemented in:" -- at least one slash
# or a known source-file extension. Generous on purpose; the goal is to catch
# empty sections, not to validate the path actually exists.
PATH_LINE_RE = re.compile(
    r"(?:[\\/])"                              # contains a path separator
    r"|"
    r"\.[a-zA-Z][a-zA-Z0-9]{0,4}\b"           # or a file extension like .kt, .py, .ts, .java
)


def _load_yaml(path):
    try:
        from ruamel.yaml import YAML
        yaml = YAML(typ="safe")
        with open(path, "r", encoding="utf-8") as f:
            return yaml.load(f)
    except ImportError:
        import yaml as pyyaml
        with open(path, "r", encoding="utf-8") as f:
            return pyyaml.safe_load(f)


def get_ac_ids_from_story(story_file):
    """Return ordered list of AC ids declared in the story YAML."""
    data = _load_yaml(story_file)
    if not isinstance(data, dict):
        raise ValueError(f"{story_file} did not contain a YAML mapping")
    ac_list = data.get("acceptance_criteria") or []
    if not isinstance(ac_list, list):
        raise ValueError(f"{story_file}: acceptance_criteria must be a list, got {type(ac_list).__name__}")
    ids = []
    for item in ac_list:
        if isinstance(item, dict) and "id" in item:
            ids.append(str(item["id"]))
        else:
            raise ValueError(f"{story_file}: each AC entry must be a mapping with an 'id' field; got {item!r}")
    return ids


def split_sections(content):
    """Return list of (ac_id, section_text) pairs."""
    matches = list(AC_HEADING_RE.finditer(content))
    sections = []
    for i, m in enumerate(matches):
        ac_id = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        sections.append((ac_id, content[start:end]))
    return sections


def has_implementation_path(section_text):
    """True if any non-empty line in the section looks like a file path."""
    for line in section_text.splitlines():
        line = line.strip().lstrip("-*").strip()
        if not line or line.lower().startswith("implemented in"):
            continue
        if PATH_LINE_RE.search(line):
            return True
    return False


def find_banned_words(section_text):
    """Return list of (pattern, matched_text) for any banned-word hits."""
    hits = []
    for pat in BANNED_PATTERNS:
        for m in re.finditer(pat, section_text, re.IGNORECASE):
            hits.append({"pattern": pat, "match": m.group(0)})
    return hits


def verify(story_id, stories_dir):
    stories_dir = Path(stories_dir)
    story_file = stories_dir / f"{story_id}.yaml"
    sidecar = stories_dir / f"{story_id}.implementation.md"

    if not story_file.exists():
        return {
            "success": False,
            "story": story_id,
            "error": f"story file not found: {story_file}",
            "error_type": "story_missing",
        }, 2

    try:
        ac_ids = get_ac_ids_from_story(story_file)
    except Exception as e:
        return {
            "success": False,
            "story": story_id,
            "error": f"failed to read AC list from {story_file}: {e}",
            "error_type": "yaml_error",
        }, 2

    if not sidecar.exists():
        return {
            "success": False,
            "story": story_id,
            "error": f"AC implementation map sidecar not found at {sidecar}. "
                     f"Developer must write this file mapping every AC to its production code.",
            "error_type": "sidecar_missing",
            "expected_sidecar": str(sidecar),
            "expected_ac_count": len(ac_ids),
        }, 1

    content = sidecar.read_text(encoding="utf-8")
    sections = split_sections(content)
    sectioned_ids = [ac for ac, _ in sections]
    section_lookup = dict(sections)

    missing_ac = [ac for ac in ac_ids if ac not in section_lookup]
    extra_ac = [ac for ac in sectioned_ids if ac not in ac_ids]

    issues = []

    if missing_ac:
        issues.append(f"sidecar missing sections for AC(s): {', '.join(missing_ac)}")

    banned_hits_per_ac = {}
    no_path_acs = []

    for ac in ac_ids:
        if ac not in section_lookup:
            continue
        section = section_lookup[ac]
        bw = find_banned_words(section)
        if bw:
            banned_hits_per_ac[ac] = bw
        if not has_implementation_path(section):
            no_path_acs.append(ac)

    if banned_hits_per_ac:
        details = []
        for ac, hits in banned_hits_per_ac.items():
            words = sorted({h["match"] for h in hits})
            details.append(f"{ac}: {', '.join(words)}")
        issues.append("banned-word hits (Developer is rolling deferral forward, not implementing): "
                      + "; ".join(details))

    if no_path_acs:
        issues.append(f"AC(s) with no implementation path listed: {', '.join(no_path_acs)}")

    if not issues:
        return {
            "success": True,
            "story": story_id,
            "sidecar": str(sidecar),
            "ac_count": len(ac_ids),
            "covered": ac_ids,
            "extra_sections": extra_ac,  # informational, not a failure
        }, 0

    return {
        "success": False,
        "story": story_id,
        "sidecar": str(sidecar),
        "expected_ac": ac_ids,
        "missing_ac": missing_ac,
        "no_path_ac": no_path_acs,
        "banned_word_hits": banned_hits_per_ac,
        "error": "; ".join(issues),
        "error_type": "incomplete",
    }, 1


def main():
    parser = argparse.ArgumentParser(description="Verify a story's AC implementation map sidecar.")
    parser.add_argument("story_id", help="Story ID (e.g., STORY-3)")
    parser.add_argument("--stories-dir", required=True, help="Path to FEATURE_STORIES_<feature>/")
    args = parser.parse_args()

    if not re.match(r"^STORY-\d+$", args.story_id):
        print(json.dumps({"success": False, "error": f"invalid story id '{args.story_id}'"}))
        sys.exit(2)

    try:
        result, exit_code = verify(args.story_id, args.stories_dir)
    except Exception as e:
        result = {"success": False, "error": str(e), "error_type": type(e).__name__}
        exit_code = 2

    print(json.dumps(result))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
