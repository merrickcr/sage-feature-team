"""CLI entry point: ``python -m ssg build`` and ``python -m ssg serve``.

The only module that prints or decides exit codes (per docs/conventions.md).
Library code raises; this module catches, renders a one-line message, and maps
the outcome to stdout/stderr and an exit code.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from .builder import build_site
from .errors import FrontMatterError
from .serve import DEFAULT_PORT, serve_dist

USAGE = "usage: python -m ssg (build [--include-drafts] | serve [--port N])"
INCLUDE_DRAFTS_FLAG = "--include-drafts"
DIST_EMPTY_MSG = "dist/ is empty — run 'python -m ssg build' first"


def _run_build(*, include_drafts: bool = False) -> int:
    start = time.perf_counter()
    try:
        page_count = build_site(Path.cwd(), include_drafts=include_drafts)
    except (FileNotFoundError, FrontMatterError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    print(f"built {page_count} pages in {elapsed_ms}ms")
    return 0


def _parse_port(args: list[str]) -> int | None:
    """Parse an optional ``--port N`` from serve args.

    Returns: the port, or None if the args are malformed.
    """
    if not args:
        return DEFAULT_PORT
    if len(args) == 2 and args[0] == "--port":
        try:
            return int(args[1])
        except ValueError:
            return None
    return None


def _run_serve(args: list[str]) -> int:
    port = _parse_port(args)
    if port is None:
        print(USAGE, file=sys.stderr)
        return 2

    dist_dir = Path.cwd() / "dist"

    def announce(server) -> None:
        chosen = server.server_address[1]
        # Print the port first with no other digits ahead of it: the test
        # reads back the first 2-5 digit run on a stdout line as the port,
        # so a leading "127.0.0.1" would be misread.
        print(f"serving on port {chosen} (http://127.0.0.1:{chosen}/)", flush=True)

    def log(line: str) -> None:
        print(line, flush=True)

    try:
        serve_dist(dist_dir, port=port, log=log, on_bound=announce)
    except ValueError:
        print(DIST_EMPTY_MSG, file=sys.stderr)
        return 1
    except OSError:
        print(
            f"port {port} is already in use — try a different --port",
            file=sys.stderr,
        )
        return 1

    print("stopping", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Dispatch the CLI. Returns the process exit code.

    Returns: 0 on success, nonzero on any error.
    """
    args = sys.argv[1:] if argv is None else argv

    if not args:
        print(USAGE, file=sys.stderr)
        return 2

    command, rest = args[0], args[1:]
    if command == "build":
        if rest == [INCLUDE_DRAFTS_FLAG]:
            return _run_build(include_drafts=True)
        if rest:
            print(USAGE, file=sys.stderr)
            return 2
        return _run_build()
    if command == "serve":
        return _run_serve(rest)

    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
