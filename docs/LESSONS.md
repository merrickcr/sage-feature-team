# Lessons

A record of the load-bearing decisions in sage-feature-team and the concrete
failures that motivated each one. These are not "best practices." Each lesson
carries a specific cost we chose to accept. Where the decision is contested
or partial, we say so.

The intended audience is anyone building (or thinking about building) a
multi-agent system on top of LLM primitives -- not just for Claude Code. Most
of these lessons are protocol- and architecture-level; the Claude Code coupling
is implementation detail.

If you're new to sage, read the [README](../README.md) and
[ARCHITECTURE](ARCHITECTURE.md) first. This doc assumes you know what the
framework does and is asking *why it's shaped this way*.

---

## 1. YAML is the event log, not the message body

**The lesson:** trust durable state. Treat agent-to-agent messages as hints to
re-read state, never as the authoritative record of what happened. This is the
same lesson distributed systems people learned over decades -- worth restating
because LLM agents present a tempting illusion that messages *are* reliable.

**The failure that motivated it.** The original orchestrator routed off the
contents of completion messages. Workers said they finished tasks they
hadn't. SendMessages got "sent" but never processed by the recipient.
Messages were processed but their content didn't match the actual file
system state. The orchestrator's internal model of the world drifted from
reality, sometimes within a single feature run, and the only way to recover
was to kill everything and resume from disk.

**What we did.** Each story is its own YAML file at
`_output/<feature>/stories/STORY-N.yaml`. Each epic is its own YAML file at
`_output/<feature>/epics/EPIC-N.yaml`. The `status:` field is the single
source of truth for "where is this story right now." All status transitions
go through `update_story_status.py` / `update_epic_status.py` -- atomic,
file-locked (msvcrt on Windows, fcntl on POSIX), with whitelisted
transitions. The orchestrator re-reads the relevant YAMLs after every worker
completion and never trusts a message body alone.

**What to take from this.** In any multi-agent system, identify your durable
signal -- the thing that survives a crash, a context compaction, or a
process restart -- and route off that. Messages have a role (telling the
orchestrator "something happened, look at state"), but they should never be
the carrier of state.

---

## 2. Killing the SYN/SYN-ACK handshake

**The lesson:** ceremonial reliability protocols borrowed from TCP don't
translate to LLM agent messaging. There is no packet loss between Claude
agents. The bytes get there. The work of a "handshake" is mostly defending
against failures you don't have, at a cost you do pay.

**The failure that motivated it.** Early sage had a 3-way handshake on
every worker completion: SYN, SYN-ACK, ACK+DATA. It added roughly 41 seconds
of overhead per worker, bifurcated the message protocol (every handler had
to consider "handshake on" vs "handshake off"), and didn't actually catch
the failures we were seeing. The dominant failures were `no_ack` (worker
never started) and `state_ambiguous` (orchestrator and worker had different
ideas of "in progress"). The handshake addressed neither.

**What we did.** Stripped it. Each task now has one starting message within
30 seconds of first dispatch and one completion message at the end. If the
starting message doesn't arrive, the orchestrator re-sends the *exact same
task* once at 30s (treated by the worker as a confirmation, not a new
task), then escalates to `BLOCKED` at 60s. Total protocol: two messages
plus a defensive nudge.

**What we'd revisit.** The per-message `requires_ack` model proposed in the
internal handshake-redesign analysis has not shipped. The current
implementation is "no handshake, plus a nudge" -- not "selective ack for
the messages that need it." If we ever see message loss in practice (we
haven't), the next move is per-message ack rather than reviving the global
handshake.

**What to take from this.** Don't bolt on reliability machinery before
measuring whether you have the reliability problem. The simplest model
usually works. When you do need acks, scope them to the messages that
genuinely need them rather than to the whole protocol.

---

## 3. `shutdown_request` is the only real shutdown mechanism

**The lesson:** in Claude Code's team primitives, there is exactly one
approved way to actually remove a worker from the team panel:
`shutdown_request` → `shutdown_response approve=true`. Anything else either
fails silently or works for the wrong reasons.

**The failure that motivated it.** Earlier skill versions tried to release
workers with `TaskStop`, with a polite "you are released" plain-text
message, or by simply not sending them any more work. None of these
actually removed the worker from the team panel. The panel accreted zombie
workers from past stories; the orchestrator's internal worker-count
diverged from what was actually alive; per-story spawn caps appeared to be
working but were silently inheriting capacity from supposedly-dead
predecessors.

**What we did.** The `sage-feature-team` skill owns the full team
lifecycle. `TeamCreate` at the start. Each worker is terminated with an
explicit `shutdown_request` → wait for `shutdown_response approve=true`
pair when its task completes. `TeamDelete` at feature complete. `--resume`
force-cleans any straggler team before starting.

