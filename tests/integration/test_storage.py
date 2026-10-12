import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier, Event

import pytest

from apartment_booking.errors import (
    BookingConflictError,
    StorageBusyError,
    StorageError,
)
from apartment_booking.services.bookings import BookingService
from apartment_booking.storage.database import Database, database_path, transaction
from apartment_booking.storage.repositories import Repository


def test_default_and_override_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("APARTMENT_BOOKING_DB")
    assert database_path() == tmp_path / "data/apartment_booking.db"
    monkeypatch.setenv("APARTMENT_BOOKING_DB", "alternative/db.sqlite")
    assert database_path() == tmp_path / "alternative/db.sqlite"


def test_create_directories(tmp_path):
    database = Database(tmp_path / "nested/data/bookings.db")
    database.initialize()
    assert database.path.is_file()


def test_bad_paths_are_controlled(tmp_path):
    with pytest.raises(StorageError, match="Database error"):
        Database(tmp_path).initialize()
    parent = tmp_path / "regular-file"
    parent.write_text("not a directory")
    with pytest.raises(StorageError, match="Cannot create storage directory"):
        Database(parent / "child/test.db").initialize()


def test_foreign_keys_checks_and_restricted_deletion(db, apartment, bookings):
    booking = bookings.create(apartment.id, "Guest", 1, "2027-06-10", "2027-06-15")
    with pytest.raises(StorageError):
        with db.connection() as connection, transaction(connection):
            Repository(connection).insert_booking(
                replace(booking, id="new", apartment_id="missing")
            )
    for statement, args in [
        ("UPDATE apartments SET capacity = ?", (0,)),
        ("UPDATE apartments SET nightly_price_cents = ?", (-1,)),
        ("UPDATE bookings SET status = ?", ("INVALID",)),
        ("UPDATE bookings SET guest_count = ?", (0,)),
        ("DELETE FROM apartments WHERE id = ?", (apartment.id,)),
    ]:
        with pytest.raises(StorageError):
            with db.connection() as connection, transaction(connection):
                connection.execute(statement, args)
    assert bookings.list() == [booking]


def test_interrupt_rolls_back_and_closes_connection(db, apartments):
    with pytest.raises(KeyboardInterrupt):
        with db.connection() as connection, transaction(connection):
            connection.execute(
                "INSERT INTO apartments VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("test", "Name", "City", 1, 100, 1, "timestamp"),
            )
            raise KeyboardInterrupt
    assert apartments.list() == []
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connection.execute("SELECT 1")


def test_busy_timeout_and_retry(db, apartment):
    short_wait = BookingService(Database(db.path, timeout_ms=30))
    with db.connection() as connection, transaction(connection):
        with pytest.raises(StorageBusyError, match="busy, please retry"):
            short_wait.create(apartment.id, "Guest", 1, "2027-06-10", "2027-06-15")
    assert short_wait.list() == []
    short_wait.create(apartment.id, "Guest", 1, "2027-06-10", "2027-06-15")
    assert len(short_wait.list()) == 1


def test_simultaneous_conflicting_connections_never_double_book(
    db, apartment, bookings
):
    barrier = Barrier(2)

    def compete(guest):
        service = BookingService(Database(db.path))
        barrier.wait(timeout=5)
        try:
            service.create(apartment.id, guest, 2, "2027-06-10", "2027-06-15")
        except BookingConflictError:
            return "conflict"
        return "saved"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(compete, ["Guest One", "Guest Two"]))
    assert sorted(outcomes) == ["conflict", "saved"]
    assert len(bookings.list()) == 1


def test_waiting_writer_rechecks_after_first_transaction_commits(
    db, apartment, bookings
):
    existing = bookings.create(apartment.id, "First", 2, "2027-06-01", "2027-06-03")
    started = Event()

    def contender():
        started.set()
        return BookingService(Database(db.path)).create(
            apartment.id, "Second", 1, "2027-06-12", "2027-06-14"
        )

    with ThreadPoolExecutor(max_workers=1) as pool:
        with db.connection() as connection, transaction(connection):
            repo = Repository(connection)
            repo.update_booking(
                replace(existing, check_in="2027-06-10", check_out="2027-06-15")
            )
            future = pool.submit(contender)
            assert started.wait(5)
            assert not future.done()
        with pytest.raises(BookingConflictError):
            future.result(timeout=5)
    assert len(bookings.list()) == 1
    assert bookings.list()[0].check_in == "2027-06-10"


def test_failed_change_after_update_rolls_back(db, bookings, apartment, monkeypatch):
    original = bookings.create(apartment.id, "Original", 2, "2027-06-10", "2027-06-15")
    update = Repository.update_booking

    def fail_after_update(self, booking):
        update(self, booking)
        raise sqlite3.OperationalError("simulated write failure")

    monkeypatch.setattr(Repository, "update_booking", fail_after_update)
    with pytest.raises(StorageError, match="simulated write failure"):
        bookings.change(original.id, "New", 1, "2027-07-10", "2027-07-15")
    assert bookings.list() == [original]
