# STORY-6 Implementation Map

Last updated: 2026-05-24 by Developer (cycle 1)

## AC33 ("GET /hello.html -> 200 and body equals the bytes of dist/hello.html")
Implemented in:
- src/ssg/serve.py:66 (`make_server` -- builds an `HTTPServer` whose handler is `_DistHandler` rooted at `dist_dir` via `partial(_DistHandler, directory=str(dist_dir), ...)`, so `http.server`'s file-serving returns each existing file's exact bytes with status 200)
- src/ssg/serve.py:22 (`_DistHandler` -- subclasses `SimpleHTTPRequestHandler`, which maps the request path to a file under the served directory and writes its bytes back unchanged)
- src/ssg/serve.py:89 (`serve_dist` -- binds the server and runs `serve_forever` on the worker thread so the handler actually answers live GET requests)
- src/ssg/__main__.py:69 (`_run_serve` -- calls `serve_dist(dist_dir, ...)` with `dist_dir = Path.cwd() / "dist"`, so `GET /hello.html` resolves to `dist/hello.html`)

## AC34 ("GET a path that does not exist in dist/ -> 404")
Implemented in:
- src/ssg/serve.py:22 (`_DistHandler` -- inherits `SimpleHTTPRequestHandler.send_head`, which returns HTTP 404 when the requested path has no corresponding file under the served directory)
- src/ssg/serve.py:66 (`make_server` -- roots the handler at `dist_dir`; a path absent from `dist/` therefore yields the standard 404)
- src/ssg/serve.py:36 (`_DistHandler.log_error` -- the 404 is still served normally; this only routes the duplicate error log so output stays single-sourced, it does not alter the response status)

## AC35 ("binds 127.0.0.1, not 0.0.0.0; default port is 8000")
Implemented in:
- src/ssg/serve.py:18 (`DEFAULT_HOST = "127.0.0.1"` -- module-level constant the AC35 test imports and asserts; loopback, never `0.0.0.0`)
- src/ssg/serve.py:19 (`DEFAULT_PORT = 8000` -- module-level constant the AC35 test imports and asserts as the default)
- src/ssg/serve.py:66 (`make_server` -- `HTTPServer((host, port), handler)` binds the address tuple using `host` defaulting to `DEFAULT_HOST`, so the server is reachable only on 127.0.0.1)
- src/ssg/serve.py:51 (`make_server` signature -- `host: str = DEFAULT_HOST`, `port: int = DEFAULT_PORT`, carrying the loopback/8000 defaults into the bind)
- src/ssg/__main__.py:16 (`_run_serve` imports `DEFAULT_PORT`; `_parse_port` returns `DEFAULT_PORT` (8000) when no `--port` is given, src/ssg/__main__.py:41)

## AC36 ("Ctrl-C / interrupt -> prints 'stopping', exits 0, in-flight request completes")
Implemented in:
- src/ssg/serve.py:100 (`serve_dist` -- runs `server.serve_forever` on a daemon worker thread so the interrupt is received by the main thread between requests rather than mid-handler)
- src/ssg/serve.py:95 (`serve_dist._request_stop` -- the installed signal handler sets a `threading.Event` instead of tearing the process down, turning the interrupt into a graceful stop request)
- src/ssg/serve.py:117 (`_install_stop_handlers` -- registers the handler for `SIGINT` and, on Windows, `SIGBREAK` so a `CTRL_BREAK_EVENT` delivered to a new process group is caught rather than killing the process)
- src/ssg/serve.py:112 (`serve_dist` finally-block -- calls `server.shutdown()` then `worker.join()`; `shutdown()` stops the serve loop only at the top of its next iteration, so a request being served when the interrupt arrived runs to completion before the loop exits, and `serve_dist` then returns normally)
- src/ssg/__main__.py:80 (`_run_serve` -- after `serve_dist` returns from the clean shutdown, prints `stopping` to stdout and returns 0; the only place 'stopping' is printed and the exit code is decided)
- src/ssg/__main__.py:108 (`sys.exit(main())` -- the 0 returned on clean shutdown becomes the process exit status)
