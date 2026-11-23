"""HTTP behaviour of the three services, with their stores replaced by fakes."""

import unittest

from apartment_booking.database import BookingConflictError, RecordNotFoundError
from dimora.apartment.app import create_app as apartment_app
from dimora.query.app import create_app as query_app
from dimora.reservation.app import create_app as reservation_app


class FakeApartmentStore:
    def __init__(self):
        self.calls = []

    def pending_count(self):
        return 0

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


class FakeReservationStore:
    def pending_count(self):
        return 2

    def known_apartments(self):
        return 1

    def create_booking(self, apartment_name, start, end, booker, people):
        return {"id": 9, "apartment_name": apartment_name, "total_price": 400.0}, 1

    def change_booking(self, *args):
        return {"id": 9}, 2

    def cancel_booking(self, *args):
        return {"id": 9}, 3


class FakeReadModel:
    def __init__(self):
        self.versions = {("booking", 9): 1}

    def ping(self):
        pass

    def list_apartments(self):
        return [{"id": 5, "name": "Casa"}]

    def list_bookings(self):
        return []

    def search_available_apartments(self, start, end, people):
        if people <= 0:
            raise ValueError("Number of people must be at least 1.")
        return [{"id": 5, "start_date": start}]

    def current_version(self, aggregate, entity_id):
        return self.versions.get((aggregate, entity_id))


APARTMENT = {"name": "Casa", "country": "Italia", "city": "Roma", "street_and_number": "Via 1",
             "max_people": 2, "price_per_night": "85,50"}


class ApartmentServiceTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeApartmentStore()
        self.writes = []
        self.client = apartment_app(self.store, on_write=lambda: self.writes.append(1)).test_client()

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

    def test_reads_are_not_served_here(self):
        self.assertEqual(self.client.get("/api/apartments").status_code, 405)
        self.assertEqual(self.client.get("/health").json["data"]["status"], "ok")


class ReservationServiceTests(unittest.TestCase):
    def setUp(self):
        self.client = reservation_app(FakeReservationStore()).test_client()

    def test_every_write_returns_the_booking_version(self):
        booking = {"apartment_name": "Casa", "start_date": "2027-03-01", "end_date": "2027-03-05",
                   "booker_name": "Anna", "num_people": 2}
        created = self.client.post("/api/bookings", json=booking)
        self.assertEqual((created.status_code, created.headers["X-Consistency-Token"]), (201, "booking:9@1"))
        change = {**{k: booking[k] for k in ("apartment_name", "start_date", "end_date")},
                  "new_start_date": "2027-03-02", "new_end_date": "2027-03-06", "num_people": 3}
        self.assertEqual(self.client.patch("/api/bookings", json=change).headers["X-Consistency-Token"],
                         "booking:9@2")
        cancel = {k: booking[k] for k in ("apartment_name", "start_date", "end_date")}
        self.assertEqual(self.client.delete("/api/bookings", json=cancel).headers["X-Consistency-Token"],
                         "booking:9@3")

    def test_health_reports_the_outbox_and_the_apartment_copy(self):
        self.assertEqual(self.client.get("/health").json["data"],
                         {"status": "ok", "database": "ok", "pending_events": 2, "known_apartments": 1})


class QueryServiceTests(unittest.TestCase):
    def setUp(self):
        self.read_model = FakeReadModel()
        self.client = query_app(self.read_model, consistency_timeout=0.1).test_client()

    def test_reads_use_the_original_envelope(self):
        self.assertEqual(self.client.get("/api/apartments").json, {"data": [{"id": 5, "name": "Casa"}]})
        self.assertEqual(self.client.get("/api/health").json["data"], {"status": "ok", "database": "ok"})
        search = self.client.get("/api/availability?start_date=2027-03-01&end_date=2027-03-02&num_people=0")
        self.assertEqual(search.status_code, 400)

    def test_x_wait_for_reports_fresh_or_stale(self):
        fresh = self.client.get("/api/bookings", headers={"X-Wait-For": "booking:9@1"})
        self.assertEqual(fresh.headers["X-Consistency"], "fresh")
        stale = self.client.get("/api/bookings", headers={"X-Wait-For": "booking:9@2"})
        self.assertEqual(stale.headers["X-Consistency"], "stale")
        self.assertNotIn("X-Consistency", self.client.get("/api/bookings").headers)
        bad = self.client.get("/api/bookings", headers={"X-Wait-For": "nonsense"})
        self.assertEqual(bad.status_code, 400)

    def test_documentation_and_overview(self):
        self.assertEqual(self.client.get("/api/openapi.json").json["openapi"], "3.1.0")
        docs = self.client.get("/docs")
        self.assertEqual(docs.status_code, 200)
        self.assertIn("Content-Security-Policy", docs.headers)
        script = self.client.get("/static/api_docs.js")
        self.assertEqual(script.status_code, 200)
        script.close()
        services = {route["service"] for route in self.client.get("/api").json["data"]["routes"]}
        self.assertEqual(services, {"query", "apartment", "reservation"})

    def test_writes_are_not_served_here(self):
        self.assertEqual(self.client.post("/api/bookings", json={}).status_code, 405)


if __name__ == "__main__":
    unittest.main()
