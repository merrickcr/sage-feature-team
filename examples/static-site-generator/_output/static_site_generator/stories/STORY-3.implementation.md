# STORY-3 Implementation Map

Last updated: 2026-05-24 by Developer (cycle 1)

## AC12 ("one <basename>.html per source + index, stdout 'built N pages in <ms>ms'")
Implemented in:
- src/ssg/builder.py:79 (`build_site` -- `content_dir.glob("*.md")`, sorted, walks `./content/` flatly with no recursion)
- src/ssg/builder.py:84 (`build_site` -- loops sources, calls `parse_post`, records each `_Entry` with `basename = source.stem`)
- src/ssg/builder.py:91 (`build_site` -- writes `dist/<basename>.html` via `render_page` for every entry, mapping `content/hello-world.md` -> `dist/hello-world.html`)
- src/ssg/builder.py:95 (`build_site` -- writes `dist/index.html` in addition to the per-page files)
- src/ssg/builder.py:97 (`build_site` -- returns `len(entries)`, the source-page count excluding the index)
- src/ssg/__main__.py:30 (`main` -- captures the returned page count and prints the single line `built {page_count} pages in {elapsed_ms}ms` to stdout)
- src/ssg/__main__.py:38 (`main` -- `print(f"built {page_count} pages in {elapsed_ms}ms")`, the exact PRD summary format)

## AC13 ("index sorted by date desc, date-less last alpha, title linked + date when present")
Implemented in:
- src/ssg/builder.py:110 (`_sorted_for_index` -- partitions into dated/date-less, sorts dated by `post.date` descending, sorts date-less by `post.title.lower()`, returns dated followed by date-less)
- src/ssg/builder.py:104 (`_render_index` -- iterates `_sorted_for_index(entries)` to emit the `<li>` items in order)
- src/ssg/builder.py:123 (`_index_line` -- builds `<li><a href="<basename>.html">title</a>...`, linking the escaped title to its page)
- src/ssg/builder.py:127 (`_index_line` -- appends `<span class="date">...</span>` only `if entry.post.date is not None`, so the date shows only when present)

## AC14 ("no ./content/ -> nonzero exit, stderr says create a content/ directory")
Implemented in:
- src/ssg/builder.py:73 (`build_site` -- `if not content_dir.is_dir():` raises `FileNotFoundError` whose message names the missing path and tells the user to create a `content/` directory)
- src/ssg/__main__.py:34 (`main` -- catches `FileNotFoundError`, prints the message to `sys.stderr`, and returns exit code 1; no `dist/` is created because the raise happens before any write)

## AC15 ("empty ./content/ -> exit zero, index contains 'No posts yet.'")
Implemented in:
- src/ssg/builder.py:79 (`build_site` -- an empty `content/` yields an empty `sources`/`entries` list; the directory exists so no error is raised)
- src/ssg/builder.py:102 (`_render_index` -- `if not entries:` branch emits `<p>No posts yet.</p>` as the index body)
- src/ssg/builder.py:43 (`NO_POSTS_MESSAGE = "No posts yet."` constant inserted into that body)
- src/ssg/__main__.py:38 (`main` -- returns 0 and prints `built 0 pages in <ms>ms` for the empty-but-present directory)

## AC16 ("malformed front-matter -> nonzero exit, stderr names the file, no partial dist/")
Implemented in:
- src/ssg/builder.py:84 (`build_site` -- parses every source in the loop BEFORE the `dist/` wipe at src/ssg/builder.py:88, so a parse failure aborts before any output is written)
- src/ssg/builder.py:85 (`build_site` -- `parse_post(source)` raises `FrontMatterError` on invalid YAML; the message from src/ssg/parser.py names the offending file)
- src/ssg/__main__.py:34 (`main` -- catches `FrontMatterError`, prints the file-naming message to `sys.stderr`, returns exit code 1, and prints no success summary)

## AC17 ("pre-existing ./dist/ wiped and recreated -- stale files absent afterward")
Implemented in:
- src/ssg/builder.py:88 (`build_site` -- `if dist_dir.exists(): shutil.rmtree(dist_dir)` removes the whole `dist/` tree, then `dist_dir.mkdir(parents=True)` recreates it empty, so any stale file not derived from current content is gone)
- src/ssg/builder.py:71 (`build_site` -- `dist_dir = root / DIST_DIRNAME`; only this `dist/` path is removed, so sibling files outside `dist/` and the `content/` tree are never touched)

## AC18 ("two consecutive builds produce byte-identical dist/ output")
Implemented in:
- src/ssg/builder.py:133 (`_write_file` -- opens with `encoding="utf-8", newline="\n"`, forcing LF + UTF-8 so output bytes do not vary by platform default)
- src/ssg/builder.py:79 (`build_site` -- `sorted(content_dir.glob("*.md"))` gives a deterministic source order each run)
- src/ssg/builder.py:110 (`_sorted_for_index` -- a total deterministic ordering of index entries, identical across runs for the same content)
- src/ssg/renderer.py:38 (`render_page` -- pure, timestamp-free page rendering, so per-page bytes are stable across runs)

## AC19 ("build against tests/fixtures/sample_site/ matches tests/fixtures/expected_dist/ byte-for-byte")
Implemented in:
- src/ssg/builder.py:56 (`build_site` -- the full pipeline: parse + `render_page` each source to `dist/<basename>.html`, plus the index, producing the same file set as the snapshot)
- src/ssg/builder.py:23 (`_INDEX_TEMPLATE` -- the index document template whose head/style/`<h1>Index</h1>`/`<ul>` markup matches tests/fixtures/expected_dist/index.html exactly)
- src/ssg/builder.py:123 (`_index_line` -- emits each `<li>` exactly as the snapshot index lists them: title anchor plus optional `<span class="date">`)
- src/ssg/builder.py:133 (`_write_file` -- LF + UTF-8 writes so produced bytes equal the LF-newline fixture files)
- Verified by ad-hoc smoke build per docs/build_run.md: produced dist/ was byte-identical to tests/fixtures/expected_dist/ for all five files
