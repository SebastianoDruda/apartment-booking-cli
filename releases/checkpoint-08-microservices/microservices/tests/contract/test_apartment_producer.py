"""Producer side of the event contract: what the apartment service publishes."""

import json
import unittest
from pathlib import Path

from dimora.apartment.store import to_event
from dimora.common.events import Event

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts" / "events"
ROW = {"id": 3, "name": "Casa Aurora", "address": "Italia, Amalfi, Via Roma 1", "max_people": 4,
       "price_per_night": 180.0, "removed_at": None, "version": 1}


def example(event_type: str) -> dict:
    return json.loads((CONTRACTS / f"{event_type}.json").read_text())


class ApartmentProducerContractTests(unittest.TestCase):
    def assert_same_shape(self, produced: dict, expected: dict) -> None:
        self.assertEqual(set(produced), set(expected))
        for name, value in expected.items():
            if isinstance(value, dict):
                self.assert_same_shape(produced[name], value)
            else:
                self.assertIs(type(produced[name]), type(value), name)

    def test_every_published_event_matches_its_contract(self):
        cases = {
            "apartment.added": ROW,
            "apartment.price_changed": {**ROW, "price_per_night": 195.0, "version": 2},
            "apartment.removed": {**ROW, "removed_at": "2027-05-01T10:15:00+00:00", "version": 3},
        }
        for event_type, row in cases.items():
            with self.subTest(event_type=event_type):
                produced = json.loads(to_event({**row, "last_event": event_type}).to_json())
                self.assert_same_shape(produced, example(event_type))
                self.assertEqual(produced["data"]["removed"], event_type == "apartment.removed")

    def test_examples_are_valid_events(self):
        for path in sorted(CONTRACTS.glob("*.json")):
            with self.subTest(contract=path.name):
                Event.from_json(path.read_bytes())


if __name__ == "__main__":
    unittest.main()
