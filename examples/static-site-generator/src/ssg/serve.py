"""Local preview server for a built ``dist/`` (``python -m ssg serve``).

Library module: it serves ``dist/`` over ``http.server`` and surfaces problems
by raising -- it MUST NOT print (per docs/conventions.md). Request logging and
the ``stopping`` notice are delivered through caller-supplied callbacks so that
``__main__`` remains the only module that writes to stdout/stderr.
"""

from __future__ import annotations

import signal
import threading
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Callable

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


class _DistHandler(SimpleHTTPRequestHandler):
    """Serves files from a fixed directory and routes logs to a callback.

    ``SimpleHTTPRequestHandler`` writes its access log to stderr by default;
    routing it through ``log`` keeps all output decisions in the CLI.
    """

    def __init__(self, *args, log: Callable[[str], None], **kwargs) -> None:
        self._log = log
        super().__init__(*args, **kwargs)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        self._log(format % args)

    def log_error(self, format: str, *args) -> None:  # noqa: A002
        # Errors (e.g. 404s) already arrive via log_request; suppress the
        # duplicate stderr line so logging stays single-sourced.
        pass


def _validate_dist(dist_dir: Path) -> None:
    if not dist_dir.is_dir():
        raise ValueError(f"{dist_dir}: dist directory does not exist")
    if not any(dist_dir.iterdir()):
        raise ValueError(f"{dist_dir}: dist directory is empty")


def make_server(
    dist_dir: Path,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    log: Callable[[str], None] | None = None,
) -> HTTPServer:
    """Bind an HTTP server serving ``dist_dir`` on ``host:port``.

    ``port`` 0 binds an OS-chosen free port; read it back from
    ``server.server_address[1]``. ``log`` (if given) receives one line per
    request. Raises ValueError if ``dist_dir`` is missing or empty.

    Returns: a bound, not-yet-serving ``HTTPServer``.
    """
    _validate_dist(dist_dir)
    sink: Callable[[str], None] = log if log is not None else (lambda _line: None)
    handler = partial(_DistHandler, directory=str(dist_dir), log=sink)
    return HTTPServer((host, port), handler)


def serve_dist(
    dist_dir: Path,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    log: Callable[[str], None] | None = None,
    on_bound: Callable[[HTTPServer], None] | None = None,
) -> None:
    """Serve ``dist_dir`` until interrupted (Ctrl-C), then shut down cleanly.

    Binds via :func:`make_server`, invokes ``on_bound(server)`` once bound (so
    the caller can learn the chosen port), then serves until an interrupt.
    Serving runs on a worker thread; the main thread waits on an event that an
    installed signal handler sets (SIGINT, and SIGBREAK on Windows where Ctrl-C
    in a new process group arrives as CTRL_BREAK_EVENT). ``shutdown()`` then
    lets the in-flight request finish before the loop stops, so a request being
    served when the interrupt arrived completes rather than being dropped.
    Raises ValueError if ``dist_dir`` is missing or empty.

    Returns: None (returns normally after a clean shutdown).
    """
    server = make_server(dist_dir, host, port, log)
    if on_bound is not None:
        on_bound(server)

    stop = threading.Event()

    def _request_stop(_signum, _frame) -> None:
        stop.set()

    previous = _install_stop_handlers(_request_stop)

    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        # Block until a signal sets the event. ``wait()`` returns on the signal
        # (or KeyboardInterrupt, the fallback when no handler was installable).
        while not stop.wait(timeout=0.5):
            if not worker.is_alive():
                break
    except KeyboardInterrupt:
        pass
    finally:
        _restore_handlers(previous)
        server.shutdown()
        worker.join()
        server.server_close()


def _install_stop_handlers(handler) -> dict[int, object]:
    """Install ``handler`` for the interrupt signals; return prior handlers.

    Signals can only be set from the main thread; if serving runs off-main
    (e.g. under a test harness), this is a no-op and the loop falls back to
    KeyboardInterrupt.

    Returns: a mapping of signal number to its previous handler.
    """
    previous: dict[int, object] = {}
    signums = [signal.SIGINT]
    if hasattr(signal, "SIGBREAK"):
        signums.append(signal.SIGBREAK)
    for signum in signums:
        try:
            previous[signum] = signal.signal(signum, handler)
        except (ValueError, OSError):
            pass
    return previous


def _restore_handlers(previous: dict[int, object]) -> None:
    for signum, prior in previous.items():
        try:
            signal.signal(signum, prior)
        except (ValueError, OSError):
            pass
