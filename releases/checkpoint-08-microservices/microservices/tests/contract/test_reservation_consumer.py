"""Consumer side of the event contract: what the reservation service relies on."""

import json
import unittest
from pathlib import Path

from dimora.common.events import EVENT_TYPES, QUEUES, Event

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts" / "events"

# Every field ReservationStore.apply_apartment_event reads, with its type.
READS = {"name": str, "address": str, "max_people": int, "price_per_night": float, "removed": bool}


class ReservationConsumerContractTests(unittest.TestCase):
    def test_there_is_a_contract_for_every_event_on_the_bus(self):
        self.assertEqual({path.stem for path in CONTRACTS.glob("*.json")}, set(EVENT_TYPES))

    def test_every_example_carries_what_the_copy_needs(self):
        for path in sorted(CONTRACTS.glob("*.json")):
            with self.subTest(contract=path.name):
                event = Event.from_json(path.read_bytes())
                for name, kind in READS.items():
                    self.assertIsInstance(event.data[name], kind, name)
                self.assertEqual(event.data["id"], event.entity_id)

    def test_the_reservation_queue_receives_every_apartment_event(self):
        self.assertIn("apartment.*", QUEUES["reservation.apartment-events"])
        for path in CONTRACTS.glob("*.json"):
            self.assertTrue(json.loads(path.read_text())["type"].startswith("apartment."))


if __name__ == "__main__":
    unittest.main()
