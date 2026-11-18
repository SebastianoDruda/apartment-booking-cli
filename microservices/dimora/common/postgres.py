"""PostgreSQL helpers for the command-side services."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from collections.abc import Iterator

import psycopg
from psycopg.rows import dict_row


def connect(dsn: str) -> psycopg.Connection:
    return psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5)


@contextmanager
def transaction(dsn: str) -> Iterator[psycopg.Connection]:
    """Open a connection, run one transaction, commit on success, roll back on error."""
    with connect(dsn) as connection:
        yield connection


def wait_until_ready(dsn: str, log: logging.Logger, timeout: float = 60.0) -> None:
    """Block until PostgreSQL accepts connections, so a service can start before its database."""
    deadline = time.monotonic() + timeout
    delay = 0.5
    while True:
        try:
            with connect(dsn) as connection:
                connection.execute("SELECT 1")
            return
        except psycopg.OperationalError as error:
            if time.monotonic() >= deadline:
                raise
            log.info("Waiting for PostgreSQL: %s", str(error).strip().splitlines()[0])
            time.sleep(delay)
            delay = min(delay * 2, 5.0)


def ensure_schema(dsn: str, statements: tuple[str, ...], lock_key: int) -> None:
    """Create tables and indexes once, even when several replicas start together."""
    with transaction(dsn) as connection:
        connection.execute("SELECT pg_advisory_xact_lock(%s)", (lock_key,))
        for statement in statements:
            connection.execute(statement)
