"""Publish every apartment again, for example to rebuild the reservation copy.

    python -m dimora.tools.republish                 # publish every apartment again
    python -m dimora.tools.republish --rebuild-copy  # rebuild the copy from zero

Resetting ``published_version`` to 0 makes the apartment service publish each
row's current state on its next pass. The reservation service ignores versions
it already holds and fills in whatever is missing. With ``--rebuild-copy`` its
copy is emptied first, so it is rebuilt from the events alone; until they
arrive, bookings and availability leave out the apartments not yet copied.
"""

from __future__ import annotations

import argparse

from dimora.common import config
from dimora.common.postgres import connect


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rebuild-copy", action="store_true",
                        help="empty the reservation service's apartment copy before publishing")
    args = parser.parse_args(argv)
    config.configure_logging("republish")

    if args.rebuild_copy:
        with connect(config.postgres_dsn("reservation")) as connection:
            count = connection.execute("DELETE FROM apartment_copies").rowcount
        print(f"Emptied the apartment copy ({count} row(s)).")

    with connect(config.postgres_dsn("apartment")) as connection:
        count = connection.execute("UPDATE apartments SET published_version = 0").rowcount
    print(f"Marked {count} apartments row(s) for publishing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
