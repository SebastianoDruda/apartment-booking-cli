"""HTTP behaviour of the reservation service, with its store replaced by a fake."""

import unittest

from dimora.reservation.app import create_app as reservation_app


class FakeReservationStore:
    def __init__(self):
        self.versions = {("booking", 9): 1, ("apartment", 5): 3}
        self.searches = []

    def known_apartments(self):
        return 1

    def list_bookings(self):
        return [{"id": 9, "apartment_name": "Casa"}]

    def search_available_apartments(self, start, end, people):
        if people <= 0:
            raise ValueError("Number of people must be at least 1.")
        self.searches.append((start, end, people))
        return [{"id": 5, "start_date": start}]

    def current_version(self, aggregate, entity_id):
        return self.versions.get((aggregate, entity_id))

    def create_booking(self, apartment_name, start, end, booker, people):
        return {"id": 9, "apartment_name": apartment_name, "total_price": 400.0}, 1

    def change_booking(self, *args):
        return {"id": 9}, 2

    def cancel_booking(self, *args):
        return {"id": 9}, 3


BOOKING = {"apartment_name": "Casa", "start_date": "2027-03-01", "end_date": "2027-03-05",
           "booker_name": "Anna", "num_people": 2}


class ReservationWriteTests(unittest.TestCase):
    def setUp(self):
        self.client = reservation_app(FakeReservationStore(), consistency_timeout=0.1).test_client()

    def test_every_write_returns_the_booking_version(self):
        created = self.client.post("/api/bookings", json=BOOKING)
        self.assertEqual((created.status_code, created.headers["X-Consistency-Token"]), (201, "booking:9@1"))
        change = {**{k: BOOKING[k] for k in ("apartment_name", "start_date", "end_date")},
                  "new_start_date": "2027-03-02", "new_end_date": "2027-03-06", "num_people": 3}
        self.assertEqual(self.client.patch("/api/bookings", json=change).headers["X-Consistency-Token"],
                         "booking:9@2")
        cancel = {k: BOOKING[k] for k in ("apartment_name", "start_date", "end_date")}
        self.assertEqual(self.client.delete("/api/bookings", json=cancel).headers["X-Consistency-Token"],
                         "booking:9@3")

    def test_health_reports_the_apartment_copy(self):
        self.assertEqual(self.client.get("/health").json["data"],
                         {"status": "ok", "database": "ok", "known_apartments": 1})

    def test_apartment_routes_are_not_served_here(self):
        self.assertEqual(self.client.get("/api/apartments").status_code, 404)
        self.assertEqual(self.client.post("/api/apartments", json={}).status_code, 404)


class ReservationReadTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeReservationStore()
        self.client = reservation_app(self.store, consistency_timeout=0.1).test_client()

    def test_reads_use_the_original_envelope(self):
        self.assertEqual(self.client.get("/api/bookings").json, {"data": [{"id": 9, "apartment_name": "Casa"}]})
        search = self.client.get("/api/availability?start_date=2027-03-01&end_date=2027-03-02&num_people=2")
        self.assertEqual(search.json["data"], [{"id": 5, "start_date": "2027-03-01"}])
        self.assertEqual(self.store.searches, [("2027-03-01", "2027-03-02", 2)])
        invalid = self.client.get("/api/availability?start_date=2027-03-01&end_date=2027-03-02&num_people=0")
        self.assertEqual(invalid.status_code, 400)

    def test_x_wait_for_covers_bookings_and_the_apartment_copy(self):
        fresh = self.client.get("/api/bookings", headers={"X-Wait-For": "booking:9@1, apartment:5@3"})
        self.assertEqual(fresh.headers["X-Consistency"], "fresh")
        stale = self.client.get("/api/availability?start_date=2027-03-01&end_date=2027-03-02&num_people=1",
                                headers={"X-Wait-For": "apartment:5@4"})
        self.assertEqual(stale.headers["X-Consistency"], "stale", "the apartment event has not arrived")
        self.assertNotIn("X-Consistency", self.client.get("/api/bookings").headers)

    def test_writes_do_not_wait(self):
        response = self.client.post("/api/bookings", json=BOOKING, headers={"X-Wait-For": "apartment:5@9"})
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("X-Consistency", response.headers)


if __name__ == "__main__":
    unittest.main()
