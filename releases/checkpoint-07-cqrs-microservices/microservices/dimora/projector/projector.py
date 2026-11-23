"""Projection rules: how each event changes the read model.

The read model holds two collections, ``apartments`` and ``bookings``. Each
booking document also carries a copy of its apartment's name, address and
capacity, so the query service answers every GET with a single read.

Events of different services can arrive in any order, so a booking may arrive
before its apartment. The projector stores it anyway and fills in the apartment
details as soon as the apartment is known; until then the booking stays hidden.
Every write is guarded by the row version, which makes the rules idempotent.
"""

from __future__ import annotations

from typing import Any, Protocol

from dimora.common.events import Event

APARTMENTS = "apartments"
BOOKINGS = "bookings"


class ReadStore(Protocol):
    def upsert_if_newer(self, collection: str, doc_id: int, version: int, fields: dict[str, Any]) -> bool:
        """Write ``fields`` and ``version`` unless the stored version is the same or newer."""

    def get(self, collection: str, doc_id: int) -> dict[str, Any] | None:
        """Return one document, or None."""

    def set_fields(self, collection: str, doc_id: int, fields: dict[str, Any]) -> None:
        """Overwrite some fields of one document, if it exists."""

    def set_booking_apartment_fields(self, apartment_id: int, fields: dict[str, Any]) -> None:
        """Overwrite the apartment copy inside every booking of ``apartment_id``."""


def key(text: str) -> str:
    """Case-insensitive sort and match key, like SQLite's NOCASE in the original edition."""
    return text.casefold()


def apartment_fields(apartment: dict[str, Any]) -> dict[str, Any]:
    return {
        "apartment_name": apartment["name"],
        "apartment_name_key": apartment["name_key"],
        "apartment_address": apartment["address"],
        "apartment_max_people": apartment["max_people"],
        "apartment_removed": apartment["removed"],
    }


class Projector:
    def __init__(self, store: ReadStore) -> None:
        self.store = store

    def apply(self, event: Event) -> bool:
        """Apply one event; return False when it was older than what the view holds."""
        if event.aggregate == "apartment":
            return self._apartment(event)
        return self._booking(event)

    def _apartment(self, event: Event) -> bool:
        data = event.data
        applied = self.store.upsert_if_newer(APARTMENTS, event.entity_id, event.version, {
            "name": data["name"],
            "name_key": key(data["name"]),
            "address": data["address"],
            "max_people": data["max_people"],
            "price_per_night": data["price_per_night"],
            "removed": bool(data["removed"]),
        })
        # Always propagate the stored state: if a previous delivery stopped after the
        # first write, this redelivery completes it. A removed apartment hides its
        # bookings at once, before the reservation service has cancelled them.
        current = self.store.get(APARTMENTS, event.entity_id)
        if current is not None:
            self.store.set_booking_apartment_fields(event.entity_id, apartment_fields(current))
        return applied

    def _booking(self, event: Event) -> bool:
        data = event.data
        applied = self.store.upsert_if_newer(BOOKINGS, event.entity_id, event.version, {
            "apartment_id": data["apartment_id"],
            "booker_name": data["booker_name"],
            "booker_key": key(data["booker_name"]),
            "start_date": data["start_date"],
            "end_date": data["end_date"],
            "num_people": data["num_people"],
            "price_per_night": data["price_per_night"],
            "nights": data["nights"],
            "total_price": data["total_price"],
            "status": data["status"],
        })
        apartment = self.store.get(APARTMENTS, data["apartment_id"])
        if apartment is not None:
            self.store.set_fields(BOOKINGS, event.entity_id, apartment_fields(apartment))
        return applied
