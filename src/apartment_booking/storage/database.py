import os
import sqlite3
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from importlib.resources import files
from pathlib import Path

from apartment_booking.errors import StorageBusyError, StorageError


def database_path() -> Path:
    return (
        Path(os.environ.get("APARTMENT_BOOKING_DB", "data/apartment_booking.db"))
        .expanduser()
        .resolve()
    )


def initialize(connection: sqlite3.Connection) -> None:
    # Only used outside transactions: executescript may commit a pending transaction.
    connection.executescript(
        files("apartment_booking.storage").joinpath("schema.sql").read_text("utf-8")
    )


@contextmanager
def connect(path: str | Path, timeout_ms: int = 5000) -> Iterator[sqlite3.Connection]:
    connection = None
    try:
        connection = sqlite3.connect(
            str(path), isolation_level=None, timeout=timeout_ms / 1000
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        yield connection
    except sqlite3.Error as exc:
        code = getattr(exc, "sqlite_errorcode", 0) & 0xFF
        if code in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
            raise StorageBusyError("Database is busy, please retry.") from exc
        raise StorageError(
            f"Database error: {exc}. Check the storage path and permissions."
        ) from exc
    finally:
        if connection is not None:
            connection.close()


@contextmanager
def transaction(connection: sqlite3.Connection) -> Iterator[None]:
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield
        connection.execute("COMMIT")
    finally:
        if connection.in_transaction:
            connection.execute("ROLLBACK")


class Database:
    def __init__(self, path: Path, timeout_ms: int = 5000) -> None:
        self.path = path.expanduser().resolve()
        self.timeout_ms = timeout_ms

    def initialize(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StorageError(f"Cannot create storage directory: {exc}") from exc
        with self.connection() as connection:
            initialize(connection)

    def connection(self) -> AbstractContextManager[sqlite3.Connection]:
        return connect(self.path, self.timeout_ms)
