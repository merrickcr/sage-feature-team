# STORY-2 Implementation Map

Last updated: 2026-05-24 by Developer (cycle 1)

## AC8 ("complete document with title in <title> and <h1>, date, and body")
Implemented in:
- src/ssg/renderer.py:18 (`_PAGE_TEMPLATE` -- standalone `<!DOCTYPE html>` document with `<title>{title}</title>`, `<h1>{title}</h1>`, the date paragraph, and the `{body}` region)
- src/ssg/renderer.py:42 (`render_page` -- escapes the title, builds the date markup, and formats it into the template, returning the full document)

## AC9 ("title but no date -> no date markup, no error")
Implemented in:
- src/ssg/renderer.py:43 (`render_page` -- `if post.date is not None` branch; when `post.date` is `None`, `date` is set to the empty string at src/ssg/renderer.py:46, so no date markup is emitted)
- src/ssg/renderer.py:48 (`render_page` -- title still formatted into `<title>` and `<h1>` regardless of date)

## AC10 ("empty body still renders a complete document, no error")
Implemented in:
- src/ssg/renderer.py:48 (`render_page` -- the `{body}` field accepts an empty/whitespace `post.html`; the surrounding `<!DOCTYPE html>`/`<html>`/`<title>`/`<h1>` structure in `_PAGE_TEMPLATE` at src/ssg/renderer.py:18 is unconditional, so the document is always complete and `.format` never raises on an empty body)

## AC11 ("renderer is deterministic -- byte-identical across runs")
Implemented in:
- src/ssg/renderer.py:18 (`_PAGE_TEMPLATE` -- a static module-level string constant with no timestamps or run-dependent content)
- src/ssg/renderer.py:48 (`render_page` -- output is a pure function of `post.title`, `post.date`, and `post.html` via `str.format`, so two calls on the same post produce identical bytes)
