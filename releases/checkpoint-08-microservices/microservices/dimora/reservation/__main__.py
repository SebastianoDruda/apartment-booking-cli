"""Start the reservation service: ``python -m dimora.reservation``.

One process runs two things: the HTTP interface, and the consumer that keeps
the apartment copy up to date from apartment events.
"""

from __future__ import annotations

import threading

from dimora.common import config
from dimora.common.events import Event
from dimora.common.http import serve
from dimora.common.messaging import consume_forever
from dimora.common.postgres import wait_until_ready
from dimora.reservation.app import create_app
from dimora.reservation.store import ReservationStore

QUEUE = "reservation.apartment-events"


def main() -> None:
    log = config.configure_logging("reservation-service")
    dsn = config.postgres_dsn("reservation")
    wait_until_ready(dsn, log)
    store = ReservationStore(dsn, copy_grace=config.float_setting("DIMORA_COPY_GRACE", 5.0))
    store.ensure_schema()

    def handle(event: Event) -> None:
        cancelled = store.apply_apartment_event(event)
        log.info("Applied %s", event.event_id)
        if cancelled:
            log.info("Cancelled %s booking(s) of removed apartment %s", cancelled, event.entity_id)

    stop = threading.Event()
    threading.Thread(
        target=consume_forever, name="apartment-events",
        args=(config.rabbitmq_url(), QUEUE, handle, stop, log), daemon=True,
    ).start()

    timeout = config.float_setting("DIMORA_CONSISTENCY_TIMEOUT", 3.0)
    log.info("Reservation service listening on port %s", config.http_port())
    serve(create_app(store, consistency_timeout=timeout), config.http_port(),
          threads=config.http_threads())


if __name__ == "__main__":
    main()
