"""Front-matter extraction and Markdown-to-HTML body conversion.

Pure functions: the only disk access is reading the single file path handed
to :func:`parse_post`. No directory walking, no printing.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from markdown_it import MarkdownIt

from .errors import FrontMatterError

FRONT_MATTER_DELIMITER = "---"
_NON_ALNUM_RUN = re.compile(r"[^a-z0-9]+")

# Recognized string spellings for the boolean ``draft`` field. Any other
# non-boolean string is an error (the parser raises, naming the file).
_DRAFT_TRUE_STRINGS = frozenset({"true", "yes", "1"})
_DRAFT_FALSE_STRINGS = frozenset({"false", "no", "0"})

# html=True lets raw inline HTML in the body pass through unsanitized,
# matching conventional Markdown behavior.
_MD = MarkdownIt("commonmark", {"html": True})


@dataclass
class Post:
    """A parsed Markdown post.

    Attributes: ``title`` (str), ``date`` (ISO string or None), ``html`` (str),
    ``tags`` (list of tag strings, empty when absent), ``draft`` (bool, True
    when the post is a draft).
    """

    title: str
    date: str | None
    html: str
    tags: list[str]
    draft: bool


def parse_post(path: Path) -> Post:
    """Parse one Markdown file into a :class:`Post`.

    Splits optional ``---``-delimited YAML front-matter from the body, reads the
    recognized ``title``/``date`` fields (falling back to a filename-derived
    title), and renders the body to HTML.

    Returns: the parsed :class:`Post`.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8")

    front_matter, body = _split_front_matter(text, path)

    title = front_matter.get("title")
    if title is None:
        title = _title_from_filename(path)
    else:
        title = str(title)

    date = _coerce_date(front_matter.get("date"))

    tags = _coerce_tags(front_matter.get("tags"), path)

    draft = _coerce_draft(front_matter.get("draft"), path)

    html = _MD.render(body)

    return Post(title=title, date=date, html=html, tags=tags, draft=draft)


def slugify(text: str) -> str:
    """Convert text to a URL slug.

    Lowercases the input, then replaces each run of non-alphanumeric characters
    with a single ``-``. No leading/trailing stripping, so ``"Hello, World!"``
    becomes ``"hello-world-"``. Deterministic for a given input.

    Returns: the slug string.
    """
    return _NON_ALNUM_RUN.sub("-", text.lower())


def _split_front_matter(text: str, path: Path) -> tuple[dict, str]:
    """Return (front_matter_mapping, body). Mapping is empty when absent."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != FRONT_MATTER_DELIMITER:
        return {}, text

    for index in range(1, len(lines)):
        if lines[index].rstrip("\r\n") == FRONT_MATTER_DELIMITER:
            raw = "".join(lines[1:index])
            body = "".join(lines[index + 1:])
            return _parse_yaml(raw, path), body

    # Opening delimiter with no closing one: treat as malformed front-matter.
    raise FrontMatterError(
        f"{path.name}: invalid front-matter: missing closing '{FRONT_MATTER_DELIMITER}'"
    )


def _parse_yaml(raw: str, path: Path) -> dict:
    """Parse a front-matter block, raising FrontMatterError on bad YAML."""
    try:
        loaded = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise FrontMatterError(
            f"{path.name}: invalid front-matter: {exc}"
        ) from exc

    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise FrontMatterError(
            f"{path.name}: invalid front-matter: expected a YAML mapping, "
            f"got {type(loaded).__name__}"
        )
    return loaded


def _coerce_tags(value: object, path: Path) -> list[str]:
    """Normalize the front-matter ``tags`` field to a list of strings.

    Missing or empty tags yield an empty list. A non-list (e.g. ``tags: foo``)
    raises FrontMatterError naming the file and stating tags must be a list.
    """
    if value is None:
        return []
    if not isinstance(value, list):
        raise FrontMatterError(
            f"{path.name}: tags must be a list, got {type(value).__name__}"
        )
    return [str(tag) for tag in value]


def _coerce_draft(value: object, path: Path) -> bool:
    """Normalize the front-matter ``draft`` field to a bool.

    Missing field or boolean ``false`` -> published (False); boolean ``true``
    -> draft (True). Strings are matched case-insensitively against a small
    set: ``true``/``yes``/``1`` -> True, ``false``/``no``/``0`` -> False. Any
    other string raises FrontMatterError naming the file.
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _DRAFT_TRUE_STRINGS:
            return True
        if normalized in _DRAFT_FALSE_STRINGS:
            return False
    raise FrontMatterError(
        f"{path.name}: invalid 'draft' value {value!r}: expected a boolean or "
        f"one of true/false/yes/no/1/0"
    )


def _coerce_date(value: object) -> str | None:
    """Normalize a front-matter date to an ISO string, or None when absent."""
    if value is None:
        return None
    if isinstance(value, (_dt.date, _dt.datetime)):
        return value.isoformat()
    return str(value)


def _title_from_filename(path: Path) -> str:
    """Derive a title from the filename: dashes -> spaces, title-cased."""
    return path.stem.replace("-", " ").title()
