"""Regression tests for price validation, atomic writes and recoverable CLI errors."""

from __future__ import annotations

import io
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from unittest.mock import patch

from apartment_booking.cli import ApartmentBookingCLI
from apartment_booking.database import BookingDatabase
from apartment_booking.__main__ import main


class TestPriceValidation(unittest.TestCase):
    def setUp(self) -> None:
        self.db = BookingDatabase(":memory:")
        self.addCleanup(self.db.close)

    def test_invalid_prices_cannot_create_or_update_apartments(self) -> None:
        self.db.add_apartment("Existing", "Example address", 2, 100)
        for price in (float("nan"), float("inf"), float("-inf"), 0, -1, 0.001):
            with self.subTest(price=price):
                with self.assertRaises(ValueError):
                    self.db.add_apartment("Invalid", "Example address", 2, price)
                with self.assertRaises(ValueError):
                    self.db.update_apartment_price("Existing", price)
                self.assertEqual(len(self.db.list_apartments()), 1)
                self.assertEqual(self.db.get_apartment_by_name("Existing")["price_per_night"], 100)

    def test_cli_price_formats_and_rounding_remain_supported(self) -> None:
        for value, expected in (("120", 120), ("120,50", 120.5), ("120.50 €", 120.5),
                                ("0.01", 0.01), ("12.345", round(12.345, 2))):
            with self.subTest(value=value):
                self.assertEqual(ApartmentBookingCLI._parse_price(value), expected)

    def test_cli_recovers_after_invalid_price_and_can_save_valid_price(self) -> None:
        for price in ("nan", "inf", "-inf", "1e309", "0.001", "not a number"):
            with self.subTest(price=price):
                db = BookingDatabase(":memory:")
                self.addCleanup(db.close)
                inputs = iter([
                    "2", "apartment add", "Invalid", "Italy", "Rome", "Example 1", "2", price,
                    "apartment add", "Valid", "Italy", "Rome", "Example 2", "2", "120,50",
                    "exit",
                ])
                output = io.StringIO()
                ApartmentBookingCLI(db=db, input_fn=lambda _: next(inputs), output_stream=output).run()
                self.assertIn("[Error]", output.getvalue())
                self.assertIn("Goodbye!", output.getvalue())
                self.assertEqual([a["name"] for a in db.list_apartments()], ["Valid"])
                self.assertEqual(db.list_apartments()[0]["price_per_night"], 120.5)

    def test_overflowing_total_does_not_create_or_change_booking(self) -> None:
        self.db.add_apartment("Large price", "Example address", 2, 1e308)
        with self.assertRaisesRegex(ValueError, "Total price is too large"):
            self.db.create_booking("Large price", "2027-01-01", "2027-01-03", "Guest", 1)
        self.assertEqual(self.db.list_bookings(), [])
        self.db.create_booking("Large price", "2027-01-01", "2027-01-02", "Guest", 1)
        with self.assertRaisesRegex(ValueError, "Total price is too large"):
            self.db.change_booking("Large price", "2027-01-01", "2027-01-02",
                                   "2027-01-01", "2027-01-03", 1)
        self.assertEqual(self.db.list_bookings()[0]["end_date"], "2027-01-02")

    def test_existing_booking_totals_still_follow_current_price(self) -> None:
        self.db.add_apartment("Demo", "Example address", 2, 100)
        self.db.create_booking("Demo", "2027-01-01", "2027-01-03", "Guest", 1)
        self.db.update_apartment_price("Demo", 120.5)
        self.assertEqual(self.db.list_bookings()[0]["total_price"], 241)
        self.assertEqual(self.db.get_booking("Demo", "2027-01-01", "2027-01-03")["total_price"], 241)


