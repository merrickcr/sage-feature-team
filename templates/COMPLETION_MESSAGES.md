# Completion Messages

Shared completion-message templates for every role. Each role file references this template instead of inlining its variants. When you (an agent) are ready to send your completion message, Read this file, locate your role's section, pick the variant matching your outcome, and send it.

## Conventions (apply to every variant)

- One `SendMessage(to="User", ...)` per task. No retransmissions, no SYN/ACK, no message IDs.
- Opener: `@User: [Feature: <feature_name>] ...`
- Footer: `--- STATUS: <DONE|FAILED|BLOCKED> | READY: <yes|no> | BLOCKER: <none|category>`
- The orchestrator routes on the YAML state, not on your message body -- but the orchestrator also relays specific failure details (test output, `verify_ac_map.py` JSON) to the next worker, so include them verbatim when present.
- Do NOT mix narration into the completion message. Use your own transcript for narration; the completion message is structured handoff only.

---

## ProductOwner

### Spec Approved (sent only after explicit "APPROVED" from User)

```python
SendMessage(
  to="User",
  summary="Spec complete: {feature_name}",
  message=f"""@User: [Feature: {feature_name}] Specification and stories complete and approved.

Spec file:    _output/{feature_name}/spec.md
Epics dir:    _output/{feature_name}/epics/
Stories dir:  _output/{feature_name}/stories/

Status: User approval received
Feature overview: [Brief description]
Requirements: {count_requirements} defined
Edge Cases: {count_edge_cases} documented
Epics: {count_epics} YAML files written (all status: TODO)
Stories: {count_stories} YAML files written (all status: TODO)
Acceptance Criteria: {count_criteria} total, distributed across stories

--- STATUS: DONE | READY: yes | BLOCKER: none""")
```

---

## TestCreator

### Success

```python
SendMessage(
  to="User",
  summary="Tests complete: {feature_name}",
  message=f"""@User: [Feature: {feature_name}] Tests created.

Test file: <path where you created the file>
Test functions: <count and names>
Coverage: All acceptance criteria covered for target stories

Stories advanced to IN_DEV: <STORY-1, STORY-3, ...>
Stories left at TODO (deps not met): <STORY-N or "none">

--- STATUS: DONE | READY: yes | BLOCKER: none""")
```

### Blocked (no tagging convention defined, etc.)

Use the universal Blocked variant at the bottom of this file.

---

## Developer

### Success (story(ies) flipped to TESTING)

```python
SendMessage(
  to="User",
  summary="Developer: {feature_name} (STORY-N done)",
  message=f"""@User: [Feature: {feature_name}] Developer cycle complete.

Fixed tests:
- test_name_1
- test_name_2

Files changed:
- <path/to/file_1>
- <path/to/file_2>

Stories advanced to TESTING: <STORY-1, STORY-3, ...>

AC implementation map sidecars (one per story; verified by verify_ac_map.py):
- _output/{feature_name}/stories/STORY-1.implementation.md (AC1, AC2, AC3 -- all wired)
- _output/{feature_name}/stories/STORY-3.implementation.md (AC4, AC5 -- all wired)

Verifier output: all sidecars passed verify_ac_map.py

Changes summary: [Describe what was fixed and why]

--- STATUS: DONE | READY: yes | BLOCKER: none""")
```

**Do NOT send this until** every advanced story has an AC implementation map sidecar AND `verify_ac_map.py` returned success for it. If the verifier fails on any story, fix the gap (write the missing wiring) before flipping that story or sending the completion message.

### Cannot Proceed (Blocked)

Use the universal Blocked variant at the bottom of this file.

---

## Tester

### Tests Passed (one or more stories advanced to DONE)

