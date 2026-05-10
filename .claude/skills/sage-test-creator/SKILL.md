---
name: sage-test-creator
description: Run the TestCreator agent inline to write tests for the next ready story (or a specific story)
when_to_use: When you want to create tests for a story that has been spec'd but not yet implemented, without running the full team workflow
---

# Sage TestCreator Skill (inline)

You ARE the TestCreator for this invocation. Run the role inline in this conversation — no team, no SendMessage, no [SYN]/[ACK] handshake, no ACK protocol. Speak to the user directly.

---

## Step 1: Parse Input

Usage:
```
/sage-test-creator                    # Auto-pick: next story at TODO with deps DONE
/sage-test-creator STORY-3            # Target a specific story
/sage-test-creator --feature add_dark_mode STORY-3
```

Compute:
- **explicit_story** — first positional arg matching `STORY-\d+`, else null
- **feature_name** — `--feature <name>` if given, else auto-detect (Step 3)

---

## Step 2: Load Rendered TestCreator Prompt

```bash
python _tools/load_agents.py full
```

(Or `python .sage/_tools/load_agents.py full` from inside an installed project.)

From the JSON, extract `agents.TestCreator`. **Read this rendered prompt as your role context** — especially the "Project-Specific Instructions" section (test framework, file location, naming convention, story-ID tagging convention).

**Skip these parts of the rendered prompt** — only apply when running as a spawned worker:
- ACK message / `STATUS: ACKNOWLEDGED`
- Handshake `[SYN]` / `[SYN-ACK]` / `[ACK]` flow
- Any `SendMessage(to="User", ...)` calls — talk to the user with normal text instead
- Task-Waiting Rule (the skill invocation IS the task)
- Silence Rule (you should communicate normally)

If `success` is false, surface the loader's `error` and stop.

---

## Step 3: Detect Current Feature

If `feature_name` was passed via `--feature`, use it directly. Otherwise:

1. List directories matching `<output_dir>/FEATURE_STORIES_*/` (output_dir from sage-config.yaml; default `_output`)
2. **Zero matches** → tell the user: "No FEATURE_STORIES_<feature>/ directory found in <output_dir>. Run /sage-po first to create a spec and stories." Stop.
3. **Exactly one match** → use it; extract `feature_name` from the directory name
4. **Multiple matches** → show the list to the user and ask which feature to work on. Wait for their answer before continuing.

Compute:
- `stories_dir = <output_dir>/FEATURE_STORIES_<feature_name>/`
- `spec_file   = <output_dir>/FEATURE_SPEC_<feature_name>.md`

---

## Step 4: Determine Target Story

Read every YAML file in `stories_dir` (and `spec_file` for feature-level context).

**If `explicit_story` was given:**
- Find `<stories_dir>/<STORY-N>.yaml`. Error if missing.
- Validate it's at `status: TODO` and its `dependencies:` all resolve to stories with `status: DONE`. If not:
  - If status is already past `TODO`: tell the user and ask whether to proceed anyway (use `--force` on the helper if so), pick a different story, or abort.
  - If a dep is not `DONE`: tell the user the unmet deps and ask whether to proceed anyway, switch story, or abort.

**If no story was given (auto-pick):**
- Find the first story (lowest STORY-N) where: `status: TODO` AND every entry in `dependencies:` resolves to a story with `status: DONE` (`[]` counts as satisfied).
- If none qualify: tell the user the current state (which stories are blocked on what) and stop.

Set `target_story` to the chosen story ID.

---

## Step 5: Do the Work (per TestCreator role)

Following the TestCreator role file (already rendered in Step 2):

1. **Read project instructions** for test framework, file location, naming, and **story-ID tagging convention**. If the project instructions don't specify a tagging convention, ask the user before proceeding (don't pick one yourself — Tester needs to use the same one).
2. **Read `target_story`'s YAML** to get its `acceptance_criteria:` block (the contract for the tests you write).
3. **Flip `target_story` to `CREATE_TESTS`** via the helper script:
   ```bash
   python .sage/_tools/update_story_status.py STORY-N CREATE_TESTS --stories-dir <stories_dir>
   ```
   (Use `_tools/update_story_status.py` if running from the sage-feature-team source itself.)
   Check the JSON return; on `success: false`, stop and report.
4. **Write the test file(s)** for `target_story`'s AC, using the project's framework, location, naming, and tagging convention. Tag/group test functions by `target_story`'s ID so the mapping is recoverable from the test file alone.
5. **Flip `target_story` from `CREATE_TESTS` to `IN_DEV`** via the helper script:
   ```bash
   python .sage/_tools/update_story_status.py STORY-N IN_DEV --stories-dir <stories_dir>
   ```
6. **Report to the user** as plain text:
   ```
   Story: <target_story> → IN_DEV
   AC covered: AC1, AC2, ...
   Tests written: <count>
   Test file(s):
     - <path>
   Test functions:
     - <name1>
     - <name2>
     ...
   ```

---

## Key Rules (from TestCreator role)

- Read project instruction files BEFORE writing tests
- Follow project's test naming and location conventions exactly
- Use the project's test framework — don't switch
- Test names describe behavior, not AC numbers
- Always use `update_story_status.py` for status flips — never hand-edit story YAMLs
- Tag/group every test by story ID using the project convention
- If the target story's `acceptance_criteria:` is empty, stop and ask the user
- NO test execution, NO code implementation
- NEVER set a story to `IN_DEV` without an actual test for it
- NEVER touch stories outside the target

---

## What This Skill Does NOT Do

- Does not run Developer or Tester (use `/sage-developer` and `/sage-tester` next)
- Does not loop through multiple ready stories — handles exactly one per invocation
- Does not create a progress file
