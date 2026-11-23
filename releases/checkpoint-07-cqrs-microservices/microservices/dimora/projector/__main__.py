"""Start the projector: ``python -m dimora.projector``."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from pymongo.errors import PyMongoError

from dimora.common import config
from dimora.common.events import Event
from dimora.common.messaging import consume_forever
from dimora.projector.mongo import MongoReadStore, connect, ensure_indexes
from dimora.projector.projector import Projector

QUEUE = "projector.events"
# Touched while the consumer runs; the container health check reads its age.
HEARTBEAT = Path("/tmp/projector.alive")


def main() -> None:
    log = config.configure_logging("projector")
    db = connect(config.mongo_url(), config.mongo_database())
    while True:
        try:
            ensure_indexes(db)
            break
        except PyMongoError as error:
            log.info("Waiting for MongoDB: %s", error)
            time.sleep(2)
    projector = Projector(MongoReadStore(db))

    def handle(event: Event) -> None:
        applied = projector.apply(event)
        log.info("%s %s", "Projected" if applied else "Skipped older", event.event_id)

    def heartbeat() -> None:
        try:
            HEARTBEAT.touch()
        except OSError:
            pass

    log.info("Projector started")
    consume_forever(config.rabbitmq_url(), QUEUE, handle, threading.Event(), log, on_idle=heartbeat)


if __name__ == "__main__":
    main()
