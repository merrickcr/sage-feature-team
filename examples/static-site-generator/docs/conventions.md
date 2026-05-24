# Code conventions (`ssg`)

## Language & layout

- Python 3.10+, PEP 8, type hints on every public function.
- Package code lives in `src/ssg/`.
- One module per concern, kept under ~150 lines each.
- Suggested module split (Developer may adjust if a story makes a better case):
  - `parser.py` — front-matter extraction + Markdown→HTML body conversion
  - `renderer.py` — page template wrapping (title, date, body)
  - `builder.py` — content directory walking, dist writes, index generation
  - `__main__.py` — CLI entry point (`python -m ssg build`)
- Public functions get docstrings (one-line summary + a Returns line is enough). Private helpers (`_foo`) don't need them.

## Errors

- Raise specific exceptions (`ValueError`, `FileNotFoundError`, or a custom class in `errors.py`). Never raise bare `Exception`.
- Error messages name the offending file and the actual problem in one line. Good: `"hello.md: invalid front-matter: expected a YAML mapping, got list"`. Bad: `"parse failed"`.
- Library modules (anything under `src/ssg/` other than `__main__.py`) MUST NOT print or write to stdout/stderr. Surface problems by raising; the CLI decides what to render.

## CLI

- `__main__.py` is the only place that prints.
- Success summary on stdout: `built N pages in <ms>ms` (PRD requirement, exact format).
- Failures: write to stderr, name the file, exit nonzero.

## Imports

- Standard library first, then third-party, then local — separated by blank lines.
- No wildcard imports (`from foo import *`).
- Module-level constants in `UPPER_SNAKE_CASE`.
