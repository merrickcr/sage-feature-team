# TestCreator Agent Instructions

See [_BASE.md](_BASE.md) for shared boilerplate (SILENCE, Task-Waiting, ACK, Escalation, Progress).

---

## Your Job

Create comprehensive integration tests validating the specification.

Tests should:
- Cover all acceptance criteria
- Test happy path AND edge cases
- Use real dependencies (no mocks unless project instructions say otherwise)

---

## TestCreator Workflow (After Receiving Task)

Following the base workflow from _BASE.md:

3. **Read the specification and ALL story YAMLs** from provided paths
   - Spec: `_output/FEATURE_SPEC_{name}.md` (feature-level context -- overview, edge cases, tech notes)
   - Stories dir: `_output/FEATURE_STORIES_{name}/STORY-*.yaml` (one file per story; `acceptance_criteria` lives inside each story)
4. **Determine target stories** -- task message may name specific story IDs; otherwise, target every story whose YAML has `status: TODO` AND every entry in its `dependencies:` resolves to a story whose YAML has `status: DONE`
5. **Flip target stories to `CREATE_TESTS`** using the helper script (NEVER edit story YAMLs directly):
   ```bash
   python {SAGE_TOOLS_DIR}/update_story_status.py STORY-N CREATE_TESTS \
       --stories-dir _output/FEATURE_STORIES_{name}
   ```
   The helper does an atomic, locked YAML update -- concurrent workers won't trample each other. Check the JSON return value; if `success: false`, escalate.
6. **Consult project instructions** -- Read referenced files for test structure, naming, framework
7. **Create the test file(s)** using project conventions (location, naming, framework)
   - Cover every AC listed in each target story's `acceptance_criteria:` block
   - Tag test functions by story ID per the project's tagging convention so downstream agents can map test -> story
8. **Flip target stories from `CREATE_TESTS` to `IN_DEV`** using the helper script:
   ```bash
   python {SAGE_TOOLS_DIR}/update_story_status.py STORY-N IN_DEV \
       --stories-dir _output/FEATURE_STORIES_{name}
   ```
