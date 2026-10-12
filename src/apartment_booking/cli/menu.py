from collections.abc import Callable

from rich.console import Console

from apartment_booking import validation
from apartment_booking.cli.display import Display, money
from apartment_booking.cli.prompts import CancelAction, Prompts
from apartment_booking.errors import BookingError, ValidationError
from apartment_booking.models import Apartment, Booking
from apartment_booking.services.apartments import ApartmentService
from apartment_booking.services.bookings import BookingService
from apartment_booking.services.demo import DemoService


def whole_number(value: str, label: str, maximum: int = 20) -> int:
    if not value.isascii() or not value.isdigit():
        raise ValidationError(f"{label} must be a whole number from 1 to {maximum}.")
    return validation.integer(int(value), label, maximum)


class Menu:
    def __init__(
        self,
        console: Console,
        apartments: ApartmentService,
        bookings: BookingService,
        demo: DemoService,
    ) -> None:
        self.display = Display(console)
        self.prompts = Prompts(console)
        self.apartments = apartments
        self.bookings = bookings
        self.demo = demo

    def run(self) -> None:
        self.display.message(
            "APARTMENT BOOKING\nLocal apartment and reservation management"
        )
        self.loop(
            "MAIN MENU",
            [
                ("Apartments", self.apartment_menu),
                ("Bookings", self.booking_menu),
                ("Search availability", self.search),
                ("Demo & data", self.demo_menu),
            ],
            back="Exit",
        )

    def loop(
        self,
        title: str,
        actions: list[tuple[str, Callable[[], None]]],
        back: str = "Back",
    ) -> None:
        while True:
            self.display.menu(title, [name for name, _ in actions], back)
            choice = self.prompts.choice("Select an option: ", len(actions))
            if choice == 0:
                return
            while True:
                try:
                    actions[choice - 1][1]()
                    break
                except CancelAction:
                    self.display.message("Action cancelled. No changes were saved.")
                    break
                except BookingError as exc:
                    self.display.message(f"ERROR: {exc}\nNo changes were saved.")
                    if self.prompts.choice("0. Back   1. Try again: ", 1) == 0:
                        break

    def apartment_menu(self) -> None:
        self.loop(
            "APARTMENTS",
            [
                ("View apartments", self.view_apartments),
                ("Add apartment", self.add_apartment),
                ("Update apartment", self.update_apartment),
                ("Remove apartment (archive)", self.archive_apartment),
            ],
        )

    def booking_menu(self) -> None:
        self.loop(
            "BOOKINGS",
            [
                ("View bookings", self.view_bookings),
                ("Create booking", self.create_booking),
                ("Change booking", self.change_booking),
                ("Cancel booking", self.cancel_booking),
            ],
        )

    def demo_menu(self) -> None:
        self.loop(
            "DEMO & DATA",
            [
                ("Load sample data (empty database only)", self.load_demo),
                ("Reset database to sample data", self.reset_demo),
                ("View storage information", self.storage_info),
            ],
        )

    def view_apartments(self) -> None:
        self.display.apartments(self.apartments.list())
        while True:
            choice = self.prompts.choice(
                "0. Back   1. Active   2. All   3. Archived: ", 3
            )
            if choice == 0:
                return
            self.display.apartments(
                self.apartments.list({1: "active", 2: "all", 3: "archived"}[choice])
            )

    def choose_apartment(self) -> Apartment:
        apartments = self.apartments.list()
        self.display.apartments(apartments)
        if not apartments:
            raise CancelAction
        number = self.prompts.choice("Select apartment (0. Back): ", len(apartments))
        if not number:
            raise CancelAction
        return apartments[number - 1]

    def apartment_fields(
        self, original: Apartment | None = None
    ) -> tuple[str, str, int, int]:
        p = self.prompts
        name = p.field(
            "Name",
            lambda v: validation.text(v, "Name"),
            original.name if original else None,
        )
        city = p.field(
            "City",
            lambda v: validation.text(v, "City"),
            original.city if original else None,
        )
        capacity = p.field(
            "Capacity (1–20)",
            lambda v: whole_number(v, "Capacity"),
            str(original.capacity) if original else None,
        )
        price = p.field(
            "Nightly price in EUR (e.g. 125.50)",
            validation.price,
            money(original.nightly_price_cents).removeprefix("EUR ")
            if original
            else None,
        )
        self.display.message(
            f"Apartment: {name}\nCity: {city}\nCapacity: {capacity}\n"
            f"Nightly price: {money(price)}"
        )
        return name, city, capacity, price

    def save(self, action: Callable[[], object], success: str) -> None:
        if self.prompts.confirm():
            action()
            self.display.message(f"SUCCESS: {success}")
        else:
            self.display.message("Action cancelled. No changes were saved.")

    def add_apartment(self) -> None:
        fields = self.apartment_fields()
        self.save(lambda: self.apartments.add(*fields), "Apartment added.")

    def update_apartment(self) -> None:
        apartment = self.choose_apartment()
        fields = self.apartment_fields(apartment)
        self.save(
            lambda: self.apartments.update(apartment.id, *fields), "Apartment updated."
        )

    def archive_apartment(self) -> None:
        apartment = self.choose_apartment()
        self.display.message(
            f"Archive {apartment.name} ({apartment.city})? "
            "Booking history will be preserved."
        )
        self.save(lambda: self.apartments.archive(apartment.id), "Apartment archived.")

    def apartment_map(self) -> dict[str, Apartment]:
        return {a.id: a for a in self.apartments.list("all")}

    def view_bookings(self) -> None:
        self.display.bookings(self.bookings.list(), self.apartment_map())

    def choose_booking(self) -> Booking:
        bookings = self.bookings.list(confirmed_only=True)
        self.display.bookings(bookings, self.apartment_map())
        if not bookings:
            raise CancelAction
        number = self.prompts.choice(
            "Select confirmed booking (0. Back): ", len(bookings)
        )
        if not number:
            raise CancelAction
        return bookings[number - 1]

    def dates(self, original: Booking | None = None) -> tuple[str, str]:
        start = self.prompts.field(
            "Check-in YYYY-MM-DD",
            validation.iso_date,
            original.check_in if original else None,
        )

        def end_date(value: str) -> str:
            return validation.period(start, value)[1]

        end = self.prompts.field(
            "Check-out YYYY-MM-DD", end_date, original.check_out if original else None
        )
        return start, end

    def booking_fields(
        self, apartment: Apartment, original: Booking | None = None
    ) -> tuple[str, int, str, str]:
        guest = self.prompts.field(
            "Guest name",
            lambda v: validation.text(v, "Guest name"),
            original.guest_name if original else None,
        )
        count = self.prompts.field(
            f"Guests (1–{apartment.capacity})",
            lambda v: whole_number(v, "Guests", apartment.capacity),
            str(original.guest_count) if original else None,
        )
        start, end = self.dates(original)
        self.bookings.check_availability(
            apartment.id, start, end, original.id if original else ""
        )
        self.display.booking_summary(apartment, guest, count, start, end)
        return guest, count, start, end

    def create_booking(self) -> None:
        apartment = self.choose_apartment()
        fields = self.booking_fields(apartment)
        self.save(
            lambda: self.bookings.create(apartment.id, *fields), "Booking created."
        )

    def change_booking(self) -> None:
        booking = self.choose_booking()
        apartment = self.apartment_map()[booking.apartment_id]
        fields = self.booking_fields(apartment, booking)
        self.save(lambda: self.bookings.change(booking.id, *fields), "Booking changed.")

    def cancel_booking(self) -> None:
        booking = self.choose_booking()
        self.display.booking_summary(
            self.apartment_map()[booking.apartment_id],
            booking.guest_name,
            booking.guest_count,
            booking.check_in,
            booking.check_out,
        )
        self.save(
            lambda: self.bookings.cancel(booking.id),
            "Booking cancelled; its dates are now released.",
        )

    def search(self) -> None:
        start, end = self.dates()
        guests = self.prompts.field(
            "Guests (blank defaults to 1)", lambda v: whole_number(v or "1", "Guests")
        )
        available = self.bookings.available(start, end, guests)
        self.display.message(
            f"AVAILABLE: {len(available)} apartment(s) "
            f"for {guests} guest(s), {start} to {end}."
        )
        if available:
            self.display.apartments(available)
        else:
            self.display.message(
                "UNAVAILABLE: No apartments match. "
                "Try other dates or fewer guests, or add an apartment."
            )

    def load_demo(self) -> None:
        apartments, bookings = self.demo.load()
        self.display.message(
            f"SUCCESS: Sample data loaded: "
            f"{apartments} apartments, {bookings} bookings."
        )

    def reset_demo(self) -> None:
        self.display.message(
            "WARNING: All existing apartments and bookings "
            "will be replaced with sample data."
        )
        confirmation = self.prompts.read(
            "Type RESET exactly to replace all data; anything else cancels: ",
            strip=False,
        )
        if confirmation != "RESET":
            self.display.message("Reset cancelled. No changes were saved.")
            return
        apartments, bookings = self.demo.load(reset=True, confirmation=confirmation)
        self.display.message(
            f"SUCCESS: Database reset: {apartments} apartments, {bookings} bookings."
        )

    def storage_info(self) -> None:
        apartments, bookings = self.demo.counts()
        self.display.message(
            f"Database: {self.demo.database.path}\n"
            f"Apartments: {apartments}\nBookings: {bookings}\n"
            f"Demo fixture: {self.demo.fixture}\n"
            f"Fixture available: {'yes' if self.demo.fixture.is_file() else 'no'}"
        )
