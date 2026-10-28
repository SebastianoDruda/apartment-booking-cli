"""Database and business logic layer for the Apartment Booking System."""

from __future__ import annotations

import calendar
import math
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator

DEFAULT_DB_PATH = Path(
    os.environ.get("APARTMENT_BOOKING_DB_PATH")
    or Path(__file__).resolve().parent.parent / "apartment_booking.db"
)

_DATE_PATTERNS = (
    # YYYY-MM-DD or YYYY/MM/DD
    (re.compile(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$"), ("year", "month", "day")),
    # DD.MM.YYYY or DD/MM/YYYY
    (re.compile(r"^(\d{1,2})[./](\d{1,2})[./](\d{4})$"), ("day", "month", "year")),
)


class RecordNotFoundError(ValueError):
    """The apartment or booking requested by an operation does not exist."""


class BookingConflictError(ValueError):
    """An apartment name or date range conflicts with existing data."""


def parse_price_input(value: str) -> float:
    """Parse the price formats accepted by both the CLI and HTTP interface."""
    normalized = value.strip().replace(",", ".").replace("€", "").strip()
    try:
        price = float(normalized)
    except ValueError as exc:
        raise ValueError("Price per night must be a valid number (e.g., 85 or 85.50).") from exc
    return validate_price(price)


def parse_date(date_str: str) -> str:
    """Parse a date string into ISO format (YYYY-MM-DD) with strict month/day validation.

    Supports YYYY-MM-DD, DD.MM.YYYY, DD/MM/YYYY, and YYYY/MM/DD.
    Explicitly checks whether the month exists (1..12) and whether the day is valid
    for that specific month and year (e.g. rejecting 31st of September since September
    only has 30 days).
    """
    cleaned = date_str.strip()
    if not cleaned:
        raise ValueError("Date cannot be empty. Please use YYYY-MM-DD (e.g., 2026-09-30).")

    for pattern, order in _DATE_PATTERNS:
        match = pattern.match(cleaned)
        if match:
            parts = {name: int(val) for name, val in zip(order, match.groups())}
            year, month, day = parts["year"], parts["month"], parts["day"]

            if month < 1 or month > 12:
                raise ValueError(
                    f"Invalid month '{month}' in '{cleaned}': month must be between 1 and 12."
                )

            max_days = calendar.monthrange(year, month)[1]
            month_name = calendar.month_name[month]
            if day < 1 or day > max_days:
                raise ValueError(
                    f"Invalid date '{cleaned}': {month_name} {year} only has {max_days} days "
                    f"(day {day} is not possible)."
                )

            return date(year, month, day).isoformat()

    raise ValueError(
        f"Invalid date format '{cleaned}'. Please use YYYY-MM-DD (e.g., 2026-09-30) or DD.MM.YYYY."
    )


def validate_date_range(start_str: str, end_str: str) -> tuple[str, str, int]:
    """Validate a booking date range and return (start_iso, end_iso, nights)."""
    start_iso = parse_date(start_str)
    end_iso = parse_date(end_str)

    start_date = datetime.strptime(start_iso, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_iso, "%Y-%m-%d").date()

    if end_date <= start_date:
        raise ValueError(
            f"Invalid date range ({start_iso} to {end_iso}): end date must be after start date."
        )

    nights = (end_date - start_date).days
    return start_iso, end_iso, nights


def format_address(country: str, city: str, street_and_number: str) -> str:
    """Validate and format a standardized apartment address as 'Country, City, Street and house number'."""
    clean_country = country.strip()
    clean_city = city.strip()
    clean_street = street_and_number.strip()

    if not clean_country:
        raise ValueError("Country cannot be empty.")
    if not clean_city:
        raise ValueError("City cannot be empty.")
    if not clean_street:
        raise ValueError("Street and house number cannot be empty.")

    return f"{clean_country}, {clean_city}, {clean_street}"


def validate_price(value: float) -> float:
    """Return a finite, positive nightly price rounded to two decimal places."""
    price = float(value)
    if not math.isfinite(price):
        raise ValueError("Price per night must be a finite number.")
    price = round(price, 2)
    if price <= 0:
        raise ValueError("Price per night must be greater than 0 EUR after rounding.")
    return price


def calculate_total_price(nights: int, price_per_night: float) -> float:
    """Calculate a total without allowing floating-point overflow."""
    total = nights * validate_price(price_per_night)
    if not math.isfinite(total):
        raise ValueError("Total price is too large. Use a lower nightly price or a shorter stay.")
    return round(total, 2)


class BookingDatabase:
    """SQLite persistence and validation for apartments and bookings."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = str(db_path)
        self._persistent_conn: sqlite3.Connection | None = None
        if self.db_path == ":memory:":
            self._persistent_conn = sqlite3.connect(":memory:")
            self._persistent_conn.row_factory = sqlite3.Row
            self._persistent_conn.execute("PRAGMA foreign_keys = ON;")
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._persistent_conn is not None:
            return self._persistent_conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _close_if_needed(self, conn: sqlite3.Connection) -> None:
        if self._persistent_conn is None:
            conn.close()

    @contextmanager
    def _write_connection(self) -> Iterator[sqlite3.Connection]:
        """Keep validation and writes atomic, rolling back on any failure."""
        conn = self._get_connection()
        try:
            with conn:
                # Reserve the writer before reading availability or existing records.
                conn.execute("BEGIN IMMEDIATE;")
                yield conn
        finally:
            self._close_if_needed(conn)

    def close(self) -> None:
        """Close persistent in-memory connection if open."""
        if self._persistent_conn is not None:
            self._persistent_conn.close()
            self._persistent_conn = None

    def _init_db(self) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS apartments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                        address TEXT NOT NULL,
                        max_people INTEGER NOT NULL CHECK (max_people > 0),
                        price_per_night REAL NOT NULL CHECK (price_per_night > 0)
                    );
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS bookings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        apartment_id INTEGER NOT NULL,
                        booker_name TEXT NOT NULL,
                        start_date TEXT NOT NULL,
                        end_date TEXT NOT NULL,
                        num_people INTEGER NOT NULL CHECK (num_people > 0),
                        FOREIGN KEY (apartment_id) REFERENCES apartments(id) ON DELETE CASCADE
                    );
                    """
                )
        finally:
            self._close_if_needed(conn)

    # ------------------------------------------------------------------
    # Apartment Management
    # ------------------------------------------------------------------

    def add_apartment(
        self, name: str, address: str, max_people: int, price_per_night: float
    ) -> dict[str, Any]:
        """Add a new apartment to the database."""
        clean_name = name.strip()
        clean_address = address.strip()

        if not clean_name:
            raise ValueError("Apartment name cannot be empty.")
        if not clean_address:
            raise ValueError("Apartment address cannot be empty.")
        if int(max_people) <= 0:
            raise ValueError("Maximum number of people must be at least 1.")
        max_people_int = int(max_people)
        price_float = validate_price(price_per_night)

        with self._write_connection() as conn:
            existing = conn.execute(
                "SELECT id FROM apartments WHERE name = ? COLLATE NOCASE;",
                (clean_name,),
            ).fetchone()
            if existing is not None:
                raise BookingConflictError(f"Apartment '{clean_name}' already exists.")

            cursor = conn.execute(
                """
                INSERT INTO apartments (name, address, max_people, price_per_night)
                VALUES (?, ?, ?, ?);
                """,
                (clean_name, clean_address, max_people_int, price_float),
            )
            apartment_id = cursor.lastrowid

            return {
                "id": apartment_id,
                "name": clean_name,
                "address": clean_address,
                "max_people": max_people_int,
                "price_per_night": price_float,
            }

    def update_apartment_price(self, name: str, new_price_per_night: float) -> dict[str, Any]:
        """Update the price per night (EUR) of an existing apartment."""
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Apartment name cannot be empty.")
        price_float = validate_price(new_price_per_night)

        with self._write_connection() as conn:
            row = conn.execute(
                """
                SELECT id, name, address, max_people, price_per_night
                FROM apartments
                WHERE name = ? COLLATE NOCASE;
                """,
                (clean_name,),
            ).fetchone()
            if row is None:
                raise RecordNotFoundError(f"Apartment '{clean_name}' does not exist.")

            old_price = float(row["price_per_night"])
            conn.execute(
                "UPDATE apartments SET price_per_night = ? WHERE id = ?;",
                (price_float, row["id"]),
            )

            return {
                "id": row["id"],
                "name": row["name"],
                "address": row["address"],
                "max_people": row["max_people"],
                "old_price_per_night": old_price,
                "price_per_night": price_float,
            }

    def remove_apartment(self, name: str) -> dict[str, Any]:
        """Remove an apartment (and its bookings) by name."""
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Apartment name cannot be empty.")

        with self._write_connection() as conn:
            row = conn.execute(
                """
                SELECT id, name, address, max_people, price_per_night
                FROM apartments
                WHERE name = ? COLLATE NOCASE;
                """,
                (clean_name,),
            ).fetchone()
            if row is None:
                raise RecordNotFoundError(f"Apartment '{clean_name}' does not exist.")

            conn.execute("DELETE FROM apartments WHERE id = ?;", (row["id"],))

            return dict(row)

    def get_apartment_by_name(self, name: str) -> dict[str, Any] | None:
        """Retrieve a single apartment by name (case-insensitive)."""
        clean_name = name.strip()
        if not clean_name:
            return None

        conn = self._get_connection()
        try:
            row = conn.execute(
                """
                SELECT id, name, address, max_people, price_per_night
                FROM apartments
                WHERE name = ? COLLATE NOCASE;
                """,
                (clean_name,),
            ).fetchone()
            return dict(row) if row is not None else None
        finally:
            self._close_if_needed(conn)

    def list_apartments(self) -> list[dict[str, Any]]:
        """Return all apartments ordered alphabetically by name."""
        conn = self._get_connection()
        try:
            rows = conn.execute(
                """
                SELECT id, name, address, max_people, price_per_night
                FROM apartments
                ORDER BY name COLLATE NOCASE ASC;
                """
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            self._close_if_needed(conn)

    # ------------------------------------------------------------------
    # Booking Management & Search
    # ------------------------------------------------------------------

    def _has_overlapping_booking(
        self,
        conn: sqlite3.Connection,
        apartment_id: int,
        start_iso: str,
        end_iso: str,
        exclude_booking_id: int | None = None,
    ) -> bool:
        """Check whether an apartment already has an overlapping booking."""
        if exclude_booking_id is None:
            row = conn.execute(
                """
                SELECT id FROM bookings
                WHERE apartment_id = ?
                  AND start_date < ?
                  AND end_date > ?
                LIMIT 1;
                """,
                (apartment_id, end_iso, start_iso),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT id FROM bookings
                WHERE apartment_id = ?
                  AND id != ?
                  AND start_date < ?
                  AND end_date > ?
                LIMIT 1;
                """,
                (apartment_id, exclude_booking_id, end_iso, start_iso),
            ).fetchone()
        return row is not None

    def create_booking(
        self,
        apartment_name: str,
        start_date_str: str,
        end_date_str: str,
        booker_name: str,
        num_people: int,
    ) -> dict[str, Any]:
        """Create a booking if the apartment exists, has enough capacity, and is free."""
        clean_apt_name = apartment_name.strip()
        clean_booker = booker_name.strip()

        if not clean_apt_name:
            raise ValueError("Apartment name cannot be empty.")
        if not clean_booker:
            raise ValueError("Booker name cannot be empty.")

        start_iso, end_iso, nights = validate_date_range(start_date_str, end_date_str)

        people_int = int(num_people)
        if people_int <= 0:
            raise ValueError("Number of people must be at least 1.")

        with self._write_connection() as conn:
            apt = conn.execute(
                """
                SELECT id, name, address, max_people, price_per_night
                FROM apartments
                WHERE name = ? COLLATE NOCASE;
                """,
                (clean_apt_name,),
            ).fetchone()
            if apt is None:
                raise RecordNotFoundError(f"Apartment '{clean_apt_name}' does not exist.")

            if people_int > apt["max_people"]:
                raise ValueError(
                    f"Apartment '{apt['name']}' is not big enough for {people_int} people "
                    f"(maximum capacity: {apt['max_people']})."
                )

            if self._has_overlapping_booking(conn, apt["id"], start_iso, end_iso):
                raise BookingConflictError(
                    f"Apartment '{apt['name']}' is not available from {start_iso} to {end_iso} "
                    "(dates overlap with an existing booking)."
                )

            total_price = calculate_total_price(nights, apt["price_per_night"])

            cursor = conn.execute(
                """
                INSERT INTO bookings (apartment_id, booker_name, start_date, end_date, num_people)
                VALUES (?, ?, ?, ?, ?);
                """,
                (apt["id"], clean_booker, start_iso, end_iso, people_int),
            )
            booking_id = cursor.lastrowid

            return {
                "id": booking_id,
                "apartment_id": apt["id"],
                "apartment_name": apt["name"],
                "apartment_address": apt["address"],
                "apartment_max_people": apt["max_people"],
                "price_per_night": float(apt["price_per_night"]),
                "booker_name": clean_booker,
                "start_date": start_iso,
                "end_date": end_iso,
                "nights": nights,
                "num_people": people_int,
                "total_price": total_price,
            }

    def get_booking(
        self, apartment_name: str, start_date_str: str, end_date_str: str
    ) -> dict[str, Any] | None:
        """Find a booking by apartment name and date range."""
        clean_apt_name = apartment_name.strip()
        start_iso, end_iso, nights = validate_date_range(start_date_str, end_date_str)

        conn = self._get_connection()
        try:
            row = conn.execute(
                """
                SELECT
                    b.id,
                    b.apartment_id,
                    b.booker_name,
                    b.start_date,
                    b.end_date,
                    b.num_people,
                    a.name AS apartment_name,
                    a.address AS apartment_address,
                    a.max_people AS apartment_max_people,
                    a.price_per_night
                FROM bookings b
                JOIN apartments a ON b.apartment_id = a.id
                WHERE a.name = ? COLLATE NOCASE
                  AND b.start_date = ?
                  AND b.end_date = ?;
                """,
                (clean_apt_name, start_iso, end_iso),
            ).fetchone()
            if row is None:
                return None
            result = dict(row)
            result["nights"] = nights
            result["total_price"] = calculate_total_price(nights, row["price_per_night"])
            return result
        finally:
            self._close_if_needed(conn)

    def change_booking(
        self,
        apartment_name: str,
        old_start_str: str,
        old_end_str: str,
        new_start_str: str,
        new_end_str: str,
        new_num_people: int,
    ) -> dict[str, Any]:
        """Update the date range and number of people for an existing booking."""
        clean_apt_name = apartment_name.strip()
        if not clean_apt_name:
            raise ValueError("Apartment name cannot be empty.")

        old_start_iso, old_end_iso, _ = validate_date_range(old_start_str, old_end_str)
        new_start_iso, new_end_iso, new_nights = validate_date_range(new_start_str, new_end_str)

        people_int = int(new_num_people)
        if people_int <= 0:
            raise ValueError("Number of people must be at least 1.")

        with self._write_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    b.id,
                    b.apartment_id,
                    b.booker_name,
                    b.start_date,
                    b.end_date,
                    b.num_people,
                    a.name AS apartment_name,
                    a.address AS apartment_address,
                    a.max_people AS apartment_max_people,
                    a.price_per_night
                FROM bookings b
                JOIN apartments a ON b.apartment_id = a.id
                WHERE a.name = ? COLLATE NOCASE
                  AND b.start_date = ?
                  AND b.end_date = ?;
                """,
                (clean_apt_name, old_start_iso, old_end_iso),
            ).fetchone()

            if row is None:
                raise RecordNotFoundError(
                    f"No booking found for apartment '{clean_apt_name}' "
                    f"from {old_start_iso} to {old_end_iso}."
                )

            if people_int > row["apartment_max_people"]:
                raise ValueError(
                    f"Apartment '{row['apartment_name']}' is not big enough for {people_int} people "
                    f"(maximum capacity: {row['apartment_max_people']})."
                )

            if self._has_overlapping_booking(
                conn,
                row["apartment_id"],
                new_start_iso,
                new_end_iso,
                exclude_booking_id=row["id"],
            ):
                raise BookingConflictError(
                    f"Apartment '{row['apartment_name']}' is not available from "
                    f"{new_start_iso} to {new_end_iso} (dates overlap with another booking)."
                )

            total_price = calculate_total_price(new_nights, row["price_per_night"])

            conn.execute(
                """
                UPDATE bookings
                SET start_date = ?, end_date = ?, num_people = ?
                WHERE id = ?;
                """,
                (new_start_iso, new_end_iso, people_int, row["id"]),
            )

            return {
                "id": row["id"],
                "apartment_id": row["apartment_id"],
                "apartment_name": row["apartment_name"],
                "apartment_address": row["apartment_address"],
                "apartment_max_people": row["apartment_max_people"],
                "price_per_night": float(row["price_per_night"]),
                "booker_name": row["booker_name"],
                "old_start_date": old_start_iso,
                "old_end_date": old_end_iso,
                "old_num_people": row["num_people"],
                "start_date": new_start_iso,
                "end_date": new_end_iso,
                "nights": new_nights,
                "num_people": people_int,
                "total_price": total_price,
            }

    def cancel_booking(
        self, apartment_name: str, start_date_str: str, end_date_str: str
    ) -> dict[str, Any]:
        """Cancel (delete) a booking by apartment name and date range."""
        clean_apt_name = apartment_name.strip()
        if not clean_apt_name:
            raise ValueError("Apartment name cannot be empty.")

        start_iso, end_iso, nights = validate_date_range(start_date_str, end_date_str)

        with self._write_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    b.id,
                    b.apartment_id,
                    b.booker_name,
                    b.start_date,
                    b.end_date,
                    b.num_people,
                    a.name AS apartment_name,
                    a.address AS apartment_address,
                    a.max_people AS apartment_max_people,
                    a.price_per_night
                FROM bookings b
                JOIN apartments a ON b.apartment_id = a.id
                WHERE a.name = ? COLLATE NOCASE
                  AND b.start_date = ?
                  AND b.end_date = ?;
                """,
                (clean_apt_name, start_iso, end_iso),
            ).fetchone()

            if row is None:
                raise RecordNotFoundError(
                    f"No booking found for apartment '{clean_apt_name}' "
                    f"from {start_iso} to {end_iso}."
                )

            conn.execute("DELETE FROM bookings WHERE id = ?;", (row["id"],))

            result = dict(row)
            result["nights"] = nights
            result["total_price"] = calculate_total_price(nights, row["price_per_night"])
            return result

    def list_bookings(self) -> list[dict[str, Any]]:
        """Return all bookings together with their booked apartment details."""
        conn = self._get_connection()
        try:
            rows = conn.execute(
                """
                SELECT
                    b.id,
                    b.apartment_id,
                    b.booker_name,
                    b.start_date,
                    b.end_date,
                    b.num_people,
                    a.name AS apartment_name,
                    a.address AS apartment_address,
                    a.max_people AS apartment_max_people,
                    a.price_per_night
                FROM bookings b
                JOIN apartments a ON b.apartment_id = a.id
                ORDER BY b.start_date ASC, a.name COLLATE NOCASE ASC;
                """
            ).fetchall()

            results: list[dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                start_dt = datetime.strptime(item["start_date"], "%Y-%m-%d").date()
                end_dt = datetime.strptime(item["end_date"], "%Y-%m-%d").date()
                nights = max((end_dt - start_dt).days, 1)
                item["nights"] = nights
                item["total_price"] = calculate_total_price(nights, item["price_per_night"])
                results.append(item)
            return results
        finally:
            self._close_if_needed(conn)

    def search_available_apartments(
        self, start_date_str: str, end_date_str: str, num_people: int
    ) -> list[dict[str, Any]]:
        """Search apartments available for a date range that fit the requested number of people."""
        start_iso, end_iso, nights = validate_date_range(start_date_str, end_date_str)
        people_int = int(num_people)
        if people_int <= 0:
            raise ValueError("Number of people must be at least 1.")

        conn = self._get_connection()
        try:
            rows = conn.execute(
                """
                SELECT a.id, a.name, a.address, a.max_people, a.price_per_night
                FROM apartments a
                WHERE a.max_people >= ?
                  AND NOT EXISTS (
                      SELECT 1
                      FROM bookings b
                      WHERE b.apartment_id = a.id
                        AND b.start_date < ?
                        AND b.end_date > ?
                  )
                ORDER BY a.price_per_night ASC, a.name COLLATE NOCASE ASC;
                """,
                (people_int, end_iso, start_iso),
            ).fetchall()

            results: list[dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                item["nights"] = nights
                item["total_price"] = calculate_total_price(nights, item["price_per_night"])
                item["start_date"] = start_iso
                item["end_date"] = end_iso
                results.append(item)
            return results
        finally:
            self._close_if_needed(conn)

