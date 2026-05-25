"""Build orchestration: walk content/, write dist/, generate index.

Walks ``./content/`` flatly (no recursion), parses and renders each ``*.md``
into ``dist/<basename>.html``, generates ``dist/index.html``, and wipes-then-
recreates ``dist/`` so stale output never lingers. Pure library code per
docs/conventions.md: it raises on problems and never prints; the CLI decides
what to render and which exit code to use.

All files are written with UTF-8 encoding and LF newlines so output is
byte-identical across runs and platforms (idempotency).
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from html import escape
from pathlib import Path

from .parser import Post, parse_post, slugify
from .renderer import render_page

CONTENT_DIRNAME = "content"
DIST_DIRNAME = "dist"
TAGS_DIRNAME = "tags"
INDEX_FILENAME = "index.html"
NO_POSTS_MESSAGE = "No posts yet."
DRAFT_PREFIX = "[DRAFT] "

_INDEX_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Index</title>
<style>
body {{ max-width: 40rem; margin: 2rem auto; padding: 0 1rem;
  font-family: system-ui, sans-serif; line-height: 1.6; }}
.date {{ color: #666; font-size: 0.9rem; }}
</style>
</head>
<body>
<h1>Index</h1>
{body}</body>
</html>
"""

_TAG_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tag: {tag}</title>
<style>
body {{ max-width: 40rem; margin: 2rem auto; padding: 0 1rem;
  font-family: system-ui, sans-serif; line-height: 1.6; }}
