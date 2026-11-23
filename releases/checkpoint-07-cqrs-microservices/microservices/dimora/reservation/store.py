"""Write model of the reservation service: the only owner of booking data.

To check capacity and overlaps without calling the apartment service, it keeps a
small copy of every apartment (id, name, address, capacity, nightly price), fed
by apartment events. Each booking stores the nightly price it was made at, so a
later price change only affects new bookings.

Cancelling a booking keeps the row with status ``cancelled``: the slot is free
again, and the cancellation is published like any other change.
"""

from __future__ import annotations

import time
from datetime import date
from typing import Any

from psycopg import errors

from apartment_booking.database import (
    BookingConflictError, RecordNotFoundError, calculate_total_price, validate_date_range,
)
from dimora.common import events
from dimora.common.events import Event
from dimora.common.postgres import ensure_schema, transaction

SOURCE = "reservation-service"
SCHEMA_LOCK = 7_000_002

SCHEMA = (
    # btree_gist lets one exclusion constraint combine "same apartment" with "dates overlap".
    "CREATE EXTENSION IF NOT EXISTS btree_gist",
    """
    CREATE TABLE IF NOT EXISTS apartment_copies (
        id BIGINT PRIMARY KEY,
        name TEXT NOT NULL,
        address TEXT NOT NULL,
        max_people BIGINT NOT NULL,
        price_per_night DOUBLE PRECISION NOT NULL,
        removed BOOLEAN NOT NULL DEFAULT FALSE,
        version INTEGER NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS apartment_copies_name"
    " ON apartment_copies (lower(name)) WHERE NOT removed",
    """
    CREATE TABLE IF NOT EXISTS bookings (
        id BIGSERIAL PRIMARY KEY,
        apartment_id BIGINT NOT NULL,
        booker_name TEXT NOT NULL,
        start_date DATE NOT NULL,
        end_date DATE NOT NULL,
        num_people BIGINT NOT NULL CHECK (num_people > 0),
        price_per_night DOUBLE PRECISION NOT NULL CHECK (price_per_night > 0),
        status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'cancelled')),
        last_event TEXT NOT NULL,
        version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
        published_version INTEGER NOT NULL DEFAULT 0,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CHECK (end_date > start_date),
        -- Last line of defence against double bookings, even under concurrent writes.
        CONSTRAINT bookings_no_overlap EXCLUDE USING gist (
            apartment_id WITH =, daterange(start_date, end_date) WITH &&
        ) WHERE (status = 'active')
    )
    """,
    "CREATE INDEX IF NOT EXISTS bookings_unpublished"
    " ON bookings (id) WHERE published_version < version",
)

BOOKING_COLUMNS = (
    "b.id, b.apartment_id, b.booker_name, b.start_date, b.end_date, b.num_people,"
    " b.price_per_night, b.status, b.last_event, b.version"
)
APARTMENT_COLUMNS = (
    "a.name AS apartment_name, a.address AS apartment_address,"
    " a.max_people AS apartment_max_people"
)


def iso(value: date | str) -> str:
    return value.isoformat() if isinstance(value, date) else value


def nights_between(start: date | str, end: date | str) -> int:
    return (date.fromisoformat(iso(end)) - date.fromisoformat(iso(start))).days


def public(row: dict[str, Any], apartment: dict[str, Any]) -> dict[str, Any]:
    """The booking as the REST API has always returned it."""
    nights = nights_between(row["start_date"], row["end_date"])
    price = float(row["price_per_night"])
    return {
        "id": row["id"],
        "apartment_id": row["apartment_id"],
        "apartment_name": apartment["name"],
        "apartment_address": apartment["address"],
        "apartment_max_people": apartment["max_people"],
        "price_per_night": price,
        "booker_name": row["booker_name"],
        "start_date": iso(row["start_date"]),
        "end_date": iso(row["end_date"]),
        "nights": nights,
        "num_people": row["num_people"],
        "total_price": calculate_total_price(nights, price),
    }


def to_event(row: dict[str, Any]) -> Event:
    nights = nights_between(row["start_date"], row["end_date"])
    price = float(row["price_per_night"])
    return Event(
        type=row["last_event"], entity_id=row["id"], version=row["version"], source=SOURCE,
        data={
            "id": row["id"],
            "apartment_id": row["apartment_id"],
            "booker_name": row["booker_name"],
            "start_date": iso(row["start_date"]),
            "end_date": iso(row["end_date"]),
            "num_people": row["num_people"],
            "price_per_night": price,
            "nights": nights,
            "total_price": calculate_total_price(nights, price),
            "status": row["status"],
        },
    )


def apartment_of(row: dict[str, Any]) -> dict[str, Any]:
    return {"name": row["apartment_name"], "address": row["apartment_address"],
            "max_people": row["apartment_max_people"]}


class ReservationStore:
    def __init__(self, dsn: str, copy_grace: float = 2.0) -> None:
        self.dsn = dsn
        # How long a booking for an apartment the copy does not know yet waits for its
        # apartment.added event. A client that creates an apartment and books it right
        # away would otherwise race the event by a few milliseconds.
        self.copy_grace = copy_grace

    def _wait_for_apartment(self, clean_name: str) -> None:
        deadline = time.monotonic() + self.copy_grace
        with transaction(self.dsn) as connection:
            while True:
                known = connection.execute(
                    "SELECT 1 FROM apartment_copies WHERE lower(name) = lower(%s) AND NOT removed",
                    (clean_name,),
                ).fetchone()
                if known is not None or time.monotonic() >= deadline:
                    return
                connection.commit()  # end the snapshot so the next read sees new rows
                time.sleep(0.05)

    def ensure_schema(self) -> None:
        ensure_schema(self.dsn, SCHEMA, SCHEMA_LOCK)

    # ------------------------------------------------------------------
    # Lookups inside a transaction
    # ------------------------------------------------------------------

    @staticmethod
    def _apartment_for_update(connection, clean_name: str) -> dict[str, Any]:
        # Locking the copy serialises bookings of one apartment, like BEGIN IMMEDIATE did.
        row = connection.execute(
            """
            SELECT id, name, address, max_people, price_per_night FROM apartment_copies
            WHERE lower(name) = lower(%s) AND NOT removed
            ORDER BY id DESC LIMIT 1
            FOR UPDATE
            """,
            (clean_name,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"Apartment '{clean_name}' does not exist.")
        return row

    @staticmethod
    def _active_booking_for_update(connection, clean_name: str, start_iso: str, end_iso: str):
        return connection.execute(
            f"""
            SELECT {BOOKING_COLUMNS}, {APARTMENT_COLUMNS}
            FROM bookings b JOIN apartment_copies a ON a.id = b.apartment_id
            WHERE lower(a.name) = lower(%s) AND NOT a.removed
              AND b.status = 'active' AND b.start_date = %s AND b.end_date = %s
            FOR UPDATE OF b, a
            """,
            (clean_name, start_iso, end_iso),
        ).fetchone()

    @staticmethod
    def _overlaps(connection, apartment_id: int, start_iso: str, end_iso: str,
                  exclude_booking_id: int | None = None) -> bool:
        row = connection.execute(
            """
            SELECT 1 FROM bookings
            WHERE apartment_id = %s AND status = 'active'
              AND start_date < %s AND end_date > %s
              AND id IS DISTINCT FROM %s
            LIMIT 1
            """,
            (apartment_id, end_iso, start_iso, exclude_booking_id),
        ).fetchone()
        return row is not None

    # ------------------------------------------------------------------
    # Commands (validation mirrors apartment_booking.database.BookingDatabase)
    # ------------------------------------------------------------------

    def create_booking(self, apartment_name: str, start_date_str: str, end_date_str: str,
                       booker_name: str, num_people: int) -> tuple[dict[str, Any], int]:
        clean_apt_name = apartment_name.strip()
        clean_booker = booker_name.strip()
        if not clean_apt_name:
            raise ValueError("Apartment name cannot be empty.")
        if not clean_booker:
            raise ValueError("Booker name cannot be empty.")
        start_iso, end_iso, _nights = validate_date_range(start_date_str, end_date_str)
        people = int(num_people)
        if people <= 0:
            raise ValueError("Number of people must be at least 1.")

        def conflict(name: str) -> BookingConflictError:
            return BookingConflictError(
                f"Apartment '{name}' is not available from {start_iso} to {end_iso} "
                "(dates overlap with an existing booking)."
            )

        self._wait_for_apartment(clean_apt_name)
        try:
            with transaction(self.dsn) as connection:
                apartment = self._apartment_for_update(connection, clean_apt_name)
                if people > apartment["max_people"]:
                    raise ValueError(
                        f"Apartment '{apartment['name']}' is not big enough for {people} people "
                        f"(maximum capacity: {apartment['max_people']})."
                    )
                if self._overlaps(connection, apartment["id"], start_iso, end_iso):
                    raise conflict(apartment["name"])
                row = connection.execute(
                    f"""
                    INSERT INTO bookings AS b (apartment_id, booker_name, start_date, end_date,
                                               num_people, price_per_night, last_event)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING {BOOKING_COLUMNS}
                    """,
                    (apartment["id"], clean_booker, start_iso, end_iso, people,
                     float(apartment["price_per_night"]), events.BOOKING_CREATED),
                ).fetchone()
        except errors.ExclusionViolation as error:
            raise conflict(clean_apt_name) from error
        return public(row, apartment), row["version"]

    def change_booking(self, apartment_name: str, old_start_str: str, old_end_str: str,
                       new_start_str: str, new_end_str: str,
                       new_num_people: int) -> tuple[dict[str, Any], int]:
        clean_apt_name = apartment_name.strip()
        if not clean_apt_name:
            raise ValueError("Apartment name cannot be empty.")
        old_start_iso, old_end_iso, _ = validate_date_range(old_start_str, old_end_str)
        new_start_iso, new_end_iso, _ = validate_date_range(new_start_str, new_end_str)
        people = int(new_num_people)
        if people <= 0:
            raise ValueError("Number of people must be at least 1.")

        try:
            with transaction(self.dsn) as connection:
                current = self._active_booking_for_update(
                    connection, clean_apt_name, old_start_iso, old_end_iso)
                if current is None:
                    raise RecordNotFoundError(
                        f"No booking found for apartment '{clean_apt_name}' "
                        f"from {old_start_iso} to {old_end_iso}."
                    )
                apartment = apartment_of(current)
                if people > apartment["max_people"]:
                    raise ValueError(
                        f"Apartment '{apartment['name']}' is not big enough for {people} people "
                        f"(maximum capacity: {apartment['max_people']})."
                    )
                if self._overlaps(connection, current["apartment_id"], new_start_iso, new_end_iso,
                                  exclude_booking_id=current["id"]):
                    raise BookingConflictError(
                        f"Apartment '{apartment['name']}' is not available from "
                        f"{new_start_iso} to {new_end_iso} (dates overlap with another booking)."
                    )
                row = connection.execute(
                    f"""
                    UPDATE bookings AS b
                    SET start_date = %s, end_date = %s, num_people = %s,
                        version = version + 1, last_event = %s, updated_at = now()
                    WHERE id = %s
                    RETURNING {BOOKING_COLUMNS}
                    """,
                    (new_start_iso, new_end_iso, people, events.BOOKING_CHANGED, current["id"]),
                ).fetchone()
        except errors.ExclusionViolation as error:
            raise BookingConflictError(
                f"Apartment '{clean_apt_name}' is not available from "
                f"{new_start_iso} to {new_end_iso} (dates overlap with another booking)."
            ) from error

        result = public(row, apartment)
        result.update({
            "old_start_date": old_start_iso,
            "old_end_date": old_end_iso,
            "old_num_people": current["num_people"],
        })
        return result, row["version"]

    def cancel_booking(self, apartment_name: str, start_date_str: str,
                       end_date_str: str) -> tuple[dict[str, Any], int]:
        clean_apt_name = apartment_name.strip()
        if not clean_apt_name:
            raise ValueError("Apartment name cannot be empty.")
        start_iso, end_iso, _ = validate_date_range(start_date_str, end_date_str)

        with transaction(self.dsn) as connection:
            current = self._active_booking_for_update(connection, clean_apt_name, start_iso, end_iso)
            if current is None:
                raise RecordNotFoundError(
                    f"No booking found for apartment '{clean_apt_name}' "
                    f"from {start_iso} to {end_iso}."
                )
            row = connection.execute(
                f"""
                UPDATE bookings AS b
                SET status = 'cancelled', version = version + 1, last_event = %s, updated_at = now()
                WHERE id = %s
                RETURNING {BOOKING_COLUMNS}
                """,
                (events.BOOKING_CANCELLED, current["id"]),
            ).fetchone()
        return public(row, apartment_of(current)), row["version"]

    # ------------------------------------------------------------------
    # Apartment events (consumed from RabbitMQ)
    # ------------------------------------------------------------------

    def apply_apartment_event(self, event: Event) -> int:
        """Update the apartment copy; when an apartment is removed, cancel its bookings.

        Returns how many bookings were cancelled. Applying the same or an older
        version again changes nothing, so redelivered events are harmless.
        """
        data = event.data
        with transaction(self.dsn) as connection:
            connection.execute(
                """
                INSERT INTO apartment_copies AS a
                    (id, name, address, max_people, price_per_night, removed, version)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name, address = EXCLUDED.address,
                    max_people = EXCLUDED.max_people, price_per_night = EXCLUDED.price_per_night,
                    removed = EXCLUDED.removed, version = EXCLUDED.version
                WHERE a.version < EXCLUDED.version
                """,
                (event.entity_id, data["name"], data["address"], data["max_people"],
                 data["price_per_night"], bool(data["removed"]), event.version),
            )
            removed = connection.execute(
                "SELECT removed FROM apartment_copies WHERE id = %s", (event.entity_id,)
            ).fetchone()["removed"]
            if not removed:
                return 0
            # Same outcome as the original ON DELETE CASCADE, expressed as cancellations
            # that are themselves published.
            cancelled = connection.execute(
                """
                UPDATE bookings
                SET status = 'cancelled', version = version + 1, last_event = %s, updated_at = now()
                WHERE apartment_id = %s AND status = 'active'
                """,
                (events.BOOKING_CANCELLED, event.entity_id),
            )
            return cancelled.rowcount

    # ------------------------------------------------------------------
    # Outbox
    # ------------------------------------------------------------------

    def pending_events(self, limit: int) -> list[Event]:
        with transaction(self.dsn) as connection:
            rows = connection.execute(
                f"SELECT {BOOKING_COLUMNS} FROM bookings b WHERE b.published_version < b.version"
                " ORDER BY b.id LIMIT %s",
                (limit,),
            ).fetchall()
        return [to_event(row) for row in rows]

    def mark_published(self, entity_id: int, version: int) -> None:
        with transaction(self.dsn) as connection:
            connection.execute(
                "UPDATE bookings SET published_version = %s WHERE id = %s AND published_version < %s",
                (version, entity_id, version),
            )

    def pending_count(self) -> int:
        with transaction(self.dsn) as connection:
            return connection.execute(
                "SELECT count(*) AS pending FROM bookings WHERE published_version < version"
            ).fetchone()["pending"]

    def known_apartments(self) -> int:
        with transaction(self.dsn) as connection:
            return connection.execute(
                "SELECT count(*) AS known FROM apartment_copies WHERE NOT removed"
            ).fetchone()["known"]
