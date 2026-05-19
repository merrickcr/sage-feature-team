# Sage Feature Team -- Recent Change Summary

**Scope:** changes landed in May 2026 (PR #2 merged 2026-05-17 plus follow-up commits on master).

**Audience:** independent reviewers (human or agent) who have not been part of the conversations that produced these changes. This document is self-contained -- read it cold and you can review the work without backtracking.

**What this document is NOT:** a tutorial or onboarding doc. For framework basics, read `README.md`, `HANDBOOK.md`, and `agents/_BASE.md`. This is a delta narrative.

---

## TL;DR

Two major capabilities and four operational refinements:

1. **Epic layer (required, default 1 per feature)** -- adds a verification scope between feature and story. Every feature has at least one epic; multi-epic split is opt-in.
2. **EpicVerifier checkpoint** -- a new agent role that runs after every story in an epic hits `DONE`, performs cross-story regression + AC-map re-verification + epic-level acceptance check, then flips the epic to `VERIFIED` (unlocking downstream epics) or re-opens specific stories with details.
3. **`--serial` CLI flag** on `/sage-feature-team` forces `max_parallel_workers=1` for debugging or test-isolation-sensitive projects.
4. **NARRATION rule** replaces the old SILENCE rule: agents narrate freely in their own transcript output; SendMessage discipline (exactly 2 per task) is preserved.
5. **Developer "Explain Your Code Changes"** -- explicit instruction for the Developer agent to describe non-trivial edits (What / Why / Where) in its transcript as it works.
6. **Starting-message nudge** -- the orchestrator now re-sends a worker's task at T=30s if no starting message arrived, before escalating to BLOCKED at T=60s. Fixes a measured-in-practice spawn race.
7. **Task-list disambiguation** -- `_BASE.md` clarifies that shared task list entries are informational, not assignment channels (an early run had a PO refuse work because it misread orchestrator planning notes as instructions to itself).

Everything is backward-compatible at the orchestrator level except #1 (which makes the `epics/` directory mandatory; the PO must always produce at least `EPIC-1.yaml`).

---

## 1. Epic Layer

### Concept

A feature now has the structure:

```
_output/<feature_name>/
  spec.md
  epics/
    EPIC-1.yaml        # at least one; only split into multiple when warranted
    EPIC-2.yaml
  stories/
    STORY-1.yaml       # every story has `epic: EPIC-N` field
    STORY-2.yaml
    ...
  verification/        # written by EpicVerifier
    EPIC-1.md
    EPIC-2.md
```

**Default is one epic per feature.** The PO guidance in `agents/product-owner.md` says: split only when (a) 8+ stories, (b) they cluster into 2-4 themes with distinct user-visible value, AND (c) you want mid-feature verification checkpoints. "When in doubt, use one epic."

### Schema additions

Epic YAML:
```yaml
id: EPIC-1
title: ...
status: TODO   # TODO | IN_PROGRESS | DONE | VERIFIED | BLOCKED
depends_on: []   # other EPIC ids; satisfied only at VERIFIED (not DONE)
story_ids: [STORY-1, STORY-2]
acceptance: |     # OPTIONAL -- epic-level cross-story criteria
  ...
```

Story YAML gained a required field:
```yaml
epic: EPIC-1   # required; story must belong to exactly one epic
```

### Invariants enforced

- Every story has an `epic:` field naming an existing epic id
- Every epic's `story_ids:` must match the stories that name it (two-way consistency)
- Union of all `story_ids` equals the full set of story files (no orphans)
- Cross-epic story dependencies are forbidden -- a story's `dependencies:` may only name stories in the same epic; cross-epic ordering uses epic `depends_on:`
- An epic `depends_on:` is satisfied ONLY at `VERIFIED` (not `DONE`) -- the verifier is the gate

### Status rollup (computed; never auto-written)

`_tools/list_eligible.py` computes each epic's rollup status from its stories:
- BLOCKED if any story is BLOCKED
- DONE if every story is DONE
- TODO if every story is TODO
- IN_PROGRESS otherwise

The on-disk `status:` field is authoritative for `VERIFIED` only (written by EpicVerifier). The rollup-from-stories is what `list_eligible.py` uses to decide `epic_ready_to_verify`.

### Files added / changed

| File | Change |
|---|---|
| `agents/product-owner.md` | New "Epics" section: when to split; epic YAML format; rules. `epic:` field required on stories. Approval/completion templates list epics. |
| `_tools/list_eligible.py` | Loads epics; epic-aware eligibility; surfaces `epics` map + `epic_ready_to_verify` bucket; story is blocked if its epic's `depends_on` epics aren't all VERIFIED. |
| `_tools/update_epic_status.py` | **NEW.** Atomic locked epic status updater. Same FileLock/YAML-backend as `update_story_status.py`. |
| `_tools/rollup_status.py` | **NEW.** Read-only renderer: produces a human-readable epic/story tree to `progress.md` or stdout. |
| `.claude/skills/sage-po/SKILL.md` | Step 3 always creates `epics_dir`; preflight checks it. |

---

## 2. EpicVerifier Checkpoint

### Role

A new agent (`agents/epic-verifier.md`) that the orchestrator spawns when `list_eligible.py` reports an epic in `epic_ready_to_verify` (every story DONE but epic on-disk status not yet VERIFIED).

### What it does

1. Runs `_tools/verify_epic.py --feature <name> --epic EPIC-N` as a mechanical preconditions gate (all stories DONE + every AC implementation map still verifies via `verify_ac_map.py`)
2. If preconditions fail (a story regressed, or a story's AC map no longer verifies because another story edited a shared file), re-opens the failing stories to IN_DEV with reasons `ac_map_regression` or `cross_story_regression`
3. Runs the regression scoped to the epic using the project's tagging convention (e.g. `pytest -m "STORY-1 or STORY-2 or STORY-3"`). Catches cross-story regressions that per-story Testers cannot see.
4. If the epic YAML has an optional `acceptance:` block, interprets whether the implemented code satisfies it (judgment call)
5. On success: writes `_output/<feature>/verification/EPIC-N.md` and flips the epic YAML to `VERIFIED` via `update_epic_status.py`. This unlocks any downstream epic whose `depends_on` lists this one.

### Orchestrator behavior

`sage-feature-team` SKILL.md Step 6 was extended:
- New eligibility bucket from `list_eligible.py`: `epic_ready_to_verify`
- Worker name: `EpicVerifier-EPIC-N` (re-runs append `-cN` like other workers)
- Verifier failures count against a separate `verify_cycle_count[EPIC-N]` budget (uses the same `max_cycles` config knob); on exhaustion the epic is escalated
- New exit condition: scheduler loop ends when every epic is `VERIFIED` (or escalated)

### Files added / changed

| File | Change |
|---|---|
| `agents/epic-verifier.md` | **NEW.** Full agent role file modeled on `agents/tester.md` -- preconditions gate, regression run, AC-map re-check, optional acceptance interpretation, artifact write, status flip. |
| `_tools/verify_epic.py` | **NEW.** Mechanical preconditions gate. Does NOT run tests. |
| `.claude/skills/sage-feature-team/SKILL.md` | Step 6 spawns EpicVerifier workers; Step 6e handles VERIFIED/FAILED/BLOCKED outcomes; Step 6h exits when all epics VERIFIED. Step 7 final report includes epic verification status. |
| `_tools/load_agents.py` | Added `EpicVerifier` slug mapping. |
| `sage-config.yaml` | Added EpicVerifier to `team.agents.full`. |

---

## 3. `--serial` CLI Flag

`/sage-feature-team "feature" --serial` overrides `max_parallel_workers` to `1`. Useful for:
- Debugging: easier to follow one worker at a time
- Test-isolation-sensitive projects: avoids parallel Tester runs colliding on shared fixtures/DBs
- Watching the orchestrator's behavior step by step

Single-bullet change in `sage-feature-team` SKILL.md Step 1. The downstream scheduler code already gates on `max_parallel_workers`; no other code paths changed.

---

## 4. NARRATION Rule (replaces SILENCE Rule)

### Before

`_BASE.md` had a strict "be silent, no narration, no commentary" rule. Agents output exactly 2 SendMessages (starting + completion) AND were also told to stay quiet in their own transcripts between those messages.

### After

Two channels, two different rules:

- **Own transcript** (text output visible when user inspects the agent panel): narrate freely -- explain decisions, walk through code, describe tradeoffs.
- **SendMessage** (team panel / orchestrator handshake): still strictly 2 per task. Extra SendMessages confuse routing and re-trigger handlers.

The asymmetry preserves the orchestrator's contract while making agent work readable.

### Developer "Explain Your Code Changes"

Specific addition to `agents/developer.md`: a new section instructing the Developer to narrate each non-trivial code change with **What / Why / Where**, give a brief plan for multi-file work, and narrate the hypothesis → evidence → fix loop when debugging. Explicit anti-instruction: don't narrate tool plumbing ("I'm going to use Read now") -- narrate the work, not the keystrokes.

### Files changed

| File | Change |
|---|---|
| `agents/_BASE.md` | SILENCE RULE → NARRATION RULE. Two-channel framing. |
| `agents/{developer,product-owner,test-creator,tester,epic-verifier}.md` | Boilerplate pointer updated `SILENCE` → `NARRATION`. |
| `agents/developer.md` | New "Explain Your Code Changes" section + matching Key Rule. |

---

## 5. Starting-Message Nudge (spawn race mitigation)

### Problem

Empirically, freshly-spawned workers often went idle without sending their starting message in response to the first `SendMessage` task. A single re-send fixed it reliably. Suspected cause: race between `Agent()` spawning the worker process and the orchestrator's first `SendMessage()` arriving (which may land before the worker is ready to receive).

### Fix

**Two complementary changes** -- because the cause is probably both a real delivery race AND an over-emphatic prompt:

**`agents/_BASE.md`:**
- STOP section now ends with an explicit wake-up paragraph telling the agent that silence ends as soon as the first task arrives and the starting message is non-negotiable
- "Starting Message Within 60s" → **"Within 30s of First Task"** with explicit guidance that a duplicate task message is the orchestrator nudging, not a new task -- treat it as confirmation and respond

**`sage-feature-team` SKILL.md Step 8 (starting-message monitoring):**
- T=0-30s: wait
- **T=30s: nudge** -- re-send the EXACT same task message (one retry only)
- T=30-60s: wait
- T=60s: escalate to BLOCKED (as before)

Includes a rationale paragraph so future-you doesn't strip the nudge as redundant.

---

## 6. Task-List Disambiguation

### Problem

An early run had the ProductOwner refuse work because it saw the orchestrator's `TaskList` entries (Phase 2 / EpicVerifier-related tasks the orchestrator had created for its own bookkeeping) and interpreted them as tasks being assigned to itself. The PO sent a "role mismatch" reply.

### Fix

**`agents/_BASE.md`** -- added a bullet to the "These do NOT count as tasks" list:
> Entries you see in the shared team task list (TaskList / TaskGet output, task panel items). The task list is the orchestrator's own planning surface -- it is NOT an assignment channel. Tasks arrive only via SendMessage.

**`sage-feature-team` SKILL.md** -- added a DON'T rule telling the orchestrator NOT to pollute the shared task list with downstream-phase entries (they're visible to all teammates and look like assignments).

---

## Files Added (full list)

- `agents/epic-verifier.md`
- `_tools/update_epic_status.py`
- `_tools/verify_epic.py`
- `_tools/rollup_status.py`
- `TODO_PHASE_3.md` (deferred work plan, not implemented)
- `CHANGE_SUMMARY.md` (this file)

## Files Modified (highlights)

- `agents/_BASE.md` -- NARRATION rule, spawn/wake-up tightening, task-list disambiguation
- `agents/product-owner.md` -- mandatory epic layer + epic schema/rules
- `agents/developer.md` -- "Explain Your Code Changes" section
- `agents/{tester,test-creator,product-owner,developer,epic-verifier}.md` -- NARRATION pointer update
- `_tools/list_eligible.py` -- epic-aware eligibility + rollup
- `_tools/load_agents.py` -- EpicVerifier slug
- `_tools/setup_project.py` -- installer copies new agent + 4 new tools; scaffolds `sage-epic-verifier-config.yaml`
- `.claude/skills/sage-feature-team/SKILL.md` -- verifier phase, `--serial` flag, 30s nudge, task-list rule
- `.claude/skills/sage-po/SKILL.md` -- always creates `epics_dir`
- `sage-config.yaml` -- registers EpicVerifier role
- `C:\Users\merri\.claude\skills\sage-install\SKILL.md` -- updated install summary (10 tools, 5 agents, 5 skeleton configs)

---

## Out of Scope (deferred)

`TODO_PHASE_3.md` captures the Phase 3 plan -- richer per-item status fields (priority, cycle_history, risk, tags, required blocked_reason). Deliberately deferred until 1-2 real feature runs through the Phase 1/2 flow inform which fields actually matter. Reviewers can scrutinize that TODO independently.

---

## Suggested Review Focus

If you're reviewing this work, the highest-leverage things to scrutinize:

1. **Epic dependency semantics** (`_tools/list_eligible.py`): is the "VERIFIED, not DONE" gate on `epic.depends_on` correct? Does it ever cause deadlock when an upstream epic has no verifier-eligible stories?

2. **EpicVerifier re-open behavior** (`agents/epic-verifier.md`): when the verifier re-opens a story for cross-story regression, does the Developer's next cycle have enough context to actually fix it (failure details forwarded via the verifier's completion message)?