class TestAtomicWrites(unittest.TestCase):
    def test_validation_failure_releases_transaction_in_memory_and_on_disk(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            for path in (":memory:", Path(directory) / "test.db"):
                with self.subTest(path=str(path)):
                    db = BookingDatabase(path)
                    try:
                        db.add_apartment("Demo", "Example address", 2, 100)
                        with self.assertRaisesRegex(ValueError, "not big enough"):
                            db.create_booking("Demo", "2027-01-01", "2027-01-03", "Guest", 3)
                        db.create_booking("Demo", "2027-01-01", "2027-01-03", "Guest", 2)
                        with self.assertRaisesRegex(ValueError, "not available"):
                            db.create_booking("Demo", "2027-01-02", "2027-01-04", "Guest", 1)
                        db.create_booking("Demo", "2027-01-03", "2027-01-04", "Guest", 1)
                        self.assertEqual(len(db.list_bookings()), 2)
                    finally:
                        db.close()

    def test_failed_write_rolls_back_and_connection_can_be_reused(self) -> None:
        db = BookingDatabase(":memory:")
        self.addCleanup(db.close)
        db.add_apartment("Demo", "Example address", 2, 100)
        conn = db._get_connection()
        conn.execute("""
            CREATE TRIGGER reject_booking AFTER INSERT ON bookings
            BEGIN SELECT RAISE(ABORT, 'simulated storage constraint'); END;
        """)
        with self.assertRaises(sqlite3.IntegrityError):
            db.create_booking("Demo", "2027-01-01", "2027-01-03", "Guest", 1)
        self.assertEqual(db.list_bookings(), [])
        conn.execute("DROP TRIGGER reject_booking;")
        db.create_booking("Demo", "2027-01-01", "2027-01-03", "Guest", 1)
        self.assertEqual(len(db.list_bookings()), 1)

    def test_simultaneous_create_and_change_requests_cannot_overlap(self) -> None:
        for first_kind, second_kind in (("create", "create"), ("create", "change"),
                                        ("change", "change")):
            with self.subTest(first=first_kind, second=second_kind):
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "test.db"
                    first = BookingDatabase(path)
                    second = BookingDatabase(path)
                    first.add_apartment("Demo", "Example address", 2, 100)
                    if first_kind == "change":
                        first.create_booking("Demo", "2027-02-01", "2027-02-03", "First", 1)
                    if second_kind == "change":
                        first.create_booking("Demo", "2027-03-01", "2027-03-03", "Second", 1)

                    checked = threading.Event()
                    release = threading.Event()
                    second_connected = threading.Event()
                    original_check = first._has_overlapping_booking
                    original_connect = second._get_connection

                    def pause_after_check(*args, **kwargs):
                        result = original_check(*args, **kwargs)
                        checked.set()
                        if not release.wait(timeout=10):
                            raise RuntimeError("Timed out waiting to release first writer")
                        return result

                    def signal_second_connection():
                        conn = original_connect()
                        second_connected.set()
                        return conn

                    def book(db, kind, old_start, old_end):
                        try:
                            if kind == "create":
                                db.create_booking("Demo", "2027-01-01", "2027-01-03", "Guest", 1)
                            else:
                                db.change_booking("Demo", old_start, old_end,
                                                  "2027-01-01", "2027-01-03", 1)
                            return "saved"
                        except ValueError as error:
                            return str(error)

                    try:
                        with patch.object(first, "_has_overlapping_booking", side_effect=pause_after_check), \
                             patch.object(second, "_get_connection", side_effect=signal_second_connection), \
                             ThreadPoolExecutor(max_workers=2) as pool:
                            future_one = pool.submit(book, first, first_kind, "2027-02-01", "2027-02-03")
                            try:
                                self.assertTrue(checked.wait(timeout=5))
                                future_two = pool.submit(book, second, second_kind, "2027-03-01", "2027-03-03")
                                self.assertTrue(second_connected.wait(timeout=5))
                                # Keep the first writer between its availability check and write.
                                # Without the transaction the second writer can save in this gap.
                                try:
                                    future_two.result(timeout=0.2)
                                except TimeoutError:
                                    pass
                            finally:
                                release.set()
                            self.assertEqual(future_one.result(timeout=5), "saved")
                            self.assertIn("not available", future_two.result(timeout=5))
                        bookings = first.list_bookings()
                        self.assertEqual(sum(b["start_date"] == "2027-01-01" for b in bookings), 1)
                        if second_kind == "change":
                            self.assertIsNotNone(first.get_booking("Demo", "2027-03-01", "2027-03-03"))
                    finally:
                        first.close()
                        second.close()


class TestDatabaseErrorHandling(unittest.TestCase):
    def test_cli_recovers_from_expected_sqlite_errors(self) -> None:
        for error in (sqlite3.OperationalError("database is locked"),
                      sqlite3.OperationalError("attempt to write a readonly database"),
                      sqlite3.IntegrityError("constraint failed")):
            with self.subTest(error=str(error)):
                db = BookingDatabase(":memory:")
                self.addCleanup(db.close)
                output = io.StringIO()
                inputs = iter(["2", "apartment view", "apartment view", "exit"])
                with patch.object(db, "list_apartments", side_effect=[error, []]):
                    ApartmentBookingCLI(db=db, input_fn=lambda _: next(inputs), output_stream=output).run()
                self.assertIn("[Error] Database operation failed", output.getvalue())
                self.assertIn("No apartments found.", output.getvalue())
                self.assertIn("Goodbye!", output.getvalue())

    def test_real_locked_database_rejects_write_and_recovers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.db"
            db = BookingDatabase(path)
            locker = sqlite3.connect(path)
            try:
                locker.execute("BEGIN IMMEDIATE;")
                # Avoid waiting SQLite's default five seconds in this regression test.
                with patch.object(db, "_get_connection", side_effect=lambda: sqlite3.connect(path, timeout=0.01)):
                    with self.assertRaisesRegex(sqlite3.OperationalError, "locked"):
                        db.add_apartment("Blocked", "Example address", 2, 100)
                locker.rollback()
                db.add_apartment("Saved", "Example address", 2, 100)
                self.assertEqual([a["name"] for a in db.list_apartments()], ["Saved"])
            finally:
                locker.close()
                db.close()

    def test_startup_database_error_has_friendly_message_and_failure_status(self) -> None:
        output = io.StringIO()
        with patch("apartment_booking.__main__.ApartmentBookingCLI", side_effect=sqlite3.OperationalError("unable to open database file")), \
             patch("sys.stderr", output):
            with self.assertRaises(SystemExit) as error:
                main()
        self.assertEqual(error.exception.code, 1)
        self.assertIn("[Error] Database operation failed", output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())

    def test_programming_errors_are_not_swallowed(self) -> None:
        db = BookingDatabase(":memory:")
        self.addCleanup(db.close)
        inputs = iter(["2", "apartment view"])
        with patch.object(db, "list_apartments", side_effect=sqlite3.ProgrammingError("bug")):
            with self.assertRaises(sqlite3.ProgrammingError):
                ApartmentBookingCLI(db=db, input_fn=lambda _: next(inputs), output_stream=io.StringIO()).run()

    def test_main_closes_database_on_normal_and_exceptional_exit(self) -> None:
        for error in (None, RuntimeError("unexpected failure")):
            with self.subTest(error=error), patch("apartment_booking.__main__.ApartmentBookingCLI") as factory:
                factory.return_value.run.side_effect = error
                if error is None:
                    main()
                else:
                    with self.assertRaises(RuntimeError):
                        main()
                factory.return_value.db.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
