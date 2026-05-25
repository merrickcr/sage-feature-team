# STORY-1 Implementation Map

Last updated: 2026-05-24T00:00:00Z by Developer (cycle 1)

The parser layer is implemented across three files:
- `src/ssg/parser.py` — `Post` dataclass, `parse_post`, `slugify`, and private helpers
- `src/ssg/errors.py` — the `FrontMatterError` exception
- `src/ssg/__init__.py` — package marker so `ssg.parser` imports cleanly

## AC1 ("full front-matter: title + date + rendered body")
Front-matter title and date are read from the parsed YAML mapping; the body is
rendered to HTML by the shared markdown-it instance. Dates parsed by PyYAML into
`datetime.date` are normalized back to the ISO string the contract expects.
Implemented in:
- src/ssg/parser.py:38 (`parse_post` reads title/date, renders body)
- src/ssg/parser.py:51 (title field read from front-matter mapping)
- src/ssg/parser.py:57 (date read and normalized)
- src/ssg/parser.py:59 (body rendered to HTML via `_MD.render`)
- src/ssg/parser.py:124 (`_coerce_date` returns ISO string)

## AC2 ("no front-matter: title from filename, date is None")
When the first line is not the `---` delimiter, the whole file is treated as
body and the title is derived from the filename (dashes to spaces, title-cased);
no front-matter means no date, so `date` is None.
Implemented in:
- src/ssg/parser.py:51 (filename fallback when title absent)
- src/ssg/parser.py:80 (`_split_front_matter` returns empty mapping when no delimiter)
- src/ssg/parser.py:133 (`_title_from_filename` dashes to spaces, title-cased)

## AC3 ("unexpected front-matter field ignored")
Only the recognized `title` and `date` keys are read from the front-matter
mapping; every other key (e.g. `author`) is never copied onto the `Post`, so the
post never gains an unexpected attribute.
Implemented in:
- src/ssg/parser.py:51 (only `title` read from mapping)
- src/ssg/parser.py:57 (only `date` read from mapping)
- src/ssg/parser.py:25 (`Post` dataclass declares only title/date/html fields)

## AC4 ("front-matter present, empty body succeeds")
A closing `---` with nothing after it yields an empty body string; rendering an
empty string returns an empty HTML body, and title/date are still populated. No
error is raised in this case.
Implemented in:
- src/ssg/parser.py:90 (`_split_front_matter` returns the post-delimiter remainder as body, empty here)
- src/ssg/parser.py:59 (empty body rendered to empty HTML)

## AC5 ("malformed YAML front-matter raises a specific exception naming the file")
Invalid YAML raises `yaml.YAMLError`, which is caught and re-raised as the
specific `FrontMatterError` whose message includes the file name. A
non-mapping front-matter block is rejected the same way.
Implemented in:
- src/ssg/errors.py:9 (`FrontMatterError` specific exception)
- src/ssg/parser.py:106 (catch YAML error, raise `FrontMatterError` naming the file)
- src/ssg/parser.py:116 (non-mapping front-matter raises `FrontMatterError`)

## AC6 ("raw inline HTML passes through unsanitized")
The shared markdown-it instance is constructed with `html=True`, so raw inline
HTML in the body is emitted verbatim into the rendered output.
Implemented in:
- src/ssg/parser.py:33 (`_MD = MarkdownIt("commonmark", {"html": True})`)
- src/ssg/parser.py:59 (body rendered through that instance)

## AC7 ("shared slugify: lowercase, non-alnum runs to single dash, deterministic")
`slugify` lowercases the input and replaces each run of non-alphanumeric
characters with a single `-`, performing no stripping, so `"Hello, World!"`
returns `"hello-world-"`. It is a pure function of its input, so the same input
always yields the same output.
Implemented in:
- src/ssg/parser.py:64 (`slugify` public function)
- src/ssg/parser.py:31 (`_NON_ALNUM_RUN` regex used by `slugify`)
