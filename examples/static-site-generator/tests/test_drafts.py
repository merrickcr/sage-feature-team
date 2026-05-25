"""STORY-5 tests: drafts -- excluded by default, --include-drafts with [DRAFT].

Seam under test: ``python -m ssg build`` (the ``__main__`` CLI wired to
``ssg.builder``), driven exactly as STORY-3's builder/e2e and STORY-4's tag
tests drive it -- a real ``content/`` directory on disk, an actual subprocess
invocation of ``python -m ssg build`` (optionally with ``--include-drafts``)
with ``cwd`` set to a temp project and ``PYTHONPATH`` pointing at ``src/``. All
assertions are on OBSERVABLE output only: files written under ``dist/``
(including/excluding a draft's page and its tag pages), their byte contents,
the index/post/tag HTML, process stdout/stderr, and the exit code. No internal
functions are called and no call counts are asserted.

Public contract these tests pin down (the Developer implements it in
``src/ssg``):

  - A post may declare ``draft: true``. By default drafts are excluded
    ENTIRELY: no ``dist/<slug>.html`` page, no entry on ``dist/index.html``,
    and no entry or count contribution to any ``dist/tags/<slug>.html`` page.
  - ``python -m ssg build --include-drafts`` includes drafts: the draft's page
    is generated and it appears on the index and on its tag pages, and its
    title is prefixed with ``[DRAFT]`` on the index, on tag pages, and in the
    post page's ``<title>`` and ``<h1>``.
  - The ``draft`` field accepts booleans and a small set of truthy/falsey
    strings: ``true`` / ``yes`` / ``1`` (truthy) -> draft; ``false`` (and a
    missing field) -> published. Any OTHER non-boolean string (e.g.
    ``maybe``) fails loudly: nonzero exit with the offending file named.
  - If every post is a draft and ``--include-drafts`` is not set, the build
    succeeds and ``dist/index.html`` says ``No posts yet.`` (same as an empty
    content directory, per STORY-3 AC15).

These tests assert the structural facts the PRD calls out (page presence/
absence, index/tag membership, the ``[DRAFT]`` marker, exit codes), so they
stay robust to incidental template whitespace. Byte-exact snapshot coverage
lives in the e2e/EpicVerifier scope, not here.

All tests are named ``test_story_5_*`` so the Tester can filter with
``pytest -k "story_5"``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"


def _run_build(cwd: Path, *extra_args: str) -> subprocess.CompletedProcess:
    """Invoke ``python -m ssg build [extra_args...]`` in ``cwd``.

    Runs as a real subprocess so we observe the actual CLI surface: stdout,
    stderr, and exit code. ``src/`` is placed on PYTHONPATH because v0.1 ships
    no packaging config (mirrors tests/conftest.py's sys.path shim and the
    STORY-3/STORY-4 tests). ``--include-drafts`` is passed via ``extra_args``.
    """
    env = {
        **dict(os.environ),
        "PYTHONPATH": str(SRC_DIR),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
    }
    return subprocess.run(
        [sys.executable, "-m", "ssg", "build", *extra_args],
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


# --- AC27: draft:true excluded by default (no page/index/tag contribution) ----

def test_story_5_draft_excluded_by_default_has_no_page(tmp_path):
    content = tmp_path / "content"
    _write(content / "draft.md", "---\ntitle: Draft\ndate: 2026-05-02\ndraft: true\n---\n\nd\n")
    _write(content / "live.md", "---\ntitle: Live\ndate: 2026-05-01\n---\n\nl\n")

    result = _run_build(tmp_path)

    assert result.returncode == 0, result.stderr
    # No HTML page is generated for the draft; the published post still builds.
    assert not (tmp_path / "dist" / "draft.html").exists()
    assert (tmp_path / "dist" / "live.html").is_file()


def test_story_5_draft_excluded_by_default_absent_from_index(tmp_path):
    content = tmp_path / "content"
    _write(content / "draft.md", "---\ntitle: Draft\ndate: 2026-05-02\ndraft: true\n---\n\nd\n")
    _write(content / "live.md", "---\ntitle: Live\ndate: 2026-05-01\n---\n\nl\n")

    result = _run_build(tmp_path)

    assert result.returncode == 0, result.stderr
    index = _read(tmp_path / "dist" / "index.html")
    # The draft has no entry on the index; the published post does.
    assert "draft.html" not in index, index
    assert "live.html" in index, index


def test_story_5_draft_contributes_no_tag_page_or_count(tmp_path):
    content = tmp_path / "content"
    # The draft carries a tag that NO published post carries. By default that
    # tag must not produce a tag page nor appear in the index Tags section.
    _write(
        content / "draft.md",
        "---\ntitle: Draft\ndate: 2026-05-02\ndraft: true\ntags: [secret]\n---\n\nd\n",
    )
    _write(
        content / "live.md",
        "---\ntitle: Live\ndate: 2026-05-01\ntags: [public]\n---\n\nl\n",
    )

    result = _run_build(tmp_path)

    assert result.returncode == 0, result.stderr
    tags_dir = tmp_path / "dist" / "tags"
    # Only the published post's tag yields a page; the draft-only tag does not.
    produced = sorted(p.name for p in tags_dir.glob("*.html"))
    assert produced == ["public.html"], produced
    assert not (tags_dir / "secret.html").exists()
    # The index Tags section never mentions the draft-only tag.
    index = _read(tmp_path / "dist" / "index.html")
    assert "secret" not in index, index


def test_story_5_draft_sharing_a_tag_does_not_inflate_count(tmp_path):
    content = tmp_path / "content"
    # Both a draft and a published post carry tag "shared"; by default only the
    # published post counts toward that tag and appears on its page.
    _write(
        content / "draft.md",
        "---\ntitle: Draft\ndate: 2026-05-02\ndraft: true\ntags: [shared]\n---\n\nd\n",
    )
    _write(
        content / "live.md",
        "---\ntitle: Live\ndate: 2026-05-01\ntags: [shared]\n---\n\nl\n",
    )

    result = _run_build(tmp_path)

    assert result.returncode == 0, result.stderr
    page = _read(tmp_path / "dist" / "tags" / "shared.html")
    # The shared tag page lists only the published post, not the draft.
    assert "live.html" in page, page
    assert "draft.html" not in page, page


# --- AC28: --include-drafts includes the draft with a [DRAFT] prefix ----------

def test_story_5_include_drafts_generates_page_and_index_entry(tmp_path):
    content = tmp_path / "content"
    _write(
        content / "draft.md",
        "---\ntitle: Draft\ndate: 2026-05-02\ndraft: true\ntags: [python]\n---\n\nd\n",
    )

    result = _run_build(tmp_path, "--include-drafts")

    assert result.returncode == 0, result.stderr
    # The draft's page now exists and it appears on the index.
    assert (tmp_path / "dist" / "draft.html").is_file()
    index = _read(tmp_path / "dist" / "index.html")
    assert "draft.html" in index, index


def test_story_5_include_drafts_adds_post_to_its_tag_pages(tmp_path):
    content = tmp_path / "content"
    _write(
        content / "draft.md",
        "---\ntitle: Draft\ndate: 2026-05-02\ndraft: true\ntags: [python]\n---\n\nd\n",
    )

    result = _run_build(tmp_path, "--include-drafts")

    assert result.returncode == 0, result.stderr
    # The draft-only tag now has a page that lists the draft.
    page = tmp_path / "dist" / "tags" / "python.html"
    assert page.is_file(), sorted(p.name for p in (tmp_path / "dist" / "tags").glob("*"))
    assert "draft.html" in _read(page), _read(page)


def test_story_5_include_drafts_marks_index_entry_with_draft_prefix(tmp_path):
    content = tmp_path / "content"
    _write(content / "draft.md", "---\ntitle: My Draft\ndate: 2026-05-02\ndraft: true\n---\n\nd\n")

    result = _run_build(tmp_path, "--include-drafts")

    assert result.returncode == 0, result.stderr
    index = _read(tmp_path / "dist" / "index.html")
    # The index entry's title is prefixed with [DRAFT].
    assert "[DRAFT] My Draft" in index, index


def test_story_5_include_drafts_marks_tag_page_entry_with_draft_prefix(tmp_path):
    content = tmp_path / "content"
    _write(
        content / "draft.md",
        "---\ntitle: My Draft\ndate: 2026-05-02\ndraft: true\ntags: [python]\n---\n\nd\n",
    )

    result = _run_build(tmp_path, "--include-drafts")

    assert result.returncode == 0, result.stderr
    page = _read(tmp_path / "dist" / "tags" / "python.html")
    # The draft's title is prefixed with [DRAFT] where it is listed on the tag page.
    assert "[DRAFT] My Draft" in page, page


def test_story_5_include_drafts_marks_post_title_and_h1_with_draft_prefix(tmp_path):
    content = tmp_path / "content"
    _write(content / "draft.md", "---\ntitle: My Draft\ndate: 2026-05-02\ndraft: true\n---\n\nbody\n")

    result = _run_build(tmp_path, "--include-drafts")

    assert result.returncode == 0, result.stderr
    page = _read(tmp_path / "dist" / "draft.html")
    # Both the <title> and the <h1> carry the [DRAFT] prefix on the draft's page.
    assert "<title>[DRAFT] My Draft</title>" in page, page
    assert "<h1>[DRAFT] My Draft</h1>" in page, page


def test_story_5_published_post_has_no_draft_prefix(tmp_path):
    content = tmp_path / "content"
    # With --include-drafts on, a published post alongside a draft must NOT gain
    # a [DRAFT] marker -- the prefix is exclusive to drafts.
    _write(content / "draft.md", "---\ntitle: Draft\ndate: 2026-05-02\ndraft: true\n---\n\nd\n")
    _write(content / "live.md", "---\ntitle: Live Post\ndate: 2026-05-01\n---\n\nl\n")

    result = _run_build(tmp_path, "--include-drafts")

    assert result.returncode == 0, result.stderr
    page = _read(tmp_path / "dist" / "live.html")
    assert "[DRAFT]" not in page, page
    assert "<h1>Live Post</h1>" in page, page


# --- AC29: truthy strings (true/yes/1) are treated as drafts ------------------

def test_story_5_string_true_is_draft(tmp_path):
    content = tmp_path / "content"
    _write(content / "post.md", '---\ntitle: Q\ndate: 2026-05-01\ndraft: "true"\n---\n\nx\n')

    result = _run_build(tmp_path)

    assert result.returncode == 0, result.stderr
    # draft: "true" (string) is a draft -> excluded by default.
    assert not (tmp_path / "dist" / "post.html").exists()
    assert "post.html" not in _read(tmp_path / "dist" / "index.html")


def test_story_5_string_yes_is_draft(tmp_path):
    content = tmp_path / "content"
    _write(content / "post.md", '---\ntitle: Q\ndate: 2026-05-01\ndraft: "yes"\n---\n\nx\n')

    result = _run_build(tmp_path)

    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "dist" / "post.html").exists()
    assert "post.html" not in _read(tmp_path / "dist" / "index.html")


def test_story_5_string_one_is_draft(tmp_path):
    content = tmp_path / "content"
    _write(content / "post.md", '---\ntitle: Q\ndate: 2026-05-01\ndraft: "1"\n---\n\nx\n')

    result = _run_build(tmp_path)

    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "dist" / "post.html").exists()
    assert "post.html" not in _read(tmp_path / "dist" / "index.html")


# --- AC30: draft:"false" or no draft field -> published -----------------------

def test_story_5_string_false_is_published(tmp_path):
    content = tmp_path / "content"
    _write(content / "post.md", '---\ntitle: Q\ndate: 2026-05-01\ndraft: "false"\n---\n\nx\n')

    result = _run_build(tmp_path)

    assert result.returncode == 0, result.stderr
    # draft: "false" (string) is NOT a draft -> published by default.
    assert (tmp_path / "dist" / "post.html").is_file()
    index = _read(tmp_path / "dist" / "index.html")
    assert "post.html" in index, index
    # A published post carries no [DRAFT] marker.
    assert "[DRAFT]" not in _read(tmp_path / "dist" / "post.html")


def test_story_5_missing_draft_field_is_published(tmp_path):
    content = tmp_path / "content"
    _write(content / "post.md", "---\ntitle: Q\ndate: 2026-05-01\n---\n\nx\n")

    result = _run_build(tmp_path)

    assert result.returncode == 0, result.stderr
    # No draft field -> published.
    assert (tmp_path / "dist" / "post.html").is_file()
    assert "post.html" in _read(tmp_path / "dist" / "index.html")


def test_story_5_boolean_false_is_published(tmp_path):
    content = tmp_path / "content"
    _write(content / "post.md", "---\ntitle: Q\ndate: 2026-05-01\ndraft: false\n---\n\nx\n")

    result = _run_build(tmp_path)

    assert result.returncode == 0, result.stderr
    # draft: false (boolean) -> published.
    assert (tmp_path / "dist" / "post.html").is_file()
    assert "post.html" in _read(tmp_path / "dist" / "index.html")


# --- AC31: unrecognized non-boolean string -> nonzero, error names the file ---

def test_story_5_unrecognized_draft_string_fails_nonzero(tmp_path):
    content = tmp_path / "content"
    _write(content / "good.md", "---\ntitle: Good\ndate: 2026-05-02\n---\n\nok\n")
    _write(content / "bad.md", '---\ntitle: Bad\ndate: 2026-05-01\ndraft: "maybe"\n---\n\nbody\n')

    result = _run_build(tmp_path)

    assert result.returncode != 0
    # No success summary leaks to stdout on failure.
    assert "built" not in result.stdout.lower(), result.stdout


def test_story_5_unrecognized_draft_string_error_names_file(tmp_path):
    content = tmp_path / "content"
    _write(content / "bad.md", '---\ntitle: Bad\ndate: 2026-05-01\ndraft: "maybe"\n---\n\nbody\n')

    result = _run_build(tmp_path)

    assert result.returncode != 0
    # The error message names the offending file so the author can find it.
    assert "bad.md" in result.stderr, result.stderr


# --- AC32: all posts are drafts + no --include-drafts -> "No posts yet." ------

def test_story_5_all_drafts_no_flag_says_no_posts_yet(tmp_path):
    content = tmp_path / "content"
    _write(content / "a.md", "---\ntitle: A\ndate: 2026-05-02\ndraft: true\n---\n\na\n")
    _write(content / "b.md", "---\ntitle: B\ndate: 2026-05-01\ndraft: true\n---\n\nb\n")

    result = _run_build(tmp_path)

    assert result.returncode == 0, result.stderr
    index = tmp_path / "dist" / "index.html"
    assert index.is_file()
    # Same as an empty content directory (STORY-3 AC15).
    assert "No posts yet." in _read(index), _read(index)


def test_story_5_all_drafts_no_flag_generates_no_post_pages(tmp_path):
    content = tmp_path / "content"
    _write(content / "a.md", "---\ntitle: A\ndate: 2026-05-02\ndraft: true\n---\n\na\n")
    _write(content / "b.md", "---\ntitle: B\ndate: 2026-05-01\ndraft: true\n---\n\nb\n")

    result = _run_build(tmp_path)

    assert result.returncode == 0, result.stderr
    # No post pages and no tags dir when every post is an excluded draft.
    assert not (tmp_path / "dist" / "a.html").exists()
    assert not (tmp_path / "dist" / "b.html").exists()
