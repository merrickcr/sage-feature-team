# STORY-8 Implementation Map

Last updated: 2026-05-24 by Developer (cycle 1)

## AC39 ("no ./dist/ directory -> exit nonzero, stderr exactly the empty-dist message")
Implemented in:
- src/ssg/serve.py:42 (`_validate_dist` -- the `if not dist_dir.is_dir():` branch raises `ValueError` when no `dist/` directory exists, so the missing-directory case is surfaced as a raise rather than a print, per the library-raises rule)
- src/ssg/serve.py:63 (`make_server` -- calls `_validate_dist(dist_dir)` first thing, before any `HTTPServer` bind, so a missing `dist/` fails fast)
- src/ssg/serve.py:89 (`serve_dist` -- delegates binding to `make_server`, so the `_validate_dist` raise propagates up to the CLI before serving starts)
- src/ssg/__main__.py:57 (`_run_serve` -- builds `dist_dir = Path.cwd() / "dist"` and passes it into `serve_dist`, so the validated path is the user's current-directory `dist/`)
- src/ssg/__main__.py:71 (`_run_serve` -- the `except ValueError:` arm catches the `_validate_dist` raise, writes `DIST_EMPTY_MSG` to stderr via `print(..., file=sys.stderr)`, and `return 1` gives the nonzero exit code)
- src/ssg/__main__.py:20 (`DIST_EMPTY_MSG` -- the exact em-dash string `"dist/ is empty — run 'python -m ssg build' first"`, which is the literal the test imports and asserts stderr equals)

## AC40 ("./dist/ exists but is empty -> exit nonzero, same empty-dist message")
Implemented in:
- src/ssg/serve.py:44 (`_validate_dist` -- after the is_dir check, the `if not any(dist_dir.iterdir()):` branch raises `ValueError` when the directory exists but yields no entries, covering the empty-directory case with the same exception type as the missing case)
- src/ssg/serve.py:63 (`make_server` -- runs `_validate_dist(dist_dir)` ahead of the bind, so an empty `dist/` is rejected before a socket is opened)
- src/ssg/__main__.py:71 (`_run_serve` -- the single `except ValueError:` arm handles both the missing and empty cases identically: same `DIST_EMPTY_MSG` to stderr, same `return 1`, so AC39 and AC40 produce byte-identical output as the AC requires)
- src/ssg/__main__.py:20 (`DIST_EMPTY_MSG` -- the one shared message constant used for both the missing-dir and empty-dir failures, guaranteeing the two cases emit the same text)

## AC41 ("requested port already bound -> exit nonzero, stderr names the port and suggests --port")
Implemented in:
- src/ssg/__main__.py:36 (`_parse_port` -- parses `["--port", N]` into the integer port the user requested, so the exact busy port number flows through to the bind and is available to name in the error message)
- src/ssg/__main__.py:51 (`_run_serve` -- captures the parsed `port` and threads it both into `serve_dist(dist_dir, port=port, ...)` and into the error string, so the message names the same port that failed to bind)
- src/ssg/serve.py:66 (`make_server` -- the `HTTPServer((host, port), handler)` bind call; `HTTPServer` leaves `allow_reuse_address` False, so binding a port another socket already holds raises `OSError` (e.g. WinError 10048/10013) rather than silently succeeding)
- src/ssg/__main__.py:74 (`_run_serve` -- the `except OSError:` arm catches the failed bind from `make_server` and writes the actionable error to stderr)
- src/ssg/__main__.py:76 (`_run_serve` -- the error string `f"port {port} is already in use — try a different --port"` interpolates the busy port number (satisfying "names port N") and contains the literal substring `--port` (satisfying "suggests the --port flag"); the surrounding `return 1` gives the nonzero exit)
