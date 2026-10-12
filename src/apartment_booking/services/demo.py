import json
from pathlib import Path

from apartment_booking import validation
from apartment_booking.errors import (
    BookingError,
    OperationNotAllowedError,
    ValidationError,
)
from apartment_booking.models import Apartment, Booking, BookingStatus
from apartment_booking.services.apartments import validate_fields as apartment_fields
from apartment_booking.services.bookings import require_available
from apartment_booking.services.bookings import validate_fields as booking_fields
from apartment_booking.storage.database import (
    Database,
    connect,
    initialize,
    transaction,
)
from apartment_booking.storage.repositories import Repository


class DemoService:
    def __init__(self, database: Database, fixture: Path) -> None:
        self.database = database
        self.fixture = fixture.resolve()

    def validate(self) -> tuple[list[Apartment], list[Booking]]:
        """Validate in disposable memory using the same schema and overlap query.

        No live database rows are touched until the entire document is valid.
        """
        try:
            raw = json.loads(self.fixture.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValidationError(
                f"Cannot read demo fixture {self.fixture}: {exc}"
            ) from exc
        try:
            if (
                not isinstance(raw, dict)
                or type(raw.get("schema_version")) is not int
                or raw["schema_version"] != 1
            ):
                raise ValidationError("Demo fixture must have schema_version 1.")
            if not isinstance(raw["apartments"], list) or not isinstance(
                raw["bookings"], list
            ):
                raise ValidationError("Demo apartments and bookings must be lists.")
            apartments, bookings = [], []
            now = validation.timestamp()
            with connect(":memory:") as connection:
                initialize(connection)
                repo = Repository(connection)
                with transaction(connection):
                    for item in raw["apartments"]:
                        active = item.get("is_active", True)
                        if type(active) is not bool:
                            raise ValidationError(
                                "Fixture is_active must be a boolean."
                            )
                        apartment = Apartment(
                            validation.uuid_string(item["id"]),
                            *apartment_fields(
                                item["name"],
                                item["city"],
                                item["capacity"],
                                item["nightly_price_cents"],
                            ),
                            active,
                            now,
                        )
                        repo.insert_apartment(apartment)
                        apartments.append(apartment)
                    for item in raw["bookings"]:
                        apartment = repo.apartment(
                            validation.uuid_string(item["apartment_id"])
                        )
                        booking = Booking(
                            validation.uuid_string(item["id"]),
                            apartment.id,
                            *booking_fields(
                                item["guest_name"],
                                item["guest_count"],
                                item["check_in"],
                                item["check_out"],
                                apartment.capacity,
                            ),
                            BookingStatus(item["status"]),
                            now,
                            now,
                        )
                        if booking.status == BookingStatus.CONFIRMED:
                            require_available(
                                repo, apartment, booking.check_in, booking.check_out
                            )
                        repo.insert_booking(booking)
                        bookings.append(booking)
            return apartments, bookings
        except (KeyError, TypeError, ValueError, AttributeError, BookingError) as exc:
            raise ValidationError(f"Invalid demo fixture: {exc}") from exc

    def load(self, *, reset: bool = False, confirmation: str = "") -> tuple[int, int]:
        if reset and confirmation != "RESET":
            raise OperationNotAllowedError(
                "Reset cancelled: exact confirmation RESET is required."
            )
        apartments, bookings = self.validate()
        with self.database.connection() as connection, transaction(connection):
            repo = Repository(connection)
            if not reset and repo.counts() != (0, 0):
                raise OperationNotAllowedError(
                    "Sample data can only be loaded into an empty database. "
                    "No changes were saved."
                )
            if reset:
                repo.clear()
            for apartment in apartments:
                repo.insert_apartment(apartment)
            for booking in bookings:
                repo.insert_booking(booking)
        return len(apartments), len(bookings)

    def counts(self) -> tuple[int, int]:
        with self.database.connection() as connection:
            return Repository(connection).counts()
