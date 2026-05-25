# EPIC-2 Verification — Content organization (tags and drafts)

**Status:** VERIFIED
**Feature:** static_site_generator
**Stories in scope:** STORY-4 (tags), STORY-5 (drafts)
**Verified:** 2026-05-24

## 1. Preconditions gate

`python -X utf8 .sage/_tools/verify_epic.py --feature static_site_generator --epic EPIC-2`

- `success: true`
- `all_done: true` (STORY-4 and STORY-5 both DONE)
- `ac_maps_verified: true`, `failed_stories: []`

## 2. Regression

- **EPIC-2 cross-story** (`pytest tests/ -k "story_4 or story_5" -v`): 35 passed, 0 failed.
  - test_tags.py: 15 tests (STORY-4)
  - test_drafts.py: 20 tests (STORY-5)
- **Full suite** (`pytest tests/ -v`): **79 passed, 0 failed.** No cross-epic regressions — EPIC-1 (story_1/2/3) and EPIC-3 (story_6/7/8) tests all still green after EPIC-2.

## 3. Idempotency check (PRD requirement)

Per docs/build_run.md: built the sample fixture twice into separate dist trees and `diff -r` between them.

- Both builds: `built 4 pages in <ms>ms`
- `diff -r first dist` produced **no output** → byte-identical, idempotent.
- Also covered by `tests/test_e2e.py::test_story_3_build_is_idempotent_byte_identical` (passing) and the `expected_dist` byte-for-byte snapshot test (passing).

## 4. Epic-level acceptance (beyond per-story AC)

Verified the cross-story behaviors described in EPIC-2's acceptance block via live `python -m ssg build` runs on a tagged + draft content set:

- **Tag pages:** unique tags each produce `dist/tags/<slug>.html`.
- **Index Tags section:** `<h2>Tags</h2>` lists each tag with post count and links to its page.
- **Per-post tag display:** post pages link each of their tags to the corresponding tag page.
- **Draft exclusion by default:** `draft: true` post produced no page, was absent from index, and did not inflate its tag's count (python count = 1 with one draft + one published).
- **`--include-drafts` + `[DRAFT]` marker:** draft page generated; `[DRAFT]` prefix present on the index entry, on the tag-page entry, and in the post's `<title>` and `<h1>`.
- **Cross-story slugify agreement (the named cross-story requirement):** a single shared `slugify` is defined in `src/ssg/parser.py:79` and imported by both `src/ssg/builder.py` (tag page filenames, line 157) and `src/ssg/renderer.py` (tag link hrefs, line 72). So post basenames and tag slugs derive from the same function. Confirmed by `test_story_4_cpp_and_cdashdash_share_one_tag_page` (tags `c++`/`c--` collapse to one page).

## 5. Notes for reviewers

- The sample_site e2e fixture carries no tags, so `dist/tags/` is absent for that fixture by design (AC24: no tag dir when no tags) — tag/draft behavior is exercised by the dedicated unit/integration tests and confirmed manually here.
- Environment: Python 3.14.3, pytest 9.0.3, win32. Builds run with `PYTHONUTF8=1`; output is LF-newline and byte-stable across runs.
