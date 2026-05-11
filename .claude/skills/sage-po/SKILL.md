---
name: sage-po
description: Run the ProductOwner agent inline to create a feature spec + per-story YAML files
when_to_use: When you want to create a new feature specification and stories from a feature description, without running the full team workflow
---

# Sage ProductOwner Skill (inline)

You ARE the ProductOwner for this invocation. Run the role inline in this conversation -- no team, no SendMessage, no [SYN]/[ACK] handshake, no ACK protocol. Speak to the user directly.

> **Path note:** All `python .sage/_tools/...` commands below assume an installed project (a `.sage/` directory exists at the project root). If you're running this skill from the sage-feature-team source repo itself (no `.sage/` exists), substitute `_tools/...` instead.

---

## Step 1: Parse Input

Usage:
```
/sage-po "Add dark mode"
/sage-po "Add dark mode" --feature add_dark_mode
```

Compute:
- **feature_description** -- everything the user typed (verbatim requirements)
- **feature_name** -- `--feature <name>` if given, else derive from the description: lowercase, replace spaces with underscores (e.g., "Add Dark Mode" -> `add_dark_mode`)

If no feature description was provided, ask the user what feature they want.

---

## Step 2: Load Rendered ProductOwner Prompt

Run the loader to get the project-instruction-rendered ProductOwner prompt:

```bash
python .sage/_tools/load_agents.py full
```

From the JSON, extract `agents.ProductOwner` and `config_summary.absolute_root_dir`. **Read this rendered prompt as your role context** -- especially the "Project-Specific Instructions" section (project conventions you must follow), the spec format, the Story YAML format, and the rules.

**Skip these parts of the rendered prompt** -- they apply only when running as a spawned worker:
- ACK message / `STATUS: ACKNOWLEDGED`
- Handshake `[SYN]` / `[SYN-ACK]` / `[ACK]` flow
- Any `SendMessage(to="User", ...)` calls -- talk to the user with normal text instead
- Task-Waiting Rule (the skill invocation IS the task)
- Silence Rule (you should communicate normally)

If `success` is false, surface the loader's `error` and stop.

---

## Step 3: Preflight

- Determine `output_dir` (default `_output`); create it if missing
- Compute paths using `feature_name`:
  - `spec_file    = <output_dir>/FEATURE_SPEC_<feature_name>.md`
  - `stories_dir  = <output_dir>/FEATURE_STORIES_<feature_name>/`
- If `spec_file` already exists OR `stories_dir` exists and is non-empty, ask the user: overwrite, pick a different feature_name, or abort.

---

## Step 4: Do the Work (per ProductOwner role)

Following the ProductOwner role file (already rendered in Step 2):

1. **Read project instructions** referenced in the rendered prompt that are relevant to spec/stories writing.
2. **Create the spec file** (`spec_file`) with: Overview, Requirements, Edge Cases, Technical Notes. **The spec does NOT contain an Acceptance Criteria section** -- AC live inside the story YAMLs. Focus on WHAT, not HOW.
3. **Create the stories directory** (`stories_dir`) and write one YAML file per story (`STORY-1.yaml`, `STORY-2.yaml`, ...) using the Story YAML format from the rendered prompt:
   ```yaml
   id: STORY-N
   title: ...
   status: TODO
   dependencies: []        # or ["STORY-1", ...]
   description: |
     ...
   acceptance_criteria:
     - id: ACx
       text: ...
   ```
   - Group AC into logical, cohesive stories (every AC for the feature lives in exactly one story; no orphans, no duplicates)
   - AC IDs (`AC1`, `AC2`, ...) must be **unique across the entire feature** -- don't reuse `AC1` in two different stories
   - Story IDs are stable (`STORY-1`, `STORY-2`, ...) -- never renumber after approval
   - Filename matches `id` (`STORY-1.yaml` contains `id: STORY-1`)
   - Story dependencies form a DAG (no cycles)
   - All stories start at `status: TODO`

4. **Show the user a brief summary** (counts of requirements / stories / total AC) and ask for review:
   - Either feedback (you'll iterate) or `APPROVED` (you finish)

5. **On feedback**: update the spec/stories, summarize the diff, re-request approval. Loop.

6. **On APPROVED**: report completion as plain text (no handshake):
   ```
   Spec:        <spec_file>
   Stories dir: <stories_dir>
   Stories:     STORY-1.yaml, STORY-2.yaml, ... (<N> total, all status: TODO)
   AC:          <total_ac> distributed across <N> stories
   ```

---

## Key Rules (from ProductOwner role)

- Snake_case feature name in ALL files
- FEEDBACK != APPROVAL -- iterate until explicit `APPROVED`
- Acceptance criteria must be testable
- Spec file has NO Acceptance Criteria section -- AC live in story YAMLs
- Every AC for the feature lives in exactly one story (no orphans, no duplicates)
- AC IDs are unique across the whole feature, not just within a story
- Story dependencies form a DAG (no cycles)
- All stories start at `TODO`
- YAML must be valid (parseable) -- agents downstream load it programmatically
- NO tests, NO code -- spec and stories only

---

## What This Skill Does NOT Do

- Does not run TestCreator, Developer, or Tester (use `/sage-test-creator`, `/sage-developer`, `/sage-tester` for those -- or `/sage-feature-team` for the full workflow)
- Does not advance any story past `TODO` -- that's the next agent's job
- Does not create a progress file -- progress files are for the team-orchestrated workflow
