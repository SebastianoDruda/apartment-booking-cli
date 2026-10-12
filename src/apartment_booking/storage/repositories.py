import sqlite3
from dataclasses import asdict

from apartment_booking.errors import NotFoundError
from apartment_booking.models import Apartment, Booking, BookingStatus


def apartment_from_row(row: sqlite3.Row) -> Apartment:
    return Apartment(**{**dict(row), "is_active": bool(row["is_active"])})


def booking_from_row(row: sqlite3.Row) -> Booking:
    return Booking(**{**dict(row), "status": BookingStatus(row["status"])})


class Repository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def apartments(self, view: str = "active") -> list[Apartment]:
        rows = self.connection.execute(
            """SELECT * FROM apartments
               WHERE ? = 'all' OR is_active = ? ORDER BY name COLLATE NOCASE, id""",
            (view, view == "active"),
        )
        return [apartment_from_row(row) for row in rows]

    def apartment(self, apartment_id: str) -> Apartment:
        row = self.connection.execute(
            "SELECT * FROM apartments WHERE id = ?", (apartment_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(
                "Apartment not found. Return to the list and try again."
            )
        return apartment_from_row(row)

    def insert_apartment(self, apartment: Apartment) -> None:
        self.connection.execute(
            """INSERT INTO apartments VALUES
               (:id, :name, :city, :capacity, :nightly_price_cents,
                :is_active, :created_at)""",
            asdict(apartment),
        )

    def update_apartment(self, apartment: Apartment) -> None:
        self.connection.execute(
            """UPDATE apartments SET name=:name, city=:city, capacity=:capacity,
               nightly_price_cents=:nightly_price_cents, is_active=:is_active
               WHERE id=:id""",
            asdict(apartment),
        )

    def bookings(self, confirmed_only: bool = False) -> list[Booking]:
        rows = self.connection.execute(
            """SELECT b.* FROM bookings b JOIN apartments a ON a.id = b.apartment_id
               WHERE ? = 0 OR b.status = 'CONFIRMED'
               ORDER BY b.check_in, a.name COLLATE NOCASE, b.id""",
            (confirmed_only,),
        )
        return [booking_from_row(row) for row in rows]

    def booking(self, booking_id: str) -> Booking:
        row = self.connection.execute(
            "SELECT * FROM bookings WHERE id = ?", (booking_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError("Booking not found. Return to the list and try again.")
        return booking_from_row(row)

    def conflicts(
        self, apartment_id: str, check_in: str, check_out: str, exclude_id: str = ""
    ) -> list[Booking]:
        # Authoritative half-open rule, also used by search and demo validation.
        rows = self.connection.execute(
            """SELECT * FROM bookings WHERE apartment_id = ? AND status = 'CONFIRMED'
               AND check_in < ? AND ? < check_out AND id != ? ORDER BY check_in""",
            (apartment_id, check_out, check_in, exclude_id),
        )
        return [booking_from_row(row) for row in rows]

    def current_bookings(self, apartment_id: str, today: str) -> list[Booking]:
        rows = self.connection.execute(
            """SELECT * FROM bookings WHERE apartment_id = ? AND status = 'CONFIRMED'
               AND check_out > ? ORDER BY check_in""",
            (apartment_id, today),
        )
        return [booking_from_row(row) for row in rows]

    def insert_booking(self, booking: Booking) -> None:
        self.connection.execute(
            """INSERT INTO bookings VALUES
               (:id, :apartment_id, :guest_name, :guest_count,
               :check_in, :check_out, :status, :created_at, :updated_at)""",
            asdict(booking),
        )

    def update_booking(self, booking: Booking) -> None:
        self.connection.execute(
            """UPDATE bookings SET guest_name=:guest_name, guest_count=:guest_count,
               check_in=:check_in, check_out=:check_out, status=:status,
               updated_at=:updated_at WHERE id=:id""",
            asdict(booking),
        )

    def counts(self) -> tuple[int, int]:
        row = self.connection.execute(
            "SELECT (SELECT count(*) FROM apartments), (SELECT count(*) FROM bookings)"
        ).fetchone()
        return row[0], row[1]

    def clear(self) -> None:
        self.connection.execute("DELETE FROM bookings")
        self.connection.execute("DELETE FROM apartments")
