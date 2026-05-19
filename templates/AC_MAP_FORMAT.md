# AC Implementation Map Sidecar

Shared spec referenced by Developer (writes it), Tester (verifies it as Gate B), and EpicVerifier (re-verifies it during cross-story regression).

The map is the contract that proves every AC in a story is wired to production code. A green test run alone is not sufficient -- AC the tests don't cover (UI, device-only, manual-only) must still be wired with named production file paths.

---

## Path

```
_output/{feature_name}/stories/STORY-N.implementation.md
```

One file per story, written by Developer at the end of each cycle (before flipping the story TESTING).

## Format

```markdown
# STORY-N Implementation Map

Last updated: <ISO timestamp> by Developer (cycle <n>)

## AC1 ("<verbatim or paraphrased AC text>")
Implemented in:
- <path/to/file.ext>:<line> (<one-line role, e.g. "composable", "call site", "view model wiring">)
- <path/to/file.ext>:<line>

## AC2 ("...")
Implemented in:
- <path/to/file.ext>:<line>

## AC3 ("...")
Implemented in:
- <path/to/file.ext>:<line>
```

## Rules

- One `## AC<id>` heading per AC in the story's `acceptance_criteria:` list. Same IDs (`AC1`, `AC2`, ...). No missing AC.
- Each section MUST list at least one production file path under `Implemented in:`. Tests, fixtures, mocks, and unit-test files do NOT count -- list the production code that ships to the user.
- For UI AC, name **both** the surface (composable / view / route) AND a call site (where it's invoked from -- navigation graph, parent screen, button onClick handler). A composable file with zero call sites does NOT satisfy a UI AC.
- For wiring AC ("X triggers Y"), name both ends of the wire.
- If an AC genuinely belongs in a different story (the spec was wrong), STOP and escalate to the User. Do not silently push it forward -- the failure mode this whole gate exists to prevent is exactly that.

## FORBIDDEN words and phrases in AC sections

These are rejected by `_tools/verify_ac_map.py`. The canonical list is `BANNED_PATTERNS` at the top of that script -- read it there if you need the exact regexes. For human reference:

- "deferred", "defer", "future story", "later story"
- "next pass", "next cycle", "next PR"
- "TODO", "FIXME", "will be done", "to be implemented"
- "punted", "placeholder", "pending", "not implemented", "not yet", "postponed"

If the verifier rejects your map, fix the gap (write the missing wiring) -- don't reword to dodge the check. Tester re-runs the verifier as Gate B, so a lie costs you a cycle.

## Verification

```bash
python {SAGE_TOOLS_DIR}/verify_ac_map.py STORY-N --stories-dir _output/{feature_name}/stories
```

`success: true` -> map is acceptable. `success: false` -> the JSON output names the missing/banned AC; fix and re-run.
