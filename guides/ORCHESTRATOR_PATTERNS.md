# Orchestrator Patterns (Reusable)

**Shared patterns used by both `/sage-feature-team` and `/sage-dev-test` skills.**

These patterns can be referenced by any skill that spawns and coordinates agents. Extract them here to avoid duplication across skill definitions.

---

## Pattern 1: Graduated Timeout (ACK Monitoring)

**Used by:** Both skills for all agent acknowledgments

**Purpose:** Ensure agent received task before proceeding

**Timeline:**
- **T=0-30s:** Normal response time (expected)
- **T=30s:** Send gentle check if no ACK
- **T=45s:** Send reminder if still no ACK
- **T=60s:** ESCALATE if no ACK

**Values from config:**
- `timeout_ack_initial: 30`
- `timeout_ack_remind: 45`
- `timeout_ack_escalate: 60`

**Implementation:**
```python
# Pseudocode
send_task_to_agent(agent_name, task_message)

# Wait for ACK with graduated timeout
if no_ack_after(30s):
    send_gentle_check()
if no_ack_after(45s):
    send_reminder()
if no_ack_after(60s):
    escalate("Agent ACK Timeout")
else:
    continue_to_next_step()
```

---

## Pattern 2: Work Completion Monitoring

**Used by:** Both skills for all agent work completion

**Purpose:** Ensure agent finished work before proceeding to next agent

**Timeouts:**
- **5 minutes (soft):** Send gentle status check
- **8 minutes (hard):** ESCALATE if still no completion report

**Values from config:**
- `timeout_work_hard: 480` (8 minutes)

**Implementation:**
```python
# After ACK received
start_work_timer = now()

if no_completion_after(5min):
    send_status_check()
    
if no_completion_after(8min):
    escalate("Agent Work Timeout")
else:
    read_progress_file()
    proceed_to_next_step()
```

---

## Pattern 3: Dev/Tester Cycle Loop

**Used by:** Both skills for test/fix cycles

**Purpose:** Iterate until tests pass or max cycles reached

**Algorithm:**
```
cycle_count = 1
max_cycles = [from config] (default: 5)

WHILE cycle_count <= max_cycles:
  
  [1] Route to Developer:
      Send failing test names
      Wait for ACK (Pattern 1: graduated timeout)
      Wait for completion (Pattern 2: work completion)
      Read progress file: verify Development = DONE
  
  [2] Route to Tester:
      Send test command
      Wait for ACK (Pattern 1: graduated timeout)
      Wait for completion (Pattern 2: work completion)
      Read progress file: check Testing result
  
  [3] Check result:
      IF Testing = PASSED:
        -> SUCCESS, break loop
      
      ELSE IF Testing = FAILED and cycle_count < max_cycles:
        -> Extract failing test names from progress file
        -> Extract failure details using TEST_FAILURE format
        -> cycle_count += 1
        -> LOOP (go to [1] with new cycle count)
      
      ELSE IF cycle_count == max_cycles AND Testing = FAILED:
        -> ESCALATE WITH "Max cycles exceeded"
        -> Do NOT increment cycle_count or continue loop
        -> break loop

END WHILE

Return: SUCCESS or ESCALATION
```

**Key Rules:**
- Max cycles definition: "Allow up to N full Developer->Tester rounds"
- Example: max_cycles=5 means Cycle 1, 2, 3, 4, 5 allowed (no Cycle 6)
- Hard stop: After Cycle N FAILED and cycle_count == max_cycles, escalate immediately

---

## Pattern 4: SendMessage Format Standard

**Used by:** Both skills for all agent communications

**Format:**
```python
SendMessage(
  to="AgentName",
  summary="[Feature: feature_name] Brief action description",
  message="""@User: [Feature: feature_name] Detailed instructions.

[Task: task-id-feature-name]

Context:
[Relevant files, background information]

Job: [What agent should do]

Reference: HANDBOOK.md""")
```

**Key Elements:**
- `to`: Agent name (e.g., "Developer", "Tester")
- `summary`: One-line action (under 70 characters)
- `message`: Multiline with @User prefix, task ID, context, job, reference
- Feature context: Always include `[Feature: feature_name]` for tracing
- Reference: Point to HANDBOOK.md or guides for protocol details

---

## Pattern 5: Timeout & Escalation Handling

**Used by:** Both skills when timeouts occur

### ACK Timeout (Agent doesn't acknowledge within 60 seconds)

```python
SendMessage(
  to="User",
  summary="Feature workflow blocked: ACK timeout",
  message="""[Feature: {feature_name}] ESCALATION: Agent ACK Timeout

Agent: [which agent]
Time: Waited 60+ seconds for ACK
Phase: [which phase]
Evidence: No @User: Acknowledged message received

The agent may be hung or unresponsive. Manual intervention required.

Recommended action: Check agent logs, restart workflow or manually complete the phase.""")
```

### Work Timeout (Agent doesn't report completion within 8 minutes)

