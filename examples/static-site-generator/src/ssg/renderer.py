"""Per-page HTML template wrapping.

Wraps a parsed :class:`~ssg.parser.Post` (title, optional date, HTML body) in
the built-in standalone document template. Pure: returns the document string,
never prints (per docs/conventions.md). Deterministic -- the template carries
no timestamps or run-dependent content, so rendering the same post twice yields
byte-identical output.
"""

from __future__ import annotations

from html import escape

from .parser import Post, slugify

DRAFT_PREFIX = "[DRAFT] "

_PAGE_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
body {{ max-width: 40rem; margin: 2rem auto; padding: 0 1rem;
  font-family: system-ui, sans-serif; line-height: 1.6; }}
.date {{ color: #666; font-size: 0.9rem; }}
</style>
</head>
<body>
<h1>{title}</h1>
{date}{tags}<article>
{body}</article>
</body>
</html>
"""


def render_page(post: Post) -> str:
    """Render a parsed post into a complete standalone HTML document.

    The title is HTML-escaped and placed in both the ``<title>`` element and an
    ``<h1>``; a draft post's title is prefixed with ``[DRAFT]``. The date is
    shown only when ``post.date`` is present; otherwise no date markup is
    emitted. The post's already-rendered HTML body passes through unescaped.

    Returns: the full HTML document as a string.
    """
    display_title = f"{DRAFT_PREFIX}{post.title}" if post.draft else post.title
    title = escape(display_title)
    if post.date is not None:
        date = f'<p class="date">{escape(post.date)}</p>\n'
    else:
        date = ""

    tags = _render_tags(post.tags)

    return _PAGE_TEMPLATE.format(title=title, date=date, tags=tags, body=post.html)


def _render_tags(tags: list[str]) -> str:
    """Render a post's tags as links to their tag pages, or "" when none.

    Each tag links to ``tags/<slug>.html`` (relative to dist/, where the post
    page lives). Returns the empty string for an untagged post so its document
    stays byte-identical to the pre-tags output.
    """
    if not tags:
        return ""
    links = ", ".join(
        f'<a href="tags/{escape(slugify(tag))}.html">{escape(tag)}</a>'
        for tag in tags
    )
    return f'<p class="tags">{links}</p>\n'
