"""HTTP tests always use temporary SQLite files, never user data."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.web import create_app


class TestWebAPI(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db_path = Path(self.directory.name) / "http.db"
        self.app = create_app({"TESTING": True, "DATABASE_PATH": str(self.db_path)})
        self.app.logger.disabled = True
        self.client = self.app.test_client()

    def test_overview_and_health(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("routes", response.json["data"])
        self.assertFalse(self.db_path.exists())
        self.assertFalse(self.app.debug)
        response = self.client.get("/api/health")
        self.assertEqual(response.json["data"], {"status": "ok", "database": "ok"})
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_http_errors_are_json_and_preserve_allowed_methods(self) -> None:
        response = self.client.get("/does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.json)
        response = self.client.post("/api/health")
        self.assertEqual(response.status_code, 405)
        self.assertIn("GET", response.headers["Allow"])
        self.assertIn("error", response.json)


if __name__ == "__main__":
    unittest.main()
