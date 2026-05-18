# TODO: Phase 3 -- Richer Per-Item Status

**Status:** not started -- deferred until 1-2 real features have run through the Phase 1/2 flow so we can see which fields actually matter in practice.

**Prerequisites:** Phase 1 (epic layer) and Phase 2 (EpicVerifier checkpoint) are complete and merged.

---

## Goal

Add scheduling- and observability-friendly fields to story and epic YAMLs so the orchestrator can make smarter decisions and post-mortems are easier to write. None of this adds new capability -- it's quality-of-life on top of the existing state machine.

The story/epic YAMLs stay the source of truth. No new tools required, only field additions and a few orchestrator behaviors that read them.

---

## Proposed fields (in rough value order -- implement top-down, stop when ROI drops)

### 1. `priority: P0 | P1 | P2` -- on stories and epics

**Why:** When `max_parallel_workers` is saturated, the scheduler currently sorts eligible stories by ID. Priority lets the PO mark "do this first" without renumbering.

**How to apply:**
- Default: `P1` if omitted (do NOT require the field)
- `list_eligible.py` returns its lists unchanged; the orchestrator sorts each role's eligible list by `(priority, story_id)` before slicing to `available_slots`
- Epic priority influences which epic's stories drain first when multiple epics have eligible work (sort across all roles by `(epic.priority, story.priority, story_id)`)

**Files:**
- `agents/product-owner.md` § Story Format, § Epic Format -- document optional field
- `.claude/skills/sage-feature-team/SKILL.md` § 6b -- after `list_eligible.py`, sort each bucket by priority before taking `min(slots, len(eligible))`

---

### 2. `cycle_history: [...]` -- on stories

**Why:** When the orchestrator forwards Tester's failure details to the next Developer cycle, that context lives only in the worker message. If we want to debug "why did STORY-3 take 5 cycles?" later, we have to read worker transcripts. Persisting it on the YAML makes the story file self-explanatory.

**Shape:**
```yaml
cycle_history:
  - cycle: 1
    role: Tester
    outcome: gate_a_failed
    summary: "3 tests failed in WorkoutScreenTest"
    timestamp: 2026-05-17T14:22:00Z
  - cycle: 2
    role: Tester
    outcome: gate_b_failed
    summary: "verify_ac_map.py: AC2 has no impl path"
    timestamp: 2026-05-17T14:48:00Z
```

**How to apply:**
- Tester appends an entry whenever it flips a story back to IN_DEV
- EpicVerifier appends an entry when it re-opens a story
- Developer reads the latest entry to know what to fix (orchestrator stops needing to paste failure details into the task message verbatim -- the story's own history has it)
- `verify_ac_map.py` does NOT touch this (sidecar markdown still holds the implementation map)

**Files:**
- `_tools/update_story_status.py` -- accept an optional `--cycle-entry '<json>'` arg that appends to `cycle_history` atomically alongside the status flip
- `agents/tester.md`, `agents/epic-verifier.md` -- pass the entry when flipping to IN_DEV
- `agents/developer.md` -- on receiving a task message for cycle >1, read the story's last cycle_history entry as the source of failure context

**Tradeoff:** YAML files grow over the lifetime of a slow story. Cap at last N entries (e.g., N=10) and drop oldest.

---

### 3. `risk: low | medium | high` -- on stories and epics

**Why:** Today `max_cycles` is a single config knob. A risky story (touches DB schema, depends on a flaky third-party API) might legitimately need more retries than a UI tweak.

**How to apply:**
- Default: `medium`
- Effective max_cycles per story = `config.max_cycles * {low: 0.5, medium: 1.0, high: 2.0}` (rounded up, min 1)
- Same for epics: `verify_cycle_count[EPIC-N]` budget scales by epic risk

**Files:**
- `agents/product-owner.md` -- document field + guidance for when to mark high (touches shared state, integrates with external system, refactors load-bearing code)
- `.claude/skills/sage-feature-team/SKILL.md` § 6e -- compute effective cap when checking `cycle_count > max_cycles`

---

### 4. `tags: [...]` -- on stories and epics

**Why:** Lets the orchestrator (or `/sage-dev-test`) filter to a subset on resume or partial runs. E.g., `--resume add_dark_mode --tag critical` only runs work on tagged items.

**How to apply:**
- Free-form list of strings; PO picks the vocabulary
- `list_eligible.py` accepts `--tag <name>` and filters eligible buckets to stories with that tag (or stories in an epic with that tag)
- `sage-feature-team` skill accepts `--tag <name>` and forwards to `list_eligible.py` calls

**Files:**
- `_tools/list_eligible.py` -- add `--tag` filter
- `.claude/skills/sage-feature-team/SKILL.md` § 1 -- parse `--tag` from invocation; pass to every `list_eligible.py` call

---

### 5. `blocked_reason` REQUIRED when `status: BLOCKED` (already supported; tighten enforcement)

**Why:** `update_story_status.py` allows BLOCKED without a reason today (the field gets written only if `--reason` is passed). That makes for empty BLOCKED entries when an agent flips status without arguments.

**How to apply:**
- `update_story_status.py`: reject `BLOCKED` without `--reason` (existing exit code 1 path)
- Same for `update_epic_status.py`

**Files:**
- `_tools/update_story_status.py`, `_tools/update_epic_status.py` -- add precondition check

**Tradeoff:** Tightens the contract; existing callers that omit reason will start failing. Audit agent files to confirm all BLOCKED flips already pass a reason (they should, per agent role docs).

---

## What NOT to add (yet)

- `assignee` / `owner` -- the orchestrator already owns assignment; this would be premature
- `effort_estimate` / `points` -- no consumer; without a downstream use, it's just data drift
- `linked_pr` -- useful but belongs to git/CI integration, not the story YAML
- `created_at` / `updated_at` -- git history already has this; YAML mtime is good enough
- `priority` on AC (sub-story granularity) -- AC are story-internal; if you need AC-level priority, that's a sign the story is too big

---

## Suggested implementation order

If/when you tackle this:

1. **#1 (priority)** -- smallest change, biggest immediate scheduler win for capacity-bound runs
2. **#5 (require blocked_reason)** -- one-line check per tool, hardens the contract
3. **#2 (cycle_history)** -- biggest single quality-of-life win; replaces "paste failure details into next message" with "Developer reads the YAML"
4. **#3 (risk-scaled max_cycles)** -- only worth it if you've seen real cycle budget exhaustion patterns
5. **#4 (tags)** -- only worth it if you've found yourself wanting to run partial workflows

Stop after whichever of these stops returning value. The system already works without any of them.

---

## Decision criteria before starting

Before opening this TODO, ask:

1. Have you actually run 1-2 real features through the Phase 1/2 flow? If no, **wait** -- the field set above is informed guesses.
2. Of those runs, which moments did you wish the orchestrator behaved differently? Map that wish to a field above (or recognize it doesn't match any -- which means the field set is wrong, not that you should ignore the pain).
3. Is the pain frequent enough to justify the schema change? Once-per-feature pain rarely justifies it; once-per-story pain usually does.