```python
SendMessage(
  to="User",
  summary="Tests passed: {feature_name}",
  message=f"""@User: [Feature: {feature_name}] Tests passed.

Results: All {total_tests} tests passed in {elapsed_time} seconds.

{json.dumps({"test_results": {"passed": total_tests, "failed": 0, "failures": []}})}

Stories advanced to DONE: <STORY-1, STORY-3, ...>     # passed BOTH gates (tests + AC map)
Stories sent back to IN_DEV (AC map gate failed): <STORY-IDs or "none">
  For each: paste the verify_ac_map.py JSON verbatim so Developer knows exactly what to fix
Stories still at TESTING (not in this run's target set): <STORY-N or "none">

--- STATUS: DONE | READY: yes | BLOCKER: none""")
```

### Tests Failed (Gate A failure: test failure, build break, dex error)

```python
SendMessage(
  to="User",
  summary="Tests failed: {feature_name}",
  message=f"""@User: [Feature: {feature_name}] Tests failed.

Results: {passed_count} passed, {failed_count} failed in {elapsed_time} seconds.

{json.dumps({"test_results": {"passed": passed_count, "failed": failed_count, "failures": failures}})}

Stories advanced to DONE (passed BOTH gates: tests + AC map): <STORY-IDs or "none">
Stories sent back to IN_DEV (had failing tests): <STORY-IDs or "none">
Stories sent back to IN_DEV (AC map gate failed despite passing tests): <STORY-IDs or "none">
  For each: paste the verify_ac_map.py JSON verbatim so Developer knows exactly what to fix

--- STATUS: FAILED | READY: no | BLOCKER: none""")
```

### Blocked (infrastructure unrecoverable, tagging convention undefined)

Use the universal Blocked variant at the bottom of this file.

---

## EpicVerifier

### Verified (success)

```python
SendMessage(
  to="User",
  summary="Verified: {feature_name} EPIC-N",
  message=f"""@User: [Feature: {feature_name}] [EPIC-N] Verification passed.

Status: VERIFIED
Stories in scope: STORY-1, STORY-2, ...
Tests run: {total_tests} (all passed) in {elapsed_time}s
Selector: {selector}
Epic acceptance: {satisfied | n/a}

Artifact: _output/{feature_name}/verification/EPIC-N.md
Epic YAML: status flipped DONE -> VERIFIED

--- STATUS: DONE | READY: yes | BLOCKER: none""")
```

### Failed (cross-story regression or AC map regression -- stories re-opened)

```python
SendMessage(
  to="User",
  summary="Verification failed: {feature_name} EPIC-N",
  message=f"""@User: [Feature: {feature_name}] [EPIC-N] Verification FAILED -- stories re-opened.

Status: FAILED
Stories in scope: STORY-1, STORY-2, ...
Re-opened stories: STORY-N (cross_story_regression), STORY-M (ac_map_regression), ...
For each re-opened story: paste the failure details / verify_ac_map JSON verbatim so the Developer knows exactly what to fix.

Artifact: not written (verification incomplete)
Epic YAML: NOT flipped to VERIFIED (preconditions failed)

--- STATUS: FAILED | READY: no | BLOCKER: none""")
```

### Blocked (epic acceptance gap with no owning story, missing tagging convention)

Use the universal Blocked variant at the bottom of this file.

---

## Universal Blocked Variant (any role)

For Outcome 3 (truly unrecoverable -- requires user action). Substitute your role's specifics into the body; the shape is the same regardless of which role you are.

```python
SendMessage(
  to="User",
  summary=f"BLOCKED: {feature_name} <STORY-N or EPIC-N or task-id>",
  message=f"""@User: [Feature: {feature_name}] BLOCKED on <scope>.

STATUS: BLOCKED | BLOCKER: <category>

Why: <one paragraph>
What user must decide: <specific question>
Current state: <relevant files / config / output excerpt>
Recommended action: <if applicable>

--- STATUS: BLOCKED | READY: no | BLOCKER: <category>""")
```

Before sending Blocked: confirm you've flipped the relevant YAML (`update_story_status.py STORY-N BLOCKED --reason "..."` or `update_epic_status.py EPIC-N BLOCKED --reason "..."`). The orchestrator routes on YAML state, not the message body, but it expects them to match.
