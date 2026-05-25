# PRD: Static Site Generator (`ssg`) — v0.1

## Background

I want a tiny static site generator I can use for a personal notes site. Everything off-the-shelf (Jekyll, Hugo, Eleventy, Astro) is overkill — I want something I can read end-to-end in an afternoon, modify confidently, and that has exactly the features I need and nothing else.

This is v0.1. It covers three small, separable feature areas that together get me to "I can write notes in Markdown, organize them, and preview the site locally before deploying anywhere." Each area is independently valuable, and they build on each other in a clear order so we can ship and verify them progressively.

## Goals

This v0.1 covers three feature areas. Each delivers value on its own.

**Build pipeline — foundational, must ship first.**
- A user can author content as plain Markdown files in `content/` with optional YAML front-matter.
- A user can run `python -m ssg build` and get a `dist/` directory with one HTML page per Markdown file plus an index.
- A user can open `dist/index.html` in a browser and have it work.

**Content organization — independently valuable, depends on build pipeline.**
- A user can tag posts in front-matter (`tags: [foo, bar]`) and get per-tag listing pages alongside the main index.
- A user can mark posts as drafts (`draft: true`) and have them excluded from the published build, with an opt-in flag to include them.

**Local preview — independently valuable, depends on build pipeline.**
- A user can run `python -m ssg serve` to view the built site over HTTP without deploying anywhere.

These three areas are intentionally separable. After the build pipeline ships, the site is fully usable for a single-page-per-post site without categorization or local preview — it just produces HTML files. Tags and serve layer on top without disrupting the underlying build.

The generator should be a small Python package, fully tested with pytest, no networking outside the optional `serve` command, no external services beyond the standard library plus a Markdown library and PyYAML. A reader looking at the source should be able to understand the whole thing in under an hour.

## Non-goals (explicitly out of scope for v0.1)

- Themes, multiple templates, or template inheritance
- Asset pipelines (CSS bundling, image optimization, JS handling)
- **Live reload** specifically (the `serve` command is plain `http.server`; no file watching, no auto-refresh)
- RSS feeds, sitemaps, search
- Nested directories under `content/` (flat layout only for v0.1)
- Scheduled publishing or any status workflow beyond the `draft` boolean
- Multi-language / i18n
- Comments or any dynamic features
- Any configuration file — v0.1 should work with zero config

We will revisit any of these in v0.2 if v0.1 ships cleanly.

---

## Feature area 1: Build pipeline

### Content authoring

A user creates files like `content/hello-world.md`:

```markdown
---
title: Hello, world
date: 2026-05-24
---

This is my first post. It supports **markdown**, including:

- Lists
- `inline code`
- [Links](https://example.com)
```

The front-matter block is optional and is delimited by `---` lines. The recognized fields for the build pipeline are `title` (string) and `date` (ISO `YYYY-MM-DD`). Other fields are silently ignored at this layer — content organization adds `tags` and `draft` later. Users can add their own metadata without breaking the build.

### Build command

The user runs:

```
python -m ssg build
```

…from the project root. The command:

1. Reads every `*.md` file in `./content/` (flat — no recursion in v0.1).
2. Parses each one: extracts front-matter, converts the body Markdown to HTML.
3. Wraps each page in a built-in HTML template that includes the title, date, and body.
4. Writes the result to `./dist/<basename>.html` (so `content/hello-world.md` produces `dist/hello-world.html`).
5. Generates `./dist/index.html` listing all pages, sorted by date descending. Pages without a date sort last, alphabetically by title.
6. Prints a one-line summary: `built N pages in <ms>ms`.

If `./dist/` already exists, it is wiped and recreated. The user should never lose work because we deleted something — but `dist/` is build output, not user content.

### Output

The HTML should be valid enough that a browser renders it correctly. It does not need to validate against strict HTML5, and it does not need to be styled prettily — a tiny inline `<style>` block in the template is fine. The point of v0.1 is "it works," not "it's pretty."

