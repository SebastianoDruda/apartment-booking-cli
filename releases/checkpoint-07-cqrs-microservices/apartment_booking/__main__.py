"""Run the Apartment Booking CLI with ``python -m apartment_booking``."""

from __future__ import annotations

import sqlite3
import sys

from apartment_booking.cli import ApartmentBookingCLI, database_error_message, is_storage_error


def main() -> None:
    """Start the Apartment Booking CLI."""
    try:
        cli = ApartmentBookingCLI()
    except sqlite3.DatabaseError as err:
        if not is_storage_error(err):
            raise
        print(database_error_message(err), file=sys.stderr)
        raise SystemExit(1) from None
    try:
        cli.run()
    finally:
        cli.db.close()


if __name__ == "__main__":
    main()

