"""Import the original edition's SQLite database into a fresh event-driven stack.

    python -m dimora.tools.import_sqlite /import/apartment_booking.db

Apartments go to the apartment service's database and bookings to the
reservation service's database, keeping their ids. Every imported apartment
starts with ``published_version = 0``, so the apartment service publishes all of
them on its next pass and the reservation service fills its apartment copy
without any extra step. Imported bookings appear as soon as their apartment has
reached that copy.

Each booking stores the nightly price its apartment has at import time, which is
the price the original edition displayed for it.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from dimora.apartment.store import ApartmentStore
from dimora.common import config, events
from dimora.common.postgres import connect, wait_until_ready
from dimora.reservation.store import ReservationStore


def read_source(path: Path) -> tuple[list[sqlite3.Row], list[sqlite3.Row]]:
    if not path.is_file():
        raise SystemExit(f"{path} does not exist.")
    source = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    try:
        apartments = source.execute(
            "SELECT id, name, address, max_people, price_per_night FROM apartments ORDER BY id"
        ).fetchall()
        bookings = source.execute(
            """
            SELECT b.id, b.apartment_id, b.booker_name, b.start_date, b.end_date, b.num_people,
                   a.price_per_night
            FROM bookings b JOIN apartments a ON a.id = b.apartment_id
            ORDER BY b.id
            """
        ).fetchall()
    except sqlite3.DatabaseError as error:
        raise SystemExit(f"{path} is not an Apartment Booking database: {error}") from None
    finally:
        source.close()
    return apartments, bookings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("database", type=Path, help="SQLite file of the original edition")
    args = parser.parse_args(argv)
    log = config.configure_logging("import")

    apartments, bookings = read_source(args.database)
    apartment_dsn = config.postgres_dsn("apartment")
    reservation_dsn = config.postgres_dsn("reservation")
    for dsn in (apartment_dsn, reservation_dsn):
        wait_until_ready(dsn, log)
    ApartmentStore(apartment_dsn).ensure_schema()
    ReservationStore(reservation_dsn).ensure_schema()

    with connect(apartment_dsn) as apartment_db, connect(reservation_dsn) as reservation_db:
        existing = (apartment_db.execute("SELECT count(*) AS n FROM apartments").fetchone()["n"]
                    + reservation_db.execute("SELECT count(*) AS n FROM bookings").fetchone()["n"])
        if existing:
            print("The target databases already contain data; import only into a fresh stack.",
                  file=sys.stderr)
            return 1

        for row in apartments:
            apartment_db.execute(
                """
                INSERT INTO apartments (id, name, address, max_people, price_per_night, last_event)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (row["id"], row["name"], row["address"], row["max_people"], row["price_per_night"],
                 events.APARTMENT_ADDED),
            )
        for row in bookings:
            reservation_db.execute(
                """
                INSERT INTO bookings (id, apartment_id, booker_name, start_date, end_date,
                                      num_people, price_per_night, last_event)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (row["id"], row["apartment_id"], row["booker_name"], row["start_date"],
                 row["end_date"], row["num_people"], row["price_per_night"], events.BOOKING_CREATED),
            )
        # Keep generated ids above the imported ones.
        apartment_db.execute(
            "SELECT setval(pg_get_serial_sequence('apartments', 'id'),"
            " GREATEST((SELECT max(id) FROM apartments), 1))"
        )
        reservation_db.execute(
            "SELECT setval(pg_get_serial_sequence('bookings', 'id'),"
            " GREATEST((SELECT max(id) FROM bookings), 1))"
        )

    print(f"Imported {len(apartments)} apartment(s) and {len(bookings)} booking(s); "
          "the apartment service publishes the apartments on its next pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
