#!/usr/bin/env python3
"""Serve the built React app on the Local Hub with SPA fallback.

This intentionally has no third-party runtime dependency. Static assets are
served normally and unknown browser routes fall back to index.html so routes
such as /cafe/orders and /super-admin work after refresh on the local LAN.
"""

from __future__ import annotations

import argparse
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


class SpaHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        request_path = urlsplit(self.path).path
        relative = request_path.lstrip("/")
        candidate = Path(self.directory or ".") / relative
        if request_path != "/" and not candidate.exists():
            self.path = "/index.html"
        super().do_GET()

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        super().end_headers()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", required=True)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4173)
    args = parser.parse_args()

    root = Path(args.directory).resolve()
    index = root / "index.html"
    if not index.is_file():
        raise SystemExit(f"React build not found: {index}")

    os.chdir(root)
    handler = lambda *a, **kw: SpaHandler(*a, directory=str(root), **kw)  # noqa: E731
    server = ThreadingHTTPServer((args.bind, args.port), handler)
    print(f"Serving Local Hub UI from {root} on http://{args.bind}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
