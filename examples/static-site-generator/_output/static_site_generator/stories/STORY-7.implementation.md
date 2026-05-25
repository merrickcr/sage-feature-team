# STORY-7 Implementation Map

Last updated: 2026-05-24 by Developer (cycle 1)

## AC37 ("serve --port 9001 binds to 9001, not the default 8000")
Implemented in:
- src/ssg/__main__.py:36 (`_parse_port` -- recognizes `["--port", N]` and returns `int(N)`, so the requested port (e.g. 9001) is what flows through; it returns the 8000 default ONLY when no args are given, so a supplied `--port` always overrides the default)
- src/ssg/__main__.py:51 (`_run_serve` -- calls `serve_dist(dist_dir, port=port, ...)`, passing the parsed port straight through to the server rather than the default)
- src/ssg/serve.py:49 (`make_server` -- forwards `port` into `HTTPServer((host, port), handler)`, binding the exact requested port number)
- src/ssg/serve.py:66 (`make_server` -- the `HTTPServer((host, port), handler)` bind call; with port=9001 the listening socket is bound to 9001, not 8000)
- src/ssg/__main__.py:59 (`_run_serve.announce` -- reads `server.server_address[1]` and prints `serving on port {chosen} ...`, so the reported port equals the bound (requested) port for the AC37 assertion)

## AC38 ("serve --port 0 binds an OS-chosen free nonzero port and prints it")
Implemented in:
- src/ssg/__main__.py:36 (`_parse_port` -- `int("0")` yields 0, so `--port 0` is passed through as the integer 0 rather than rejected)
- src/ssg/__main__.py:51 (`_run_serve` -- passes `port=0` into `serve_dist`, which forwards it to the bind)
- src/ssg/serve.py:66 (`make_server` -- `HTTPServer((host, 0), handler)` asks the kernel to assign a free ephemeral port; the bound socket then carries the OS-chosen nonzero port)
- src/ssg/__main__.py:59 (`_run_serve.announce` -- after binding, reads the concrete chosen port from `server.server_address[1]` (never 0 once bound) and prints `serving on port {chosen} ...` to stdout, satisfying the "prints the chosen port" requirement)
- src/ssg/serve.py:74 (`serve_dist` -- invokes `on_bound(server)` immediately after binding via `make_server`, which is how `announce` learns and prints the OS-chosen port before serving begins)
