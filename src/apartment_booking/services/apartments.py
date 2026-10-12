from collections.abc import Callable
from dataclasses import replace
from datetime import date
from uuid import uuid4

from apartment_booking import validation
from apartment_booking.errors import OperationNotAllowedError, ValidationError
from apartment_booking.models import Apartment
from apartment_booking.storage.database import Database, transaction
from apartment_booking.storage.repositories import Repository


def validate_fields(
    name: str, city: str, capacity: int, nightly_price_cents: int
) -> tuple[str, str, int, int]:
    return (
        validation.text(name, "Name"),
        validation.text(city, "City"),
        validation.integer(capacity, "Capacity"),
        validation.cents(nightly_price_cents),
    )


class ApartmentService:
    def __init__(
        self, database: Database, today: Callable[[], date] = date.today
    ) -> None:
        self.database = database
        self.today = today

    def list(self, view: str = "active") -> list[Apartment]:
        if view not in ("active", "all", "archived"):
            raise ValidationError("Choose active, all or archived apartments.")
        with self.database.connection() as connection:
            return Repository(connection).apartments(view)

    def add(
        self, name: str, city: str, capacity: int, nightly_price_cents: int
    ) -> Apartment:
        fields = validate_fields(name, city, capacity, nightly_price_cents)
        apartment = Apartment(str(uuid4()), *fields, True, validation.timestamp())
        with self.database.connection() as connection, transaction(connection):
            Repository(connection).insert_apartment(apartment)
        return apartment

    def update(
        self,
        apartment_id: str,
        name: str,
        city: str,
        capacity: int,
        nightly_price_cents: int,
    ) -> Apartment:
        name, city, capacity, nightly_price_cents = validate_fields(
            name, city, capacity, nightly_price_cents
        )
        with self.database.connection() as connection, transaction(connection):
            repo = Repository(connection)
            original = repo.apartment(apartment_id)
            self.require_active(original)
            if any(
                b.guest_count > capacity
                for b in repo.current_bookings(apartment_id, self.today().isoformat())
            ):
                raise OperationNotAllowedError(
                    "Capacity would invalidate a confirmed ongoing or future booking."
                )
            updated = replace(
                original,
                name=name,
                city=city,
                capacity=capacity,
                nightly_price_cents=nightly_price_cents,
            )
            repo.update_apartment(updated)
            return updated

    def archive(self, apartment_id: str) -> Apartment:
        with self.database.connection() as connection, transaction(connection):
            repo = Repository(connection)
            original = repo.apartment(apartment_id)
            self.require_active(original)
            blocking = repo.current_bookings(apartment_id, self.today().isoformat())
            if blocking:
                details = "; ".join(
                    f"{b.guest_name}: {b.check_in} to {b.check_out}" for b in blocking
                )
                raise OperationNotAllowedError(
                    f"Cannot archive: confirmed bookings prevent it: {details}."
                )
            updated = replace(original, is_active=False)
            repo.update_apartment(updated)
            return updated

    @staticmethod
    def require_active(apartment: Apartment) -> None:
        if not apartment.is_active:
            raise OperationNotAllowedError(
                "Apartment is archived and cannot be used for this action."
            )
