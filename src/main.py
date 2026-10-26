"""Entry point for running the Apartment Booking System via `python src/main.py`."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

# Ensure the project root is on sys.path when running `python src/main.py` directly.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cli import ApartmentBookingCLI, database_error_message


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

