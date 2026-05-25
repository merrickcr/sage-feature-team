"""STORY-4 tests: tags -- per-tag pages, index Tags section, per-post tag links.

Seam under test: ``python -m ssg build`` (the ``__main__`` CLI wired to
``ssg.builder``), driven exactly as STORY-3's builder/e2e tests drive it -- a
real ``content/`` directory on disk, an actual subprocess invocation of
``python -m ssg build`` with ``cwd`` set to a temp project and ``PYTHONPATH``
pointing at ``src/``. All assertions are on OBSERVABLE output only: files
written under ``dist/`` (including ``dist/tags/<slug>.html``), their byte
contents, the index/post HTML, process stdout/stderr, and the exit code. No
internal functions are called and no call counts are asserted.

Public contract these tests pin down (the Developer implements it in
``src/ssg``):

  - A post may declare ``tags: [foo, bar]`` in front-matter. For each unique
    tag across published posts, the build writes ``dist/tags/<slug>.html``
    listing every post carrying that tag, sorted by date descending (date-less
    last, alphabetical by title) -- the same order rule as the main index.
  - ``<slug>`` is the tag run through EPIC-1's shared ``slugify`` (lowercase,
    each run of non-alphanumeric chars -> a single ``-``, no stripping). Tags
    that slugify to the same value share ONE tag page listing all their posts.
  - ``dist/index.html`` gains a "Tags" section listing each tag with its post
    count, each linking to that tag's ``tags/<slug>.html`` page.
  - Each post's own HTML page displays its tags, each linked to the
    corresponding ``tags/<slug>.html`` page.
  - A post with no ``tags`` field, or ``tags: []``, appears on no tag page and
    contributes nothing to the index Tags section.
  - When NO post has any tag, no ``dist/tags/`` directory is created and the
    index omits the Tags section entirely (no empty "Tags" heading).
  - ``tags: foo`` (a string instead of a list) -> nonzero exit; stderr names the
    offending file and states tags must be a list.

These tests assert the structural facts the PRD calls out (file existence,
link targets, listing membership, ordering, post counts), so they stay robust
to incidental template whitespace. Byte-exact snapshot coverage lives in the
e2e/EpicVerifier scope, not here.

All tests are named ``test_story_4_*`` so the Tester can filter with
``pytest -k "story_4"``.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"


def _run_build(cwd: Path) -> subprocess.CompletedProcess:
    """Invoke ``python -m ssg build`` in ``cwd`` and capture the result.

    Runs as a real subprocess so we observe the actual CLI surface: stdout,
    stderr, and exit code. ``src/`` is placed on PYTHONPATH because v0.1 ships
    no packaging config (mirrors tests/conftest.py's sys.path shim and the
    STORY-3 builder/e2e tests).
    """
    env = {
        **dict(os.environ),
        "PYTHONPATH": str(SRC_DIR),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
    }
    return subprocess.run(
        [sys.executable, "-m", "ssg", "build"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=env,
    )


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write LF so generated dist output is comparable across platforms.
    path.write_text(content, encoding="utf-8", newline="\n")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _link_positions(html: str, hrefs: list[str]) -> dict[str, int]:
    """Map each href substring to the index where it first appears in ``html``."""
    return {h: html.find(h) for h in hrefs}


def _tags_section(index_html: str) -> str | None:
    """Return the index region from the 'Tags' heading onward, or None.

    The index already carries an ``<h1>Index</h1>`` and a posts ``<ul>``; the
    Tags section is identified by a heading whose text is exactly ``Tags``
    (e.g. ``<h2>Tags</h2>``). Returns the substring from that heading to the
    end of the document so membership/order/count assertions can be scoped to
    the Tags listing rather than the posts listing.
    """
    match = re.search(r"<h[1-6][^>]*>\s*Tags\s*</h[1-6]>", index_html)
    if match is None:
        return None
    return index_html[match.start():]


# --- AC20: per-tag page exists, lists tagged posts, sorted date desc ---------

def test_story_4_creates_a_page_per_unique_tag(tmp_path):
    content = tmp_path / "content"
    _write(content / "a.md", "---\ntitle: A\ndate: 2026-05-01\ntags: [python, learning]\n---\n\na\n")
    _write(content / "b.md", "---\ntitle: B\ndate: 2026-05-02\ntags: [python]\n---\n\nb\n")

    result = _run_build(tmp_path)

    assert result.returncode == 0, result.stderr
    tags_dir = tmp_path / "dist" / "tags"
    # One page per UNIQUE tag (python, learning) -- python is shared, not duplicated.
    assert (tags_dir / "python.html").is_file()
    assert (tags_dir / "learning.html").is_file()
    produced = sorted(p.name for p in tags_dir.glob("*.html"))
    assert produced == ["learning.html", "python.html"], produced


def test_story_4_tag_page_lists_every_post_with_that_tag(tmp_path):
    content = tmp_path / "content"
    _write(content / "first.md", "---\ntitle: First\ndate: 2026-05-01\ntags: [python]\n---\n\nx\n")
    _write(content / "second.md", "---\ntitle: Second\ndate: 2026-05-02\ntags: [python]\n---\n\nx\n")
    # A third post that does NOT carry the tag must not appear on the page.
    _write(content / "third.md", "---\ntitle: Third\ndate: 2026-05-03\ntags: [other]\n---\n\nx\n")

    result = _run_build(tmp_path)
    assert result.returncode == 0, result.stderr

    page = _read(tmp_path / "dist" / "tags" / "python.html")
    # Both python-tagged posts are linked from the python tag page...
    assert 'href="../first.html"' in page or 'href="first.html"' in page, page
    assert 'href="../second.html"' in page or 'href="second.html"' in page, page
    # ...and the non-python post is absent.
    assert "third.html" not in page, page


def test_story_4_tag_page_sorts_posts_date_desc_then_dateless_alpha(tmp_path):
    content = tmp_path / "content"
    # All share tag "t": two dated (out of order) + two date-less (reverse alpha).
    _write(content / "older.md", "---\ntitle: Older\ndate: 2026-01-02\ntags: [t]\n---\n\nx\n")
    _write(content / "newer.md", "---\ntitle: Newer\ndate: 2026-05-24\ntags: [t]\n---\n\nx\n")
    _write(content / "zeta.md", "---\ntitle: Zeta\ntags: [t]\n---\n\nx\n")
    _write(content / "alpha.md", "---\ntitle: Alpha\ntags: [t]\n---\n\nx\n")

    result = _run_build(tmp_path)
    assert result.returncode == 0, result.stderr

    page = _read(tmp_path / "dist" / "tags" / "t.html")
    positions = {
        name: page.find(f"{name}.html") for name in ("newer", "older", "alpha", "zeta")
    }
    assert all(p != -1 for p in positions.values()), positions
    # Dated descending (newer < older), then date-less alphabetical (alpha < zeta),
    # with all dated before all date-less -- the same rule as the main index.
    assert (
        positions["newer"] < positions["older"] < positions["alpha"] < positions["zeta"]
    ), positions


def test_story_4_tag_slug_uses_shared_slugify_rule(tmp_path):
    content = tmp_path / "content"
    # "Web Dev" -> slugify -> "web-dev" (lowercased, non-alnum run -> single '-').
    _write(content / "a.md", "---\ntitle: A\ndate: 2026-05-01\ntags: ['Web Dev']\n---\n\nx\n")

    result = _run_build(tmp_path)
    assert result.returncode == 0, result.stderr

    tags_dir = tmp_path / "dist" / "tags"
    assert (tags_dir / "web-dev.html").is_file(), sorted(p.name for p in tags_dir.glob("*"))


# --- AC21: index gains a Tags section: each tag, its count, linked -----------

def test_story_4_index_has_tags_section_linking_each_tag(tmp_path):
    content = tmp_path / "content"
    _write(content / "a.md", "---\ntitle: A\ndate: 2026-05-01\ntags: [python, learning]\n---\n\nx\n")
    _write(content / "b.md", "---\ntitle: B\ndate: 2026-05-02\ntags: [python]\n---\n\nx\n")

    result = _run_build(tmp_path)
    assert result.returncode == 0, result.stderr

    index = _read(tmp_path / "dist" / "index.html")
    section = _tags_section(index)
    assert section is not None, index
    # Each tag links to its tag page from within the Tags section.
    assert 'href="tags/python.html"' in section, section
    assert 'href="tags/learning.html"' in section, section


def test_story_4_index_tags_section_shows_post_count(tmp_path):
    content = tmp_path / "content"
    # python on 2 posts, learning on 1.
    _write(content / "a.md", "---\ntitle: A\ndate: 2026-05-01\ntags: [python, learning]\n---\n\nx\n")
    _write(content / "b.md", "---\ntitle: B\ndate: 2026-05-02\ntags: [python]\n---\n\nx\n")

    result = _run_build(tmp_path)
    assert result.returncode == 0, result.stderr

    index = _read(tmp_path / "dist" / "index.html")
    section = _tags_section(index)
    assert section is not None, index
    # Scope each count to the region around that tag's link so we read the
    # right number even if templates differ in punctuation/markup.
    py_pos = section.find('href="tags/python.html"')
    learn_pos = section.find('href="tags/learning.html"')
    assert py_pos != -1 and learn_pos != -1, section
    # The count for each tag appears in its list entry. Order the two link
    # positions and slice each entry's text up to the next entry (or end).
    bounds = sorted([py_pos, learn_pos])
    py_entry = section[py_pos: bounds[1] if py_pos == bounds[0] else len(section)]
    learn_entry = section[learn_pos: bounds[1] if learn_pos == bounds[0] else len(section)]
    assert "2" in py_entry, py_entry
    assert "1" in learn_entry, learn_entry


# --- AC22: each post page displays its tags, each linked to its tag page ------

def test_story_4_post_page_links_each_of_its_tags(tmp_path):
    content = tmp_path / "content"
    _write(content / "post.md", "---\ntitle: Tagged Post\ndate: 2026-05-01\ntags: [python, learning]\n---\n\nbody\n")

    result = _run_build(tmp_path)
    assert result.returncode == 0, result.stderr

    page = _read(tmp_path / "dist" / "post.html")
    # The post page links to BOTH of its tag pages. A post page lives at
    # dist/post.html and tag pages at dist/tags/<slug>.html, so the link is
    # tags/<slug>.html (relative to dist/).
    assert 'href="tags/python.html"' in page, page
    assert 'href="tags/learning.html"' in page, page
    # The visible tag names appear on the page too.
    assert "python" in page
    assert "learning" in page


def test_story_4_untagged_post_page_links_no_tag_pages(tmp_path):
    content = tmp_path / "content"
    _write(content / "tagged.md", "---\ntitle: Tagged\ndate: 2026-05-02\ntags: [python]\n---\n\nx\n")
    _write(content / "bare.md", "---\ntitle: Bare\ndate: 2026-05-01\n---\n\nx\n")

    result = _run_build(tmp_path)
    assert result.returncode == 0, result.stderr

    bare = _read(tmp_path / "dist" / "bare.html")
    # A post with no tags links to no tag page.
    assert "tags/" not in bare, bare


# --- AC23: no-tags / empty-tags post contributes nothing to tags --------------

def test_story_4_empty_and_missing_tags_excluded_from_tag_listings(tmp_path):
    content = tmp_path / "content"
    _write(content / "tagged.md", "---\ntitle: Tagged\ndate: 2026-05-03\ntags: [python]\n---\n\nx\n")
    _write(content / "empty.md", "---\ntitle: Empty\ndate: 2026-05-02\ntags: []\n---\n\nx\n")
    _write(content / "none.md", "---\ntitle: None\ndate: 2026-05-01\n---\n\nx\n")

    result = _run_build(tmp_path)
    assert result.returncode == 0, result.stderr

    # Only the python tag page exists -- empty/none contribute no tags.
    tags_dir = tmp_path / "dist" / "tags"
    produced = sorted(p.name for p in tags_dir.glob("*.html"))
    assert produced == ["python.html"], produced

    # The python tag page lists only the tagged post, not empty/none.
    page = _read(tags_dir / "python.html")
    assert "tagged.html" in page, page
    assert "empty.html" not in page, page
    assert "none.html" not in page, page

    # The index Tags section lists python (count 1) and nothing for empty/none.
    index = _read(tmp_path / "dist" / "index.html")
    section = _tags_section(index)
    assert section is not None, index
    assert 'href="tags/python.html"' in section, section
    # No tag page link for the untagged posts.
    assert "empty.html" not in section
    assert "none.html" not in section


# --- AC24: no tags anywhere -> no tags/ dir, index omits Tags section ----------

def test_story_4_no_tags_anywhere_creates_no_tags_dir(tmp_path):
    content = tmp_path / "content"
    _write(content / "a.md", "---\ntitle: A\ndate: 2026-05-02\ntags: []\n---\n\nx\n")
    _write(content / "b.md", "---\ntitle: B\ndate: 2026-05-01\n---\n\nx\n")

    result = _run_build(tmp_path)
    assert result.returncode == 0, result.stderr

    # No dist/tags/ directory at all.
    assert not (tmp_path / "dist" / "tags").exists()


def test_story_4_no_tags_anywhere_omits_index_tags_section(tmp_path):
    content = tmp_path / "content"
    _write(content / "a.md", "---\ntitle: A\ndate: 2026-05-02\ntags: []\n---\n\nx\n")
    _write(content / "b.md", "---\ntitle: B\ndate: 2026-05-01\n---\n\nx\n")

    result = _run_build(tmp_path)
    assert result.returncode == 0, result.stderr

    index = _read(tmp_path / "dist" / "index.html")
    # No Tags heading at all (not an empty section).
    assert _tags_section(index) is None, index


# --- AC25: tags as a string (not a list) -> nonzero, stderr names the file ----

def test_story_4_string_tags_fails_nonzero(tmp_path):
    content = tmp_path / "content"
    _write(content / "good.md", "---\ntitle: Good\ndate: 2026-05-02\ntags: [python]\n---\n\nok\n")
    _write(content / "bad.md", "---\ntitle: Bad\ndate: 2026-05-01\ntags: foo\n---\n\nbody\n")

    result = _run_build(tmp_path)

    assert result.returncode != 0
    # No success summary leaks to stdout.
    assert "built" not in result.stdout.lower(), result.stdout


def test_story_4_string_tags_error_names_file_and_says_list(tmp_path):
    content = tmp_path / "content"
    _write(content / "bad.md", "---\ntitle: Bad\ndate: 2026-05-01\ntags: foo\n---\n\nbody\n")

    result = _run_build(tmp_path)

    assert result.returncode != 0
    err = result.stderr.lower()
    # The error names the offending file and states tags must be a list.
    assert "bad.md" in result.stderr, result.stderr
    assert "tags" in err and "list" in err, result.stderr


# --- AC26: tags slugifying to the same value share one tag page ---------------

def test_story_4_tags_slugifying_to_same_value_share_one_page(tmp_path):
    content = tmp_path / "content"
    # 'c++' -> 'c--' (each non-alnum char in the run? '++' is one run -> 'c-'),
    # and the spec's own example: 'node.js' and 'node-js' both slugify to
    # 'node-js'. Use that pair so the shared-slug page name is unambiguous.
    _write(content / "one.md", "---\ntitle: One\ndate: 2026-05-02\ntags: ['node.js']\n---\n\nx\n")
    _write(content / "two.md", "---\ntitle: Two\ndate: 2026-05-01\ntags: ['node-js']\n---\n\nx\n")

    result = _run_build(tmp_path)
    assert result.returncode == 0, result.stderr

    tags_dir = tmp_path / "dist" / "tags"
    # Exactly ONE shared tag page named by the common slug.
    produced = sorted(p.name for p in tags_dir.glob("*.html"))
    assert produced == ["node-js.html"], produced

    # That single page lists BOTH posts.
    page = _read(tags_dir / "node-js.html")
    assert "one.html" in page, page
    assert "two.html" in page, page


def test_story_4_cpp_and_cdashdash_share_one_tag_page(tmp_path):
    content = tmp_path / "content"
    # 'c++' and 'c--' both slugify to 'c-' (trailing non-alnum run -> single '-').
    _write(content / "plus.md", "---\ntitle: Plus\ndate: 2026-05-02\ntags: ['c++']\n---\n\nx\n")
    _write(content / "dash.md", "---\ntitle: Dash\ndate: 2026-05-01\ntags: ['c--']\n---\n\nx\n")

    result = _run_build(tmp_path)
    assert result.returncode == 0, result.stderr

    tags_dir = tmp_path / "dist" / "tags"
    produced = sorted(p.name for p in tags_dir.glob("*.html"))
    # A single shared page (named by the common slug 'c-').
    assert produced == ["c-.html"], produced

    page = _read(tags_dir / "c-.html")
    assert "plus.html" in page, page
    assert "dash.html" in page, page