```python
SendMessage(
  to="User",
  summary="Feature workflow blocked: Work timeout",
  message="""[Feature: {feature_name}] ESCALATION: Work Timeout

Agent: [which agent]
Time: Waited 8 minutes for completion report
Phase: [which phase]
Last event: [ACK received at T=Xs ago]

The agent may be stuck or hung.

Recommended action: Check agent logs, restart workflow, or manually complete the phase.""")
```

### Cycle Limit Exceeded

```python
SendMessage(
  to="User",
  summary="Feature workflow blocked: Max cycles exceeded",
  message="""[Feature: {feature_name}] ESCALATION: Max Cycles Exceeded

Cycles completed: {cycle_count}/{max_cycles}
Phase: Development/Testing
Last failure: [List failed tests from progress file]

The developer was unable to fix the failing tests within max_cycles attempts.

Recommended action: Review test failures, adjust test requirements, or implement a different approach.""")
```

---

## Pattern 6: Final Reporting

**Used by:** Both skills when workflow completes

### Success (Full Mode)

```python
SendMessage(
  to="User",
  summary="Feature complete: {feature_name}",
  message="""[Feature: {feature_name}] Feature Development Complete

Status: SUCCESS
Mode: Full Workflow
Cycles used: {cycle_count}/{max_cycles}

Artifacts created:
- Specification: _output/FEATURE_SPEC_{feature_name}.md
- Tests: <test file path from TestCreator's report>
- Code changes: [See git diff for modified files]

All acceptance criteria tested and passing.""")
```

### Success (Dev-Test Mode)

```python
SendMessage(
  to="User",
  summary="Tests fixed: {feature_name}",
  message="""[Feature: {feature_name}] Test/Fix Cycle Complete

Status: SUCCESS
Mode: Dev-Test Only
Cycles used: {cycle_count}/{max_cycles}

Test Results:
- All tests passing
- Test file: <from Tester's report>

Code changes: [See git diff for modified files]""")
```

### Escalation

```python
SendMessage(
  to="User",
  summary="Feature workflow blocked: [Reason]",
  message="""[Feature: {feature_name}] Feature Development Blocked

Status: ESCALATION
Blocker: [ACK timeout | Work timeout | Max cycles exceeded | Test hang]

Details:
[Include specific error, test failures, or blocker description]

Next steps:
[Recommend what user should do to unblock]""")
```

---

## How Skills Use These Patterns

### /sage-feature-team Skill

1. **Mode:** full (or dev-test-only)
2. **Phase 1 (Full mode only):** ProductOwner
   - Uses Pattern 1 (Graduated Timeout) for ACK
   - Uses Pattern 2 (Work Completion) for spec creation
   - Uses Pattern 4 (SendMessage Format) for task
   - Uses Pattern 5 (Escalation) for timeouts

3. **Phase 2 (Full mode only):** TestCreator
   - Uses Pattern 1, 2, 4, 5 (same as ProductOwner)

4. **Dev/Test Cycle Loop:**
   - Uses Pattern 3 (Cycle Loop) for test/fix iterations
   - Uses Pattern 1, 2, 4, 5 for each cycle step
   - Uses Pattern 6 (Final Reporting) when complete

### /sage-dev-test Skill

1. **Mode:** dev-test-only (tests already exist, no spec/test creation)
2. **Skip Phases:** ProductOwner and TestCreator
3. **Dev/Test Cycle Loop:**
   - Uses Pattern 3 (Cycle Loop) directly (same algorithm)
   - Uses Pattern 1, 2, 4, 5 for each cycle step
   - Uses Pattern 6 (Final Reporting) when complete

### Pattern Reuse Summary

| Pattern | sage-feature-team | sage-dev-test | Notes |
|---------|-------------------|---------------|-------|
| 1: Graduated Timeout | [OK] (all agents) | [OK] (Dev+Tester) | Same algorithm |
| 2: Work Completion | [OK] (all phases) | [OK] (Dev+Tester) | Same algorithm |
| 3: Cycle Loop | [OK] (Dev/Tester) | [OK] (Dev/Tester) | Identical algorithm |
| 4: SendMessage Format | [OK] (all messages) | [OK] (all messages) | Identical format |
| 5: Escalation Handling | [OK] (timeouts) | [OK] (timeouts) | Identical templates |
| 6: Final Reporting | [OK] (completion) | [OK] (completion) | Mode-specific, same pattern |

**Result:** Both skills reference these shared patterns instead of duplicating them in SKILL.md.

---

## Configuration Values Used by Patterns

From `sage-config.yaml`:

```yaml
limits:
  max_cycles: 5                  # Pattern 3: Max dev/test cycles
  timeout_ack_initial: 30        # Pattern 1: Initial check
  timeout_ack_remind: 45         # Pattern 1: Reminder
  timeout_ack_escalate: 60       # Pattern 1: Hard escalation
  timeout_work_hard: 480         # Pattern 2: 8 minutes hard timeout
```

---

**Last Updated:** 2026-05-03  
**Status:** Ready for reference by both skills