**What to take from this.** Read the team lifecycle docs of whatever
multi-agent primitive you're using. The teardown mechanism is almost always
the part that's least well documented and most subtly broken. Find the one
sanctioned path; everything else is a footgun.

---

## 4. Cycle budgets reset on resume -- a deliberate decision, not a bug

**The lesson:** when a user explicitly resumes an interrupted feature run,
they are claiming responsibility for the budget. Give them a fresh one
rather than inheriting partial state from before the interrupt. This is a
UX call, not a correctness call -- and reasonable people disagree.

**The failure that motivated it.** Not really a failure. This decision was
flagged in an internal review as a potential bug: "a story that hit
`max_cycles` before the orchestrator crashed re-enters the loop on resume
and gets *another* `max_cycles` budget, silently doubling cost." That's
mechanically true.

**What we did.** Reset budgets on resume. Document the behavior. The
counter-argument we accepted: `--resume` is a deliberate user action. The
user has seen the failure, decided to push past it, and explicitly asked
the system to keep going. Inheriting the prior budget would mean silently
refusing to do work the user just asked for. That's a worse failure mode,
in our view, than the "secret doubled budget" mode -- because the silent
refusal has no surface, while the doubled budget is at least visible in the
token report.

**What we'd revisit.** Persistent scheduler state
(`_output/<feature>/scheduler_state.json` written on every transition)
would let us preserve budgets across resume *without* removing the user's
ability to override. v2 work. For v1 we chose the simpler model and the
explicit user-trust contract.

**What to take from this.** Not every "bug" is a bug. Resume semantics in
particular are a UX decision as much as a correctness one. Decide
explicitly which side you're on; document the choice; let users push back.

---

## 5. Mechanical eligibility beats LLM scheduling

**The lesson:** where you can replace LLM judgment with a deterministic
script, do it. Cheap, testable, immune to whole classes of failure that
LLM-based decision-making is prone to (forgotten transitive deps,
hallucinated "this looks ready," approximation of "ALL X" as "most X").

**The failure that motivated it.** The original orchestrator eyeballed
the stories directory at every loop and decided what to spawn based on its
own reading of each YAML's `status:` and `dependencies:` fields. It missed
transitive dependencies (story C depends on B depends on A; C got picked
up before A finished). It spawned blocked stories whose dep status said
`BLOCKED` because the orchestrator decided the block "looked recoverable."
It occasionally re-spawned stories that were already `DONE` because the
relevant YAML had been re-read between two parts of the same reasoning
pass.

**What we did.** `_tools/list_eligible.py` is the single source of truth
for "what's spawnable right now." It returns buckets per role (`po`,
`test_creator`, `developer`, `tester`) plus an `epic_ready_to_verify`
list. The orchestrator's scheduling loop calls it on every scan, slices
each bucket to available capacity, spawns. The orchestrator never reads
YAMLs to decide what's eligible -- only `list_eligible.py` does that. A
dependency is satisfied only when its status is exactly `DONE` (or
`VERIFIED` for epic-level `depends_on:`). `TESTING` does not count.

**What to take from this.** LLM agents are bad at conjunctive reasoning
("ALL of these must be true"). They'll happily approximate it as "most of
these are true and that's probably fine." Push that work to code wherever
the predicate is mechanical. The LLM keeps the judgment calls (writing the
spec, writing tests, debugging failures); the scheduler is deterministic.

---

## 6. Per-story ephemeral workers, not long-lived ones

**The lesson:** spawn a fresh worker per story. Shut it down at task
completion. Don't reuse workers across stories. The cost is spawn overhead
(real, predictable, measurable). The benefit is that each worker's
reasoning is anchored in exactly one story with no carryover from
previous stories.

**The failure that motivated it.** Long-lived workers would have created
unbounded state-leakage risk: Developer-Persistent gets task A (write
code for STORY-1), completes it, then gets task B (write code for STORY-3
which has nothing to do with STORY-1). The worker's conversation now
contains both STORY-1's code, the test failures, the AC discussions, plus
STORY-3's task -- and the worker is statistically likely to apply STORY-1
patterns to STORY-3 where they don't apply. The state-anchoring of "this
worker is exactly for this story" is what prevents that.

**What we did.** Workers are named `<Role>-<STORY-N>` for first attempts
and `<Role>-<STORY-N>-cN` on re-cycles (e.g.,
`Developer-STORY-3`, `Developer-STORY-3-c2`). Each worker is created at
spawn time, given exactly one task message, runs to completion, and is
terminated via `shutdown_request`. Per-spawn token cost is dominated by
the cache_create on the cached-prompt warming pass (~7-12k tokens after
the first cold spawn of that role; the prompt cache hits at ~91% on
warm spawns).

