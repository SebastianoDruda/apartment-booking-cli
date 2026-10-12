from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

from apartment_booking.models import Apartment, Booking


def money(cents: int) -> str:
    return f"EUR {cents // 100}.{cents % 100:02d}"


class Display:
    def __init__(self, console: Console) -> None:
        self.console = console

    def message(self, message: str) -> None:
        self.console.print(message, markup=False, highlight=False)

    def menu(self, title: str, options: list[str], back: str = "Back") -> None:
        self.console.rule(title, style="bold")
        for number, option in enumerate(options, 1):
            self.message(f"  {number}. {option}")
        self.message(f"  0. {back}")

    def apartments(self, apartments: list[Apartment]) -> None:
        if not apartments:
            self.message(
                "No apartments in this view. Add an apartment "
                "or load sample data in Demo & data."
            )
            return
        table = Table(
            "#",
            "Apartment / city",
            "Guests",
            "Nightly price",
            "Status",
            box=box.SIMPLE,
            padding=(0, 1),
        )
        for number, apartment in enumerate(apartments, 1):
            table.add_row(
                str(number),
                Text(f"{apartment.name}\n{apartment.city}"),
                str(apartment.capacity),
                money(apartment.nightly_price_cents),
                "active" if apartment.is_active else "archived",
            )
        self.console.print(table)

    def bookings(
        self, bookings: list[Booking], apartments: dict[str, Apartment]
    ) -> None:
        if not bookings:
            self.message(
                "No bookings in this view. Create a booking "
                "or load sample data in Demo & data."
            )
            return
        table = Table(
            "#",
            "Apartment / guest",
            "Guests",
            "Check-in / out",
            "Status",
            box=box.SIMPLE,
            padding=(0, 1),
        )
        for number, booking in enumerate(bookings, 1):
            table.add_row(
                str(number),
                Text(f"{apartments[booking.apartment_id].name}\n{booking.guest_name}"),
                str(booking.guest_count),
                f"{booking.check_in}\n{booking.check_out}",
                booking.status.lower(),
            )
        self.console.print(table)

    def booking_summary(
        self,
        apartment: Apartment,
        guest: str,
        guests: int,
        check_in: str,
        check_out: str,
    ) -> None:
        self.message(
            f"Apartment: {apartment.name} ({apartment.city})\n"
            f"Guest: {guest}\nGuests: {guests}\nDates: {check_in} to {check_out}"
        )
