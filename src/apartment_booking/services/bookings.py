from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

from apartment_booking import validation
from apartment_booking.errors import BookingConflictError, OperationNotAllowedError
from apartment_booking.models import Apartment, Booking, BookingStatus
from apartment_booking.services.apartments import ApartmentService
from apartment_booking.storage.database import Database, transaction
from apartment_booking.storage.repositories import Repository


def validate_fields(
    guest_name: str, guest_count: int, check_in: str, check_out: str, capacity: int
) -> tuple[str, int, str, str]:
    return (
        validation.text(guest_name, "Guest name"),
        validation.integer(guest_count, "Guests (within apartment capacity)", capacity),
        *validation.period(check_in, check_out),
    )


def require_available(
    repo: Repository,
    apartment: Apartment,
    check_in: str,
    check_out: str,
    exclude_id: str = "",
) -> None:
    if repo.conflicts(apartment.id, check_in, check_out, exclude_id):
        raise BookingConflictError(
            f"BOOKING UNAVAILABLE — {apartment.name}, {check_in} to {check_out}: "
            "a confirmed booking overlaps the requested period."
        )


class BookingService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def list(self, confirmed_only: bool = False) -> list[Booking]:
        with self.database.connection() as connection:
            return Repository(connection).bookings(confirmed_only)

    def check_availability(
        self, apartment_id: str, check_in: str, check_out: str, exclude_id: str = ""
    ) -> None:
        """Check before confirmation; write operations must still recheck atomically."""
        validation.period(check_in, check_out)
        with self.database.connection() as connection:
            connection.execute("BEGIN")
            repo = Repository(connection)
            apartment = repo.apartment(apartment_id)
            ApartmentService.require_active(apartment)
            require_available(repo, apartment, check_in, check_out, exclude_id)

    def create(
        self,
        apartment_id: str,
        guest_name: str,
        guest_count: int,
        check_in: str,
        check_out: str,
    ) -> Booking:
        with self.database.connection() as connection, transaction(connection):
            repo = Repository(connection)
            apartment = repo.apartment(apartment_id)
            ApartmentService.require_active(apartment)
            fields = validate_fields(
                guest_name, guest_count, check_in, check_out, apartment.capacity
            )
            require_available(repo, apartment, check_in, check_out)
            now = validation.timestamp()
            booking = Booking(
                str(uuid4()), apartment_id, *fields, BookingStatus.CONFIRMED, now, now
            )
            repo.insert_booking(booking)
            return booking

    def change(
        self,
        booking_id: str,
        guest_name: str,
        guest_count: int,
        check_in: str,
        check_out: str,
    ) -> Booking:
        with self.database.connection() as connection, transaction(connection):
            repo = Repository(connection)
            original = repo.booking(booking_id)
            self.require_confirmed(original)
            apartment = repo.apartment(original.apartment_id)
            ApartmentService.require_active(apartment)
            guest_name, guest_count, check_in, check_out = validate_fields(
                guest_name, guest_count, check_in, check_out, apartment.capacity
            )
            require_available(repo, apartment, check_in, check_out, original.id)
            updated = replace(
                original,
                guest_name=guest_name,
                guest_count=guest_count,
                check_in=check_in,
                check_out=check_out,
                updated_at=validation.timestamp(),
            )
            repo.update_booking(updated)
            return updated

    def cancel(self, booking_id: str) -> Booking:
        with self.database.connection() as connection, transaction(connection):
            repo = Repository(connection)
            original = repo.booking(booking_id)
            self.require_confirmed(original)
            updated = replace(
                original,
                status=BookingStatus.CANCELLED,
                updated_at=validation.timestamp(),
            )
            repo.update_booking(updated)
            return updated

    def available(
        self, check_in: str, check_out: str, guests: int = 1
    ) -> list[Apartment]:
        validation.period(check_in, check_out)
        validation.integer(guests, "Guests")
        with self.database.connection() as connection:
            # A read transaction gives the whole search a consistent snapshot.
            connection.execute("BEGIN")
            repo = Repository(connection)
            return [
                a
                for a in repo.apartments()
                if a.capacity >= guests
                and not repo.conflicts(a.id, check_in, check_out)
            ]

    @staticmethod
    def require_confirmed(booking: Booking) -> None:
        if booking.status != BookingStatus.CONFIRMED:
            raise OperationNotAllowedError(
                "Booking is already cancelled; no changes were saved."
            )
