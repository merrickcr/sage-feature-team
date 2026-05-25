"""STORY-7 integration tests for the ``serve --port`` flag.

Seam under test: the ``serve`` command exactly as a user runs it -- a real
``dist/`` on disk, an actual ``python -m ssg serve --port <N>`` subprocess, and
real HTTP requests against the running server. All assertions are on observable
output: the chosen-port line printed to stdout and the HTTP status of a request
made against that port.

Per docs/testing.md, serve tests must never depend on a fixed port being free.
For ``--port <N>`` (AC37) we therefore discover a currently-free port at runtime
(bind port 0, read it back, release it) and ask the server for that exact
number, retrying if the brief release window let something else grab it. For
``--port 0`` (AC38) the OS picks the port and the command prints it; we assert
the printed port is nonzero and is genuinely serving.

AC coverage:
  - AC37: ``serve --port <N>`` binds to N (the requested port, not the default
    8000) -- the command reports N and a request to N succeeds.
  - AC38: ``serve --port 0`` binds an OS-chosen free, nonzero port and prints
    that chosen port to stdout.

All tests are named ``test_story_7_*`` so the Tester can filter with
``pytest -k "story_7"``.
"""

from __future__ import annotations

import http.client
import os
import re
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"

HOST = "127.0.0.1"
HELLO_HTML = b"<!doctype html><html><body><h1>hello</h1></body></html>\n"
DEFAULT_PORT = 8000
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

    The command prints the bound port on a stdout line; we scan line by line
    (readline blocks until the server has bound and printed) and return the
    first integer in the 2-5 digit range we find. If the process exits before
    printing a port, surface its stdout/stderr to make the failure debuggable.
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


def _find_free_port() -> int:
    """Ask the OS for a currently-free TCP port on loopback, then release it.

    Binding port 0 lets the kernel choose a port that is free *right now*; we
    read it back and close the socket so the server can claim it. There is a
    tiny window between release and re-bind, which the caller handles by
    retrying with a fresh free port if needed -- this keeps the test from ever
    depending on a hard-coded port being available.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


# --- AC37: --port <N> binds the requested port (not the default 8000) --------

def test_story_7_port_flag_binds_requested_port_not_default(tmp_path):
    """``serve --port <N>`` reports and serves on N, and N is not the default.

    We request a port the OS just told us was free (never a hard-coded one).
    Because there is a small release-then-rebind race, we retry on a fresh free
    port a few times before giving up; a genuine bug (ignoring --port, or always
    using 8000) fails every attempt, while a transient port steal is shrugged
    off.
    """
    _make_dist(tmp_path)

    last_error: AssertionError | None = None
    for _attempt in range(5):
        requested = _find_free_port()
        assert requested != DEFAULT_PORT  # OS-chosen ephemeral ports are high
        proc = _popen_serve(tmp_path, "--port", str(requested))
        try:
            try:
                reported = _read_chosen_port(proc)
            except AssertionError as exc:
                # Port likely got stolen in the release window -> retry. Only
                # treat it as a real failure if every attempt fails.
                last_error = exc
                continue

            assert reported == requested, (
                f"serve --port {requested} bound port {reported} instead "
                f"(must honor the requested port, not fall back to a default)"
            )
            assert reported != DEFAULT_PORT

            # And it is genuinely serving on that requested port.
            status, body = _http_get(requested, "/hello.html")
            assert status == 200
            assert body == HELLO_HTML
            return
        finally:
            _interrupt(proc)
            _terminate_quietly(proc)

    raise AssertionError(
        f"could not bind a freshly-discovered free port across retries: {last_error}"
    )


# --- AC38: --port 0 binds an OS-chosen free nonzero port and prints it -------

def test_story_7_port_zero_binds_nonzero_chosen_port_and_prints_it(tmp_path):
    """``serve --port 0`` prints a nonzero OS-chosen port and serves on it."""
    _make_dist(tmp_path)
    proc = _popen_serve(tmp_path, "--port", "0")
    try:
        chosen = _read_chosen_port(proc)

        assert chosen != 0, "--port 0 must resolve to a concrete nonzero port"
        assert chosen > 0

        # The printed port is the one actually being served.
        status, body = _http_get(chosen, "/hello.html")
        assert status == 200
        assert body == HELLO_HTML
    finally:
        _interrupt(proc)
        _terminate_quietly(proc)