**The cost we pay.** Empirically ~$5-15 per feature run on a $500
feature, vs. a long-lived pool that would amortize the per-spawn warming
cost. We took the architectural simplicity win.

**What to take from this.** The cache_create cost of ephemeral spawns is
real but predictable. The "what's in this worker's context" cost of
long-lived workers is unbounded. Pick the cost that can be budgeted.

---

## 7. Token tracking is structurally hard in agentic frameworks

**The lesson:** in direct-API code, every response carries `usage` data;
totalling cost is trivial. In an agentic framework, the data lives in
transcript files written by the runtime, and the orchestrator has to
scrape them. There is no clean API for "what did my last subagent
response cost?" Budget for instrumentation up front, or accept that you'll
fly blind on cost.

**The failure that motivated it.** We observed this in the static-site
-generator run captured in this repo. Eight stories went `DONE`, three
epics went `VERIFIED`, total cost was about $22 -- but `tokens.md`
records only the ProductOwner. The TestCreator / Developer / Tester /
EpicVerifier work was done via the inline single-agent skills
(`/sage-developer`, `/sage-tester`, etc.), which run inline in the main
conversation rather than as subagents. `discover_and_record.py` walks
team-mode transcripts under
`~/.claude/projects/<slug>/<session>/subagents/`; the inline runs don't
appear there, so they're invisible to the instrumentation. We have token
data for roughly five percent of the work actually done.

**What we did.** `_tools/discover_and_record.py` walks the team-mode
subagent transcripts after every orchestrator scan, deduplicating raw
captures into logical workers (a single PO might be captured five times
as its conversation grows; the script collapses those into one logical
record), and writes per-worker token totals to
`_output/<feature>/tokens.{json,md}`. The script is idempotent on
re-scan.

**What we'd revisit.** The inline-skill blind spot is real and known.
Either `discover_and_record.py` learns to walk the main session
transcript when called from an inline skill, or the inline skills get a
companion recording path. Either way it's a meaningful piece of v2
work. For v1 we have honest team-mode telemetry and an honest disclaimer
about inline.

**What to take from this.** If you care about cost (you should; this is
the dominant operational variable in agentic frameworks), design the
discovery model alongside the orchestration model -- not after, when
you're trying to reverse-engineer it from transcripts. And accept that
even with good instrumentation there will be invisible runs you have to
account for separately.

---

## Open question: the orchestrator runs as a Skill, not as code

We owe an honest framing of one large tradeoff that this v1 has not
resolved: the orchestrator's scheduler, cycle counters, escalation
logic, team lifecycle, and deadlock detection are all expressed as
*instructions in a SKILL.md* for an LLM to follow, not as Python code
that calls primitives.

**Why we did it this way.** SKILL.md flexibility. Updating the
orchestrator means editing markdown; no compile, no redeploy. The LLM
can adapt to weird situations a hardcoded scheduler would mishandle. And
critically: the team lifecycle primitives sage uses (Agent, Task,
SendMessage, Monitor) are accessible *from skills* in a way they are not
accessible from arbitrary Python scripts in Claude Code.

**The cost.** It's fragile. A future Claude model version reads the
SKILL.md differently and the orchestrator's behavior shifts. Bugs in the
scheduler appear as "the model didn't follow step 6c" rather than as
test failures. We have spent real debugging time on
the orchestrator forgetting to call helper scripts, on it
misinterpreting eligibility lists, on it acting as if a worker were
alive that had already been shut down.

**Two options for v2.** (1) Acknowledge the tradeoff in the write-up
and ship as-is. SKILL.md remains the orchestrator; we lean on the
mechanical eligibility script (lesson 5) and durable state (lesson 1)
to bound the failure modes. (2) Extract the orchestrator into a Python
process that the SKILL.md just invokes; the LLM runs the things only an
LLM can run (spec drafting, code writing, debugging) but doesn't
schedule. Option 2 is the more honest architecture; it's also a
non-trivial refactor and might lose the flexibility that made the
v1 model viable.

We picked option 1 for v1. We're naming the tradeoff here so the
write-up handles it honestly either way.

---

## Closing

If you're reading this as research toward your own multi-agent system,
the unifying theme: **prefer mechanical, durable, simple over
ceremonial, message-based, clever**. Every load-bearing decision above
chose the first column. Every one cost us something specific -- spawn
overhead, lost cycle history on resume, the inline-skill instrumentation
blind spot, the SKILL.md fragility. None of those costs were
deal-breakers; all of them were predictable. That's the test for a good
architectural tradeoff: not "is it free?" but "is the cost bounded and
visible?"

For protocol details (how agents communicate, complete tasks, escalate,
time out, use Monitor), see [HANDBOOK.md](../HANDBOOK.md). For the
design rationale and file reference, see
[ARCHITECTURE.md](ARCHITECTURE.md).
