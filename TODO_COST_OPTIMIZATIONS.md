# TODO: Cost Optimizations -- Real Levers

**Status:** identified but not implemented. Wait until 1-2 more real feature runs confirm the priorities before tackling these.

**Background:** the original "prompt caching is broken" hypothesis (see `CHANGE_SUMMARY.md` § Token Cost Investigation) turned out to be wrong -- the cache is already hitting at 91.1%. The real cost drivers are **per-worker conversation length** and **dev<->test cycle count**, both of which scale with operational behavior rather than architecture. The levers below target those drivers directly.

Aggregate impact estimate if all four are done: **30-50% reduction in per-feature cost** (on top of the existing cache savings). This is far more than the rejected Fix B/Fix C from the original suggestion ever could have delivered.

---

## Lever 1 -- Pre-stuff task messages with content the worker is guaranteed to need

**Highest single-lever payoff. Lowest implementation risk. Mechanical change.**

### What it is

Today, when the orchestrator dispatches a task to a worker, the task message contains only **pointers** -- "Target story: STORY-3, Stories dir: \_output/.../stories/, Spec file: \_output/.../spec.md". The worker then makes 3-5 `Read` tool calls at the start of its task to fetch the actual content of those files before it can begin work.

The proposal: have the orchestrator include the actual content (story YAML body, AC list, relevant spec excerpt) verbatim in the task message. The worker starts already knowing what to do.

### Why this saves money

The orchestrator already has the story YAML in memory -- `list_eligible.py` returns it as JSON every scheduling scan. Reading the spec.md is a one-shot file read. So the orchestrator's cost is essentially zero.

For the worker, each `Read` it doesn't have to make eliminates:
- One turn pair (assistant message with the Read tool call + user message with the result) -- saved cache_create on that turn
- The Read result's content is no longer in the conversation, which means every subsequent turn pays less cache_read on that content's behalf for the rest of the worker's life

Rough math: 3-5 saved turn pairs per worker × 70 workers per feature × ~7-10k cache_create per turn pair + downstream cache_read savings ≈ **$30-70/feature**, depending on file sizes.

### What to change

- `_tools/list_eligible.py` already returns story data; expose a sibling helper (call it `prepare_task_payload.py` or fold into the SKILL.md instructions) that, given a STORY-N, returns: story YAML body + AC list + relevant spec excerpts.
- `.claude/skills/sage-feature-team/SKILL.md` Step 6d (the per-role task message templates): include the prepared payload inline in each role's task message, replacing the current pointer-only format.
- Agent role files: drop the "Read these files at task start" steps from their workflows; first-step is now "consult the payload in your task message".

### What to leave alone

- The pointers themselves stay (worker may still need to Read additional files, write the implementation map sidecar at a specific path, etc.)
- The orchestrator still re-reads YAMLs after each completion -- that's the source-of-truth pattern, unchanged
- Don't pre-stuff the entire project's instruction files; they're already in the agent's rendered system prompt via PROJECT_INSTRUCTIONS substitution

### Risk

Low. The change is additive (workers can still Read if they need to); existing behavior degrades gracefully. Worst case: task message is too big and you trim it back.

---

## Lever 2 -- Reduce dev<->test cycle count

**Biggest cumulative payoff. Higher complexity. Requires tuning TestCreator + Developer behavior.**

### Why it matters

Each dev<->test cycle is a **fresh worker conversation** (`Developer-STORY-N-c2`, `c3`, ...). A story that takes 3 cycles costs roughly 3x a story that takes 1, because the prompt cache helps within a worker but doesn't carry across re-spawns of the same role + story (the worker name is different).

From the Breadcrumbs feature data: 27 Developer workers across 75 total workers implies a non-trivial multi-cycle rate. Halving the average cycle count likely saves 20-30% of feature cost.

### What drives unnecessary cycles

1. **TestCreator misses failure modes**, so a test that should have failed silently passes, and Tester catches it -> Developer re-cycles.
2. **Developer claims completion before checking AC implementation map locally** -- Gate B fails, story re-opens.
3. **Tester runs Gate B output isn't actionable enough** -- Developer's re-cycle fixes the surface complaint but misses the underlying gap, triggering another cycle.

### Levers within this lever

