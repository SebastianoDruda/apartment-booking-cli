"""Start the apartment service: ``python -m dimora.apartment``."""

from __future__ import annotations

from dimora.apartment.app import create_app
from dimora.apartment.store import SOURCE, ApartmentStore
from dimora.common import config
from dimora.common.http import serve
from dimora.common.messaging import Publisher
from dimora.common.outbox import OutboxRelay
from dimora.common.postgres import wait_until_ready


def main() -> None:
    log = config.configure_logging("apartment-service")
    dsn = config.postgres_dsn("apartment")
    wait_until_ready(dsn, log)
    store = ApartmentStore(dsn)
    store.ensure_schema()

    relay = OutboxRelay(store, Publisher(config.rabbitmq_url(), SOURCE), log)
    relay.start()
    log.info("Apartment service listening on port %s", config.http_port())
    serve(create_app(store, on_write=relay.wake), config.http_port())


if __name__ == "__main__":
    main()
