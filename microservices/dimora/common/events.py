"""Event contract shared by publishers and consumers.

Every event carries the *full current state* of one row (an apartment or a
booking) together with that row's version. Consumers therefore never need the
history: applying the newest version they have seen is enough, duplicates are
harmless, and an older version arriving late is simply ignored.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

EXCHANGE = "dimora.events"
DEAD_LETTER_EXCHANGE = "dimora.dead-letter"
DEAD_LETTER_QUEUE = "dimora.dead-letter"

APARTMENT_ADDED = "apartment.added"
APARTMENT_PRICE_CHANGED = "apartment.price_changed"
APARTMENT_REMOVED = "apartment.removed"
BOOKING_CREATED = "booking.created"
BOOKING_CHANGED = "booking.changed"
BOOKING_CANCELLED = "booking.cancelled"

EVENT_TYPES = frozenset({
    APARTMENT_ADDED, APARTMENT_PRICE_CHANGED, APARTMENT_REMOVED,
    BOOKING_CREATED, BOOKING_CHANGED, BOOKING_CANCELLED,
})

# Durable queues and the routing keys bound to them. Every service declares the
# whole topology when it connects, so the queues exist before the first publish
# and a consumer that starts later still receives every event.
QUEUES: dict[str, tuple[str, ...]] = {
    "reservation.apartment-events": ("apartment.*",),
    "projector.events": ("apartment.*", "booking.*"),
}

APARTMENT_FIELDS = ("id", "name", "address", "max_people", "price_per_night", "removed")
BOOKING_FIELDS = (
    "id", "apartment_id", "booker_name", "start_date", "end_date", "num_people",
    "price_per_night", "nights", "total_price", "status",
)


class InvalidEvent(ValueError):
    """A message that does not follow the event contract; it can never be processed."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass(frozen=True)
class Event:
    """One state change of an apartment or a booking."""

    type: str
    entity_id: int
    version: int
    data: dict[str, Any]
    source: str
    occurred_at: str = field(default_factory=utc_now)

    @property
    def aggregate(self) -> str:
        return self.type.split(".", 1)[0]

    @property
    def event_id(self) -> str:
        # Deterministic: republishing the same version yields the same id.
        return f"{self.aggregate}:{self.entity_id}:v{self.version}"

    def to_json(self) -> bytes:
        return json.dumps({
            "event_id": self.event_id,
            "type": self.type,
            "source": self.source,
            "entity_id": self.entity_id,
            "version": self.version,
            "occurred_at": self.occurred_at,
            "data": self.data,
        }, separators=(",", ":"), sort_keys=True).encode()

    @classmethod
    def from_json(cls, body: bytes | str) -> Event:
        try:
            payload = json.loads(body)
        except (TypeError, ValueError, UnicodeDecodeError) as error:
            raise InvalidEvent(f"Event body is not valid JSON: {error}") from error
        if not isinstance(payload, dict):
            raise InvalidEvent("Event body must be a JSON object.")

        event_type = payload.get("type")
        if event_type not in EVENT_TYPES:
            raise InvalidEvent(f"Unknown event type: {event_type!r}.")
        entity_id = payload.get("entity_id")
        version = payload.get("version")
        for name, value in (("entity_id", entity_id), ("version", version)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise InvalidEvent(f"{name} must be a positive integer.")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise InvalidEvent("data must be an object.")

        required = APARTMENT_FIELDS if event_type.startswith("apartment.") else BOOKING_FIELDS
        missing = [name for name in required if name not in data]
        if missing:
            raise InvalidEvent(f"{event_type} is missing: {', '.join(missing)}.")
        if data["id"] != entity_id:
            raise InvalidEvent("data.id must match entity_id.")

        return cls(
            type=event_type,
            entity_id=entity_id,
            version=version,
            data=data,
            source=str(payload.get("source", "unknown")),
            occurred_at=str(payload.get("occurred_at", "")),
        )
