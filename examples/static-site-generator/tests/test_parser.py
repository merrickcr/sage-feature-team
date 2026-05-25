"""STORY-1 tests: front-matter parsing, Markdown body -> HTML, slugify.

Seam under test: ``ssg.parser`` — pure functions, no disk-walking beyond
reading the single file path handed to ``parse_post``, no printing.

Public contract these tests pin down (the Developer implements it):

  - ``parse_post(path: Path) -> Post`` reads one Markdown file, splitting an
    optional ``---``-delimited YAML front-matter block from the body. The
    returned object exposes:
      * ``.title: str``  — from front-matter ``title``, else derived from the
        filename (dashes -> spaces, title-cased).
      * ``.date: str | None`` — from front-matter ``date`` (ISO string), else None.
      * ``.html: str`` — the body rendered to HTML via markdown-it-py.
  - ``slugify(text: str) -> str`` — lowercase, each run of non-alphanumeric
    characters replaced by a single ``-`` (no stripping). Deterministic.
  - ``FrontMatterError`` — a specific exception (NOT bare ``Exception``) raised
    when front-matter is not valid YAML; its message names the offending file.

All tests are named ``test_story_1_*`` so the Tester can filter with
``pytest -k "story_1"``.
"""

from __future__ import annotations

import pytest

from ssg.parser import FrontMatterError, parse_post, slugify


# --- AC1: full front-matter (title + date) and rendered body -----------------

def test_story_1_parses_simple_frontmatter(write_md):
    path = write_md(
        "hello-world.md",
        "---\ntitle: Hello, world\ndate: 2026-05-24\n---\n\nbody text\n",
    )

    post = parse_post(path)

    assert post.title == "Hello, world"
    assert post.date == "2026-05-24"
    assert "body text" in post.html


def test_story_1_parses_minimal_fixture_file(fixtures_dir):
    # Exercises the documented tests/fixtures/minimal/ content tree.
    path = fixtures_dir / "minimal" / "hello-world.md"

    post = parse_post(path)

    assert post.title == "Hello, world"
    assert post.date == "2026-05-24"
    assert "body text" in post.html


# --- AC2: no front-matter -> filename-derived title, no date -----------------

def test_story_1_title_derived_from_filename_when_no_frontmatter(write_md):
    path = write_md("hello-world.md", "# Hi")

    post = parse_post(path)

    assert post.title == "Hello World"
    assert post.date is None


def test_story_1_no_frontmatter_body_still_renders(write_md):
    path = write_md("hello-world.md", "# Hi")

    post = parse_post(path)

    # markdown-it renders '# Hi' as an <h1>; assert the text is present.
    assert "Hi" in post.html


# --- AC3: unexpected front-matter fields are ignored -------------------------

def test_story_1_unexpected_frontmatter_field_ignored(write_md):
    path = write_md(
        "post.md",
        "---\ntitle: Real Title\nauthor: Jane\n---\n\nhello\n",
    )

    post = parse_post(path)

    assert post.title == "Real Title"
    # The unexpected 'author' field must not leak onto the post as an attribute.
    assert not hasattr(post, "author")


# --- AC4: front-matter present but empty body --------------------------------

def test_story_1_empty_body_after_frontmatter_succeeds(write_md):
    path = write_md(
        "post.md",
        "---\ntitle: Lonely Title\ndate: 2026-01-01\n---\n",
    )

    post = parse_post(path)

    assert post.title == "Lonely Title"
    assert post.date == "2026-01-01"
    assert post.html.strip() == ""


# --- AC5: malformed YAML front-matter -> specific exception naming the file --

def test_story_1_malformed_frontmatter_raises_specific_error(write_md):
    path = write_md(
        "broken.md",
        "---\ntitle: : not valid: yaml:\n  - [unclosed\n---\n\nbody\n",
    )

    with pytest.raises(FrontMatterError) as excinfo:
        parse_post(path)

    # Must be a *specific* exception, not bare Exception.
    assert type(excinfo.value) is not Exception
    # Message must name the offending file.
    assert "broken.md" in str(excinfo.value)


# --- AC6: raw inline HTML in the body passes through unsanitized -------------

def test_story_1_raw_html_passes_through_unsanitized(write_md):
    path = write_md(
        "post.md",
        "---\ntitle: Raw\n---\n\n<div>x</div>\n",
    )

    post = parse_post(path)

    assert "<div>x</div>" in post.html


# --- AC7: shared slugify function --------------------------------------------

def test_story_1_slugify_replaces_nonalnum_runs():
    assert slugify("Hello, World!") == "hello-world-"


def test_story_1_slugify_is_deterministic():
    first = slugify("Hello, World!")
    second = slugify("Hello, World!")

    assert first == second == "hello-world-"
