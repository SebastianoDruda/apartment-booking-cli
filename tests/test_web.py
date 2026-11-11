"""HTTP tests always use temporary SQLite files, never user data."""

from __future__ import annotations

import io
import sqlite3
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from unittest.mock import patch
import unittest
from pathlib import Path

from apartment_booking.web import create_app
from apartment_booking.cli import ApartmentBookingCLI
from apartment_booking.database import BookingDatabase


class TestWebAPI(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db_path = Path(self.directory.name) / "http.db"
        self.app = create_app({"TESTING": True, "DATABASE_PATH": str(self.db_path)})
        self.addCleanup(setattr, self.app.logger, "disabled", self.app.logger.disabled)
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

    def create_booking(self, **overrides):
        values = dict(apartment_name="City Loft", start_date="2026-11-10", end_date="2026-11-15",
                      booker_name="Guest", num_people=2)
        values.update(overrides)
        return self.client.post("/api/bookings", json=values)

    def test_booking_lifecycle_and_current_price_totals(self) -> None:
        self.add_apartment()
        response = self.create_booking()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["data"]["total_price"], 477.5)
        self.client.patch("/api/apartments/City%20Loft/price", json={"price_per_night": 100})
        self.assertEqual(self.client.get("/api/bookings").json["data"][0]["total_price"], 500)
        response = self.client.patch("/api/bookings", json=dict(
            apartment_name="City Loft", start_date="10.11.2026", end_date="15.11.2026",
            new_start_date="2026-11-11", new_end_date="2026-11-17", num_people=3,
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["data"]["nights"], 6)
        response = self.client.delete("/api/bookings", json=dict(
            apartment_name="City Loft", start_date="2026-11-11", end_date="2026-11-17",
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/bookings").json["data"], [])
        self.assertEqual(self.client.delete("/api/bookings", json=dict(
            apartment_name="City Loft", start_date="2026-11-11", end_date="2026-11-17",
        )).status_code, 404)

    def test_availability_matches_database_and_gets_leave_records_unchanged(self) -> None:
        self.add_apartment()
        self.add_apartment(name="Small Studio", max_people=1)
        self.create_booking()
        db = BookingDatabase(self.db_path)
        self.addCleanup(db.close)
        before = (db.list_apartments(), db.list_bookings())
        for start, end in [("2026-11-10", "2026-11-15"), ("2026-11-15", "2026-11-18")]:
            response = self.client.get("/api/availability", query_string=dict(
                start_date=start, end_date=end, num_people=2,
            ))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["data"], db.search_available_apartments(start, end, 2))
        for url in ["/", "/api/health", "/api/apartments", "/api/bookings",
                    "/api/bookings?apartment_name=City%20Loft&start_date=2026-11-10&end_date=2026-11-15"]:
            self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual((db.list_apartments(), db.list_bookings()), before)

    def test_invalid_dates_capacity_and_overlaps_do_not_save(self) -> None:
        self.add_apartment()
        for changes in [dict(start_date="2026-09-31"), dict(end_date="2026-11-10"),
                        dict(num_people=4), dict(num_people=0), dict(num_people=True),
                        dict(booker_name=""), dict(start_date=None)]:
            with self.subTest(changes=changes):
                self.assertEqual(self.create_booking(**changes).status_code, 400)
        self.assertEqual(self.create_booking(apartment_name="Missing").status_code, 404)
        self.assertEqual(self.create_booking().status_code, 201)
        self.assertEqual(self.create_booking(start_date="2026-11-12").status_code, 409)
        self.assertEqual(self.create_booking(start_date="2026-11-15", end_date="2026-11-18").status_code, 201)
        original = self.client.get("/api/bookings").json["data"]
        base = dict(apartment_name="City Loft", start_date="2026-11-10", end_date="2026-11-15",
                    new_start_date="2026-11-11", new_end_date="2026-11-17", num_people=2)
        self.assertEqual(self.client.patch("/api/bookings", json=base).status_code, 409)
        self.assertEqual(self.client.patch("/api/bookings", json={**base, "num_people": 4}).status_code, 400)
        self.assertEqual(self.client.patch("/api/bookings", json={**base, "start_date": "2026-11-01"}).status_code, 404)
        self.assertEqual(self.client.get("/api/bookings").json["data"], original)

    def test_deleting_apartment_still_cascades_to_bookings(self) -> None:
        self.add_apartment()
        self.create_booking()
        self.assertEqual(self.client.delete("/api/apartments/City%20Loft").status_code, 200)
        self.assertEqual(self.client.get("/api/bookings").json["data"], [])

    def test_missing_duplicate_and_invalid_query_parameters(self) -> None:
        for query in ["", "start_date=2026-11-10", "start_date=x&end_date=y&num_people=2",
                      "start_date=2026-11-10&end_date=2026-11-15&num_people=1.5",
                      "start_date=2026-11-10&end_date=2026-11-15&num_people=2&num_people=3",
                      "start_date=2026-11-10&end_date=2026-11-15&num_people=2&extra=typo"]:
            with self.subTest(query=query):
                self.assertEqual(self.client.get("/api/availability?" + query).status_code, 400)
        for method in (self.client.post, self.client.patch, self.client.delete):
            self.assertEqual(method("/api/bookings", json={}).status_code, 400)

    def test_database_persists_between_apps_and_other_paths_are_isolated(self) -> None:
        self.add_apartment()
        self.create_booking()
        other = create_app({"TESTING": True, "DATABASE_PATH": str(self.db_path)}).test_client()
        self.assertEqual(other.get("/api/bookings").json, self.client.get("/api/bookings").json)
        isolated = create_app({"TESTING": True, "DATABASE_PATH": str(self.db_path.with_name("other.db"))}).test_client()
        self.assertEqual(isolated.get("/api/bookings").json["data"], [])

    def test_cli_and_http_share_behavior_and_records(self) -> None:
        self.add_apartment()
        db = BookingDatabase(self.db_path)
        self.addCleanup(db.close)
        inputs = iter(["1", "booking create", "City Loft", "10.11.2026", "15.11.2026", "Guest", "2", "exit"])
        out = io.StringIO()
        ApartmentBookingCLI(db=db, input_fn=lambda _: next(inputs), output_stream=out).run()
        booking = self.client.get("/api/bookings").json["data"][0]
        self.assertEqual(booking["total_price"], 477.5)
        self.assertIn("Total: 477.50 EUR", out.getvalue())
        self.assertEqual(self.create_booking().status_code, 409)
        self.assertEqual(self.client.delete("/api/bookings", json=dict(
            apartment_name="City Loft", start_date="2026-11-10", end_date="2026-11-15",
        )).status_code, 200)
        self.assertEqual(self.create_booking().json["data"]["total_price"], booking["total_price"])
        self.assertEqual(db.list_bookings()[0]["total_price"], booking["total_price"])

    def test_database_errors_and_unexpected_errors_do_not_leak_details(self) -> None:
        for error, status, code in [
            (sqlite3.OperationalError("private path"), 503, "database_unavailable"),
            (sqlite3.IntegrityError("private table"), 409, "conflict"),
            (sqlite3.ProgrammingError("private traceback"), 500, "internal_error"),
            (RuntimeError("private traceback"), 500, "internal_error"),
        ]:
            with self.subTest(error=error), patch.object(BookingDatabase, "list_apartments", side_effect=error):
                response = self.client.get("/api/health")
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json["error"]["code"], code)
                self.assertNotIn("private", response.text)
                if status == 503:
                    self.assertEqual(response.headers["Retry-After"], "1")

    def test_request_cleanup_on_success_and_error(self) -> None:
        close = BookingDatabase.close
        with patch.object(BookingDatabase, "close", autospec=True, side_effect=close) as mocked:
            self.client.get("/api/health")
            self.assertEqual(mocked.call_count, 1)
            self.client.delete("/api/apartments/missing")
            self.assertEqual(mocked.call_count, 2)

    def test_body_size_limit_returns_json(self) -> None:
        response = self.client.post("/api/apartments", data="x" * 70000, content_type="application/json")
        self.assertEqual(response.status_code, 413)
        self.assertIn("error", response.json)

    def test_concurrent_http_creates_and_changes_cannot_overlap(self) -> None:
        for first_kind, second_kind in [("post", "post"), ("post", "patch"), ("patch", "patch")]:
            with self.subTest(first=first_kind, second=second_kind):
                name = first_kind + second_kind
                self.add_apartment(name=name)
                for kind, start, end in [(first_kind, "2027-02-01", "2027-02-03"),
                                          (second_kind, "2027-03-01", "2027-03-03")]:
                    if kind == "patch":
                        self.create_booking(apartment_name=name, start_date=start, end_date=end)
                checked, release, started = threading.Event(), threading.Event(), threading.Event()
                local = threading.local()
                original = BookingDatabase._has_overlapping_booking

                def hold_first(database, *args, **kwargs):
                    result = original(database, *args, **kwargs)
                    if getattr(local, "first", False):
                        checked.set()
                        if not release.wait(10):
                            raise RuntimeError("Test writer was not released")
                    return result

                def submit(first, kind, old_start, old_end):
                    local.first = first
                    with self.app.test_client() as client:
                        if not first:
                            started.set()
                        values = dict(apartment_name=name, start_date="2027-01-01", end_date="2027-01-03", num_people=2)
                        if kind == "post":
                            values["booker_name"] = "Guest"
                        else:
                            values.update(start_date=old_start, end_date=old_end,
                                          new_start_date="2027-01-01", new_end_date="2027-01-03")
                        return getattr(client, kind)("/api/bookings", json=values)

                with patch.object(BookingDatabase, "_has_overlapping_booking", hold_first), ThreadPoolExecutor(max_workers=2) as pool:
                    one = pool.submit(submit, True, first_kind, "2027-02-01", "2027-02-03")
                    try:
                        self.assertTrue(checked.wait(5))
                        two = pool.submit(submit, False, second_kind, "2027-03-01", "2027-03-03")
                        self.assertTrue(started.wait(5))
                        try:
                            two.result(timeout=0.2)
                        except TimeoutError:
                            pass
                    finally:
                        release.set()
                    self.assertIn(one.result(5).status_code, (200, 201))
                    self.assertEqual(two.result(5).status_code, 409)
                rows = self.client.get("/api/bookings").json["data"]
                self.assertEqual(sum(b["apartment_name"] == name and b["start_date"] == "2027-01-01" for b in rows), 1)

    def test_overview_and_health(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("routes", response.json["data"])
        self.assertFalse(self.db_path.exists())
        self.assertFalse(self.app.debug)
        response = self.client.get("/api/health")
        self.assertEqual(response.json["data"], {"status": "ok", "database": "ok"})
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_documentation_and_assets_load_without_touching_database(self) -> None:
        response = self.client.get("/docs")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/html")
        self.assertIn("API Explorer", response.text)
        self.assertIn("script-src 'self'", response.headers["Content-Security-Policy"])
        for path in ("/ui", "/"):
            html_res = self.client.get(path, headers={"Accept": "text/html"})
            self.assertEqual(html_res.status_code, 200)
            self.assertEqual(html_res.mimetype, "text/html")
            self.assertIn("Apartment Booking", html_res.text)
            self.assertIn("script-src 'self'", html_res.headers["Content-Security-Policy"])
        for asset in ("api_docs.css", "api_docs.js", "ui.css", "ui.js"):
            with self.client.get("/static/" + asset) as asset_response:
                self.assertEqual(asset_response.status_code, 200)
        self.assertFalse(self.db_path.exists())

    def test_openapi_contract_covers_all_business_routes(self) -> None:
        response = self.client.get("/api/openapi.json")
        self.assertEqual(response.status_code, 200)
        spec = response.json
        self.assertEqual(spec["openapi"], "3.1.0")
        documented = {(method.upper(), path) for path, operations in spec["paths"].items()
                      for method in operations}
        actual = {(method, rule.rule.replace("<path:name>", "{name}"))
                  for rule in self.app.url_map.iter_rules()
                  if rule.endpoint not in {"static", "documentation", "openapi", "ui"}
                  for method in rule.methods - {"HEAD", "OPTIONS"}}
        self.assertEqual(documented, actual)
        self.assertFalse(self.db_path.exists())

    def test_documentation_examples_can_create_change_and_cancel(self) -> None:
        paths = self.client.get("/api/openapi.json").json["paths"]

        def example(path, method):
            return paths[path][method]["requestBody"]["content"]["application/json"]["example"].copy()

        apartment = self.client.post("/api/apartments", json=example("/api/apartments", "post"))
        self.assertEqual(apartment.status_code, 201)
        booking = self.client.post("/api/bookings", json=example("/api/bookings", "post"))
        self.assertEqual(booking.status_code, 201)
        changed = self.client.patch("/api/bookings", json=example("/api/bookings", "patch"))
        self.assertEqual(changed.status_code, 200)
        cancel = example("/api/bookings", "delete")
        cancel.update(start_date=changed.json["data"]["start_date"], end_date=changed.json["data"]["end_date"])
        self.assertEqual(self.client.delete("/api/bookings", json=cancel).status_code, 200)
        self.assertEqual(self.client.delete("/api/apartments/API%20Demo").status_code, 200)
        self.assertEqual(self.client.get("/api/bookings").json["data"], [])

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