.date {{ color: #666; font-size: 0.9rem; }}
</style>
</head>
<body>
<h1>Tag: {tag}</h1>
{body}</body>
</html>
"""


@dataclass
class _Entry:
    """A built page awaiting index listing: its dist basename and Post."""

    basename: str
    post: Post


@dataclass
class _TagGroup:
    """A unique tag slug: its display label and the entries carrying it."""

    slug: str
    label: str
    entries: list[_Entry]


def build_site(root: Path, *, include_drafts: bool = False) -> int:
    """Build the site rooted at ``root`` (expects ``root/content/``).

    Reads every ``*.md`` directly under ``content/`` (no recursion), renders
    each to ``dist/<basename>.html``, and writes ``dist/index.html``. Any
    pre-existing ``dist/`` is removed first. Aborts on the first file whose
    front-matter is invalid (the parser raises and that propagates).

    Drafts (posts with ``draft: true``) are excluded entirely by default: no
    page, no index entry, and no contribution to any tag page or count. When
    ``include_drafts`` is True they are built and their displayed title is
    prefixed with ``[DRAFT]`` on the index, tag pages, and the post page.

    Returns: the number of source pages built (the index is not counted).

    Raises: FileNotFoundError if ``content/`` does not exist; FrontMatterError
    if any source file has invalid front-matter.
    """
    root = Path(root)
    content_dir = root / CONTENT_DIRNAME
    dist_dir = root / DIST_DIRNAME

    if not content_dir.is_dir():
        raise FileNotFoundError(
            f"no '{CONTENT_DIRNAME}/' directory found at {content_dir}: "
            f"create a '{CONTENT_DIRNAME}/' directory with Markdown files to build"
        )

    sources = sorted(content_dir.glob("*.md"))

    # Parse every source first so a malformed file aborts the build before any
    # dist/ is written (AC16: no partial-dist guarantee). The draft field is
    # validated for every file even when the post will be excluded, so a bad
    # 'draft' value (AC31) fails loudly regardless of --include-drafts.
    entries: list[_Entry] = []
    for source in sources:
        post = parse_post(source)
        if post.draft and not include_drafts:
            continue
        entries.append(_Entry(basename=source.stem, post=post))

    tag_groups = _group_tags(entries)

    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir(parents=True)

    for entry in entries:
        _write_file(dist_dir / f"{entry.basename}.html", render_page(entry.post))

    if tag_groups:
        tags_dir = dist_dir / TAGS_DIRNAME
        tags_dir.mkdir()
        for group in tag_groups:
            _write_file(tags_dir / f"{group.slug}.html", _render_tag_page(group))

    _write_file(dist_dir / INDEX_FILENAME, _render_index(entries, tag_groups))

    return len(entries)


def _group_tags(entries: list[_Entry]) -> list[_TagGroup]:
    """Group entries by tag slug, sorted by slug.

    Tags whose slug collides (e.g. 'c++' and 'c--' -> 'c-') share one group.
    The group's label is the first-seen tag text for that slug (entries are
    already in sorted glob order). Returns an empty list when no post has tags.
    """
    by_slug: dict[str, _TagGroup] = {}
    for entry in entries:
        for tag in entry.post.tags:
            slug = slugify(tag)
            group = by_slug.get(slug)
            if group is None:
                group = _TagGroup(slug=slug, label=tag, entries=[])
                by_slug[slug] = group
            if entry not in group.entries:
                group.entries.append(entry)
    return [by_slug[slug] for slug in sorted(by_slug)]


def _render_tag_page(group: _TagGroup) -> str:
    """Render one tag page listing its posts in the shared index order."""
    items = "\n".join(
        _tag_page_line(e) for e in _sorted_for_index(group.entries)
    )
    body = f"<ul>\n{items}\n</ul>\n"
    return _TAG_TEMPLATE.format(tag=escape(group.label), body=body)


def _display_title(post: Post) -> str:
    """The post's title for display, prefixed with ``[DRAFT] `` when a draft."""
    if post.draft:
        return f"{DRAFT_PREFIX}{post.title}"
    return post.title


def _tag_page_line(entry: _Entry) -> str:
    """Build one ``<li>`` for a tag page (posts live one level up via ``../``)."""
    title = escape(_display_title(entry.post))
    href = escape(f"../{entry.basename}.html")
    line = f'<li><a href="{href}">{title}</a>'
    if entry.post.date is not None:
        line += f' <span class="date">{escape(entry.post.date)}</span>'
    return line + "</li>"


def _render_index(entries: list[_Entry], tag_groups: list[_TagGroup]) -> str:
    """Render the index document body and wrap it in the index template.

    Appends a Tags section only when ``tag_groups`` is non-empty, so a site
    with no tagged posts produces byte-identical output to the pre-tags index.
    """
    if not entries:
        body = f"<p>{NO_POSTS_MESSAGE}</p>\n"
    else:
        items = "\n".join(_index_line(e) for e in _sorted_for_index(entries))
        body = f"<ul>\n{items}\n</ul>\n"
    if tag_groups:
        body += _render_index_tags_section(tag_groups)
    return _INDEX_TEMPLATE.format(body=body)


def _render_index_tags_section(tag_groups: list[_TagGroup]) -> str:
    """Render the index 'Tags' section: each tag with its post count and link."""
    items = "\n".join(_index_tag_line(g) for g in tag_groups)
    return f"<h2>Tags</h2>\n<ul>\n{items}\n</ul>\n"


def _index_tag_line(group: _TagGroup) -> str:
    """Build one ``<li>`` linking a tag to its page, showing its post count."""
    label = escape(group.label)
    href = escape(f"{TAGS_DIRNAME}/{group.slug}.html")
    return f'<li><a href="{href}">{label}</a> ({len(group.entries)})</li>'


def _sorted_for_index(entries: list[_Entry]) -> list[_Entry]:
    """Order entries: dated descending, then date-less alphabetical by title.

    Dated posts sort by date descending and all precede date-less posts;
    date-less posts sort case-insensitively by title.
    """
    dated = [e for e in entries if e.post.date is not None]
    dateless = [e for e in entries if e.post.date is None]
    dated.sort(key=lambda e: e.post.date, reverse=True)
    dateless.sort(key=lambda e: e.post.title.lower())
    return dated + dateless


def _index_line(entry: _Entry) -> str:
    """Build one ``<li>`` linking the title to its page, with date if present."""
    title = escape(_display_title(entry.post))
    href = escape(f"{entry.basename}.html")
    line = f'<li><a href="{href}">{title}</a>'
    if entry.post.date is not None:
        line += f' <span class="date">{escape(entry.post.date)}</span>'
    return line + "</li>"


def _write_file(path: Path, content: str) -> None:
    """Write text as UTF-8 with LF newlines (deterministic, cross-platform)."""
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
