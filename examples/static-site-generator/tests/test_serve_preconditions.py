"""STORY-8 integration tests for the ``serve`` command's failure preconditions.

Seam under test: the ``serve`` command exactly as a user runs it -- an actual
``python -m ssg serve`` subprocess invoked from a working directory whose
``dist/`` is missing, empty, or whose requested port is already taken. All
assertions are on observable output: the process exit code (must be nonzero)
and the message written to stderr.

Per docs/conventions.md, library code raises and ``__main__`` is the only module
that prints; these tests exercise that boundary end-to-end through the CLI.

Per docs/testing.md, serve tests never depend on a fixed port being free: AC41
discovers a port at runtime by binding it ourselves (keeping the socket open so
the port is genuinely occupied), then asks the server for that same port and
asserts it refuses.

AC coverage:
  - AC39: no ./dist/ directory -> exit nonzero, stderr is exactly
    "dist/ is empty — run 'python -m ssg build' first".
  - AC40: ./dist/ exists but is empty -> exit nonzero, same message.
  - AC41: requested port already bound -> exit nonzero, stderr names the port
    and suggests the --port flag.

All tests are named ``test_story_8_*`` so the Tester can filter with
``pytest -k "story_8"``.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"

HOST = "127.0.0.1"

# The exact empty-dist message and the port-busy message are owned by the CLI
# module; import them from source so these tests assert against the real
# strings (including the em-dash) rather than re-typing a literal that could
# drift from production. conftest.py has already put src/ on sys.path.
from ssg.__main__ import DIST_EMPTY_MSG  # noqa: E402


def _serve_env() -> dict[str, str]:
    return {
        **dict(os.environ),
        "PYTHONPATH": str(SRC_DIR),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "PYTHONUNBUFFERED": "1",
    }


def _run_serve(cwd: Path, *args: str, timeout: float = 30.0) -> subprocess.CompletedProcess:
    """Run ``python -m ssg serve`` to completion and capture stdout/stderr.

    Used for the precondition cases (AC39/AC40/AC41) where the command is
    expected to fail fast and exit on its own -- so we can simply wait for it
    rather than interrupting a long-lived server. Decodes as UTF-8 so the
    em-dash in the empty-dist message round-trips regardless of host locale.
    """
    return subprocess.run(
        [sys.executable, "-m", "ssg", "serve", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_serve_env(),
        timeout=timeout,
    )


# --- AC39: no ./dist/ at all -> nonzero exit, exact empty-dist message --------

def test_story_8_serve_with_no_dist_exits_nonzero_with_empty_message(tmp_path):
    """A working dir with no ``dist/`` makes ``serve`` fail with the exact msg."""
    assert not (tmp_path / "dist").exists()

    result = _run_serve(tmp_path)

    assert result.returncode != 0, (
        f"serve should refuse to start without dist/; "
        f"got exit {result.returncode}\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert result.stderr.strip() == DIST_EMPTY_MSG, (
        f"stderr must be exactly the empty-dist message.\n"
        f"expected: {DIST_EMPTY_MSG!r}\nactual:   {result.stderr.strip()!r}"
    )


# --- AC40: ./dist/ exists but empty -> same nonzero failure -------------------

def test_story_8_serve_with_empty_dist_exits_nonzero_with_empty_message(tmp_path):
    """An existing-but-empty ``dist/`` produces the identical failure as AC39."""
    (tmp_path / "dist").mkdir()
    assert (tmp_path / "dist").is_dir()
    assert not any((tmp_path / "dist").iterdir())

    result = _run_serve(tmp_path)

    assert result.returncode != 0, (
        f"serve should refuse an empty dist/; "
        f"got exit {result.returncode}\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert result.stderr.strip() == DIST_EMPTY_MSG, (
        f"stderr must be exactly the empty-dist message.\n"
        f"expected: {DIST_EMPTY_MSG!r}\nactual:   {result.stderr.strip()!r}"
    )


# --- AC41: requested port already in use -> nonzero, names port, suggests flag

def test_story_8_serve_on_busy_port_exits_nonzero_naming_port_and_suggesting_flag(tmp_path):
    """A non-empty dist/ but an already-bound port -> clear, actionable error.

    We occupy a port ourselves by binding a listening socket and keeping it open
    for the duration of the run, so the port is genuinely in use (no reliance on
    a hard-coded port being free or taken). The server is then asked for that
    exact port; it must exit nonzero and the error must name the port number and
    point the user at the --port flag.
    """
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "hello.html").write_bytes(b"<!doctype html><html><body>hi</body></html>\n")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as blocker:
        blocker.bind((HOST, 0))
        blocker.listen(1)
        busy_port = blocker.getsockname()[1]

        # The blocking socket stays open across this call, so binding busy_port
        # must fail inside the server process.
        result = _run_serve(tmp_path, "--port", str(busy_port))

    assert result.returncode != 0, (
        f"serve should fail when the requested port is busy; "
        f"got exit {result.returncode}\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert str(busy_port) in result.stderr, (
        f"error must name the busy port {busy_port}.\nstderr: {result.stderr!r}"
    )
    assert "--port" in result.stderr, (
        f"error must suggest the --port flag.\nstderr: {result.stderr!r}"
    )
