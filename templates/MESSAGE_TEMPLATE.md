# Unified Message Template (Simple)

**One template for all messages. Fixes work rejection, cycle summary, ready signal, and message sequencing.**

---

## Basic Structure

```
@User: [Feature: {name}] {subject}

[Task: {id}] [Cycle: {n}/{m}]

{message content}

--- STATUS: {status} | READY: {yes/no} | BLOCKER: {none/reason}
```

---

## Three Key Fields

| Field | Values | Purpose |
|-------|--------|---------|
| **STATUS** | `ACKNOWLEDGED`, `COMPLETE`, `ESCALATION` | What state the agent is in |
| **READY** | `yes` or `no` | Is the agent idle and ready for next task? |
| **BLOCKER** | `none` or brief reason (e.g., `MISSING_SCHEMA`, `BLOCKED_BY_APPROVAL`) | Any external blocker |

**STATUS Values:**
- `ACKNOWLEDGED` -- Received task, starting work (transient, lasts seconds)
- `COMPLETE` -- Work is done, results in progress file, ready for routing
- `ESCALATION` -- Blocked by question, ambiguity, or external dependency (see BLOCKER reason)

---

## Examples

### Skill -> Developer: Task Assignment with Cycle Summary
```
@User: [Feature: auth_system] Fix failing tests. (Cycle 2/5)

[Task: dev-2-uuid] [Cycle: 2/5]

Failing tests from Cycle 1:
- test_login: Expected 200, got 401
- test_register: Expected 201, got 500

Spec: _output/FEATURE_SPEC_auth_system.md
Test file: tests/test_auth_system.py

--- STATUS: TASK_ASSIGNED | READY: N/A | BLOCKER: none
```

### Agent -> Skill: Acknowledgment
```
@User: [Feature: auth_system] Acknowledged. Starting now.

[Task: dev-2-uuid]

--- STATUS: ACKNOWLEDGED | READY: no | BLOCKER: none
```

### Agent -> Skill: Work Complete
```
@User: [Feature: auth_system] Code complete.

[Task: dev-2-uuid]

Fixed:
- test_login (changed hash algorithm back to bcrypt)
- test_register (fixed validation logic)

Files: sage/auth/login.py, sage/auth/validators.py

--- STATUS: COMPLETE | READY: yes | BLOCKER: none
```

### Agent -> Skill: Escalation (Blocked by External Dependency)
```
@User: [Feature: auth_system] Cannot proceed.

[Task: dev-2-uuid]

Need database schema definition for user_sessions table before I can implement. 
Test expects (id, user_id, created_at, expires_at) but schema.py doesn't define it.

--- STATUS: ESCALATION | READY: no | BLOCKER: MISSING_SCHEMA
```

---

## When to Use Each Field

| Field | Always? | Usage |
|-------|---------|-------|
| `@User:` | YES | Every message |
| `[Feature: X]` | YES | Every message |
| `{subject}` | YES | One-line summary |
| `[Task: id]` | Only for task assignments and responses | Links response back to task (sequencing) |
| `[Cycle: n/m]` | Only in dev/test cycles | Which cycle is this |
| `STATUS` | YES | End of every message |
| `READY` | YES | End of every message |
| `BLOCKER` | YES | End of every message (say "none" if no blocker) |

---

## Parsing (For Agents & Skill)

**Extract from message:**
```python
# Feature name
feature = msg.match(r"\[Feature: ([^\]]+)\]").group(1)

# Task ID (optional)
task_id = msg.match(r"\[Task: ([^\]]+)\]").group(1) if found else None

# Status (end of message)
status = msg.match(r"STATUS: (\w+)").group(1)
ready = msg.match(r"READY: (\w+)").group(1)
blocker = msg.match(r"BLOCKER: ([^\|]+)").group(1).strip()
```

---

## Why This Works

| Problem | Solution |
|---------|----------|
| **Work Rejection** | `STATUS: CANNOT_PROCEED` + `BLOCKER: reason` says "I'm blocked" (not ambiguous like escalation) |
| **Cycle Summary** | Skill includes previous results in task assignment message |
| **Ready Signal** | `READY: yes` + `STATUS: READY_FOR_NEXT_TASK` confirms completion & safety |
| **Message Sequencing** | `[Task: id]` tags every task assignment; agent echoes it in response |

---

## Validation Checklist

Before sending any message:
- [ ] `@User:` prefix present
- [ ] `[Feature: name]` present and correct
- [ ] `[Task: id]` present (if responding to a task)
- [ ] STATUS field is valid: `ACKNOWLEDGED`, `COMPLETE`, or `ESCALATION`
- [ ] READY field is `yes` or `no`
- [ ] BLOCKER field is `none` or a brief reason (e.g., `MISSING_SCHEMA`, `BLOCKED_BY_APPROVAL`)
- [ ] First line has subject (one sentence summary)

---

**Last Updated:** 2026-05-02
