# Repo hygiene pass for sage-feature-team v1 write-up prep.
# Run from the repo root in PowerShell:
#   cd C:\Users\merri\claudeProjects\sage-feature-team
#   .\_scripts\repo-hygiene-2026-05-24.ps1
#
# Makes TWO commits with a manual pause after each one:
#   1. Hygiene: line endings, gitignore, scratch doc removal, config cleanup
#   2. Reference example: commit static-site-generator/ (including _output/) in place

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot\..

Write-Host "===== STEP 0: clear stale .git/index.lock from sandbox renormalize =====" -ForegroundColor Cyan
Remove-Item -Force .git\index.lock -ErrorAction SilentlyContinue

Write-Host "===== STEP 1: lock line endings via local config =====" -ForegroundColor Cyan
# .gitattributes is the durable repo-wide fix (already written).
# This local config makes the next renormalize-and-commit behave correctly.
git config core.autocrlf input

Write-Host "===== STEP 2: delete the 4 scratch docs from repo root =====" -ForegroundColor Cyan
$scratchDocs = @(
    'CHANGE_SUMMARY.md',
    'CHANGES_SUMMARY_PROPOSALS.md',
    'TODO_PHASE_3.md',
    'TODO_COST_OPTIMIZATIONS.md'
)
foreach ($f in $scratchDocs) {
    if (Test-Path $f) {
        Remove-Item -Force $f
        Write-Host "  deleted: $f"
    } else {
        Write-Host "  already gone: $f"
    }
}

Write-Host "===== STEP 3: delete _tmp_<Role>_prompt.txt debug dumps =====" -ForegroundColor Cyan
Get-ChildItem -Path examples\static-site-generator\.sage -Filter '_tmp_*_prompt.txt' -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item -Force $_.FullName
    Write-Host "  deleted: $($_.FullName)"
}

Write-Host "===== STEP 4: stage hygiene + README polish changes (NOT the run artifacts yet) =====" -ForegroundColor Cyan
# Order matters: add .gitattributes first so renormalize applies the new rules.
git add .gitattributes
# Re-stage all tracked files using the new .gitattributes filter (strips CRLF).
git add --renormalize .
# Pick up the deletions (scratch docs).
git add -u
# Explicitly add the new gitignore-related files we modified.
git add .gitignore sage-config.yaml README.md _tools\load_agents.py examples\static-site-generator\.sage\_tools\load_agents.py 2>$null
# New docs/ tree: INSTALL.md, ARCHITECTURE.md, img/ (architecture diagram).
git add docs/

Write-Host "===== STEP 5: sanity check what is about to be committed =====" -ForegroundColor Cyan
git status --short
Write-Host ""
git diff --cached --stat
Write-Host ""
Write-Host "Expected: ~7 files staged (.gitattributes new; .gitignore, README, sage-config.yaml," -ForegroundColor DarkGray
Write-Host "_tools/load_agents.py, examples/.../load_agents.py modified; 4 scratch docs deleted)." -ForegroundColor DarkGray
Write-Host "Run artifacts (examples/static-site-generator/_output/, src/, tests/, etc.)" -ForegroundColor DarkGray
Write-Host "should still appear as untracked in `git status --short` -- that's correct." -ForegroundColor DarkGray
Write-Host ""
Write-Host "Press Enter to make commit #1 (hygiene), or Ctrl-C to abort." -ForegroundColor Yellow
Read-Host

git commit -m @"
Repo polish for v1 write-up: line endings, scratch removal, README upgrades

