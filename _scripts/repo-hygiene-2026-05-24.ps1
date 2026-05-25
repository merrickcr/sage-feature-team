# Repo hygiene pass for sage-feature-team v1 write-up prep.
# Run from the repo root in PowerShell:
#   cd C:\Users\merri\claudeProjects\sage-feature-team
#   .\_scripts\repo-hygiene-2026-05-24.ps1
#
# This script makes TWO commits:
#   1. Hygiene: line endings, gitignore, scratch doc removal, config cleanup
#   2. Reference artifact: the static-site-generator end-to-end run under runs/2026-05-24/
#
# Review each section before running. The PAUSE after each commit lets you
# inspect with `git show HEAD` before continuing.

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot\..

Write-Host "===== STEP 0: clear stale .git/index.lock from sandbox renormalize =====" -ForegroundColor Cyan
Remove-Item -Force .git\index.lock -ErrorAction SilentlyContinue

Write-Host "===== STEP 1: lock line endings via local config =====" -ForegroundColor Cyan
# .gitattributes is the durable repo-wide fix (already written by Claude).
# This local config makes the next commit normalize cleanly.
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

Write-Host "===== STEP 4: stage everything (renormalize handles line endings) =====" -ForegroundColor Cyan
git add .gitattributes
git add --renormalize .
git add -u
git add .

Write-Host "===== STEP 5: sanity check what is about to be committed =====" -ForegroundColor Cyan
git status --short
Write-Host ""
git diff --cached --stat

Write-Host ""
Write-Host "Press Enter to make commit #1 (hygiene), or Ctrl-C to abort." -ForegroundColor Yellow
Read-Host

git commit -m @"
Repo hygiene: lock line endings to LF, drop scratch docs, harden gitignore

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
- Add RENDERED_DIRNAME + write_rendered_prompts() in _tools/load_agents.py
  (and its bundled mirror): persist rendered prompts to .sage/.rendered/
  for inspection, gitignored.
- README + sage-config.yaml: chatbot -> static-site-generator references.
"@

Write-Host ""
Write-Host "===== HYGIENE COMMIT MADE. Inspect with: git show HEAD =====" -ForegroundColor Green
Write-Host ""

Write-Host "===== STEP 6: snapshot the static-site-generator run under runs/2026-05-24/ =====" -ForegroundColor Cyan
$srcRun = 'examples\static-site-generator\_output\static_site_generator'
$destRun = 'examples\static-site-generator\runs\2026-05-24\static_site_generator'

if (-not (Test-Path $srcRun)) {
    Write-Host "ERROR: $srcRun not found. Did the run get deleted?" -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path $destRun | Out-Null
Copy-Item -Recurse -Force "$srcRun\*" $destRun
Write-Host "  copied run to $destRun"

git add examples/static-site-generator/runs/

Write-Host "===== STEP 7: sanity check the run artifacts =====" -ForegroundColor Cyan
git status --short
Write-Host ""
git diff --cached --stat | Select-Object -Last 10

Write-Host ""
Write-Host "Press Enter to make commit #2 (run artifacts), or Ctrl-C to abort." -ForegroundColor Yellow
Read-Host

git commit -m @"
Add static-site-generator end-to-end run as reference artifact

First full sage-feature-team run against the bundled example:
  - 8 stories: all DONE
  - 3 epics: all VERIFIED
  - Total cost: ~$22.08 (cache hit 85.5%)

Committed under examples/static-site-generator/runs/2026-05-24/ so a reader
can see what a successful run produces without installing anything (per the
v1 write-up TODO checklist).

Includes spec.md, epics/, stories/ (YAML + implementation.md sidecars),
verification/EPIC-{1,2,3}.md, tokens.{md,json}, progress.md, and the raw
.gateA log file. The live _output/ is intentionally left untracked so
future re-runs do not dirty the working tree.
"@

Write-Host ""
Write-Host "===== BOTH COMMITS MADE =====" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps (NOT automated):" -ForegroundColor Yellow
Write-Host "  - Inspect: git log --oneline -5"
Write-Host "  - Push:    git push origin master"
Write-Host "  - Open follow-up question: should **/_output/ go into .gitignore so future"
Write-Host "    runs do not appear as 'untracked' noise? (Recommended yes, but defer until"
Write-Host "    you have decided whether runs/ snapshots replace _output/ as the artifact"
Write-Host "    store, or if both should coexist.)"
