# Workflow Routing Decision Tree

**Quick reference for Skill/Team Lead routing decisions.**

---

## Full Workflow Mode

### Read Progress File First

Before routing, **always** read: `_output/FEATURE_[feature_name]_PROGRESS.md`

### Routing Decision Tree

```
START
  |
  +-- ProductOwner = PENDING?
  |    YES -> Route to ProductOwner
  |    NO  -> Continue
  |
  +-- Tests = PENDING AND ProductOwner = DONE?
  |    YES -> Route to TestCreator
  |    NO  -> Continue
  |
  +-- Development = PENDING AND Tests = DONE?
  |    YES -> Route to Developer
  |    NO  -> Continue
  |
  +-- Testing = PENDING AND Development = DONE?
  |    YES -> Route to Tester
  |    NO  -> Continue
  |
  +-- Testing = FAILED?
  |    YES -> Route to Developer (to fix)
  |    NO  -> Continue
  |
  +-- Testing = PASSED?
  |    YES -> Feature COMPLETE
  |    NO  -> ERROR - Unknown state
```

### Status Reference

**Phase 1: Specification**
- ProductOwner creates spec
- Status: PENDING -> IN_PROGRESS -> DONE

**Phase 2: Test Creation**
- TestCreator creates tests
- Status: PENDING -> IN_PROGRESS -> DONE

**Phase 3: Development**
- Developer implements code
- Status: PENDING -> IN_PROGRESS -> DONE

**Phase 4: Testing**
- Tester runs tests
- Status: PENDING -> IN_PROGRESS -> PASSED or FAILED

### Cycle Handling (Developer Fixes)

If Testing = FAILED:
1. Route to Developer
2. Developer fixes code
3. Mark Development: IN_PROGRESS, then DONE
4. Route back to Tester
5. Repeat until Testing = PASSED or max_cycles exceeded

**Max cycles:** 5 (configurable)

---

## Dev-Test Only Mode

### Simplified Routing (No Progress File)

```
START
  |
  +-- Run full tests
  |    |
  |    +-- All pass? -> SUCCESS
  |    |
  |    +-- Some fail? -> Continue
  |
  +-- Route to Developer: Fix [failing_tests]
  |    |
  |    +-- Changes made
  |
  +-- Run targeted tests (just the failing ones)
  |    |
  |    +-- All pass? -> Run full regression
  |    |              |
  |    |              +-- All pass? -> SUCCESS
  |    |              |
  |    |              +-- Some fail? -> Cycle again
  |    |
  |    +-- Some still fail? -> Cycle again
  |
  +-- Cycle limit exceeded? -> ESCALATION
```

### Cycle Tracking

```
CYCLE 1/5
├─ Run full tests -> Failures detected
├─ Route to Developer
├─ Run targeted tests -> Pass
├─ Run full regression -> Some failures
│
CYCLE 2/5
├─ Route to Developer
├─ Run targeted tests -> Pass
├─ Run full regression -> All pass!
│
SUCCESS - Complete
```

---

## Escalation Triggers

**Stop routing and escalate if:**
- [STOP] Agent ACK timeout (60s+)
- [STOP] Agent work report timeout (8min+)
- [STOP] Test hang (30+ sec no output)
- [STOP] Cycle limit exceeded (5)
- [STOP] Workflow time limit exceeded (30 min)
- [STOP] Feature name validation failure
- [STOP] Test name validation failure
- [STOP] Same test fails twice with no code change

**Escalation message format:**
```
@User: [Feature: name] ESCALATION

Problem: [Description]
Agent: [Which agent is stuck]
Evidence: [What we tried, what failed]
Recommendation: [What to do next]
```

---

## Reading Progress File

### Progress File Location
```
_output/FEATURE_[feature_name]_PROGRESS.md
```

### Example Structure
```
# Feature Progress: <feature_name>

## Phase 1: Specification
[x] Specification created
Spec file: _output/FEATURE_SPEC_<feature_name>.md
Completed: <date>

## Phase 2: Test Creation
[ ] Integration tests created
Test file: <path per project conventions, see TestCreator's .sage config>
Completed: [pending]

## Phase 3: Development
[ ] Feature implemented
Files modified: [pending]
Completed: [pending]

## Phase 4: Testing
[ ] All tests passing
Completed: [pending]
```

### Phase Status Interpretation
- [x] = DONE (completed, ready to move on)
- [ ] = PENDING (not started)
- [~] = IN_PROGRESS (currently being worked)

---

## Common Mistakes to Avoid

[STOP] Don't modify progress file yourself (agents update their own sections)  
[STOP] Don't skip reading progress file before routing  
[STOP] Don't assume agent report = completion (file is source of truth)  
[STOP] Don't route to multiple agents simultaneously  
[STOP] Don't make technical decisions (route questions to appropriate agent)  
[STOP] Don't bypass escalation triggers (5 cycle limit, 30 min time limit)  

---

**See Also:**
- ../HANDBOOK.md — Complete protocol details
- ../.claude/skills/sage-feature-team/SKILL.md — Skill/Team Lead role

---

**Last Updated:** 2026-04-30