The index page should show, for each post: the title (linked to the post's HTML page) and the date if present.

### Build pipeline edge cases

- **No `content/` directory.** Fail with a clear error message telling the user to create one.
- **Empty `content/` directory.** Succeed; produce an `index.html` that says "No posts yet."
- **Markdown file with no front-matter.** Use the filename (with dashes converted to spaces, title-cased) as the title; no date.
- **Markdown file with malformed front-matter (e.g. invalid YAML).** Fail with a clear error naming the file. Don't try to be clever.
- **Markdown file with front-matter but no body.** Produce a page with just the title and date, empty body. Don't fail.
- **Filename collisions** (e.g. `Hello.md` and `hello.md` on a case-insensitive filesystem) — not worth solving in v0.1; we can document the constraint.
- **Front-matter has unexpected fields** (e.g. `author`). Ignore them silently; don't fail. (`tags` and `draft` are recognized once feature area 2 ships.)
- **Markdown body contains raw HTML.** Allow it through. This is the conventional Markdown behavior and we don't need to sanitize for v0.1.
- **The build is idempotent.** Running it twice with no content changes produces byte-identical `dist/` output.

---

## Feature area 2: Content organization

This area adds two recognized front-matter fields (`tags` and `draft`) and the build-time behavior that goes with them. It builds on the parser established in feature area 1.

### Tags

A post can declare tags as a list in front-matter:

```markdown
---
title: First Python post
date: 2026-05-24
tags: [python, learning]
---
```

When the build runs:

- For each unique tag across all posts, generate a tag page at `dist/tags/<slug>.html` listing every post that carries that tag, sorted by date descending (same rule as the main index). The slug is the tag lowercased with non-alphanumeric characters replaced by `-`.
- The main `dist/index.html` gains a "Tags" section listing each tag with its post count, linking to the corresponding tag page.
- On each post's HTML page, the post's tags are displayed (each linked to the corresponding tag page).

If a post has no `tags` field or an empty `tags: []` list, it is not listed on any tag page and contributes no entry to the index's Tags section.

### Drafts

A post can declare `draft: true` in front-matter. By default, drafts are excluded from the build entirely — no HTML page, no entry on the index, no entries on tag pages.

`python -m ssg build --include-drafts` includes them and renders their title with a `[DRAFT]` prefix on the index and on tag pages (the post page itself shows the prefix in `<title>` and in the page's H1). This makes the draft-inclusion mode visually obvious so a user doesn't accidentally deploy a draft build.

### Content organization edge cases

- **A post with `tags: foo` (string instead of list).** Fail with a clear error naming the file ("tags must be a list, got string").
- **A post with a tag containing special characters** (e.g. `c++`, `node.js`). Slugify aggressively — `c++` becomes `c-`, `node.js` becomes `node-js`. Multiple posts whose tags slugify to the same value share a tag page.
- **A post with `draft: true` and tags.** The post is excluded by default and so its tags don't appear in the tag listing or counts. With `--include-drafts`, the tag listings include it.
- **A post with `draft: "true"` (string instead of bool).** Treat truthy strings (`true`, `yes`, `1`) as the boolean `true`. Anything else, including `false`, is `false`. Fail loudly on unrecognized strings.
- **`tags: []` on every post.** Build succeeds; no `dist/tags/` directory is created; index's Tags section is omitted (rather than rendered as an empty heading).
- **All posts are drafts and `--include-drafts` is not set.** Same as empty `content/` directory — produce an index that says "No posts yet."

---

## Feature area 3: Local preview

This area adds one new CLI subcommand. It builds on feature area 1's `dist/` output but doesn't touch the build itself.

### Serve command

The user runs:

```
python -m ssg serve
```

…from the project root. The command:

1. Verifies that `./dist/` exists and is non-empty. If not, exit nonzero with `dist/ is empty — run 'python -m ssg build' first`.
2. Serves the contents of `./dist/` over HTTP using `http.server` (standard library), bound to `127.0.0.1` on port 8000 by default.
3. Logs each request to stdout in a compact format: `GET /hello.html 200`.
4. Runs until the user hits Ctrl-C, then prints `stopping` and exits cleanly.

A `--port <N>` flag overrides the default port.

There is no file watching, no rebuild on change, no WebSocket auto-refresh. The user re-runs `build` and refreshes the browser manually. Live reload is a v0.2 consideration.

### Local preview edge cases

- **`dist/` doesn't exist.** Fail with the message above.
- **`dist/` exists but is empty.** Same failure — refuse to serve nothing.
- **Port already in use.** Fail with a clear message naming the port and suggesting `--port`.
- **`--port 0`.** Pick any available port and print the chosen one. (Standard `http.server` behavior; worth supporting because it's the natural way to handle "give me whatever's free.")
- **Ctrl-C while a request is in flight.** Finish the in-flight request, then exit. Don't drop the connection mid-response.

---

## Technical notes

- **Language:** Python 3.10+.
- **Dependencies:** a Markdown library (pick one — `markdown-it-py` is the modern choice, but `markdown` is fine if simpler). PyYAML for front-matter parsing. `http.server` from the standard library for the serve command. No web framework, no async runtime.
- **Layout:** code in `src/ssg/`, tests in `tests/`. The package is invokable via `python -m ssg`. Subcommands (`build`, `serve`) live in their own modules.
- **Testing:** pytest. Snapshot tests are acceptable for "given this markdown, produce this HTML" cases; unit tests for the smaller pieces (front-matter parsing, slug derivation, date sorting, tag slugification). Integration tests per feature area. An end-to-end test for feature area 1 that runs the full build against a fixture content/ directory and compares dist/ against an expected fixture; a similar one for feature area 2 covering tags and drafts.
- **Serve testing.** Use `http.server`'s test hooks or spin up the server in a thread for integration tests; assert on response status and body, not on log format. Don't write tests that depend on a real network port being free — bind to port 0 and read back the chosen port.
- **No async, no concurrency.** Builds are fast enough; complexity isn't justified at this size.
- **The template is built into the code** (a Python string constant or a template file shipped with the package). Users cannot supply their own template in v0.1.
- **Slug consistency.** Both post filenames and tag slugs use the same slugification function. Define it once, test it once, reuse everywhere.

---

## Acceptance criteria (high-level — ProductOwner should refine into per-story testable AC)

The feature is done when:

**Build pipeline:**
- A new user can clone the repo, drop a markdown file into `content/`, run `python -m ssg build`, and see correct HTML in `dist/`.
- All build-pipeline user-facing behaviors above work for their happy paths.
- Each named build-pipeline edge case has either a passing test demonstrating the documented behavior, or a documented decision to defer (with reason).
- Running the build twice on unchanged content produces byte-identical output.

**Content organization:**
- Posts with tags produce tag pages in `dist/tags/`; the index shows a Tags section linking to them; each post's HTML page lists its tags.
- Posts with `draft: true` are excluded by default; `--include-drafts` includes them with a visible `[DRAFT]` marker.
- All content-organization edge cases above have passing tests.

**Local preview:**
- `python -m ssg serve` serves `dist/` on the default port; `--port` overrides; missing `dist/` exits nonzero with a clear message.
- All local-preview edge cases above have passing tests.

**Across feature areas:**
- Tests cover each feature area's integration path end-to-end and the smaller components individually.
- Adding tags/drafts (feature area 2) does not break any feature-area-1 build tests.
- Adding serve (feature area 3) does not modify any feature-area-1 or feature-area-2 code paths.

---

## Open questions for the ProductOwner

These are deliberately not resolved upstream — flagging them so PO either picks a default and notes it in the spec, or escalates for a decision:

1. **Error reporting style.** When a single Markdown file fails to parse, should the build (a) abort immediately, (b) skip that file and continue, reporting all failures at the end, or (c) skip and warn but continue? My weak preference: (b), because in a real authoring session you don't want one bad file to block previewing the rest of the site.

2. **Markdown library choice.** Either `markdown-it-py` or `markdown` is fine; the spec should pick one and note it. If neither library is materially better for our needs, default to `markdown-it-py` (more actively maintained, CommonMark-compliant).

3. **The "no posts yet" index page.** Should this be a hard requirement, or do we just produce an empty `dist/` directory in the empty-content case? My weak preference: produce the page; an empty `dist/` is confusing.

4. **Tag URL format.** Tag pages at `dist/tags/<slug>.html` (flat under a tags directory) or `dist/<slug>/index.html` (clean URLs at the top level)? My weak preference: `dist/tags/<slug>.html` for v0.1 — simpler directory layout, easier to reason about collisions with post filenames.

5. **Serve port flag.** Default 8000 is non-controversial. `--port` adds two lines of code and three test cases. Worth it for v0.1, or defer? My weak preference: include it; the cost is trivial and "the default port is taken" is a real first-five-minutes failure mode.

---

## Phasing note (for ProductOwner)

The three feature areas are deliberately separable so the build pipeline can be verified end-to-end before tags layer on, and tags can be verified before serve. This is a verification-checkpoint structure, not a release-gating one — v0.1 ships when all three are done, but each area should be independently testable so a regression in one is localized and obvious.

That's the v0.1. Keep the scope tight — anything that smells like a v0.2 feature should get noted in a "Future considerations" section of the spec and excluded from the story plan.
