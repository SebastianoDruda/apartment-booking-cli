"""Data of the apartment service: the only owner of apartment data.

It knows nothing about bookings. It answers the apartment reads from its own
table, and every change increases the row's ``version`` in the same transaction,
which queues an event for the outbox relay.
"""

from __future__ import annotations

from typing import Any

from psycopg import errors

from apartment_booking.database import BookingConflictError, RecordNotFoundError, validate_price
from dimora.common import events
from dimora.common.events import Event
from dimora.common.postgres import ensure_schema, transaction

SOURCE = "apartment-service"
SCHEMA_LOCK = 7_000_001

SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS apartments (
        id BIGSERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        address TEXT NOT NULL,
        max_people BIGINT NOT NULL CHECK (max_people > 0),
        price_per_night DOUBLE PRECISION NOT NULL CHECK (price_per_night > 0),
        removed_at TIMESTAMPTZ,
        last_event TEXT NOT NULL,
        version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
        published_version INTEGER NOT NULL DEFAULT 0,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    # Names are unique, case-insensitively, among apartments that still exist.
    "CREATE UNIQUE INDEX IF NOT EXISTS apartments_active_name"
    " ON apartments (lower(name)) WHERE removed_at IS NULL",
    "CREATE INDEX IF NOT EXISTS apartments_unpublished"
    " ON apartments (id) WHERE published_version < version",
)

COLUMNS = "id, name, address, max_people, price_per_night, removed_at, last_event, version"

# A booking token names a row this service never holds, so there is nothing to wait for.
NOT_OURS = 2**31


def public(row: dict[str, Any]) -> dict[str, Any]:
    """The apartment as the REST API has always returned it."""
    return {
        "id": row["id"],
        "name": row["name"],
        "address": row["address"],
        "max_people": row["max_people"],
        "price_per_night": float(row["price_per_night"]),
    }


def to_event(row: dict[str, Any]) -> Event:
    data = public(row)
    data["removed"] = row["removed_at"] is not None
    return Event(type=row["last_event"], entity_id=row["id"], version=row["version"],
                 data=data, source=SOURCE)


class ApartmentStore:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def ensure_schema(self) -> None:
        ensure_schema(self.dsn, SCHEMA, SCHEMA_LOCK)

    # ------------------------------------------------------------------
    # Commands (validation mirrors apartment_booking.database.BookingDatabase)
    # ------------------------------------------------------------------

    def add_apartment(self, name: str, address: str, max_people: int,
                      price_per_night: float) -> tuple[dict[str, Any], int]:
        clean_name = name.strip()
        clean_address = address.strip()
        if not clean_name:
            raise ValueError("Apartment name cannot be empty.")
        if not clean_address:
            raise ValueError("Apartment address cannot be empty.")
        if int(max_people) <= 0:
            raise ValueError("Maximum number of people must be at least 1.")
        price = validate_price(price_per_night)

        try:
            with transaction(self.dsn) as connection:
                row = connection.execute(
                    f"""
                    INSERT INTO apartments (name, address, max_people, price_per_night, last_event)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING {COLUMNS}
                    """,
                    (clean_name, clean_address, int(max_people), price, events.APARTMENT_ADDED),
                ).fetchone()
        except errors.UniqueViolation as error:
            raise BookingConflictError(f"Apartment '{clean_name}' already exists.") from error
        return public(row), row["version"]

    def _find_for_update(self, connection, clean_name: str) -> dict[str, Any]:
        row = connection.execute(
            f"""
            SELECT {COLUMNS} FROM apartments
            WHERE lower(name) = lower(%s) AND removed_at IS NULL
            FOR UPDATE
            """,
            (clean_name,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"Apartment '{clean_name}' does not exist.")
        return row

    def update_apartment_price(self, name: str, new_price: float) -> tuple[dict[str, Any], int]:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Apartment name cannot be empty.")
        price = validate_price(new_price)

        with transaction(self.dsn) as connection:
            current = self._find_for_update(connection, clean_name)
            row = connection.execute(
                f"""
                UPDATE apartments
                SET price_per_night = %s, version = version + 1, last_event = %s, updated_at = now()
                WHERE id = %s
                RETURNING {COLUMNS}
                """,
                (price, events.APARTMENT_PRICE_CHANGED, current["id"]),
            ).fetchone()
        result = public(row)
        result["old_price_per_night"] = float(current["price_per_night"])
        return result, row["version"]

    def remove_apartment(self, name: str) -> tuple[dict[str, Any], int]:
        """Mark the apartment as removed; the row stays so that its removal is published too."""
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Apartment name cannot be empty.")

        with transaction(self.dsn) as connection:
            current = self._find_for_update(connection, clean_name)
            row = connection.execute(
                f"""
                UPDATE apartments
                SET removed_at = now(), version = version + 1, last_event = %s, updated_at = now()
                WHERE id = %s
                RETURNING {COLUMNS}
                """,
                (events.APARTMENT_REMOVED, current["id"]),
            ).fetchone()
        return public(row), row["version"]

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def ping(self) -> None:
        with transaction(self.dsn) as connection:
            connection.execute("SELECT 1")

    def list_apartments(self) -> list[dict[str, Any]]:
        """Every apartment that still exists, sorted by name like SQLite's NOCASE."""
        with transaction(self.dsn) as connection:
            rows = connection.execute(
                f"SELECT {COLUMNS} FROM apartments WHERE removed_at IS NULL"
                ' ORDER BY lower(name) COLLATE "C", id'
            ).fetchall()
        return [public(row) for row in rows]

    def current_version(self, aggregate: str, entity_id: int) -> int | None:
        """Version of an apartment; other aggregates are not this service's to wait for."""
        if aggregate != "apartment":
            return NOT_OURS
        with transaction(self.dsn) as connection:
            row = connection.execute(
                "SELECT version FROM apartments WHERE id = %s", (entity_id,)
            ).fetchone()
        return row["version"] if row else None

    # ------------------------------------------------------------------
    # Outbox
    # ------------------------------------------------------------------

    def pending_events(self, limit: int) -> list[Event]:
        with transaction(self.dsn) as connection:
            rows = connection.execute(
                f"SELECT {COLUMNS} FROM apartments WHERE published_version < version"
                " ORDER BY id LIMIT %s",
                (limit,),
            ).fetchall()
        return [to_event(row) for row in rows]

    def mark_published(self, entity_id: int, version: int) -> None:
        with transaction(self.dsn) as connection:
            connection.execute(
                "UPDATE apartments SET published_version = %s WHERE id = %s AND published_version < %s",
                (version, entity_id, version),
            )

    def pending_count(self) -> int:
        with transaction(self.dsn) as connection:
            return connection.execute(
                "SELECT count(*) AS pending FROM apartments WHERE published_version < version"
            ).fetchone()["pending"]