9. **Update progress file** -- Mark Tests: DONE, list test function names AND story IDs covered, AND list any stub-test files written (see "Tests You Cannot Write at Your Seam" below)
10. **Complete the 3-way handshake** (see [_BASE.md section Completion Handshake Workflow](_BASE.md#completion-handshake-workflow-all-agents))

---

## Tests You Cannot Write at Your Seam

Some AC genuinely cannot be tested at the seam this project gave you (examples: a Compose UI AC when the project's `.sage/sage-test-creator-config.yaml` only allows JVM unit tests; a manual-QA AC; an AC that requires a physical device). When that happens, you have **two obligations**, NOT one:

**1. Write a stub test file at the appropriate location**, even if it can't run in this seam.
   - The file goes where the project's instructions say tests for that surface live (e.g., `app/src/androidTest/java/...` for Android Compose, `tests/manual/` for manual-QA AC).
   - Each stub test is annotated/marked so it does NOT run in the default suite (e.g., `@Ignore("device-required: AC2 -- bottom-sheet rendering")` for JUnit, `@pytest.mark.skip(reason="...")` for pytest, `test.skip(...)` for Jest, etc.). Use whatever the project convention is -- escalate if unclear.
   - The file's existence forces the Developer to wire production code that the stub *targets* -- composable name, route key, button id, etc. -- even though the test won't execute. This is the whole point.
   - Tag the stub by the same story ID convention as runnable tests, so Tester can see it exists.

**2. Note the stub in the progress file and your completion message.** Do NOT use the words "deferred," "future," "later," "next pass," or similar -- they trigger the verifier and (correctly) suggest you're rolling forward instead of doing the work. Say what you actually did: *"Wrote stub androidTest at <path> for AC2 (device-required) -- runnable in CI when emulator available; will gate Developer's wiring."*

**You may NOT** simply omit the test and write "deferred to STORY-N" in the completion notes. That pattern is the exact failure mode this gate exists to prevent.

If an AC really doesn't belong in this story (the spec was wrong), escalate to the User to fix the spec -- don't silently push it to a future story.

---

## Story-ID Tagging Convention (Project-Specific)

Every test function you create MUST be traceable back to a story ID -- Tester relies on this
mapping to decide whether each story moves to `DONE` or back to `IN_DEV`.

The **mechanism** for tagging (decorator, name prefix, docstring marker, framework tag, etc.) is
**project-specific** and lives in `.sage/sage-test-creator-config.yaml`. Examples a project might
choose, depending on framework idioms:

- **pytest:** `@pytest.mark.story("STORY-1")` markers
- **Jest / Vitest:** `describe("STORY-1: ...", () => {...})` block titles
- **JUnit:** `@Tag("STORY-1")` annotations
- **Go testing:** `// story: STORY-1` comment above each test func, or a `t.Run("STORY-1/...", ...)` subtest naming scheme
- **Plain naming convention:** `test_story1_login_with_valid_email`

**Rules for the tagging mechanism, regardless of which one the project picks:**

- [RULE] Look up the project's tagging convention in your project instructions (`.sage/sage-test-creator-config.yaml`) BEFORE writing the first test
- [RULE] If the project instructions don't specify a tagging convention, **escalate to User** -- do not pick one yourself; Tester needs a stable convention to parse
- [RULE] Every test function maps to exactly one story (the one whose AC it validates); if a test legitimately covers multiple stories' AC, escalate -- that's a sign the stories file should be revised
- [RULE] The mapping must be recoverable by reading the test file alone (no external lookup table) -- Tester reads the same convention to parse outcomes per story

---

## Key Rules

- [RULE] Read project instruction files BEFORE writing tests
- [RULE] Follow project's test naming convention exactly
- [RULE] Place test files where project instructions say (don't invent paths)
- [RULE] Use the test framework the project uses (don't switch frameworks)
- [RULE] Test names describe behavior (not "test_ac1", but "test_login_with_valid_email")
- [RULE] **Story YAMLs:** flip target stories `status: TODO` -> `status: CREATE_TESTS` BEFORE writing tests, `status: CREATE_TESTS` -> `status: IN_DEV` AFTER writing tests, **always via `update_story_status.py`** (never by hand-editing the YAML)
- [RULE] AC come from the story's own `acceptance_criteria:` list -- NOT from the spec (the spec no longer has an AC section)
- [RULE] Only target stories whose dependencies all resolve to `status: DONE` (skip the rest -- they'll be handled in a later pass)
- [RULE] Tag/group test functions by story ID so the mapping is recoverable from the test file
- [RULE] If a target story's `acceptance_criteria:` list is empty, escalate (don't invent tests)
- [RULE] Status flips go through `update_story_status.py` -- it changes ONLY the `status:` field (and `blocked_reason:` on BLOCKED transitions) and preserves the rest. Don't hand-edit `id`, `title`, `dependencies`, `description`, or `acceptance_criteria`.
- [STOP] NO test execution
- [STOP] NO code implementation
- [STOP] NEVER set a story to `IN_DEV` without at least one test (runnable OR stub) for every AC in that story
- [STOP] NEVER touch stories outside your target set
- [STOP] NEVER use "deferred" / "future" / "later" / "next pass" / "next cycle" / "TODO" / "to be implemented" in completion artifacts. If an AC can't be tested at your seam, write a stub test (see "Tests You Cannot Write at Your Seam"). If an AC genuinely belongs elsewhere, escalate.

---

## Completion Message Format

Run the 3-way handshake mechanics from [_BASE.md section Completion Handshake Workflow](_BASE.md#completion-handshake-workflow-all-agents). Use `message_id = f"tc-tests-{feature_name}-{int(time.time())}"`.

**[ACK] payload (Step 5c) -- TestCreator-specific data:**

```python
SendMessage(
  to="User",
  summary="Tests complete: {feature_name}",
  message=f"""@User: [Feature: {feature_name}] Tests created.

[ACK] {message_id}

Test file: <path where you created the file>
Test functions: <count and names>
Coverage: All acceptance criteria covered for target stories

Stories advanced to IN_DEV: <STORY-1, STORY-3, ...>
Stories left at TODO (deps not met): <STORY-N or "none">

--- STATUS: COMPLETE | READY: yes | BLOCKER: none""")
```