Hygiene:
- Add .gitattributes locking all text files to LF (prevents future CRLF
  churn on Windows; overrides each contributor's local core.autocrlf).
- Delete CHANGE_SUMMARY.md, CHANGES_SUMMARY_PROPOSALS.md, TODO_PHASE_3.md,
  TODO_COST_OPTIMIZATIONS.md (internal investigation scratch; salvageable
  items will be folded into docs/LESSONS.md ahead of the v1 write-up).
- Delete _tmp_<Role>_prompt.txt debug dumps under
  examples/static-site-generator/.sage/.
- Extend .gitignore: _tmp_*_prompt.txt, .claude/settings.local.json.
- Remove the hardcoded absolute_root_dir from the repo-root sage-config.yaml
  (was carrying a per-user Windows path; the demo driver doesn't need it).

README split + upgrades (write-up prep):
- Add 'What this is, and what it isn't' blockquote at the top (calls out
  Claude Code primitive coupling; lists the portable ideas).
- Add new 'Try a single agent first' section immediately after Quickstart,
  promoting the inline single-agent skills with a concrete /sage-po example.
- Add new 'How it flows' section with a Mermaid flowchart of the full
  pipeline (User -> PO -> spec/epics/stories -> APPROVED -> parallel
  scheduler -> per-story workers -> EpicVerifier -> 3 gates -> VERIFIED).
- Add docs/img/architecture.svg, .png, @2x.png, and .mermaid source.
- Split README into three docs: README stays focused on pitch + Quickstart
  + Use-sage-with-your-own-project + Try-a-single-agent + How-it-flows
  + inline-skills reference + pointers. Install content moves to
  docs/INSTALL.md (prereqs, Phase 1 + Phase 2 install flow centered on
  /sage-install, manual install, diagnostic notes, what-gets-installed
  -where). Architecture content moves to docs/ARCHITECTURE.md (core idea,
  how-a-run-works, state machine + three gates + scheduler model, files
  reference, adding a new agent).
- Bridge the Quickstart to per-project install: new 'Use sage with your
  own project' section in README shows the /sage-install invocation and
  links to INSTALL.md. INSTALL.md retitled to Phase 1 / Phase 2 so the
  per-machine vs per-project distinction is visible at a glance.

Write-up support material:
- Add docs/LESSONS.md (~2500 words). Seven lessons each with concrete
  failure + what-we-did + what-to-take-from-it: YAML as event log /
  killing the SYN-ACK handshake / shutdown_request is the only real
  shutdown / cycle budgets reset on resume (deliberate, not a bug) /
  mechanical eligibility beats LLM scheduling / per-story ephemeral
  workers / token tracking is structurally hard in agentic frameworks.
  Plus an honest 'Open question' section on the SKILL.md-as-state
  -machine tradeoff (v1 picks acknowledge-and-ship; v2 may extract).
- Refresh _tools/README.md: top-of-file user-facing vs internal split
  (caps the public surface explicitly); fixed staleness (EpicVerifier
  in the agent slug table, all 6 SKILL files in the copies table, full
  scaffolded-configs list, current layout with all 14 scripts labelled).
  Added extract_token_usage.py + record_worker_usage.py (previously
  missed in the refresh; both are real and called by every inline skill).

Audit fixes (ship-readiness pass):
- Strip 3,693 null bytes from README.md (Write-tool padding bug).
- Replace broken image refs in README (quickstart-team-panel.png /
  quickstart-output-files.png) with HTML-comment placeholders until
  screenshots exist.
- Fix examples/static-site-generator/sage-config.yaml: remove the
  hardcoded C:\Users\merri\... absolute_root_dir; same treatment as the
  root sage-config.yaml.
- Purge stale 'chatbot' references repo-wide (now uses
  static-site-generator everywhere): CLAUDE.md, sage-config.SCHEMA.md +
  its bundled mirror, .claude/skills/sage-dev-test/SKILL.md,
  .claude/skills/sage-feature-team/SKILL.md, and the SKILL_PATH_REWRITES
  in _tools/setup_project.py (the latter was a real install-time bug:
  the rewrite rules no longer matched the SKILL content, so installed
  projects shipped SKILL files with examples/static-site-generator/.sage/
  paths instead of being rewritten to .sage/).
- Sanitize /Users/merri usage example in _tools/discover_and_record.py
  (and its bundled mirror) to /Users/yourname.
- Add EpicVerifier row to the agent table in sage-config.SCHEMA.md
  (and its bundled mirror); previously missing.

Quickstart restructure (the heaviest-payoff README change in this pass):
- Replace the team-mode '/sage-feature-team' Quickstart with the lighter
  '/sage-po' inline invocation. The previous Quickstart had three issues:
  (a) its example feature ('add a /help command that lists available
  commands') is a fossil from when the bundled example was the chatbot --
  the static-site-generator has no commands; (b) the bundled example is
  already complete (8 stories DONE, 3 epics VERIFIED), so a 'kick off a new
  feature' demo on top of it is conceptually muddy; (c) it drifted from
  the originally-intended on-ramp shape (the write-up TODO said 'invoke
  /sage-po solo against the example', not the heavier team invocation).
- New Quickstart: /sage-po with a sensible feature for the bundled
  example ('Add an RSS feed at /feed.xml listing the 20 most recent posts
  sorted by date'). Same five-minute ceiling. No team panel needed, no
  screenshots required.
- Add a callout pointing at the already-committed end-to-end run as a
  no-install reference for readers who don't want to run anything yet.
- Collapse the prior 'Use sage with your own project' and 'Try a single
  agent first' sections into a single 'Going further' bullet list with
  three next-step paths (more inline skills / team mode / your own project).
- Drop the broken-screenshot HTML-comment placeholders; the new Quickstart
  doesn't reference any images.
- README: 196 lines -> 172 lines.

Loader change (already in the working tree before this pass):
- Add RENDERED_DIRNAME + write_rendered_prompts() in _tools/load_agents.py
  (and bundled mirror): persist rendered prompts to .sage/.rendered/
  for inspection (gitignored).
- README + sage-config.yaml: chatbot -> static-site-generator references.
"@

Write-Host ""
Write-Host "===== HYGIENE COMMIT MADE. Inspect with: git show HEAD =====" -ForegroundColor Green
Write-Host ""

Write-Host "===== STEP 6: stage the static-site-generator example in place =====" -ForegroundColor Cyan
# Adds everything under examples/static-site-generator/ that isn't gitignored.
# Picks up _output/ (the run), src/, tests/, content/, pyproject.toml, PRD.md.
# Skips _tmp_*_prompt.txt and .claude/settings.local.json (now gitignored).
git add examples/static-site-generator/

Write-Host "===== STEP 7: sanity check the run + example artifacts =====" -ForegroundColor Cyan
git status --short
Write-Host ""
git diff --cached --stat | Select-Object -Last 15

Write-Host ""
Write-Host "Press Enter to make commit #2 (reference example), or Ctrl-C to abort." -ForegroundColor Yellow
Read-Host

git commit -m @"
Commit static-site-generator example in place: source + first full sage run

The bundled example now ships with both:
  - The implementation sage produced (src/ssg/, tests/, content/, pyproject.toml, PRD.md)
  - The full run artifacts under examples/static-site-generator/_output/static_site_generator/:
      * spec.md, epics/, stories/ (yaml + implementation.md sidecars)
      * verification/EPIC-{1,2,3}.md
      * tokens.{md,json}, progress.md
      * .gateA log

Result of the first full /sage-feature-team run against the bundled PRD:
  - 8 stories: all DONE
  - 3 epics:   all VERIFIED
  - Total cost: ~`$22.08 (cache hit 85.5%)

Kept at _output/ rather than snapshotted to runs/<date>/ to keep the
example as one self-contained directory a reader can clone, browse, and
re-run.
"@

Write-Host ""
Write-Host "===== BOTH COMMITS MADE =====" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps (NOT automated):" -ForegroundColor Yellow
Write-Host "  - Inspect: git log --oneline -5"
Write-Host "  - Push:    git push origin master   (you'll be 4 commits ahead)"
Write-Host ""
Write-Host "Open follow-up to think about:" -ForegroundColor Yellow
Write-Host "  Re-running sage against this example (e.g. with the v2 PRD) will dirty"
Write-Host "  examples/static-site-generator/_output/ -- the live state will diverge"
Write-Host "  from what's committed. Options:"
Write-Host "    (a) Accept it: commit the new run as 'update reference example' each time"
Write-Host "    (b) Snapshot pattern: copy _output/ to a runs/<date>/ before re-running"
Write-Host "    (c) Gitignore _output/ + copy any future runs to a stable path"
Write-Host "  Defer this until you've actually re-run; the choice depends on cadence."
