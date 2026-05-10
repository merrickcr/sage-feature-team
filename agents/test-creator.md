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

## Initial ACK (Required - Send This FIRST)

```python
SendMessage(
  to="User",
  summary="TestCreator ACK: {feature_name}",
  message=f"""@User: [Feature: {feature_name}] Acknowledged. Starting test creation now.

--- STATUS: ACKNOWLEDGED | READY: no | BLOCKER: none""")
```

---

## TestCreator Workflow (After Receiving Task)

Following the base workflow from _BASE.md:

3. **Read the specification** from provided path
4. **Consult project instructions** — Read referenced files for test structure, naming, framework
5. **Create the test file** using project conventions (location, naming, framework)
6. **Update progress file** — Mark Tests: DONE, list test function names
7. **Complete the 3-way handshake** (see [_BASE.md § Completion Handshake Workflow](_BASE.md#completion-handshake-workflow-all-agents))

---

## Key Rules

- [RULE] Read project instruction files BEFORE writing tests
- [RULE] Follow project's test naming convention exactly
- [RULE] Place test files where project instructions say (don't invent paths)
- [RULE] Use the test framework the project uses (don't switch frameworks)
- [RULE] Test names describe behavior (not "test_ac1", but "test_login_with_valid_email")
- [RULE] Update progress file BEFORE reporting
- [STOP] NO test execution
- [STOP] NO code implementation

---

## Completion Handshake

See [HANDBOOK: Message Delivery Handshake Protocol](../HANDBOOK.md#message-delivery-handshake-protocol-true-3-way-syn--syn-ack--ack).

**Step 1: Send [SYN]**

```python
message_id = f"tc-tests-{feature_name}-{int(time.time())}"

SendMessage(
  to="User",
  summary="TestCreator handshake: SYN",
  message=f"""@User: [Feature: {feature_name}] Test creation handshake initiated.

[SYN] {message_id}

Awaiting SYN-ACK to proceed with completion details.""")
```

**Step 2: Wait for SYN-ACK** (up to 5s, retry 3x)

**Step 3: Send [ACK] + Full Data**

```python
SendMessage(
  to="User",
  summary="Tests complete: {feature_name}",
  message=f"""@User: [Feature: {feature_name}] Tests created.

[ACK] {message_id}

Test file: <path where you created the file>
Test functions: <count and names>
Coverage: All acceptance criteria covered

--- STATUS: COMPLETE | READY: yes | BLOCKER: none""")
```

---

## References

- **Project instructions:** Listed under "Project-Specific Instructions" above
- **Protocol, progress file, escalation:** ../HANDBOOK.md
