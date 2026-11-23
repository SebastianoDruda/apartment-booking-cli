"""Outbox relay: publishes every row whose latest version has not gone out yet.

Each write-side table carries two counters. ``version`` grows with every change,
in the same transaction as the change itself; ``published_version`` records the
last version confirmed by RabbitMQ. A row is pending while
``published_version < version``.

The relay reads pending rows, publishes their full current state, waits for the
broker's confirmation and only then stores the version it sent. Because it stores
that exact version (not a "published" flag), a change committed while the event
was in flight leaves the row pending and goes out on the next pass. A write
therefore never depends on RabbitMQ being up, and nothing is lost when it is not.
"""

from __future__ import annotations

import logging
import threading
from typing import Protocol

from dimora.common.events import Event
from dimora.common.messaging import Backoff, Publisher

BATCH_SIZE = 100


class OutboxStore(Protocol):
    def pending_events(self, limit: int) -> list[Event]:
        """Return up to ``limit`` events for rows whose version has not been published."""

    def mark_published(self, entity_id: int, version: int) -> None:
        """Record that ``version`` of a row reached the broker."""


class OutboxRelay(threading.Thread):
    """Background thread that drains the outbox; ``wake()`` makes it run immediately."""

    def __init__(self, store: OutboxStore, publisher: Publisher, log: logging.Logger,
                 interval: float = 1.0) -> None:
        super().__init__(name="outbox-relay", daemon=True)
        self.store = store
        self.publisher = publisher
        self.log = log
        self.interval = interval
        self._wake_requested = threading.Event()
        self._stop_requested = threading.Event()

    def wake(self) -> None:
        self._wake_requested.set()

    def stop(self) -> None:
        self._stop_requested.set()
        self._wake_requested.set()

    def drain(self) -> int:
        """Publish pending rows until none are left; return how many were published."""
        published = 0
        while True:
            events = self.store.pending_events(BATCH_SIZE)
            for event in events:
                self.publisher.publish(event)
                self.store.mark_published(event.entity_id, event.version)
                published += 1
                self.log.info("Published %s (%s)", event.event_id, event.type)
            if len(events) < BATCH_SIZE:
                return published

    def run(self) -> None:
        backoff = Backoff()
        delay = 0.0
        while not self._stop_requested.is_set():
            self._wake_requested.wait(delay)
            # Clear before reading, so a write committed meanwhile wakes the next pass.
            self._wake_requested.clear()
            if self._stop_requested.is_set():
                break
            try:
                self.drain()
                self.publisher.keep_alive()
                backoff.reset()
                delay = self.interval
            except Exception as error:  # noqa: BLE001 - keep the rows pending and retry
                self.publisher.close()
                delay = backoff.next()
                self.log.warning("Outbox relay paused (%s: %s); retrying in %.1f s",
                                 type(error).__name__, error, delay)
        self.publisher.close()
