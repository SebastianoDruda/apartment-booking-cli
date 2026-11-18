"""Publish every row again, for example to rebuild the read model from scratch.

    python -m dimora.tools.republish                    # refresh every consumer
    python -m dimora.tools.republish --drop-read-model  # rebuild MongoDB views from zero

Setting ``published_version`` back to 0 makes each row pending again, so the
running services publish its current state on their next pass. Consumers apply
each version once: the reservation service ignores apartment versions it already
holds, and the projector rewrites any view that is missing or out of date.
"""

from __future__ import annotations

import argparse

from dimora.common import config
from dimora.common.postgres import connect
from dimora.projector.mongo import connect as connect_read_model
from dimora.projector.mongo import ensure_indexes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--drop-read-model", action="store_true",
                        help="delete the MongoDB views before publishing again")
    args = parser.parse_args(argv)
    config.configure_logging("republish")

    if args.drop_read_model:
        read_model = connect_read_model(config.mongo_url(), config.mongo_database())
        read_model.client.drop_database(read_model.name)
        ensure_indexes(read_model)
        print(f"Dropped read model database {read_model.name}.")

    for service, table in (("apartment", "apartments"), ("reservation", "bookings")):
        with connect(config.postgres_dsn(service)) as connection:
            count = connection.execute(f"UPDATE {table} SET published_version = 0").rowcount
        print(f"Marked {count} {table} row(s) for publishing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
