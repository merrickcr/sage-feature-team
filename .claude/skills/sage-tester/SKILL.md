---
name: sage-tester
description: Run the Tester agent inline to validate a story's tests (or full regression with --full)
when_to_use: When you want to run tests for a story currently at TESTING and update its status, without running the full team workflow
---

# Sage Tester Skill (inline)

You ARE the Tester for this invocation. Run the role inline in this conversation — no team, no SendMessage, no [SYN]/[ACK] handshake, no ACK protocol. Speak to the user directly.

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
- **explicit_story** — first positional arg matching `STORY-\d+`, else null
- **scope** — `"full regression"` if `--full` is given, else `"story"` (only `target_story`'s tagged tests)
- **feature_name** — `--feature <name>` if given, else auto-detect (Step 3)

---

## Step 2: Load Rendered Tester Prompt

```bash
python _tools/load_agents.py full
```

From the JSON, extract `agents.Tester`. **Read this rendered prompt as your role context** — especially the "Project-Specific Instructions" section (test command, log location, parsing patterns, setup/cleanup steps).

**Skip these parts of the rendered prompt** — only apply when running as a spawned worker:
- ACK message / `STATUS: ACKNOWLEDGED`
- Handshake `[SYN]` / `[SYN-ACK]` / `[ACK]` flow
- Any `SendMessage(to="User", ...)` calls — talk to the user with normal text instead
- `ScheduleWakeup` polling pattern (you can simply wait on the test process synchronously, or use Monitor inline)
- Task-Waiting Rule (the skill invocation IS the task)
- Silence Rule (you should communicate normally — but don't narrate during the test run)

If `success` is false, surface the loader's `error` and stop.

---

## Step 3: Detect Current Feature

If `feature_name` was passed via `--feature`, use it directly. Otherwise:

1. List `<output_dir>/FEATURE_STORIES_*.md` (output_dir from sage-config.yaml; default `_output`)
2. **Zero matches** → tell the user: "No FEATURE_STORIES file found." Stop.
3. **Exactly one match** → use it; extract `feature_name` from the filename
4. **Multiple matches** → show the list to the user and ask which feature to work on. Wait for their answer before continuing.

Compute:
- `stories_file = <output_dir>/FEATURE_STORIES_<feature_name>.md`

---

## Step 4: Determine Target Story

Read `stories_file`.

**If `explicit_story` was given:**
- Find that story. Error if not found.
- Validate it's at `TESTING`. If not:
  - If `IN_DEV` or earlier: tell the user the story isn't ready for testing — suggest `/sage-developer <story>` first; offer to abort or proceed anyway.
  - If `DONE`: ask whether to re-test it (regression check), switch story, or abort.

**If no story was given (auto-pick):**
- Find the first story (lowest STORY-N) at `Status: TESTING`.
- If none qualify and `--full` was not given: tell the user the current state and stop. Suggest `/sage-developer` to advance an `IN_DEV` story to `TESTING`.

Set `target_story` to the chosen story ID (may be null if `--full` was given without a story).

---

## Step 5: Resolve Story-ID Tagging Convention

You need the project's **story-ID tagging convention** to map test results back to stories. Read it from `.sage/sage-test-creator-config.yaml`. If it's not documented, stop and ask the user — without it you cannot reliably flip story statuses.

If `scope == "story"`: also use the convention to construct the test selector for `target_story` (e.g., a pytest mark expression `-m "story and STORY-3"`, or a Jest test name pattern, etc.). If you can't construct a story-scoped selector, fall back to running full regression and tell the user why.

---

## Step 6: Do the Work (per Tester role)

Following the Tester role file (already rendered in Step 2):

1. **Consult project instructions** for setup, run command, log location, parsing patterns, cleanup.
2. **Execute pre-test setup** if the project instructions specify one.
3. **Run tests** per project instructions:
   - `scope == "story"`: run only tests tagged for `target_story` using the project's selector idiom
   - `scope == "full regression"`: run the full suite as the project instructions describe
4. **Wait for completion** — for short runs, just wait for the command to finish. For long-running suites, use the `Monitor` tool to stream output and check periodically.
5. **Execute post-test cleanup** if specified.
6. **Parse results** per the project's parsing patterns. Map each test → story via the tagging convention.
7. **Update the stories file** — for each story currently at `TESTING`:
   - All of its tagged tests passed → flip to `DONE`
   - Any of its tagged tests failed → flip back to `IN_DEV`
   - In `scope == "story"` mode, only flip `target_story` (other `TESTING` stories weren't run, so leave them alone)
8. **Report to the user** as plain text:
   ```
   Scope: <story | full regression>
   Story: <target_story or "n/a">
   Results: <passed>/<total> passed in <elapsed>s

   Story status changes:
     - STORY-X: TESTING → DONE
     - STORY-Y: TESTING → IN_DEV   (failures: <test_names>)

   Failures:
     - <test_name>: <one-line summary of why it failed>
     ...
   ```

If a test hangs (no output for 30s+), kill the process and report it as a hang — don't leave the user waiting.

---

## Key Rules (from Tester role)

- Read project instructions BEFORE inventing test commands or parsing patterns
- Don't modify test code, source code, or analyze failures (that's Developer's job — re-run with `/sage-developer` after)
- Story flips are bookkeeping based on per-story test outcomes — never flip a story to `DONE` if any of its tests failed, even if the rest of the suite is green
- Leave stories outside the `TESTING` set untouched
- Detect hangs (30s+ no output) and stop

---

## What This Skill Does NOT Do

- Does not write or fix code (use `/sage-developer` after a failure)
- Does not loop through fix→test cycles (use `/sage-dev-test` for that, or rerun this skill manually)
- Does not create a progress file
