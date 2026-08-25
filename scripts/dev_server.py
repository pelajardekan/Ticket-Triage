#!/usr/bin/env python3
"""
Run the whole of TicketTriage with nothing but Python.

The Azure Functions Core Tools and the SWA CLI are the "real" local runtimes,
and you should use them at least once before you deploy. But they need Node,
a .NET-based host and a working install, which is a lot of setup to lose a lab
session to. This script serves the static frontend and dispatches /api/*
straight into the same function handlers Azure will run, so the full app works
on a laptop with only `pip install -r api/requirements.txt`.

    python scripts/dev_server.py
    open http://localhost:4280

Anything that works here works on Azure, with two exceptions worth knowing:
routing rules in staticwebapp.config.json are not applied, and there is no
built-in authentication. Test those on a real deployment.
"""

import argparse
import json
import mimetypes
import pathlib
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

import azure.functions as func  # noqa: E402

import categories as categories_fn  # noqa: E402
import health as health_fn  # noqa: E402
import ticket_item as ticket_item_fn  # noqa: E402
import tickets as tickets_fn  # noqa: E402

FRONTEND = ROOT / "frontend"


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    # ---- plumbing ----------------------------------------------------
    def log_message(self, fmt, *args):
        sys.stderr.write("  %s\n" % (fmt % args))

    def _send(self, status, body: bytes, content_type: str, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    # ---- routing -----------------------------------------------------
    def _dispatch_api(self, method: str):
        parsed = urlparse(self.path)
        path = parsed.path
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        headers = {k.lower(): v for k, v in self.headers.items()}
        body = self._read_body()

        route_params = {}
        if path == "/api/tickets":
            handler = tickets_fn.main
        elif path.startswith("/api/tickets/"):
            handler = ticket_item_fn.main
            route_params = {"id": path[len("/api/tickets/"):]}
        elif path == "/api/categories":
            handler = categories_fn.main
        elif path == "/api/health":
            handler = health_fn.main
        else:
            return self._send(404, b'{"error":"No such API route."}', "application/json")

        request = func.HttpRequest(
            method=method, url=self.path, body=body or None,
            headers=headers, params=params, route_params=route_params,
        )
        try:
            response = handler(request)
        except Exception as exc:  # noqa: BLE001
            payload = json.dumps({"error": f"Unhandled error: {exc}"}).encode()
            return self._send(500, payload, "application/json")

        extra = {k: v for k, v in (response.headers or {}).items() if k.lower() != "content-type"}
        self._send(response.status_code, response.get_body(),
                   response.headers.get("Content-Type", "application/json"), extra)

    def _serve_static(self):
        path = urlparse(self.path).path
        if path in ("/", ""):
            path = "/user/submit-ticket.html"
        if path in ("/signin", "/signup", "/signout", "/lists", "/details", "/settings"):
            path = "/user/submit-ticket.html"
        if path == "/submit":
            path = "/user/submit-ticket.html"
        if path == "/admin":
            path = "/admin/ticket-lists.html"
        if path == "/admin/lists":
            path = "/admin/ticket-lists.html"
        if path == "/admin/details":
            path = "/admin/ticket-details.html"
        if path == "/admin/settings":
            path = "/admin/ticket-lists.html"
        target = (FRONTEND / path.lstrip("/")).resolve()
        if not str(target).startswith(str(FRONTEND.resolve())) or not target.is_file():
            target = FRONTEND / "index.html"

        content_type, _ = mimetypes.guess_type(str(target))
        if target.suffix == ".js":
            content_type = "text/javascript"
        self._send(200, target.read_bytes(), content_type or "application/octet-stream")

    # ---- verbs -------------------------------------------------------
    def do_GET(self):
        if self.path.startswith("/api/"):
            return self._dispatch_api("GET")
        self._serve_static()

    def do_POST(self):
        if self.path.startswith("/api/"):
            return self._dispatch_api("POST")
        self._send(405, b"", "text/plain")

    def do_PATCH(self):
        if self.path.startswith("/api/"):
            return self._dispatch_api("PATCH")
        self._send(405, b"", "text/plain")

    def do_PUT(self):
        if self.path.startswith("/api/"):
            return self._dispatch_api("PUT")
        self._send(405, b"", "text/plain")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=4280)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"TicketTriage dev server on http://{args.host}:{args.port}")
    print("  ticket form   /            admin view  /admin        health  /api/health")
    print("  Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
