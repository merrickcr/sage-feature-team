# Verification: EPIC-3

Verified at: 2026-05-24T23:46:05Z
Verifier: EpicVerifier-EPIC-3
Stories in scope: STORY-6, STORY-7, STORY-8

## Preconditions
- All stories DONE: yes
- All AC implementation maps verified: yes

(via `python -X utf8 .sage/_tools/verify_epic.py --feature static_site_generator --epic EPIC-3` — `success: true`, `all_done: true`, `ac_maps_verified: true`.)

## Cross-story regression
- Epic-scoped selector: `-k "story_6 or story_7 or story_8"`
- Epic-scoped tests run: 11
- Epic-scoped tests passed: 11
- Epic-scoped tests failed: 0

## Full regression (EPIC-1 + EPIC-2 + EPIC-3)
- Command: `python -m pytest tests/ -v --tb=short`
- Tests run: 79
- Tests passed: 79
- Tests failed: 0

No EPIC-1 (story_1–story_3) or EPIC-2 (story_4–story_5) regressions: all 35 prior-epic tests pass unchanged.

## End-to-end / idempotency
- Command: `python -m pytest tests/test_e2e.py -v --tb=short`
- 3/3 passed, including `test_story_3_build_is_idempotent_byte_identical` (build twice, byte-identical dist/) and `test_story_3_e2e_matches_expected_dist_snapshot`.

## Epic acceptance
```
`python -m ssg serve` serves dist/ on 127.0.0.1:8000; --port overrides; --port 0
picks and prints a free port; a missing or empty dist/ exits nonzero with the
exact message; a busy port fails with a clear message naming the port. Serve adds
no modifications to EPIC-1 or EPIC-2 code paths (verified by those epics' tests
still passing unchanged).
```

Satisfied: yes

Notes:
- Default bind 127.0.0.1:8000 — `src/ssg/serve.py:18-19` (`DEFAULT_HOST`, `DEFAULT_PORT`), bound in `make_server` (`src/ssg/serve.py:66`); covered by AC35.
- `--port` override — `src/ssg/__main__.py:43-46` (`_parse_port`) feeds `serve_dist`; covered by AC37.
- `--port 0` picks/prints free port — `make_server` passes port through to `HTTPServer`; `announce` prints `server.server_address[1]` at `src/ssg/__main__.py:59-64`; covered by AC38.
- Missing/empty dist → nonzero with exact message — `_validate_dist` raises (`src/ssg/serve.py:42-46`); `__main__` prints `DIST_EMPTY_MSG = "dist/ is empty — run 'python -m ssg build' first"` and returns 1 (`src/ssg/__main__.py:20,71-73`); covered by AC39/AC40.
- Busy port → clear message naming the port and suggesting --port — `OSError` caught, prints `port {port} is already in use — try a different --port` (`src/ssg/__main__.py:74-78`); covered by AC41.
- No EPIC-1/EPIC-2 modification — `serve.py` is a self-contained new module; `__main__.py` imports only `serve_dist`/`DEFAULT_PORT` and dispatches `serve` to `_run_serve`, which never calls `build_site`. Confirmed empirically by all 35 prior-epic tests + e2e idempotency passing unchanged.
- Clean shutdown finishing in-flight request (AC36) — `serve_dist` serves on a worker thread, waits on a stop event set by a SIGINT/SIGBREAK handler, then `server.shutdown()` lets the in-flight request finish before stopping (`src/ssg/serve.py:89-114`).
