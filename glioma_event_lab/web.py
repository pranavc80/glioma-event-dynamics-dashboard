"""Helpers for serving the static dashboard locally."""

from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def serve_directory(directory: str | Path, port: int = 8000) -> None:
    target = Path(directory).resolve()
    handler = partial(SimpleHTTPRequestHandler, directory=str(target))
    with ThreadingHTTPServer(("127.0.0.1", port), handler) as server:
        print(f"Serving {target} at http://127.0.0.1:{port}")
        server.serve_forever()
