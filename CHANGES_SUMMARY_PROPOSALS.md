# Sage Feature Team -- v2 Hardening Proposals

**Audience:** maintainers planning the next iteration of the framework after the May 2026 changes captured in `CHANGE_SUMMARY.md`.

**Scope:** the top 3 issues to fix before a v2 cut, focused on efficiency, token optimization, and operational hardening. Drawn from a read of `CHANGE_SUMMARY.md`, `.claude/skills/sage-feature-team/SKILL.md`, `agents/_BASE.md`, `agents/developer.md`, `agents/tester.md`, `agents/epic-verifier.md`, `_tools/list_eligible.py`, and `_tools/verify_epic.py`.

---

## Revision note (post-implementation, empirical data)

The original Issue #1 below was rewritten after a partial implementation pass surfaced real token-usage data. The original framing (uncached prompt cost across spawns) was wrong:

- Anthropic prompt cache **does** hit across subagent spawns of the same role within a session. It saturates after the first cold spawn and accounts for ~91% of input billing.
- The dominant cost item is `cache_create` (~46% of total cost). This is the price of every new turn extending the cached prefix; the delta is billed at the highest input rate.
- `cache_read` (~38%) is amortized cheaply across many turns.
- Trimming the static role prompt (the original Fix A) saves ~0.5% of a feature run. Worker pools (the original Fix B/C) would save another ~$5-15 on a $500 run. Both real, both marginal.

**The actual cost lever is per-worker conversation length x number of workers.** Issue #1 has been rewritten to target that. Issues #2 and #3 are unchanged -- they weren't challenged by the data.

---

## 1. Conversation length per worker is the dominant cost driver -- and the recent NARRATION rule made it worse

