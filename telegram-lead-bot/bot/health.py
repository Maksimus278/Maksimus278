"""Minimal HTTP health endpoint so Render free-tier web services stay alive."""
from __future__ import annotations

import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import os


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format, *args):
        pass  # suppress access logs


def start_health_server():
    """Start a background HTTP server on PORT (default 10000) for Render health checks."""
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), _Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