- **Tighter TestCreator output** -- when writing tests, explicitly enumerate every AC and confirm at least one test per AC covers happy path + at least one edge case. The TestCreator currently relies on "comprehensive integration tests" framing; could be sharpened.
- **Stricter Developer self-verification** -- before flipping a story to TESTING, Developer should explicitly walk through the AC list and confirm "AC1 is wired at <file:line>, AC2 is wired at <file:line>" in its own transcript. The NARRATION rule allows this. Possibly require it as part of the "Explain Your Code Changes" section.
- **Smarter re-cycle context from orchestrator** -- when Tester re-opens a story, the orchestrator pastes failure details into the next Developer task message. Also paste the relevant existing AC implementation map so Developer's re-cycle starts with full context instead of re-reading.
- **Per-feature cycle-count instrumentation** -- log the cycle distribution per story; investigate outliers manually after the first few runs to find the pattern.

### Risk

Medium. Behavioral changes to agents can have unintended consequences (e.g., Developer becoming overly defensive and refusing to flip TESTING). Each sub-lever should be added independently and measured.

---

## Lever 3 -- Batch tool calls in parallel where currently serial

**Solid prompt-engineering win. Needs an audit before estimating size.**

### What to look for

Tool calls that are independent (one's result doesn't feed another's input) should run in a single parallel batch. Each parallel batch is **one turn pair**, regardless of how many tool calls are in it. Five sequential Reads = 5 turn pairs; one parallel Read batch of 5 = 1 turn pair.

### Where to audit

- Developer's "consult project instructions" step: typically reads multiple instruction files -- can these be batched?
- Tester's "read all story YAMLs" + "consult project instructions": batchable?
- TestCreator's "read spec + read all story YAMLs": almost certainly batchable.
- EpicVerifier's preconditions phase: `verify_epic.py` + reading all stories in scope -- already mostly batched, but worth checking.

### How to estimate

Pick a recent worker transcript per role; count the number of turn pairs spent on sequential Read tool calls before the worker does any "thinking work". That's the upper bound on what batching could save.

### Risk

Low. Pure prompt-engineering change. Agents already do *some* parallel batching; making it explicit policy in role workflows is a small edit per file.

### Estimated impact

$20-50/feature. Modest but cheap.

---

## Lever 4 -- Scope NARRATION to key moments

**Real savings (~$10-30/feature) but watch the visibility trade-off.**

### The trade-off

NARRATION was added deliberately because you wanted transcript visibility into agent work. Reducing it has a UX cost. The honest question: do you actually use the per-change narration, or only the plan / hypothesis / final-summary narration?

If only the latter is genuinely valuable to you, **scope to key moments** is pure win:
- A brief plan at the start of an AC implementation
- The hypothesis -> evidence -> fix loop when debugging
- A final summary before sending completion
- NOT every Edit/Write tool call

If the per-change narration genuinely helps, the dollar cost is the cost of the visibility -- don't cut it.

### What to change

- `agents/developer.md` § Explain Your Code Changes: tighten "for every non-trivial code change" to "for each plan transition, hypothesis -> fix, or completion summary"
- Add an explicit anti-pattern: "Don't narrate one-line edits; one composite narration covering a related cluster of edits is better than one per file."

### Risk

Low (mechanical text change). The risk is purely UX -- if you lose useful visibility, revert.

---

## Suggested order

1. **Lever 1** first. Highest payoff, lowest risk, mechanical. Once-and-done.
2. **Lever 3** second. Cheap audit, cheap edits, no UX impact.
3. **Lever 2** third. Higher complexity but biggest cumulative payoff. Do incrementally (one sub-lever at a time) and measure.
4. **Lever 4** last. Smallest savings, real UX trade-off. Only after you've felt the cost from running more features.

---

## Measurement strategy

After each lever lands, run one real feature through and compare `_output/<feature>/tokens.json` to a baseline. Specifically:
- Total `cache_create` (the expensive bucket -- main thing we're trying to reduce)
- Total `cache_read` (cheaper; less important)
- Per-worker `message_count` (should drop with Lever 1 and Lever 3)
- Per-story cycle count (should drop with Lever 2)

The Breadcrumbs `streak_break_warning_notification` run is the current baseline: $488 total, 91.1% cache hit, 12.1M cache_create.
