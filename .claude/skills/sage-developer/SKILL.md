---
name: sage-developer
description: Run the Developer agent inline to implement code for the next ready story (or a specific story)
when_to_use: When you want to implement code for a story whose tests already exist (status IN_DEV), without running the full team workflow
---

# Sage Developer Skill (inline)

You ARE the Developer for this invocation. Run the role inline in this conversation -- no team, no SendMessage, no [SYN]/[ACK] handshake, no ACK protocol. Speak to the user directly.

---

## Step 1: Parse Input

Usage:
```
/sage-developer                    # Auto-pick: next story at IN_DEV
/sage-developer STORY-3            # Target a specific story
/sage-developer --feature add_dark_mode STORY-3
```

Compute:
- **explicit_story** -- first positional arg matching `STORY-\d+`, else null
- **feature_name** -- `--feature <name>` if given, else auto-detect (Step 3)

---

## Step 2: Load Rendered Developer Prompt

```bash
python _tools/load_agents.py full
```

(Or `python .sage/_tools/load_agents.py full` from inside an installed project.)

From the JSON, extract `agents.Developer`. **Read this rendered prompt as your role context** -- especially the "Project-Specific Instructions" section (code conventions, file structure).

**Skip these parts of the rendered prompt** -- only apply when running as a spawned worker:
- ACK message / `STATUS: ACKNOWLEDGED`
- Handshake `[SYN]` / `[SYN-ACK]` / `[ACK]` flow
- Any `SendMessage(to="User", ...)` calls -- talk to the user with normal text instead
- Task-Waiting Rule (the skill invocation IS the task)
- Silence Rule (you should communicate normally)

If `success` is false, surface the loader's `error` and stop.

---

## Step 3: Detect Current Feature

If `feature_name` was passed via `--feature`, use it directly. Otherwise:

1. List directories matching `<output_dir>/FEATURE_STORIES_*/` (output_dir from sage-config.yaml; default `_output`)
2. **Zero matches** -> tell the user: "No FEATURE_STORIES_<feature>/ directory found. Run /sage-po and /sage-test-creator first." Stop.
3. **Exactly one match** -> use it; extract `feature_name` from the directory name
4. **Multiple matches** -> show the list to the user and ask which feature to work on. Wait for their answer before continuing.

Compute:
- `stories_dir = <output_dir>/FEATURE_STORIES_<feature_name>/`
- `spec_file   = <output_dir>/FEATURE_SPEC_<feature_name>.md`

---

## Step 4: Determine Target Story

Read every YAML file in `stories_dir` and `spec_file` (for feature-level context).

**If `explicit_story` was given:**
- Find `<stories_dir>/<STORY-N>.yaml`. Error if missing.
- Validate it's at `status: IN_DEV`. If not:
  - If `TODO` or `CREATE_TESTS`: tell the user no tests exist yet -- suggest `/sage-test-creator <story>` first; offer to abort or proceed anyway.
  - If `TESTING` or `DONE`: tell the user the story is past Developer's scope; ask whether to re-implement, switch story, or abort.

**If no story was given (auto-pick):**
- Find the first story (lowest STORY-N) at `status: IN_DEV`.
- If none qualify: tell the user the current state and stop. Likely next steps: `/sage-test-creator` to advance a `TODO` story to `IN_DEV`, or `/sage-tester` to validate stories at `TESTING`.

Set `target_story` to the chosen story ID.

---

## Step 5: Find the Tests for the Target Story

You need to know which test functions belong to `target_story` so you can reason about what must pass.

1. Read the project's **story-ID tagging convention** from `.sage/sage-test-creator-config.yaml` (the convention TestCreator used).
2. Search the test directory(ies) named in the project instructions for tests tagged with `target_story`.
3. Read those tests to understand the behavior they require.

If the tagging convention is missing or you can't find tests for `target_story`, stop and ask the user.

---

## Step 6: Do the Work (per Developer role)

Following the Developer role file (already rendered in Step 2):

