"""STORY-6 integration tests for ``python -m ssg serve``.

Seam under test: the ``serve`` command as a user runs it -- a real ``dist/``
directory on disk, an actual ``python -m ssg serve`` subprocess, and real HTTP
requests against the running server. All assertions are on observable output:
HTTP response status codes, response body bytes, the chosen-port line the
command prints, and the process exit code on shutdown.

Per docs/testing.md, serve tests bind to **port 0** (the OS picks a free port)
and read the chosen port back from the command's stdout, then talk to
``127.0.0.1:<port>``. Tests never depend on a fixed port being free and never
assert on log-line format -- only on HTTP status/body and exit codes.

AC coverage:
  - AC33: GET an existing file -> 200 and body == the file's bytes.
  - AC34: GET a missing path -> 404.
  - AC35: binds 127.0.0.1 (loopback, not 0.0.0.0); default port is 8000.
  - AC36: interrupt (Ctrl-C) -> prints 'stopping', exits 0, in-flight request
    completes rather than being dropped mid-response.

All tests are named ``test_story_6_*`` so the Tester can filter with
``pytest -k "story_6"``.
"""

from __future__ import annotations

import http.client
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"

HOST = "127.0.0.1"
HELLO_HTML = b"<!doctype html><html><body><h1>hello</h1></body></html>\n"
PORT_RE = re.compile(r"(\d{2,5})")


def _serve_env() -> dict[str, str]:
    return {
        **dict(os.environ),
        "PYTHONPATH": str(SRC_DIR),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        # Force unbuffered stdout so we can read the chosen-port line promptly.
        "PYTHONUNBUFFERED": "1",
    }


def _make_dist(root: Path) -> Path:
    """Create a non-empty ``dist/`` under ``root`` containing ``hello.html``."""
    dist = root / "dist"
    dist.mkdir()
    (dist / "hello.html").write_bytes(HELLO_HTML)
    return dist


def _popen_serve(cwd: Path, *args: str) -> subprocess.Popen:
    """Start ``python -m ssg serve`` in a way that lets us interrupt it later.

    On Windows an interrupt is delivered as a CTRL_BREAK_EVENT to a fresh
    process group, so the child is created with CREATE_NEW_PROCESS_GROUP. On
    POSIX a plain SIGINT to the child suffices, so start a new session there
    too for a clean, isolated signal target.
    """
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    return subprocess.Popen(
        [sys.executable, "-m", "ssg", "serve", *args],
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=_serve_env(),
        **kwargs,
    )


def _read_chosen_port(proc: subprocess.Popen, timeout: float = 15.0) -> int:
    """Read lines from the server's stdout until the chosen port appears.

    With ``--port 0`` the command prints the OS-chosen port; we scan stdout
    line by line (readline blocks until the server has bound and printed) and
    return the first integer in the 2-5 digit range we find.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        line = proc.stdout.readline()
        if line == "":  # EOF: process exited before printing a port
            break
        match = PORT_RE.search(line)
        if match:
            return int(match.group(1))
    out = ""
    err = ""
    try:
        out, err = proc.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
    raise AssertionError(
        f"serve did not print a chosen port within {timeout}s.\n"
        f"stdout so far: {out!r}\nstderr: {err!r}"
    )


def _interrupt(proc: subprocess.Popen) -> None:
    """Deliver a Ctrl-C-equivalent interrupt to the serve process."""
    if sys.platform == "win32":
        proc.send_signal(signal.CTRL_BREAK_EVENT)
    else:
        proc.send_signal(signal.SIGINT)


def _terminate_quietly(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.kill()
        try:
            proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            pass


def _http_get(port: int, path: str, timeout: float = 5.0):
    conn = http.client.HTTPConnection(HOST, port, timeout=timeout)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read()
        return resp.status, body
    finally:
        conn.close()


@pytest.fixture
def served_site(tmp_path):
    """Start ``serve`` on an OS-chosen free port over a tmp ``dist/``.

    Yields ``(port, proc)``. The server is always interrupted/torn down after
    the test, regardless of outcome.
    """
    _make_dist(tmp_path)
    proc = _popen_serve(tmp_path, "--port", "0")
    try:
        port = _read_chosen_port(proc)
        yield port, proc
    finally:
        _interrupt(proc)
        _terminate_quietly(proc)


# --- AC33: existing file -> 200, body equals file bytes ----------------------

def test_story_6_serve_returns_200_and_file_bytes_for_existing_file(served_site):
    port, _proc = served_site

    status, body = _http_get(port, "/hello.html")

    assert status == 200
    assert body == HELLO_HTML


# --- AC34: missing path -> 404 -----------------------------------------------

def test_story_6_serve_returns_404_for_missing_path(served_site):
    port, _proc = served_site

    status, _body = _http_get(port, "/does-not-exist.html")

    assert status == 404


# --- AC35: binds loopback (127.0.0.1, not 0.0.0.0); default port is 8000 -----

def test_story_6_serve_is_reachable_on_loopback_127_0_0_1(served_site):
    """The running server answers on 127.0.0.1 -- i.e. it bound loopback."""
    port, _proc = served_site

    status, _body = _http_get(port, "/hello.html")

    assert status == 200


def test_story_6_default_host_is_loopback_and_default_port_is_8000():
    """Unspecified config binds 127.0.0.1 (not 0.0.0.0) on port 8000.

    The serve module exposes its defaults as module-level constants
    (UPPER_SNAKE_CASE per docs/conventions.md); we assert their values rather
    than binding the real 8000 (which may be in use on the test host).
    """
    sys.path.insert(0, str(SRC_DIR))
    from ssg import serve

    assert serve.DEFAULT_HOST == "127.0.0.1"
    assert serve.DEFAULT_HOST != "0.0.0.0"
    assert serve.DEFAULT_PORT == 8000


# --- AC36: Ctrl-C -> prints 'stopping', exits 0, in-flight request completes -

def test_story_6_clean_shutdown_on_interrupt_prints_stopping_and_exits_zero(tmp_path):
    _make_dist(tmp_path)
    proc = _popen_serve(tmp_path, "--port", "0")
    try:
        port = _read_chosen_port(proc)
        # Sanity: it is genuinely serving before we interrupt it.
        status, _body = _http_get(port, "/hello.html")
        assert status == 200

        _interrupt(proc)
        out, _err = proc.communicate(timeout=15)
    finally:
        _terminate_quietly(proc)

    assert proc.returncode == 0, f"expected clean exit, got {proc.returncode}"
    assert "stopping" in out


def test_story_6_in_flight_request_completes_before_shutdown(tmp_path):
    """An interrupt during a live request finishes that request, not drops it."""
    _make_dist(tmp_path)
    proc = _popen_serve(tmp_path, "--port", "0")
    try:
        port = _read_chosen_port(proc)

        # Open a connection and send a request; while the response is being
        # served, deliver the interrupt. The in-flight request must still
        # complete with the correct status and body.
        conn = http.client.HTTPConnection(HOST, port, timeout=10)
        conn.request("GET", "/hello.html")
        _interrupt(proc)
        resp = conn.getresponse()
        body = resp.read()
        conn.close()

        assert resp.status == 200
        assert body == HELLO_HTML

        out, _err = proc.communicate(timeout=15)
    finally:
        _terminate_quietly(proc)

    assert proc.returncode == 0
    assert "stopping" in out
