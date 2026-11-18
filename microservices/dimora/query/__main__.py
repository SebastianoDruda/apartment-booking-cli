"""Start the query service: ``python -m dimora.query``."""

from __future__ import annotations

from dimora.common import config
from dimora.common.http import serve
from dimora.projector.mongo import connect
from dimora.query.app import create_app
from dimora.query.read_model import ReadModel


def main() -> None:
    log = config.configure_logging("query-service")
    db = connect(config.mongo_url(), config.mongo_database())
    timeout = config.float_setting("DIMORA_CONSISTENCY_TIMEOUT", 3.0)
    log.info("Query service listening on port %s", config.http_port())
    serve(create_app(ReadModel(db), consistency_timeout=timeout), config.http_port())


if __name__ == "__main__":
    main()
