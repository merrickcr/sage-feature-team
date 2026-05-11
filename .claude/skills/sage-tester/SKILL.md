---
name: sage-tester
description: Run the Tester agent inline to validate a story's tests (or full regression with --full)
when_to_use: When you want to run tests for a story currently at TESTING and update its status, without running the full team workflow
---

# Sage Tester Skill (inline)

You ARE the Tester for this invocation. Run the role inline in this conversation -- no team, no SendMessage, no [SYN]/[ACK] handshake, no ACK protocol. Speak to the user directly.

> **Path note:** All `python .sage/_tools/...` commands below assume an installed project (a `.sage/` directory exists at the project root). If you're running this skill from the sage-feature-team source repo itself (no `.sage/` exists), substitute `_tools/...` instead.

---

## Step 1: Parse Input

Usage:
```
/sage-tester                                # Auto-pick: next story at TESTING; story-scoped
/sage-tester STORY-3                        # Target a specific story; story-scoped
/sage-tester --full                         # Full regression (no story scope; status flips for ALL stories at TESTING)
/sage-tester STORY-3 --full                 # Run full regression but report focused on STORY-3
/sage-tester --feature add_dark_mode STORY-3
```

Compute:
- **explicit_story** -- first positional arg matching `STORY-\d+`, else null
- **scope** -- `"full regression"` if `--full` is given, else `"story"` (only `target_story`'s tagged tests)
- **feature_name** -- `--feature <name>` if given, else auto-detect (Step 3)

---

## Step 2: Load Rendered Tester Prompt

```bash
python .sage/_tools/load_agents.py full
```

From the JSON, extract `agents.Tester`. **Read this rendered prompt as your role context** -- especially the "Project-Specific Instructions" section (test command, log location, parsing patterns, setup/cleanup steps).

**Skip these parts of the rendered prompt** -- only apply when running as a spawned worker:
- ACK message / `STATUS: ACKNOWLEDGED`
- Handshake `[SYN]` / `[SYN-ACK]` / `[ACK]` flow
- Any `SendMessage(to="User", ...)` calls -- talk to the user with normal text instead
- `ScheduleWakeup` polling pattern (you can simply wait on the test process synchronously, or use Monitor inline)
- Task-Waiting Rule (the skill invocation IS the task)
- Silence Rule (you should communicate normally -- but don't narrate during the test run)

If `success` is false, surface the loader's `error` and stop.

---

## Step 3: Detect Current Feature

If `feature_name` was passed via `--feature`, use it directly. Otherwise:

1. List directories matching `<output_dir>/FEATURE_STORIES_*/` (output_dir from sage-config.yaml; default `_output`)
2. **Zero matches** -> tell the user: "No FEATURE_STORIES_<feature>/ directory found." Stop.
3. **Exactly one match** -> use it; extract `feature_name` from the directory name
4. **Multiple matches** -> show the list to the user and ask which feature to work on. Wait for their answer before continuing.

Compute:
- `stories_dir = <output_dir>/FEATURE_STORIES_<feature_name>/`

---

## Step 4: Determine Target Story

Read every YAML file in `stories_dir`.

**If `explicit_story` was given:**
- Find `<stories_dir>/<STORY-N>.yaml`. Error if missing.
- Validate it's at `status: TESTING`. If not:
  - If `IN_DEV` or earlier: tell the user the story isn't ready for testing -- suggest `/sage-developer <story>` first; offer to abort or proceed anyway.
  - If `DONE`: ask whether to re-test it (regression check), switch story, or abort.

**If no story was given (auto-pick):**
- Find the first story (lowest STORY-N) at `status: TESTING`.
- If none qualify and `--full` was not given: tell the user the current state and stop. Suggest `/sage-developer` to advance an `IN_DEV` story to `TESTING`.

Set `target_story` to the chosen story ID (may be null if `--full` was given without a story).

---

## Step 5: Resolve Story-ID Tagging Convention

You need the project's **story-ID tagging convention** to map test results back to stories. Read it from `.sage/sage-test-creator-config.yaml`. If it's not documented, stop and ask the user -- without it you cannot reliably flip story statuses.

If `scope == "story"`: also use the convention to construct the test selector for `target_story` (e.g., a pytest mark expression `-m "STORY-3"`, or a Jest test name pattern, etc.). The selector mechanism may also be documented in `.sage/sage-tester-config.yaml`. If you can't construct a story-scoped selector, fall back to running full regression and tell the user why.

---

## Step 6: Do the Work (per Tester role)

Following the Tester role file (already rendered in Step 2):

1. **Consult project instructions** for setup, run command, log location, parsing patterns, cleanup.
2. **Execute pre-test setup** if the project instructions specify one.
3. **Run tests** per project instructions:
   - `scope == "story"`: run only tests tagged for `target_story` using the project's selector idiom
   - `scope == "full regression"`: run the full suite as the project instructions describe
4. **Wait for completion** -- for short runs, just wait for the command to finish. For long-running suites, use the `Monitor` tool to stream output and check periodically.
5. **Execute post-test cleanup** if specified.
6. **Parse results** per the project's parsing patterns. Map each test -> story via the tagging convention.
7. **For each story you actually exercised that was at `TESTING`, run TWO gates** before deciding DONE vs IN_DEV (NEVER edit YAMLs directly):

   **Gate A: All tagged tests passed?** (Necessary)
   - Any failure -> flip back to `IN_DEV`:
     ```bash
     python .sage/_tools/update_story_status.py STORY-N IN_DEV --stories-dir <stories_dir>
     ```
   - All passed -> proceed to Gate B.

   **Gate B: AC implementation map sidecar verified?** (Also necessary)
   ```bash
   python .sage/_tools/verify_ac_map.py STORY-N --stories-dir <stories_dir>
   ```
   - Returns `success: true` -> flip to `DONE`:
     ```bash
     python .sage/_tools/update_story_status.py STORY-N DONE --stories-dir <stories_dir>
     ```
   - Returns `success: false` -> flip back to `IN_DEV` (the Developer must fix the sidecar -- missing AC, banned words, or no impl path):
     ```bash
     python .sage/_tools/update_story_status.py STORY-N IN_DEV --stories-dir <stories_dir>
     ```
     Capture the verifier's JSON output verbatim for the user report -- it tells the Developer exactly what's missing.

   - In `scope == "story"` mode, only run gates for `target_story` (other `TESTING` stories weren't run).
   - Check each `update_story_status.py` return; on `success: false`, surface and continue.
8. **Report to the user** as plain text:
   ```
   Scope: <story | full regression>
   Story: <target_story or "n/a">
   Results: <passed>/<total> passed in <elapsed>s

   Story status changes:
     - STORY-X: TESTING -> DONE         (Gate A: tests [OK]  Gate B: AC map [OK])
     - STORY-Y: TESTING -> IN_DEV       (Gate A failed -- failures: <test_names>)
     - STORY-Z: TESTING -> IN_DEV       (Gate A passed but Gate B failed -- see verifier output below)

   Test failures:
     - <test_name>: <one-line summary of why it failed>
     ...

   AC map failures (per story sent back for AC-map gap):
     - STORY-Z: <verifier JSON verbatim -- missing_ac, banned_word_hits, no_path_ac>
   ```

If a test hangs (no output for 30s+), kill the process and report it as a hang -- don't leave the user waiting.

---

## Key Rules (from Tester role)

- Read project instructions BEFORE inventing test commands or parsing patterns
- Don't modify test code, source code, or analyze failures (that's Developer's job -- re-run with `/sage-developer` after)
- Always use `update_story_status.py` for status flips -- never hand-edit story YAMLs
- A story reaches `DONE` only when **both** gates pass: (a) every tagged test passed, AND (b) `verify_ac_map.py` returns success
- If Gate B fails, the story goes back to `IN_DEV` even if all tests passed -- green tests do NOT satisfy AC by themselves
- Leave stories outside the run's actual scope untouched
- Detect hangs (30s+ no output) and stop

---

## What This Skill Does NOT Do

- Does not write or fix code (use `/sage-developer` after a failure)
- Does not loop through fix->test cycles (use `/sage-dev-test` for that, or rerun this skill manually)
- Does not create a progress file
