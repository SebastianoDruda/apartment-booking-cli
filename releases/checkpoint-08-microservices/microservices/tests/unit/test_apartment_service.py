"""HTTP behaviour of the apartment service, with its store replaced by a fake."""

import unittest

from apartment_booking.database import BookingConflictError, RecordNotFoundError
from dimora.apartment.app import create_app as apartment_app
from dimora.apartment.store import NOT_OURS


class FakeApartmentStore:
    def __init__(self):
        self.calls = []
        self.versions = {5: 1}

    def ping(self):
        pass

    def pending_count(self):
        return 0

    def list_apartments(self):
        return [{"id": 5, "name": "Casa"}]

    def current_version(self, aggregate, entity_id):
        if aggregate != "apartment":
            return NOT_OURS
        return self.versions.get(entity_id)

    def add_apartment(self, name, address, max_people, price):
        self.calls.append(("add", name, address, max_people, price))
        if name == "Taken":
            raise BookingConflictError("Apartment 'Taken' already exists.")
        return {"id": 5, "name": name, "address": address, "max_people": max_people,
                "price_per_night": price}, 1

    def update_apartment_price(self, name, price):
        if name != "Loft/2":
            raise RecordNotFoundError(f"Apartment '{name}' does not exist.")
        return {"id": 5, "name": name, "address": "a", "max_people": 2,
                "old_price_per_night": 90.0, "price_per_night": price}, 4

    def remove_apartment(self, name):
        return {"id": 5, "name": name, "address": "a", "max_people": 2, "price_per_night": 90.0}, 5


APARTMENT = {"name": "Casa", "country": "Italia", "city": "Roma", "street_and_number": "Via 1",
             "max_people": 2, "price_per_night": "85,50"}


class ApartmentWriteTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeApartmentStore()
        self.writes = []
        self.client = apartment_app(self.store, on_write=lambda: self.writes.append(1),
                                    consistency_timeout=0.1).test_client()

    def test_create_formats_the_address_and_returns_a_token(self):
        response = self.client.post("/api/apartments", json=APARTMENT)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers["X-Consistency-Token"], "apartment:5@1")
        self.assertEqual(self.store.calls[0], ("add", "Casa", "Italia, Roma, Via 1", 2, 85.5))
        self.assertEqual(self.writes, [1], "the outbox relay is woken")

    def test_errors_keep_the_original_codes(self):
        missing = self.client.post("/api/apartments", json={"name": "x"})
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.json["error"]["code"], "invalid_request")
        taken = self.client.post("/api/apartments", json={**APARTMENT, "name": "Taken"})
        self.assertEqual((taken.status_code, taken.json["error"]["code"]), (409, "conflict"))
        absent = self.client.patch("/api/apartments/Nope/price", json={"price_per_night": 5})
        self.assertEqual((absent.status_code, absent.json["error"]["code"]), (404, "not_found"))
        self.assertEqual(self.writes, [], "failed writes publish nothing")

    def test_names_with_slashes_reach_the_store(self):
        response = self.client.patch("/api/apartments/Loft%2F2/price", json={"price_per_night": 99})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-Consistency-Token"], "apartment:5@4")
        self.assertEqual(self.client.delete("/api/apartments/Loft").headers["X-Consistency-Token"],
                         "apartment:5@5")

    def test_booking_routes_are_not_served_here(self):
        self.assertEqual(self.client.get("/api/bookings").status_code, 404)
        self.assertEqual(self.client.post("/api/bookings", json={}).status_code, 404)


class ApartmentReadTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeApartmentStore()
        self.client = apartment_app(self.store, consistency_timeout=0.1).test_client()

    def test_reads_use_the_original_envelope(self):
        self.assertEqual(self.client.get("/api/apartments").json, {"data": [{"id": 5, "name": "Casa"}]})
        self.assertEqual(self.client.get("/api/health").json["data"], {"status": "ok", "database": "ok"})
        self.assertEqual(self.client.get("/health").json["data"]["pending_events"], 0)

    def test_own_writes_are_fresh_at_once_and_unknown_versions_time_out(self):
        fresh = self.client.get("/api/apartments", headers={"X-Wait-For": "apartment:5@1"})
        self.assertEqual(fresh.headers["X-Consistency"], "fresh")
        stale = self.client.get("/api/apartments", headers={"X-Wait-For": "apartment:5@2"})
        self.assertEqual(stale.headers["X-Consistency"], "stale")
        self.assertNotIn("X-Consistency", self.client.get("/api/apartments").headers)
        bad = self.client.get("/api/apartments", headers={"X-Wait-For": "nonsense"})
        self.assertEqual(bad.status_code, 400)

    def test_booking_tokens_never_make_apartment_reads_wait(self):
        response = self.client.get("/api/apartments", headers={"X-Wait-For": "booking:9@7"})
        self.assertEqual(response.headers["X-Consistency"], "fresh")

    def test_documentation_and_overview(self):
        self.assertEqual(self.client.get("/api/openapi.json").json["openapi"], "3.1.0")
        docs = self.client.get("/docs")
        self.assertEqual(docs.status_code, 200)
        self.assertIn("Content-Security-Policy", docs.headers)
        script = self.client.get("/static/api_docs.js")
        self.assertEqual(script.status_code, 200)
        script.close()
        services = {route["service"] for route in self.client.get("/api").json["data"]["routes"]}
        self.assertEqual(services, {"apartment", "reservation"})


if __name__ == "__main__":
    unittest.main()
