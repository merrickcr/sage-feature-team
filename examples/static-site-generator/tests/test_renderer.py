"""STORY-2 tests: render a parsed post into a full HTML page.

Seam under test: ``ssg.renderer`` — a library module that wraps a parsed
post (title, optional date, HTML body) in the built-in per-page template,
producing a complete standalone HTML document. Per docs/conventions.md a
library module returns its result and never prints.

Public contract these tests pin down (the Developer implements it):

  - ``render_page(post: Post) -> str`` takes the object returned by
    ``ssg.parser.parse_post`` (exposing ``.title``, ``.date: str | None``,
    ``.html``) and returns one complete HTML document as a string. The
    document contains:
      * the title inside the ``<title>`` element AND inside an ``<h1>``,
      * the date string when ``post.date`` is present (no date markup when
        it is None),
      * the post's HTML body.
  - The renderer is deterministic: rendering the same post twice yields
    byte-identical output (no timestamps / run-dependent content).

Posts are built through the real (DONE) parser via the ``write_md`` fixture
so the tests assert on observable rendered HTML, never on internal
construction details. STORY-2 owns only the per-page template; the index
page is STORY-3.

All tests are named ``test_story_2_*`` so the Tester can filter with
``pytest -k "story_2"``.
"""

from __future__ import annotations

from ssg.parser import parse_post
from ssg.renderer import render_page


# --- AC8: full post (title + date + body) renders a complete document --------

def test_story_2_renders_complete_document_with_title_date_and_body(write_md):
    path = write_md(
        "hello-world.md",
        "---\ntitle: Hello, world\ndate: 2026-05-24\n---\n\nbody text\n",
    )
    post = parse_post(path)

    html = render_page(post)

    # A complete standalone HTML document.
    assert "<html" in html.lower()
    assert "</html>" in html.lower()

    # Title appears inside the <title> element.
    assert "<title>" in html.lower()
    title_open = html.lower().index("<title>") + len("<title>")
    title_close = html.lower().index("</title>")
    assert "Hello, world" in html[title_open:title_close]

    # Title also appears inside an <h1>.
    assert "<h1" in html.lower()
    h1_open = html.lower().index("<h1")
    h1_close = html.lower().index("</h1>")
    assert "Hello, world" in html[h1_open:h1_close]

    # The date string is present somewhere in the document.
    assert "2026-05-24" in html

    # The post's HTML body is included.
    assert "body text" in html


def test_story_2_renders_post_body_html_into_page(write_md):
    # The rendered body must carry through the parser's HTML, not re-escape it.
    path = write_md(
        "post.md",
        "---\ntitle: Bodied\ndate: 2026-01-02\n---\n\n# A Heading\n\nA paragraph.\n",
    )
    post = parse_post(path)

    html = render_page(post)

    # markdown-it renders these; the rendered markup must appear in the page.
    assert post.html in html


# --- AC9: title but no date -> no date markup, no error ----------------------

def test_story_2_renders_title_without_date(write_md):
    path = write_md("untitled-thought.md", "# Hi")  # no front-matter -> no date
    post = parse_post(path)
    assert post.date is None  # precondition for this AC

    html = render_page(post)

    # Title still appears in both <title> and <h1>.
    title_open = html.lower().index("<title>") + len("<title>")
    title_close = html.lower().index("</title>")
    assert post.title in html[title_open:title_close]

    h1_open = html.lower().index("<h1")
    h1_close = html.lower().index("</h1>")
    assert post.title in html[h1_open:h1_close]


def test_story_2_no_date_produces_no_date_text(write_md):
    # A dated post and an undated post should differ only by the date text:
    # the undated render must not contain the dated post's date string.
    dated_path = write_md(
        "dated.md",
        "---\ntitle: Same Title\ndate: 2026-05-24\n---\n\nsame body\n",
    )
    undated_path = write_md(
        "undated.md",
        "---\ntitle: Same Title\n---\n\nsame body\n",
    )
    dated = parse_post(dated_path)
    undated = parse_post(undated_path)
    assert undated.date is None

    undated_html = render_page(undated)

    # The undated page must carry no date markup.
    assert "2026-05-24" not in undated_html
    # Sanity: the date string IS present when a date exists, confirming the
    # absence above is meaningful and not a template that never shows dates.
    assert "2026-05-24" in render_page(dated)


# --- AC10: empty body still yields a complete document, no error -------------

def test_story_2_empty_body_still_renders_complete_document(write_md):
    path = write_md(
        "lonely.md",
        "---\ntitle: Lonely Title\ndate: 2026-01-01\n---\n",
    )
    post = parse_post(path)
    assert post.html.strip() == ""  # precondition: empty body

    html = render_page(post)  # must not raise

    # Still a complete HTML document.
    assert "<html" in html.lower()
    assert "</html>" in html.lower()

    # Title / H1 are still present.
    assert "<title>" in html.lower()
    h1_open = html.lower().index("<h1")
    h1_close = html.lower().index("</h1>")
    assert post.title in html[h1_open:h1_close]


# --- AC11: rendering is deterministic (byte-identical across runs) -----------

def test_story_2_render_is_byte_identical_across_runs(write_md):
    path = write_md(
        "hello-world.md",
        "---\ntitle: Hello, world\ndate: 2026-05-24\n---\n\nbody text\n",
    )
    post = parse_post(path)

    first = render_page(post)
    second = render_page(post)

    assert first == second


def test_story_2_render_is_byte_identical_for_undated_post(write_md):
    # Determinism must also hold on the no-date branch of the template.
    path = write_md("hello-world.md", "# Hi")
    post = parse_post(path)
    assert post.date is None

    assert render_page(post) == render_page(post)
