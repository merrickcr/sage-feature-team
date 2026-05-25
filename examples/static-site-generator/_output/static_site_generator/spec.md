# Feature: static_site_generator_v0_1

## Overview

A tiny static site generator (`ssg`) for a personal Markdown notes site, small enough to read end-to-end in an hour. v0.1 delivers three separable, progressively-verifiable feature areas: (1) a **build pipeline** that turns flat `content/*.md` files into a `dist/` of HTML pages plus an index; (2) **content organization** adding `tags` and `draft` front-matter handling on top of the parser; and (3) a **local preview** `serve` command that exposes `dist/` over HTTP via `http.server`. It is a small Python 3.10+ package (`src/ssg/`), invokable via `python -m ssg`, fully tested with pytest, with no dependencies beyond the standard library plus a Markdown library (`markdown-it-py`) and PyYAML, and zero config.

## Requirements

### Feature area 1 — Build pipeline (EPIC-1, foundational)
- Author content as flat `content/*.md` files (no recursion in v0.1) with optional `---`-delimited YAML front-matter. Recognized fields at this layer: `title` (string) and `date` (ISO `YYYY-MM-DD`). Other fields are silently ignored.
- `python -m ssg build` reads every `*.md` in `./content/`, parses front-matter, converts the body Markdown to HTML, wraps each page in a built-in HTML template (title, date, body), and writes `./dist/<basename>.html`.
- Generate `./dist/index.html` listing all pages, sorted by date descending; pages without a date sort last, alphabetically by title. Each index entry shows the title (linked to the post page) and the date if present.
- Print exactly `built N pages in <ms>ms` to stdout on success.
- If `./dist/` exists, wipe and recreate it. Never delete anything outside `dist/`.
- The build is idempotent: running twice on unchanged content produces byte-identical `dist/` output.

### Feature area 2 — Content organization (EPIC-2, depends on EPIC-1)
- A post may declare `tags: [foo, bar]` in front-matter. For each unique tag across published posts, generate `dist/tags/<slug>.html` listing every post carrying that tag, sorted by date descending (same rule as the main index). Slug = tag lowercased with non-alphanumeric characters replaced by `-`.
- The main `dist/index.html` gains a "Tags" section listing each tag with its post count, linking to the tag page. Each post's HTML page displays its tags, each linked to the corresponding tag page.
- A post may declare `draft: true`. By default drafts are excluded entirely (no page, no index entry, no tag-page entry). `python -m ssg build --include-drafts` includes them and prefixes their title with `[DRAFT]` on the index, on tag pages, and in the post page's `<title>` and H1.
- Slugification is a single shared function used for both post filenames and tag slugs.

### Feature area 3 — Local preview (EPIC-3, depends on EPIC-1)
- `python -m ssg serve` verifies `./dist/` exists and is non-empty (else exit nonzero with `dist/ is empty — run 'python -m ssg build' first`), serves `./dist/` over HTTP via `http.server` bound to `127.0.0.1:8000` by default, logs each request to stdout as `GET /hello.html 200`, and runs until Ctrl-C, then prints `stopping` and exits cleanly (finishing any in-flight request).
- `--port <N>` overrides the default port. `--port 0` picks any available port and prints the chosen one.

## Resolved open questions

1. **Error reporting style → (a) abort immediately on the first failing file.** Rationale: every named edge case in the PRD ("Fail with a clear error naming the file") already specifies fail-fast semantics; choosing (b) skip-and-continue would contradict those edge cases and add per-file error-aggregation machinery that v0.1 doesn't need. Fail-fast is simplest and most testable, and the error message names the offending file.
2. **Markdown library → `markdown-it-py`.** Rationale: PRD default; more actively maintained and CommonMark-compliant.
3. **"No posts yet" index page → hard requirement, always produced.** Rationale: PRD preference; an empty `dist/` with no `index.html` is confusing and would also break `serve`'s non-empty check for a legitimately-empty site.
4. **Tag URL format → `dist/tags/<slug>.html`.** Rationale: PRD preference; simpler directory layout, easier to reason about collisions with post filenames at the top level.
5. **Serve `--port` flag → included.** Rationale: PRD preference; trivial cost and "default port is taken" is a real first-five-minutes failure mode. `--port 0` (pick-any-free) is included as part of this.

## Edge Cases

### Build pipeline
- No `content/` directory → fail nonzero with a clear message telling the user to create one.
- Empty `content/` directory → succeed; produce `dist/index.html` saying "No posts yet."
- Markdown file with no front-matter → title = filename with dashes→spaces, title-cased; no date.
- Markdown file with malformed front-matter (invalid YAML) → fail nonzero, error names the file.
- Front-matter present but empty body → page with title and date, empty body; do not fail.
- Front-matter with unexpected fields (e.g. `author`) → ignore silently.
- Markdown body with raw HTML → pass through unsanitized (conventional Markdown behavior).
- Filename collisions on case-insensitive filesystems (`Hello.md` vs `hello.md`) → not solved in v0.1; documented constraint (see Future considerations).
- Idempotency → two consecutive builds on unchanged content produce byte-identical `dist/`.

