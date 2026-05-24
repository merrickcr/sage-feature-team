# Testing conventions (`ssg`)

## Framework

- pytest, no other test framework.
- Tests live in `tests/` at the project root.
- File naming: `test_<area>.py` — e.g. `test_parser.py`, `test_renderer.py`, `test_builder.py`, `test_e2e.py`.

## Story-scoped test naming (Sage convention)

Every test function name starts with the story it belongs to:

```python
def test_story_1_parses_simple_frontmatter():
    ...

def test_story_3_index_sorts_by_date_desc():
    ...
```

Why: Sage's Tester runs story-scoped via `pytest -k "story_<N>"`. The name prefix is the filter. No pytest markers, no `pyproject.toml` registration — vanilla pytest works.

If a test legitimately covers behavior owned by multiple stories (rare; almost only at the integration/e2e boundary), prefix with the higher-numbered story and name the others in the docstring.

## Test commands

- **Story-scoped (Tester worker default):** `python -m pytest tests/ -k "story_<N>" -v --tb=short`
- **Full regression (EpicVerifier):** `python -m pytest tests/ -v --tb=short`
- **Single test by name:** `python -m pytest tests/ -k "<substring>" -v`

## Fixtures

- Shared fixtures in `tests/conftest.py`.
- Sample content trees in `tests/fixtures/`:
  - `tests/fixtures/minimal/` — one `.md` file, used by parser unit tests.
  - `tests/fixtures/sample_site/` — multi-page content with mixed front-matter (with/without dates, with/without front-matter at all). Used by integration and e2e tests.
  - `tests/fixtures/expected_dist/` — snapshot of expected `dist/` output for `sample_site/`. Updated deliberately when behavior changes; reviewed in diffs.

## What kinds of tests to write

- **Unit:** small pure functions in isolation (front-matter parsing, slug derivation, date sort).
- **Integration:** one layer's public API against a fixture (e.g. parser against a real fixture file).
- **End-to-end (EpicVerifier scope):** full `python -m ssg build` against `tests/fixtures/sample_site/`, diff against `tests/fixtures/expected_dist/`.

Per the PRD, the build must be idempotent. The e2e test runs the build twice and asserts byte-identical output across runs.
