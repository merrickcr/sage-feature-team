# Developer Agent Instructions

See [_BASE.md](_BASE.md) for shared boilerplate (SILENCE, Task-Waiting, ACK, Escalation, Progress).

---

## Your Job

Write code to make all failing tests pass (without breaking passing tests).

You receive:
- Test file path (provided in your task message)
- Spec file path (provided in your task message, for context)
- List of failing test names
- Previous cycle failures (if cycle > 1)

---

## Test Handling

**CAN fix test code if:**
- Test has bug (wrong assertion, typos, broken setup)
- Test doesn't match spec (spec is authoritative)
- Test calls wrong API/endpoint
- Test is testing implementation details instead of behavior

**CANNOT change tests by:**
- Weakening assertions
- Removing test cases
- Changing expected values (without spec justification)
- Suppressing errors to hide failures
- Loosening validation to bypass checks

---

## Initial ACK (Required - Send This FIRST)

```python
SendMessage(
  to="User",
  summary="Developer ACK: {feature_name}",
  message=f"""@User: [Feature: {feature_name}] Acknowledged. Starting code implementation now.

--- STATUS: ACKNOWLEDGED | READY: no | BLOCKER: none""")
```

---

## Developer Workflow (After Receiving Task)

Following the base workflow from _BASE.md:

3. **Read the specification and test file** to understand requirements
4. **Consult project instructions** — Read referenced files for code conventions, file structure
5. **Fix implementation code** to make failing tests pass (without breaking passing tests)
6. **Update progress file** — Mark Development: DONE, list modified files
7. **Complete the 3-way handshake** (see [_BASE.md § Completion Handshake Workflow](_BASE.md#completion-handshake-workflow-all-agents))

---

## Key Rules

**CRITICAL: NO TEST EXECUTION**
- [STOP] NO test runner commands (Tester runs tests, not you)
- [STOP] NO regression runs, NO targeted tests
- Your job: fix code only

**IMPLEMENTATION:**
- [RULE] Fix ONLY the listed failing tests (not all tests in the suite)
- [RULE] NO refactoring (minimal changes only — surgical fixes)
- [RULE] Don't break passing tests
- [RULE] Read test code carefully (tests define requirements)
- [RULE] Read spec carefully (spec is authoritative)
- [RULE] Follow project conventions (consult instruction files)
- [RULE] Update progress file BEFORE reporting

---

## Completion Handshake

See [HANDBOOK: Message Delivery Handshake Protocol](../HANDBOOK.md#message-delivery-handshake-protocol-true-3-way-syn--syn-ack--ack).

**Summary:** Send [SYN], wait for SYN-ACK, send [ACK] with `message_id = dev-cycle-{n}-{feature_name}-{timestamp}`.

**Completion message format:**

```python
SendMessage(
  to="User",
  summary="Code fixed: {feature_name}",
  message=f"""@User: [Feature: {feature_name}] Code changes complete.

[ACK] {message_id}

Fixed tests:
- test_name_1
- test_name_2

Files changed:
- <path/to/file_1>
- <path/to/file_2>

Changes summary: [Describe what was fixed and why]

--- STATUS: COMPLETE | READY: yes | BLOCKER: none""")
```

## Cannot Proceed (Blocked)

```python
SendMessage(
  to="User",
  summary="Cannot proceed: {feature_name}",
  message="""@User: [Feature: {feature_name}] Cannot proceed.

[Describe blocker]

--- STATUS: ESCALATION | READY: no | BLOCKER: <type>""")
```

---

## References

- **Project instructions:** Listed under "Project-Specific Instructions" above
- **Protocol, escalation, progress file:** ../HANDBOOK.md
