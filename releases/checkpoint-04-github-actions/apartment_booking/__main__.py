"""Run the Apartment Booking CLI with ``python -m apartment_booking``."""

from __future__ import annotations

import sqlite3
import sys

from apartment_booking.cli import ApartmentBookingCLI, database_error_message


def main() -> None:
    """Start the Apartment Booking CLI."""
    try:
        cli = ApartmentBookingCLI()
    except (sqlite3.OperationalError, sqlite3.IntegrityError) as err:
        print(database_error_message(err), file=sys.stderr)
        raise SystemExit(1) from None
    try:
        cli.run()
    finally:
        cli.db.close()


if __name__ == "__main__":
    main()

