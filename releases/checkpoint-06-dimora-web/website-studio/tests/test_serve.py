"""Tests for the Dimora Studio server: static files, security headers and the API proxy."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import serve  # noqa: E402


class FakeApi(BaseHTTPRequestHandler):
    """Echoes what the proxy forwarded so tests can assert on it."""

    def _reply(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode() if length else ""
        status = 409 if self.path.startswith("/api/conflict") else 200
        payload = json.dumps({"data": {
            "method": self.command, "path": self.path, "body": body,
            "content_type": self.headers.get("Content-Type"), "cookie": self.headers.get("Cookie"),
        }}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Set-Cookie", "leak=1")
        self.end_headers()
        self.wfile.write(payload)

    do_GET = do_POST = do_PATCH = do_DELETE = _reply

    def log_message(self, *args):
        pass


def start(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


class StudioServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.public = tempfile.TemporaryDirectory()
        root = Path(cls.public.name)
        (root / "index.html").write_text("<!doctype html><title>Dimora</title>")
        (root / "app.js").write_text("export {};")
        (root / "assets").mkdir()
        (root / ".secret").write_text("nope")

        cls.api = start(ThreadingHTTPServer(("127.0.0.1", 0), FakeApi))
        api_url = f"http://127.0.0.1:{cls.api.server_address[1]}"
        cls.studio = start(serve.create_server("127.0.0.1", 0, api_url, public_dir=root))
        cls.base = f"http://127.0.0.1:{cls.studio.server_address[1]}"

        dead = ThreadingHTTPServer(("127.0.0.1", 0), FakeApi)
        dead_port = dead.server_address[1]
        dead.server_close()
        cls.offline = start(serve.create_server("127.0.0.1", 0, f"http://127.0.0.1:{dead_port}", public_dir=root))

    @classmethod
    def tearDownClass(cls):
        for server in (cls.studio, cls.api, cls.offline):
            server.shutdown()
            server.server_close()
        cls.public.cleanup()

    def request(self, path, method="GET", body=None, base=None, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request((base or self.base) + path, data=data, method=method, headers=headers or {})
        if data:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, response.headers, response.read()
        except urllib.error.HTTPError as error:
            with error:
                return error.code, error.headers, error.read()

    def test_serves_index_with_security_headers(self):
        status, headers, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn(b"Dimora", body)
        self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")

    def test_javascript_has_module_compatible_type(self):
        status, headers, _ = self.request("/app.js")
        self.assertEqual(status, 200)
        self.assertTrue(headers["Content-Type"].startswith("text/javascript"))

    def test_hides_dotfiles_directory_listings_and_traversal(self):
        self.assertEqual(self.request("/.secret")[0], 404)
        self.assertEqual(self.request("/assets/")[0], 404)
        self.assertNotEqual(self.request("/../serve.py")[2], Path(serve.__file__).read_bytes())

    def test_static_files_are_read_only(self):
        self.assertEqual(self.request("/index.html", method="POST", body={})[0], 405)

    def test_proxies_methods_paths_and_bodies(self):
        status, _, body = self.request("/api/bookings?x=1", method="PATCH", body={"a": 1})
        self.assertEqual(status, 200)
        echoed = json.loads(body)["data"]
        self.assertEqual(echoed["method"], "PATCH")
        self.assertEqual(echoed["path"], "/api/bookings?x=1")
        self.assertEqual(json.loads(echoed["body"]), {"a": 1})
        self.assertEqual(echoed["content_type"], "application/json")

    def test_preserves_encoded_path_segments(self):
        _, _, body = self.request("/api/apartments/Loft%2F2/price", method="PATCH", body={})
        self.assertEqual(json.loads(body)["data"]["path"], "/api/apartments/Loft%2F2/price")

    def test_forwards_error_status_and_drops_unlisted_headers(self):
        status, headers, _ = self.request("/api/conflict", method="POST", body={},
                                          headers={"Cookie": "session=secret"})
        self.assertEqual(status, 409)
        self.assertIsNone(headers.get("Set-Cookie"))
        _, _, body = self.request("/api/echo", headers={"Cookie": "session=secret"})
        self.assertIsNone(json.loads(body)["data"]["cookie"])

    def test_rejects_oversized_bodies(self):
        status, _, body = self.request("/api/bookings", method="POST", body={"x": "a" * (serve.MAX_BODY_BYTES + 1)})
        self.assertEqual(status, 413)
        self.assertEqual(json.loads(body)["error"]["code"], "payload_too_large")

    def test_reports_unreachable_api_as_json(self):
        status, _, body = self.request("/api/health", base=f"http://127.0.0.1:{self.offline.server_address[1]}")
        self.assertEqual(status, 502)
        self.assertEqual(json.loads(body)["error"]["code"], "api_unreachable")

    def test_rejects_invalid_api_urls(self):
        for value in ("ftp://example.com", "localhost:8000", "http://x?y=1"):
            with self.assertRaises(ValueError):
                serve.normalise_api_url(value)


if __name__ == "__main__":
    unittest.main()
