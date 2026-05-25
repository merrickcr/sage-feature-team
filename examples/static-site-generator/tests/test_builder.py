"""STORY-3 tests: the build command -- walk content/, write dist/, index, summary.

Seam under test: ``python -m ssg build`` (the ``__main__`` CLI wired to
``ssg.builder``). These tests drive the build the way a user would: a real
``content/`` directory on disk, an actual subprocess invocation of
``python -m ssg build`` with ``cwd`` set to the project under test, and
assertions on OBSERVABLE output only -- files written under ``dist/``, their
byte contents, the process stdout/stderr, and the exit code. No internal
functions are called and no call counts are asserted.

Public contract these tests pin down (the Developer implements it):

  - ``python -m ssg build`` reads every ``*.md`` in ``./content/`` (flat, no
    recursion), parses + renders each to ``./dist/<basename>.html``, and writes
    ``./dist/index.html``.
  - On success it prints exactly one line to stdout matching
    ``built N pages in <ms>ms`` (N = number of source pages, not counting the
    index) and exits zero.
  - ``index.html`` lists posts sorted by date descending; date-less posts come
    last, ordered alphabetically by title (case-insensitive). Each entry shows
    the title linked to ``<basename>.html`` and the date when the post has one.
  - No ``./content/`` directory  -> nonzero exit, stderr tells the user to
    create a ``content/`` directory.
  - Empty ``./content/``         -> zero exit, ``dist/index.html`` contains
    ``No posts yet.``.
  - Malformed YAML front-matter  -> nonzero exit, stderr names the offending
    file; build aborts (no partial-dist guarantee).
  - Pre-existing ``dist/``       -> wiped and recreated; stale files vanish.

The exact index markup is fixed by the snapshot fixture
``tests/fixtures/expected_dist/index.html`` (see ``test_e2e.py`` / AC19); these
tests assert only the structural facts the PRD calls out, so they stay robust
to incidental template whitespace.

All tests are named ``test_story_3_*`` so the Tester can filter with
``pytest -k "story_3"``.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"

# stdout success line, e.g. "built 3 pages in 7ms". The page count is N source
# pages; the trailing index.html is NOT counted.
SUMMARY_RE = re.compile(r"^built (\d+) pages in (\d+)ms$")


def _run_build(cwd: Path) -> subprocess.CompletedProcess:
    """Invoke ``python -m ssg build`` in ``cwd`` and capture the result.

    Runs as a real subprocess so we observe the actual CLI surface: stdout,
    stderr, and exit code. ``src/`` is placed on PYTHONPATH because v0.1 ships
    no packaging config (mirrors tests/conftest.py's sys.path shim).
    """
    env = {
        **_clean_env(),
        "PYTHONPATH": str(SRC_DIR),
        # Force UTF-8 / deterministic IO so byte comparisons are stable.
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


def _clean_env() -> dict:
    import os

    return dict(os.environ)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write LF so generated dist output is comparable across platforms.
    path.write_text(content, encoding="utf-8", newline="\n")


# --- AC12: build writes one HTML per source + index, prints summary ----------

def test_story_3_builds_one_html_per_source_plus_index(tmp_path):
    content = tmp_path / "content"
    _write(content / "hello-world.md", "---\ntitle: Hello\ndate: 2026-05-24\n---\n\nhi\n")
    _write(content / "second-post.md", "---\ntitle: Second\ndate: 2026-01-02\n---\n\nyo\n")
    _write(content / "third.md", "# Third\n\nno front-matter\n")

    result = _run_build(tmp_path)

    assert result.returncode == 0, result.stderr
    dist = tmp_path / "dist"
    # One <basename>.html per source file, mapping by basename.
    assert (dist / "hello-world.html").is_file()
    assert (dist / "second-post.html").is_file()
    assert (dist / "third.html").is_file()
    # Plus the index.
    assert (dist / "index.html").is_file()
    # Exactly those four html files, nothing else.
    produced = sorted(p.name for p in dist.glob("*.html"))
    assert produced == [
        "hello-world.html",
        "index.html",
        "second-post.html",
        "third.html",
    ]


def test_story_3_basename_maps_source_md_to_dist_html(tmp_path):
    content = tmp_path / "content"
    _write(content / "hello-world.md", "---\ntitle: Hello\n---\n\nhi\n")

    result = _run_build(tmp_path)

    assert result.returncode == 0, result.stderr
    # content/hello-world.md -> dist/hello-world.html (basename preserved).
    assert (tmp_path / "dist" / "hello-world.html").is_file()


def test_story_3_stdout_is_exactly_the_summary_line(tmp_path):
    content = tmp_path / "content"
    _write(content / "a.md", "---\ntitle: A\n---\n\na\n")
    _write(content / "b.md", "---\ntitle: B\n---\n\nb\n")
    _write(content / "c.md", "---\ntitle: C\n---\n\nc\n")

    result = _run_build(tmp_path)

    assert result.returncode == 0, result.stderr
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    # Exactly one summary line on stdout.
    assert len(lines) == 1, result.stdout
    match = SUMMARY_RE.match(lines[0])
    assert match is not None, repr(lines[0])
    # N counts source pages (3), not the index.
    assert match.group(1) == "3"


# --- AC13: index sorted by date desc; date-less last alpha; entries linked ---

def test_story_3_index_orders_dated_desc_then_dateless_alpha(tmp_path):
    content = tmp_path / "content"
    # Two dated (out of order) + two date-less (reverse-alpha filenames/titles).
    _write(content / "older.md", "---\ntitle: Older\ndate: 2026-01-02\n---\n\nx\n")
    _write(content / "newer.md", "---\ntitle: Newer\ndate: 2026-05-24\n---\n\nx\n")
    _write(content / "zeta.md", "---\ntitle: Zeta\n---\n\nx\n")
    _write(content / "alpha.md", "---\ntitle: Alpha\n---\n\nx\n")

    result = _run_build(tmp_path)
    assert result.returncode == 0, result.stderr

    index = (tmp_path / "dist" / "index.html").read_text(encoding="utf-8")
    # Find the order in which each post's link appears in the index.
    positions = {
        name: index.find(f'href="{name}.html"')
        for name in ("newer", "older", "alpha", "zeta")
    }
    assert all(p != -1 for p in positions.values()), positions
    # Dated descending (newer before older), then date-less alphabetical
    # (alpha before zeta), and all dated before all date-less.
    assert (
        positions["newer"]
        < positions["older"]
        < positions["alpha"]
        < positions["zeta"]
    ), positions


def test_story_3_index_entry_links_title_to_its_page(tmp_path):
    content = tmp_path / "content"
    _write(content / "hello-world.md", "---\ntitle: Hello, world\ndate: 2026-05-24\n---\n\nhi\n")

    result = _run_build(tmp_path)
    assert result.returncode == 0, result.stderr

    index = (tmp_path / "dist" / "index.html").read_text(encoding="utf-8")
    # The entry must link the title text to the post's page.
    assert 'href="hello-world.html"' in index
    assert "Hello, world" in index
    # The title text falls inside an anchor that targets the page.
    anchor = re.search(
        r'<a [^>]*href="hello-world\.html"[^>]*>(.*?)</a>', index, re.DOTALL
    )
    assert anchor is not None, index
    assert "Hello, world" in anchor.group(1)


def test_story_3_index_shows_date_only_when_present(tmp_path):
    content = tmp_path / "content"
    _write(content / "dated.md", "---\ntitle: Dated Post\ndate: 2026-05-24\n---\n\nx\n")
    _write(content / "undated.md", "---\ntitle: Undated Post\n---\n\nx\n")

    result = _run_build(tmp_path)
    assert result.returncode == 0, result.stderr

    index = (tmp_path / "dist" / "index.html").read_text(encoding="utf-8")
    # Dated post's date string appears in the index.
    assert "2026-05-24" in index

    # The undated entry must not carry a date. Isolate the undated <li>/anchor
    # region and assert no ISO date appears between the two entries.
    dated_pos = index.find('href="dated.html"')
    undated_pos = index.find('href="undated.html"')
    assert dated_pos != -1 and undated_pos != -1, index
    # The only ISO date in the whole index is the dated post's.
    assert len(re.findall(r"\d{4}-\d{2}-\d{2}", index)) == 1, index


# --- AC14: no content/ directory -> nonzero, clear stderr message ------------

def test_story_3_missing_content_dir_fails_nonzero(tmp_path):
    # tmp_path has no content/ directory at all.
    result = _run_build(tmp_path)

    assert result.returncode != 0
    # No dist/ should have been produced.
    assert not (tmp_path / "dist").exists()


def test_story_3_missing_content_dir_message_mentions_content(tmp_path):
    result = _run_build(tmp_path)

    assert result.returncode != 0
    # Clear message telling the user to create a content/ directory.
    assert "content" in result.stderr.lower()
    # Nothing leaks the success summary to stdout.
    assert "built" not in result.stdout.lower()


# --- AC15: empty content/ -> zero exit, index says "No posts yet." -----------

def test_story_3_empty_content_dir_succeeds_with_no_posts_message(tmp_path):
    content = tmp_path / "content"
    content.mkdir()  # exists but empty

    result = _run_build(tmp_path)

    assert result.returncode == 0, result.stderr
    index = tmp_path / "dist" / "index.html"
    assert index.is_file()
    assert "No posts yet." in index.read_text(encoding="utf-8")


def test_story_3_empty_content_dir_reports_zero_pages(tmp_path):
    content = tmp_path / "content"
    content.mkdir()

    result = _run_build(tmp_path)

    assert result.returncode == 0, result.stderr
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(lines) == 1, result.stdout
    match = SUMMARY_RE.match(lines[0])
    assert match is not None, repr(lines[0])
    assert match.group(1) == "0"


# --- AC16: malformed front-matter -> nonzero, stderr names the file ----------

def test_story_3_malformed_frontmatter_fails_and_names_file(tmp_path):
    content = tmp_path / "content"
    _write(content / "good.md", "---\ntitle: Good\n---\n\nok\n")
    _write(content / "broken.md", "---\ntitle: : not valid: yaml:\n  - [unclosed\n---\n\nbody\n")

    result = _run_build(tmp_path)

    assert result.returncode != 0
    # stderr must name the offending file.
    assert "broken.md" in result.stderr
    # No success summary printed.
    assert "built" not in result.stdout.lower()


# --- AC17: pre-existing dist/ is wiped and recreated -------------------------

def test_story_3_wipes_stale_dist_files(tmp_path):
    content = tmp_path / "content"
    _write(content / "hello.md", "---\ntitle: Hello\n---\n\nhi\n")

    # Pre-existing dist/ with a stale file not derived from current content.
    dist = tmp_path / "dist"
    dist.mkdir()
    stale = dist / "stale-old-page.html"
    stale.write_text("<html>stale</html>", encoding="utf-8")
    assert stale.exists()

    result = _run_build(tmp_path)

    assert result.returncode == 0, result.stderr
    # The stale file must be gone after rebuild.
    assert not stale.exists()
    # The current page and index exist.
    assert (dist / "hello.html").is_file()
    assert (dist / "index.html").is_file()


def test_story_3_build_never_deletes_outside_dist(tmp_path):
    content = tmp_path / "content"
    _write(content / "hello.md", "---\ntitle: Hello\n---\n\nhi\n")
    # A sibling file/dir outside dist/ that must survive the build.
    keepsake = tmp_path / "DO_NOT_TOUCH.txt"
    keepsake.write_text("precious", encoding="utf-8")

    result = _run_build(tmp_path)

    assert result.returncode == 0, result.stderr
    assert keepsake.exists()
    assert keepsake.read_text(encoding="utf-8") == "precious"
    # content/ is untouched too.
    assert (content / "hello.md").exists()
