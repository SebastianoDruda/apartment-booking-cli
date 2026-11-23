"""Dimora Studio development server.

Serves the static web client from ``public/`` and forwards every ``/api/*``
request to the Apartment Booking REST API. Keeping the client and the API on
the same origin means the Flask service needs no CORS configuration and the
browser can enforce a strict Content Security Policy.

Only the Python standard library is used, so the studio runs anywhere the
project already runs.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

PUBLIC_DIR = Path(__file__).resolve().parent / "public"
DEFAULT_API_URL = "http://127.0.0.1:8000"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
MAX_BODY_BYTES = 64 * 1024
PROXY_TIMEOUT_SECONDS = 10

FORWARDED_REQUEST_HEADERS = ("Content-Type", "Accept")
FORWARDED_RESPONSE_HEADERS = ("Content-Type", "Retry-After", "Allow")

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cache-Control": "no-cache",
}


class StudioHandler(SimpleHTTPRequestHandler):
    """Static file handler with a same-origin proxy for the booking API."""

    api_url = DEFAULT_API_URL
    server_version = "DimoraStudio/1.0"
    sys_version = ""
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".css": "text/css; charset=utf-8",
        ".html": "text/html; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".json": "application/json",
        ".svg": "image/svg+xml",
        ".webmanifest": "application/manifest+json",
    }

    # -- routing -----------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802 - http.server naming
        if self._is_api_request():
            self._proxy()
        elif self._is_hidden_path():
            self._send_json(HTTPStatus.NOT_FOUND, "not_found", "Resource not found.")
        else:
            super().do_GET()

    def do_HEAD(self) -> None:  # noqa: N802
        if self._is_api_request():
            self._proxy()
        elif self._is_hidden_path():
            self._send_json(HTTPStatus.NOT_FOUND, "not_found", "Resource not found.")
        else:
            super().do_HEAD()

    def do_POST(self) -> None:  # noqa: N802
        self._api_only()

    def do_PATCH(self) -> None:  # noqa: N802
        self._api_only()

    def do_PUT(self) -> None:  # noqa: N802
        self._api_only()

    def do_DELETE(self) -> None:  # noqa: N802
        self._api_only()

    def _api_only(self) -> None:
        if self._is_api_request():
            self._proxy()
        else:
            self._send_json(HTTPStatus.METHOD_NOT_ALLOWED, "method_not_allowed",
                            "Static assets are read-only.")

    def _is_api_request(self) -> bool:
        path = urlsplit(self.path).path
        return path == "/api" or path.startswith("/api/")

    def _is_hidden_path(self) -> bool:
        segments = urlsplit(self.path).path.split("/")
        return any(segment.startswith(".") for segment in segments if segment)

    # -- static files ------------------------------------------------------

    def list_directory(self, path):  # noqa: ARG002 - signature fixed by http.server
        """Never expose directory listings."""
        self._send_json(HTTPStatus.NOT_FOUND, "not_found", "Resource not found.")
        return None

    def end_headers(self) -> None:
        for name, value in SECURITY_HEADERS.items():
            self.send_header(name, value)
        super().end_headers()

    # -- proxy -------------------------------------------------------------

    def _proxy(self) -> None:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._send_json(HTTPStatus.BAD_REQUEST, "invalid_request", "Invalid Content-Length.")
            return
        if length < 0 or length > MAX_BODY_BYTES:
            self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "payload_too_large",
                            "Request body is too large.")
            return
        body = self.rfile.read(length) if length else None

        # The upstream origin is fixed; only the path and query come from the client.
        request = urllib.request.Request(self.api_url + self.path, data=body, method=self.command)
        for header in FORWARDED_REQUEST_HEADERS:
            value = self.headers.get(header)
            if value:
                request.add_header(header, value)

        try:
            with urllib.request.urlopen(request, timeout=PROXY_TIMEOUT_SECONDS) as response:
                status, headers, payload = response.status, response.headers, response.read()
        except urllib.error.HTTPError as error:
            status, headers, payload = error.code, error.headers, error.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            self._send_json(HTTPStatus.BAD_GATEWAY, "api_unreachable",
                            f"The booking API is not reachable at {self.api_url}.")
            return

        self.send_response(status)
        for header in FORWARDED_RESPONSE_HEADERS:
            value = headers.get(header)
            if value:
                self.send_header(header, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def _send_json(self, status: HTTPStatus, code: str, message: str) -> None:
        payload = json.dumps({"error": {"code": code, "message": message}}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - inherited name
        sys.stderr.write(f"[studio] {self.address_string()} {format % args}\n")


def normalise_api_url(value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError(f"API URL must be an absolute http(s) URL, got {value!r}.")
    if parts.query or parts.fragment:
        raise ValueError("API URL must not contain a query string or fragment.")
    return value.rstrip("/")


def create_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
                  api_url: str = DEFAULT_API_URL,
                  public_dir: Path = PUBLIC_DIR) -> ThreadingHTTPServer:
    """Build a server bound to ``host:port``; ``port=0`` picks a free port."""
    upstream = normalise_api_url(api_url)
    directory = str(public_dir)

    class Handler(StudioHandler):
        api_url = upstream

        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, **kwargs)

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the Dimora web client.")
    parser.add_argument("--host", default=os.environ.get("STUDIO_HOST", DEFAULT_HOST))
    parser.add_argument("--port", type=int, default=int(os.environ.get("STUDIO_PORT", DEFAULT_PORT)))
    parser.add_argument("--api", default=os.environ.get("BOOKING_API_URL", DEFAULT_API_URL),
                        help="Base URL of the Apartment Booking API.")
    args = parser.parse_args(argv)

    try:
        server = create_server(args.host, args.port, args.api)
    except (OSError, ValueError) as error:
        parser.exit(2, f"Cannot start Dimora Studio: {error}\n")

    host, port = server.server_address[:2]
    print(f"Dimora Studio  ->  http://{host}:{port}   (API: {normalise_api_url(args.api)})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