**Where:** `agents/_BASE.md` § NARRATION RULE (replaced SILENCE per `CHANGE_SUMMARY.md` #4); `agents/developer.md` § "Explain Your Code Changes" (added per `CHANGE_SUMMARY.md` #4); every worker re-reads spec/story/test/instruction files on spawn (Developer step 3, Tester step 3, EpicVerifier step 3).

**Why it matters:**

- Empirical run data: 912 Developer messages across 27 workers (~34 turns each). Each turn extends the cached prefix; the delta is billed at `cache_create` rates. `cache_create` is ~46% of total billing -- the single largest line item -- and it scales directly with turns per worker.
- The NARRATION rule (added recently) materially grows this: "Explain every non-trivial code change (What / Why / Where)" and "narrate the hypothesis -> evidence -> fix loop" produce useful transcripts but each narration is an output turn that extends the conversation and the next turn's `cache_create` delta. There's a cost-vs-readability tradeoff that wasn't quantified when NARRATION was added.
- Worker spawns also pay a `cache_create` per-spawn for the per-worker variable content (~7-12k tokens) -- which is what a worker pool would amortize, but the pool savings are ~$5-15 per run, not transformative.
- The other turn drivers are also fixable in cheaper ways than restructuring the spawn model:
  1. Number of tool calls per task (each tool call = a turn pair)
  2. NARRATION verbosity
  3. Number of dev<->test cycles (each cycle is a full new conversation)
  4. Re-exploration on failure (agent re-reads files it already read)

**Fix for v2 (in priority order):**

- **Scope NARRATION to key moments, not every change.** Rewrite the `_BASE.md` NARRATION rule and `developer.md` "Explain Your Code Changes" section to require narration only at: (a) plan announcement before multi-file work, (b) the hypothesis->evidence->fix moment when a test fails, (c) the final summary before flipping to TESTING. Drop the "explain every non-trivial Edit" expectation -- the diff is already visible to the user. Expect ~20-40% reduction in Developer turn count without losing the debugging-loop transparency that motivated the rule.
- **Batch tool calls aggressively.** Audit each role file for places where the workflow reads N files sequentially (Developer step 3 reads spec + story YAML + test file; Tester step 3 reads all story YAMLs). Replace with explicit "issue these Read calls in parallel" guidance. Each parallel batch collapses N turn pairs into 1.
- **Pre-stuff the task message with file contents the worker is guaranteed to need.** The orchestrator already knows the story YAML, the spec excerpt, and the AC list. Inlining them into the task SendMessage (instead of forcing each worker to Read them) eliminates 2-4 tool-call turns per spawn. Modest hit to task-message size; net win because the task message is one cache_create event vs. multiple turn extensions.
- **Reduce average dev<->test cycle count via upstream quality** -- this is the lever with the largest theoretical headroom but also the hardest to operationalize. Each saved cycle removes ~34 turns of Developer + ~10-15 turns of Tester. Concrete sub-fixes: make TestCreator output the AC->test-name map directly so Developer doesn't have to re-derive it; require TestCreator to write at least one test per AC even when seam-limited, so the Developer's first cycle has a higher chance of being complete.
- **Worker pools remain a backstop, not a priority.** The original proposal estimated outsized savings; empirical data caps the upside at ~$5-15 per run. Defer unless other levers are exhausted, since the architectural risk (cross-task state leakage, harder shutdown semantics) is real.

---

## 2. Orchestrator scheduler state is in-memory only; `--resume` silently loses cycle accounting

**Where:** `.claude/skills/sage-feature-team/SKILL.md` Step 6a explicitly says state lives "in your own working memory (no need to write to disk)" -- `cycle_count`, `verify_cycle_count`, `escalated`, `spawned_workers`. The only on-disk state is the per-story YAML (status + optional `blocked_reason`).

**Why it matters:**

- If the orchestrator main conversation is interrupted, killed, or context-compacted mid-feature, `--resume` rebuilds eligibility from `list_eligible.py` (YAML-only) but has no record of: how many cycles a story has already burned, whether `EPIC-2` already exhausted its verify budget, which stories were escalated and should NOT be re-scheduled, or which workers in the team panel are stragglers from the previous session.
- Two concrete failure modes that follow:
  1. A story that hit `max_cycles` before the interrupt re-enters the loop on resume and gets *another* `max_cycles` budget -- silently doubling cost.
  2. An epic whose verifier failed twice can reset to zero verify_cycles and loop indefinitely.
- The pre-epic backward-compat gap flagged in `CHANGE_SUMMARY.md` § "Backward compatibility" is a symptom of the same root issue: state lives in directory-structure conventions instead of an explicit state record.
- `TODO_PHASE_3.md` apparently captures richer per-item fields (`cycle_history`) but defers them. That deferral is the bug.

**Fix for v2:**

- Persist a single `_output/<feature>/scheduler_state.json` after every transition (cycle_count, verify_cycle_count, escalated set, last seen worker names, feature_start_time). Write-after-every-event with `FileLock` reusing the same pattern as `update_story_status.py`. Idempotent reads on resume.
- Promote Phase 3's `cycle_history` field on each YAML out of the TODO -- at minimum store `cycles_used` and `last_failure_reason` so YAML alone is sufficient for resume even without the side-state file.
- Make resume reconcile the live team membership against persisted `spawned_workers` and shut down stragglers before re-entering Step 6.

---

## 3. AC-map verification + EpicVerifier checkpoint produce a triple-verification stack that's mostly duplicate work

**Where:** Developer runs `verify_ac_map.py` before flipping to TESTING (`agents/developer.md` step 8); Tester runs it again as Gate B before flipping to DONE (`agents/tester.md` step 12); EpicVerifier runs it *again* for every story via `verify_epic.py` (`agents/epic-verifier.md` step 4). On top of that, the EpicVerifier re-runs the epic-scoped regression that per-story Testers already ran individually for each constituent story.

**Why it matters:**

- For a 4-story single-epic feature (the documented default), happy path = 4 Developer verify + 4 Tester verify + 4 EpicVerifier verify + epic-scoped regression that overlaps the union of the 4 per-story regressions = ~12 `verify_ac_map.py` invocations and a redundant test pass.
- `CHANGE_SUMMARY.md` § "Suggested Review Focus" #4 actually flags this concern ("a feature that PO decides only needs one epic still pays a small cost... should the verifier auto-skip when an epic has no acceptance block AND only one story?") but no skip path was implemented.
- Cross-story regressions are real, but for the dominant case (one epic, no `acceptance:` block) the EpicVerifier is provably catching nothing the Testers didn't already catch -- except in projects where per-story Tester scopes hide cross-test interference, which the project should solve at the test-isolation level, not by re-running the whole suite a third time.

**Fix for v2:**

- Auto-skip EpicVerifier when ALL of: single epic, no `acceptance:` block, and every constituent story's Tester ran since the last edit of any file touched by another story in the epic (compute via mtime + the AC map's file paths). Flip the epic directly to `VERIFIED` with a trivial artifact noting "auto-verified, no cross-story scope."
- Skip Developer's pre-flight `verify_ac_map.py` call. Make Tester's Gate B the single source of truth. Right now Developer runs it as a self-check, then Tester runs the same check immediately -- pure duplication. If Developer's call was meant as an honest pre-commit gate, the fact that Tester re-runs it makes Developer's call advisory at best.
- When EpicVerifier *does* run, have it consume the per-story Tester results from the YAML or `tokens.json`-adjacent run record instead of re-executing them. Only re-execute when an AC map's listed source paths have been edited since the Tester's last run for that story -- a cheap mtime/hash check.

---

## Honorable mention (not in the top 3 but worth flagging)

The 30s starting-message nudge (`CHANGE_SUMMARY.md` #5) is correct as defensive coding but it's a band-aid over an unacked SendMessage protocol. A v2 should either:

- **(a)** add a real per-message ack the orchestrator can poll, or
- **(b)** drop the dual-channel "starting message AND completion message" handshake entirely and reconcile purely off YAML status writes -- which the orchestrator is already documented to trust over message bodies.

Either path eliminates the empirical spawn race instead of papering over it.
