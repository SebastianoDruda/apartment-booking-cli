import unittest

from fakes import InMemoryReadStore

from dimora.common.events import Event
from dimora.projector.projector import APARTMENTS, BOOKINGS, Projector


def apartment_event(version=1, *, kind="apartment.added", price=100.0, removed=False, entity_id=1):
    return Event(kind, entity_id, version, {
        "id": entity_id, "name": "Casa Aurora", "address": "Italia, Amalfi, Via Roma 1",
        "max_people": 4, "price_per_night": price, "removed": removed,
    }, source="apartment-service")


def booking_event(version=1, *, kind="booking.created", status="active", entity_id=10, start="2027-03-01"):
    return Event(kind, entity_id, version, {
        "id": entity_id, "apartment_id": 1, "booker_name": "Anna Huber",
        "start_date": start, "end_date": "2027-03-05", "num_people": 2,
        "price_per_night": 100.0, "nights": 4, "total_price": 400.0, "status": status,
    }, source="reservation-service")


class ProjectorTests(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryReadStore()
        self.projector = Projector(self.store)

    def booking(self):
        return self.store.get(BOOKINGS, 10)

    def test_booking_is_joined_with_its_apartment(self):
        self.projector.apply(apartment_event())
        self.projector.apply(booking_event())
        booking = self.booking()
        self.assertEqual(booking["apartment_name"], "Casa Aurora")
        self.assertEqual(booking["apartment_max_people"], 4)
        self.assertFalse(booking["apartment_removed"])
        self.assertEqual(booking["total_price"], 400.0)

    def test_booking_before_its_apartment_is_completed_later(self):
        self.projector.apply(booking_event())
        self.assertNotIn("apartment_name", self.booking(), "hidden until the apartment is known")
        self.projector.apply(apartment_event())
        self.assertEqual(self.booking()["apartment_name"], "Casa Aurora")

    def test_duplicates_and_late_versions_change_nothing(self):
        self.projector.apply(apartment_event(1, price=100.0))
        self.assertTrue(self.projector.apply(apartment_event(3, kind="apartment.price_changed", price=150.0)))
        self.assertFalse(self.projector.apply(apartment_event(2, kind="apartment.price_changed", price=120.0)))
        self.assertFalse(self.projector.apply(apartment_event(3, kind="apartment.price_changed", price=150.0)))
        self.assertEqual(self.store.get(APARTMENTS, 1)["price_per_night"], 150.0)
        self.assertEqual(self.store.get(APARTMENTS, 1)["version"], 3)

    def test_a_price_change_keeps_the_price_a_booking_was_made_at(self):
        self.projector.apply(apartment_event())
        self.projector.apply(booking_event())
        self.projector.apply(apartment_event(2, kind="apartment.price_changed", price=300.0))
        self.assertEqual(self.booking()["price_per_night"], 100.0)
        self.assertEqual(self.booking()["total_price"], 400.0)

    def test_removing_an_apartment_hides_its_bookings_at_once(self):
        self.projector.apply(apartment_event())
        self.projector.apply(booking_event())
        self.projector.apply(apartment_event(2, kind="apartment.removed", removed=True))
        self.assertTrue(self.store.get(APARTMENTS, 1)["removed"])
        self.assertTrue(self.booking()["apartment_removed"])

    def test_cancellation_and_change_update_the_view(self):
        self.projector.apply(apartment_event())
        self.projector.apply(booking_event())
        self.projector.apply(booking_event(2, kind="booking.changed", start="2027-03-02"))
        self.assertEqual(self.booking()["start_date"], "2027-03-02")
        self.projector.apply(booking_event(3, kind="booking.cancelled", status="cancelled"))
        self.assertEqual(self.booking()["status"], "cancelled")

    def test_a_redelivery_completes_an_interrupted_projection(self):
        self.projector.apply(booking_event())
        self.store.fail_after_upsert = True
        with self.assertRaises(ConnectionError):
            self.projector.apply(apartment_event())
        self.assertNotIn("apartment_name", self.booking())
        # RabbitMQ redelivers the unacknowledged event; the version guard skips the
        # apartment write, but the bookings are still brought up to date.
        self.assertFalse(self.projector.apply(apartment_event()))
        self.assertEqual(self.booking()["apartment_name"], "Casa Aurora")


if __name__ == "__main__":
    unittest.main()