3. **Spawn race fix** (`agents/_BASE.md` + SKILL.md Step 8): is the prompt tightening + 30s nudge actually sufficient? What's the rollback if it isn't? (The 60s BLOCKED escalation is unchanged, so the worst case hasn't gotten worse -- but it's worth verifying.)

4. **Single-epic feature ergonomics**: a feature that PO decides only needs one epic still pays a small cost (one extra YAML file, one extra verifier run at the end). Is that cost-benefit acceptable, or should the verifier auto-skip when an epic has no `acceptance:` block AND only one story?

5. **NARRATION rule and orchestrator cost**: agents now produce more text in their transcripts. Does this materially change token budgets per worker? (The `_output/<feature>/tokens.json` instrumentation will show this empirically after a run or two.)

6. **Backward compatibility**: features started before this change have no `epics/` directory. `list_eligible.py` now hard-errors when `epics/` is missing. Is the `--resume` path documented for projects with in-flight pre-epic features? (Answer: no; they'd need to manually scaffold an EPIC-1.yaml wrapping all existing stories.)

---

## Verification Performed

- `_tools/load_agents.py full` -- returns `success: true` with all 5 agents
- All new tools accept `--help` and parse cleanly
- `_tools/list_eligible.py` tested against a 2-epic / 4-story fixture (cross-epic dependency correctly gates downstream stories on upstream `VERIFIED`)
- `_tools/rollup_status.py` renders the expected tree for the fixture
- `_tools/update_epic_status.py` transition validation tested: `DONE -> VERIFIED` allowed; `VERIFIED -> DONE` rejected; `--force` bypasses
- `_tools/setup_project.py` end-to-end smoke-test into a temp project: 5 agents copied, 10 tools copied, 5 skeleton configs scaffolded, loader verification reports `OK: loaded 5 agents in mode=full`

No end-to-end run of `/sage-feature-team` through a real chatbot project has been performed against the final state (the only real run was during early Phase 1/2 development and surfaced the task-list-disambiguation + spawn-race issues that have since been fixed). A live run is the next sensible validation step.

---

## Addendum: Token Cost Investigation (2026-05-18)

An external suggestion claimed the "ephemeral per-story worker" pattern is hostile to prompt caching and is the biggest token leak in the system. The original framing proposed three fixes (A: deduplicate templates across role files, B: restructure prompts for prompt-cache friendliness, C: switch to long-lived worker pools) and predicted huge savings from B and C.

**Empirical investigation against a real feature run (`streak_break_warning_notification` in Breadcrumbs, 75 workers, $488 total cost) showed the framing was wrong.** The prompt cache is already hitting at **91.1%** of input tokens. Cross-worker caching is confirmed -- workers 2..N of each role get ~22,387 tokens of `cache_read` on their very first API call. The cache shares the rendered prompt across spawns of the same role automatically.

### Per-role first-turn cache verification

For each role, I inspected the first-turn `usage` object of every worker's transcript:

| Role | Workers | Cold spawns (cache_read=0) | Warm spawns | Avg first-turn cache_read on warm |
|---|---:|---:|---:|---:|
| Developer | 27 | 3 | 24 | ~22,387 |
| TestCreator | 17 | 4 | 13 | ~22,387 |
| Tester | 26 | 0 | 26 | ~22,387 |
| ProductOwner | 5 | 5 | 0 | 0 |

Cold spawns pay ~35-37k `cache_create` to warm the cache; warm spawns pay only ~7-12k `cache_create` for the per-worker variability (task message, story-specific paths).

ProductOwner shows all 5 entries as cold spawns -- this is a recording artifact (one PO ran in this feature; the 5 entries are the same agent recorded multiple times by `discover_and_record.py`). The actual PO run was a single warm session within the orchestrator's context.

### Cost breakdown for the feature

| Bucket | Tokens | % of input | Approx $/MTok | Cost |
|---|---:|---:|---:|---:|
| cache_read (cheap reuse) | 124,422,112 | **91.1%** | $1.50 | ~$186 |
| cache_create (expensive write) | 12,117,669 | 8.9% | $18.75 | ~$227 |
| fresh input (no cache) | 4,821 | 0.0% | $15 | ~$0 |
| output | 998,417 | -- | $75 | ~$75 |

Fresh-input billing across 75 workers averaged ~64 tokens per worker -- essentially nothing. The cache is doing its job.

### Verdict on the three fixes

**Fix A (template dedup) -- implemented.** Reduced rendered prompts by 1,405 tokens total across 5 roles (~5.1%). My initial estimate of "~12.2k savings per Developer task" was arithmetically wrong because it treated `Read` tool results as one-time costs (they actually persist in conversation and are re-paid on every subsequent API call). Honest savings are ~1,625 tokens per Developer task -- but since most of those savings are in the cached prefix (cache_read at $1.50/MTok), the dollar value is ~$2-3 per feature run. **Worth doing for maintainability (single source of truth for completion messages and AC map format), not for cost.**

**Fix B (cache hoist) -- not viable.** The original premise was wrong; the cache is already saturated at 91% hit rate. There's no caching gap to close. Restructuring prompts for "cache friendliness" would not move the needle. **Skipped.**

**Fix C (worker pools) -- not worth doing.** Would save the per-spawn variable-content `cache_create` (~7-12k per spawn × ~70 spawns per feature ≈ **$5-15 per feature run**, or 1-3% of total cost). Architectural risks are substantial:
- Pool worker conversations grow unboundedly across stories. By task 20, the worker's conversation is hundreds of thousands of tokens; `cache_read` cost per API call scales linearly with conversation length and can exceed current per-spawn cost.
- Mitigations (force context reset, periodic restart, rely on auto-compaction) introduce complexity and most invalidate the cache they were meant to preserve.
- Significant rewrite of `sage-feature-team` SKILL.md Step 6 (most load-bearing file).
- Agent files need substantial changes to handle sequential tasks without state corruption.
- `--serial` becomes awkward; worker death/restart logic gets much more complex.
- A pool worker in a bad state corrupts all subsequent tasks until manually restarted.

**Skipped.** The architectural risk is not justified by 1-3% savings.

### Where the real cost actually lives

The cost driver in the data is `cache_create` (~46% of total) and `cache_read` volume (~38%). Both scale with **per-worker conversation length × number of workers**, not with how the prompt is structured. The real levers:

1. **Per-worker turn count.** Developer averaged ~34 turns per task in this feature. A worker with 60 turns costs ~2x the median. Worth instrumenting per-worker turn distribution and investigating outliers (long debugging sessions, AC exploration, redundant file re-reads).
2. **Dev<->test cycle count.** Each cycle is a fresh worker conversation. Stories that take 3 cycles cost ~3x stories that take 1. Better tests upfront and more accurate AC implementation reduce cycles.
3. **Tool call batching.** Independent tool calls running in parallel = fewer turn pairs = less `cache_create` growth.
4. **NARRATION verbosity (introduced in this session's changes).** Now visible in transcripts -- worth checking whether average turn count went up after this change. If so, the answer isn't to remove NARRATION (it's user-visible value) but to tighten its scope (key moments only, not every change).

These are operational improvements, achievable through prompt tightening and tooling -- not architectural rewrites.

### Files added by this investigation

- `templates/AC_MAP_FORMAT.md` (Fix A)
- `templates/COMPLETION_MESSAGES.md` (Fix A)
- Updated all 5 role files to reference templates instead of inlining (Fix A)
