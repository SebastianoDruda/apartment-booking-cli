import traceback
from pathlib import Path

from rich.console import Console

from apartment_booking.cli.menu import Menu
from apartment_booking.errors import BookingError
from apartment_booking.services.apartments import ApartmentService
from apartment_booking.services.bookings import BookingService
from apartment_booking.services.demo import DemoService
from apartment_booking.storage.database import Database, database_path


def main() -> int:
    console = Console(highlight=False)
    try:
        database = Database(database_path())
        database.initialize()
        Menu(
            console,
            ApartmentService(database),
            BookingService(database),
            DemoService(database, Path("data/demo.json")),
        ).run()
    except (EOFError, KeyboardInterrupt):
        console.print("\nInput ended. Goodbye.")
    except BookingError as exc:
        Console(stderr=True).print(f"ERROR: {exc}", markup=False, highlight=False)
        return 1
    except Exception:
        Console(stderr=True).print(
            "ERROR: Unexpected application failure. Diagnostic follows."
        )
        traceback.print_exc()
        return 1
    else:
        console.print("Goodbye.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