### Content organization
- `tags: foo` (string not list) → fail nonzero, error names the file (e.g. "tags must be a list, got string").
- Tag with special characters (`c++`, `node.js`) → slugify aggressively (`c++`→`c-`, `node.js`→`node-js`); tags slugifying to the same value share one tag page.
- `draft: true` post with tags → excluded by default (its tags don't appear in listings/counts); included with `--include-drafts`.
- `draft: "true"` (string) → truthy strings `true`/`yes`/`1` → boolean true; `false` → false; any other string → fail loudly naming the file.
- `tags: []` on every post → build succeeds; no `dist/tags/` directory; index's Tags section omitted entirely (not an empty heading).
- All posts are drafts and `--include-drafts` not set → same as empty content: index says "No posts yet."

### Local preview
- `dist/` doesn't exist → fail nonzero with `dist/ is empty — run 'python -m ssg build' first`.
- `dist/` exists but empty → same failure.
- Port already in use → fail nonzero with a clear message naming the port and suggesting `--port`.
- `--port 0` → bind to an OS-chosen free port and print the chosen port number.
- Ctrl-C while a request is in flight → finish the in-flight request, then exit cleanly.

## Technical Notes

- **Language:** Python 3.10+, PEP 8, type hints on every public function.
- **Layout:** code in `src/ssg/`, tests in `tests/`, invokable via `python -m ssg`. Suggested module split (per `docs/conventions.md`, Developer may adjust): `parser.py` (front-matter + Markdown→HTML), `renderer.py` (template wrapping), `builder.py` (directory walk, dist writes, index), `__main__.py` (CLI). Add `serve.py` for feature area 3 and `errors.py` / a shared `slugify` location as needed. Keep each module under ~150 lines.
- **Errors (per `docs/conventions.md`):** raise specific exceptions (`ValueError`, `FileNotFoundError`, or a custom class in `errors.py`); never bare `Exception`. Library modules under `src/ssg/` (everything except `__main__.py`) MUST NOT print — they raise; the CLI decides what to render. `__main__.py` is the only place that prints; failures go to stderr naming the file and exit nonzero.
- **CLI output:** success summary on stdout is exactly `built N pages in <ms>ms` (exact format, PRD requirement).
- **Dependencies:** `markdown-it-py` (Markdown→HTML), PyYAML (front-matter), `http.server` from the standard library (serve). No web framework, no async, no concurrency.
- **Template:** built into the code (Python string constant or shipped template file); a tiny inline `<style>` block is fine. Users cannot supply their own template in v0.1. HTML need only render correctly in a browser, not validate strictly.
- **Slug consistency:** one shared slugification function used for both post filenames and tag slugs; defined once, tested once, reused everywhere.
- **Testing (per `docs/testing.md`):** pytest only; tests in `tests/`; files named `test_<area>.py`. Every test function name is prefixed with its story, e.g. `test_story_1_parses_simple_frontmatter` (Tester filters via `pytest -k "story_<N>"`). Shared fixtures in `tests/conftest.py`; content trees in `tests/fixtures/` (`minimal/`, `sample_site/`, `expected_dist/`). Snapshot/e2e: full `python -m ssg build` against `sample_site/` diffed against `expected_dist/`; the e2e test runs build twice and asserts byte-identical output. Serve tests bind to port 0 and read back the chosen port; assert on response status/body, not log format; never depend on a fixed port being free.
- **Verification structure:** the three epics are verification checkpoints, not release gates. v0.1 ships when all three are VERIFIED, but each area is independently testable so a regression is localized. EPIC-2 and EPIC-3 each depend on EPIC-1 being VERIFIED; EPIC-2 and EPIC-3 are independent of each other.

## Future considerations (explicitly out of scope for v0.1 — revisit in v0.2)

- Themes, multiple templates, template inheritance; user-supplied templates.
- Asset pipelines (CSS bundling, image optimization, JS handling).
- Live reload / file watching / WebSocket auto-refresh for `serve` (v0.1 `serve` is plain `http.server`).
- RSS feeds, sitemaps, search.
- Nested directories under `content/` (v0.1 is flat-only).
- Scheduled publishing or any status workflow beyond the `draft` boolean.
- Multi-language / i18n; comments or any dynamic features.
- Any configuration file (v0.1 is zero-config).
- Filename collisions on case-insensitive filesystems — documented constraint, not solved in v0.1.
- Skip-and-continue / aggregated multi-file error reporting (v0.1 aborts on the first failing file).
