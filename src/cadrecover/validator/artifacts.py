"""Serve public artifacts (drawing PNGs) to miners. Only the public store is exposed."""

from __future__ import annotations

import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from cadrecover import paths


class _Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):  # quiet
        pass

    def do_PUT(self):  # read-only store
        self.send_error(405)

    do_POST = do_DELETE = do_PUT


def serve(host: str = "127.0.0.1", port: int = 8790) -> tuple[ThreadingHTTPServer, str]:
    # (8090 is commonly taken on Windows hosts, which WSL's mirrored networking shares)
    paths.ensure()
    handler = functools.partial(_Handler, directory=str(paths.PUBLIC))
    server = ThreadingHTTPServer((host, port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://{host}:{port}"
