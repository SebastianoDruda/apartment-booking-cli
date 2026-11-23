import logging
import unittest

from fakes import RecordingPublisher

from dimora.common.events import Event
from dimora.common.outbox import BATCH_SIZE, OutboxRelay


class FakeOutboxStore:
    """Rows with version / published_version, like the PostgreSQL tables."""

    def __init__(self, rows: int) -> None:
        self.rows = {i: {"version": 1, "published_version": 0} for i in range(1, rows + 1)}

    def write(self, entity_id: int) -> None:
        self.rows[entity_id]["version"] += 1

    def pending_events(self, limit):
        pending = [i for i, row in sorted(self.rows.items()) if row["published_version"] < row["version"]]
        return [Event("booking.changed", i, self.rows[i]["version"], {"id": i}, source="test")
                for i in pending[:limit]]

    def mark_published(self, entity_id, version):
        row = self.rows[entity_id]
        if row["published_version"] < version:
            row["published_version"] = version


def relay_for(store, publisher):
    return OutboxRelay(store, publisher, logging.getLogger("test.outbox"))


class OutboxRelayTests(unittest.TestCase):
    def test_drains_every_pending_row_across_batches(self):
        store = FakeOutboxStore(BATCH_SIZE + 5)
        publisher = RecordingPublisher()
        self.assertEqual(relay_for(store, publisher).drain(), BATCH_SIZE + 5)
        self.assertEqual(store.pending_events(1000), [])

    def test_a_failed_publish_leaves_the_row_pending(self):
        store = FakeOutboxStore(3)
        with self.assertRaises(ConnectionError):
            relay_for(store, RecordingPublisher(fail_on=1)).drain()
        self.assertEqual([event.entity_id for event in store.pending_events(10)], [2, 3])
        relay_for(store, RecordingPublisher()).drain()
        self.assertEqual(store.pending_events(10), [])

    def test_a_change_made_while_publishing_is_not_lost(self):
        store = FakeOutboxStore(1)
        publisher = RecordingPublisher()
        original_publish = publisher.publish

        def publish_and_race(event):
            original_publish(event)
            if event.version == 1:
                store.write(1)  # committed after the relay read version 1

        publisher.publish = publish_and_race
        relay = relay_for(store, publisher)
        relay.drain()
        # Version 1 is recorded as published, but the row is still pending for version 2 ...
        self.assertEqual([event.version for event in store.pending_events(10)], [2])
        # ... which the next pass publishes.
        relay.drain()
        self.assertEqual([event.version for event in publisher.published], [1, 2])
        self.assertEqual(store.rows[1]["published_version"], 2)

    def test_resetting_published_version_republishes_everything(self):
        store = FakeOutboxStore(2)
        publisher = RecordingPublisher()
        relay = relay_for(store, publisher)
        relay.drain()
        for row in store.rows.values():
            row["published_version"] = 0
        relay.drain()
        self.assertEqual([event.event_id for event in publisher.published],
                         ["booking:1:v1", "booking:2:v1", "booking:1:v1", "booking:2:v1"])

    def test_the_thread_publishes_when_woken_and_stops_cleanly(self):
        store = FakeOutboxStore(2)
        publisher = RecordingPublisher()
        relay = OutboxRelay(store, publisher, logging.getLogger("test.outbox"), interval=30)
        relay.start()
        relay.wake()
        relay.stop()
        relay.join(timeout=5)
        self.assertFalse(relay.is_alive())
        self.assertGreaterEqual(publisher.closed, 1)


if __name__ == "__main__":
    unittest.main()
