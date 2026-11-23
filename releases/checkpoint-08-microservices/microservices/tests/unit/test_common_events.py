import json
import unittest

from dimora.common.events import QUEUES, Event, InvalidEvent

APARTMENT = {"id": 3, "name": "Casa Aurora", "address": "Italia, Amalfi, Via Roma 1",
             "max_people": 4, "price_per_night": 180.0, "removed": False}


class EventContractTests(unittest.TestCase):
    def test_round_trip_keeps_every_field(self):
        event = Event("apartment.added", 3, 1, APARTMENT, source="apartment-service")
        parsed = Event.from_json(event.to_json())
        self.assertEqual(parsed.type, "apartment.added")
        self.assertEqual(parsed.entity_id, 3)
        self.assertEqual(parsed.version, 1)
        self.assertEqual(parsed.data, APARTMENT)
        self.assertEqual(parsed.aggregate, "apartment")

    def test_event_id_is_deterministic_per_version(self):
        first = Event("apartment.price_changed", 3, 2, APARTMENT, source="a")
        again = Event("apartment.price_changed", 3, 2, APARTMENT, source="a")
        self.assertEqual(first.event_id, "apartment:3:v2")
        self.assertEqual(first.event_id, again.event_id)

    def test_contract_violations_are_rejected(self):
        valid = json.loads(Event("apartment.added", 3, 1, APARTMENT, source="a").to_json())
        broken = [
            b"not json",
            b"[1, 2]",
            json.dumps({**valid, "type": "apartment.renamed"}),
            json.dumps({**valid, "version": 0}),
            json.dumps({**valid, "version": True}),
            json.dumps({**valid, "entity_id": "3"}),
            json.dumps({**valid, "data": []}),
            json.dumps({**valid, "data": {k: v for k, v in APARTMENT.items() if k != "max_people"}}),
            json.dumps({**valid, "entity_id": 4}),
        ]
        for body in broken:
            with self.subTest(body=body), self.assertRaises(InvalidEvent):
                Event.from_json(body)

    def test_only_apartment_events_travel_on_the_bus(self):
        self.assertEqual(QUEUES, {"reservation.apartment-events": ("apartment.*",)})
        booking = json.dumps({"type": "booking.created", "entity_id": 9, "version": 1, "data": {"id": 9}})
        with self.assertRaises(InvalidEvent):
            Event.from_json(booking)


if __name__ == "__main__":
    unittest.main()