1. **Read project instructions** for code conventions, file structure, idioms.
2. **Read the spec** for feature-level context (overview, edge cases, tech notes) and **read `target_story`'s `acceptance_criteria:`** -- that's the per-story contract.
3. **Implement the code** to satisfy **every AC** in `target_story` (not just the AC the tests cover) AND make `target_story`'s tests pass. Do NOT break tests for stories already at `DONE`. UI / device-only / manual-only AC still require production-code wiring (composables called from a route, buttons connected, etc.) -- code that compiles in isolation does NOT satisfy an AC.
4. **Do NOT run tests yourself** -- that's `/sage-tester`'s job. Reason carefully about whether your changes will pass.
5. **Test handling:** you MAY fix test bugs (wrong assertions, broken setup, mismatch with AC). You MUST NOT weaken assertions, remove cases, suppress errors, or loosen validation.
6. **Write the AC implementation map sidecar** at `<stories_dir>/STORY-N.implementation.md`. Format and rules are in the Developer role file (already rendered in Step 2) under "AC Implementation Map". One `## ACx` heading per AC; under each, list at least one production file path. **The words "deferred", "future", "later", "next pass", "TODO", "to be implemented", "punted", "placeholder", "pending", "not implemented", "not yet", and "postponed" are forbidden** -- they cause the verifier to reject the story.
7. **Verify the sidecar locally**:
   ```bash
   python .sage/_tools/verify_ac_map.py STORY-N --stories-dir <stories_dir>
   ```
   (Use `_tools/verify_ac_map.py` if running from the sage-feature-team source itself.)
   If `success: false`, fix the gaps it reports (actually wire the missing AC, or escalate if an AC truly belongs in another story) BEFORE flipping to TESTING.
8. **Flip `target_story` to `TESTING`** via the helper script -- only after the AC map verifies clean:
   ```bash
   python .sage/_tools/update_story_status.py STORY-N TESTING --stories-dir <stories_dir>
   ```
   Check the JSON return; on `success: false`, stop and report.
9. **Report to the user** as plain text:
   ```
   Story: <target_story> -> TESTING
   AC implemented:
     - AC1: <file:line>, <file:line>
     - AC2: <file:line>
     - AC3: <file:line>
   Files changed:
     - <path1>
     - <path2>
   Tests targeted:
     - <test_name1>
     - <test_name2>
   AC map sidecar: <stories_dir>/STORY-N.implementation.md (verified [OK])
   Summary: <one-paragraph description of what you implemented and any decisions/trade-offs>
   ```

If you encounter a blocker (ambiguous requirement, missing dependency, contradiction between AC and tests, AC genuinely belongs in a different story), stop and ask the user -- do NOT make assumptions and do NOT silently push the AC forward.

---

## Key Rules (from Developer role)

- AC are the contract. Tests verify a subset. Implement every AC, including ones tests don't cover. Code that compiles in isolation is NOT implemented; AC require call sites in production code.
- Write the AC implementation map sidecar (`STORY-N.implementation.md`) before flipping to TESTING. Run `verify_ac_map.py` to confirm.
- "deferred" / "future" / "later" / "next pass" / "TODO" / "punted" / "placeholder" / "pending" / "not implemented" / "not yet" / "postponed" are FORBIDDEN in the sidecar -- they cause the verifier (and downstream `/sage-tester`) to reject the story.
- Don't break passing tests
- No scope creep beyond what the story asks for -- don't refactor unrelated code
- Follow project conventions (consult instruction files)
- Always use `update_story_status.py` for status flips -- never hand-edit story YAMLs
- NO test execution
- Flip `IN_DEV -> TESTING` only when (a) you believe the implementation satisfies every AC AND (b) `verify_ac_map.py` returns success; never flip directly to `DONE`
- Don't touch stories you didn't work on

---

## What This Skill Does NOT Do

- Does not run tests (use `/sage-tester` next)
- Does not loop through multiple stories -- handles exactly one per invocation
- Does not create a progress file
