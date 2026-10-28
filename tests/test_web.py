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

    def add_apartment(self, **overrides):
        values = dict(name="City Loft", country="Italy", city="Rome", street_and_number="Example 1",
                      max_people=3, price_per_night="95,50 €")
        values.update(overrides)
        return self.client.post("/api/apartments", json=values)

    def test_apartment_lifecycle_and_case_insensitive_uniqueness(self) -> None:
        response = self.add_apartment()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["data"]["address"], "Italy, Rome, Example 1")
        self.assertEqual(response.json["data"]["price_per_night"], 95.5)
        self.assertEqual(self.add_apartment(name="CITY LOFT").status_code, 409)
        response = self.client.get("/api/apartments")
        self.assertEqual(len(response.json["data"]), 1)
        response = self.client.patch("/api/apartments/City%20Loft/price", json={"price_per_night": 100})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["data"]["price_per_night"], 100)
        response = self.client.delete("/api/apartments/City%20Loft")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/apartments").json["data"], [])
        self.assertEqual(self.client.delete("/api/apartments/City%20Loft").status_code, 404)
        self.assertEqual(self.client.patch("/api/apartments/missing/price", json={"price_per_night": 100}).status_code, 404)

    def test_invalid_json_and_fields(self) -> None:
        for kwargs, status in [
            ({"json": {}}, 400), ({"json": []}, 400),
            ({"data": "null", "content_type": "application/json"}, 400),
            ({"data": "{broken", "content_type": "application/json"}, 400),
            ({"data": "name=Demo"}, 415),
        ]:
            with self.subTest(kwargs=kwargs):
                response = self.client.post("/api/apartments", **kwargs)
                self.assertEqual(response.status_code, status)
                self.assertIn("message", response.json["error"])
        for overrides in [dict(name=None), dict(city=[]), dict(max_people=True), dict(max_people=1.5),
                          dict(max_people=0), dict(max_people=2**64), dict(price_per_night="nan"),
                          dict(price_per_night="inf"), dict(price_per_night=0.001),
                          dict(price_per_night=True), dict(price_per_night={}), dict(extra="typo")]:
            with self.subTest(overrides=overrides):
                self.assertEqual(self.add_apartment(**overrides).status_code, 400)
        self.assertEqual(self.client.get("/api/apartments").json["data"], [])

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
