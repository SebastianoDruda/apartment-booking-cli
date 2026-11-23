"""Unit and integration tests for the Apartment Booking System."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from apartment_booking.cli import (
    ApartmentBookingCLI,
    BOOKER_COMMAND_COMPLETIONS,
    MANAGER_COMMAND_COMPLETIONS,
    find_tab_completions,
    read_line_with_tab_completion,
    tab_completion_binding,
)
from apartment_booking.database import BookingDatabase, parse_date


class TestBookingDatabase(unittest.TestCase):
    """Tests for the SQLite database and business validation rules."""

    def setUp(self) -> None:
        self.db = BookingDatabase(":memory:")

    def tearDown(self) -> None:
        self.db.close()

    def test_month_and_day_calendar_validation(self) -> None:
        # September 30 is valid
        self.assertEqual(parse_date("2026-09-30"), "2026-09-30")
        self.assertEqual(parse_date("30.09.2026"), "2026-09-30")

        # September 31 is invalid because September only has 30 days
        with self.assertRaisesRegex(
            ValueError, "September 2026 only has 30 days \\(day 31 is not possible\\)"
        ):
            parse_date("2026-09-31")

        with self.assertRaisesRegex(
            ValueError, "September 2026 only has 30 days \\(day 31 is not possible\\)"
        ):
            parse_date("31.09.2026")

        # April 31 is invalid (April has 30 days)
        with self.assertRaisesRegex(
            ValueError, "April 2026 only has 30 days \\(day 31 is not possible\\)"
        ):
            parse_date("2026-04-31")

        # February 29 in non-leap year vs leap year
        with self.assertRaisesRegex(
            ValueError, "February 2026 only has 28 days \\(day 29 is not possible\\)"
        ):
            parse_date("2026-02-29")
        self.assertEqual(parse_date("2028-02-29"), "2028-02-29")

        # Invalid month number
        with self.assertRaisesRegex(ValueError, "month must be between 1 and 12"):
            parse_date("2026-13-10")

    def test_apartment_crud_and_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_file = Path(tmpdir) / "test_booking.db"

            # First session: add and update apartment
            db1 = BookingDatabase(db_file)
            apt = db1.add_apartment("Alpine Suite", "Bergstrasse 10, Munich", 4, 120.0)
            self.assertEqual(apt["name"], "Alpine Suite")
            self.assertEqual(apt["max_people"], 4)
            self.assertEqual(apt["price_per_night"], 120.0)

            updated = db1.update_apartment_price("Alpine Suite", 145.50)
            self.assertEqual(updated["old_price_per_night"], 120.0)
            self.assertEqual(updated["price_per_night"], 145.50)

            # Second session (restart): verify data persisted
            db2 = BookingDatabase(db_file)
            apartments = db2.list_apartments()
            self.assertEqual(len(apartments), 1)
            self.assertEqual(apartments[0]["name"], "Alpine Suite")
            self.assertEqual(apartments[0]["price_per_night"], 145.50)

            # Remove apartment
            db2.remove_apartment("Alpine Suite")
            self.assertEqual(db2.list_apartments(), [])

    def test_booking_creation_overlap_and_capacity(self) -> None:
        self.db.add_apartment("City Loft", "Hauptstrasse 5, Berlin", 3, 95.0)

        # Valid booking
        booking = self.db.create_booking(
            apartment_name="City Loft",
            start_date_str="2026-08-01",
            end_date_str="2026-08-05",
            booker_name="Anna Schmidt",
            num_people=2,
        )
        self.assertEqual(booking["nights"], 4)
        self.assertEqual(booking["total_price"], 380.0)

        # Exceeding max capacity should fail
        with self.assertRaisesRegex(ValueError, "not big enough"):
            self.db.create_booking(
                apartment_name="City Loft",
                start_date_str="2026-08-10",
                end_date_str="2026-08-12",
                booker_name="Max Weber",
                num_people=4,
            )

        # Overlapping date range should fail
        with self.assertRaisesRegex(ValueError, "not available"):
            self.db.create_booking(
                apartment_name="City Loft",
                start_date_str="2026-08-03",
                end_date_str="2026-08-07",
                booker_name="Max Weber",
                num_people=2,
            )

        # Adjacent booking starting on checkout day should succeed
        adjacent = self.db.create_booking(
            apartment_name="City Loft",
            start_date_str="2026-08-05",
            end_date_str="2026-08-08",
            booker_name="Max Weber",
            num_people=3,
        )
        self.assertEqual(adjacent["start_date"], "2026-08-05")

    def test_booking_change_and_cancel(self) -> None:
        self.db.add_apartment("Lake House", "Seestrasse 1, Konstanz", 4, 150.0)
        self.db.create_booking(
            "Lake House", "2026-09-01", "2026-09-05", "Tom Keller", 2
        )
        self.db.create_booking(
            "Lake House", "2026-09-10", "2026-09-15", "Lisa Meier", 3
        )

        # Change first booking to an overlapping range with second booking -> should fail
        with self.assertRaisesRegex(ValueError, "not available"):
            self.db.change_booking(
                apartment_name="Lake House",
                old_start_str="2026-09-01",
                old_end_str="2026-09-05",
                new_start_str="2026-09-08",
                new_end_str="2026-09-12",
                new_num_people=2,
            )

        # Change first booking to exceed capacity -> should fail
        with self.assertRaisesRegex(ValueError, "not big enough"):
            self.db.change_booking(
                apartment_name="Lake House",
                old_start_str="2026-09-01",
                old_end_str="2026-09-05",
                new_start_str="2026-09-02",
                new_end_str="2026-09-06",
                new_num_people=6,
            )

        # Valid change (overlapping with its own previous range is allowed)
        updated = self.db.change_booking(
            apartment_name="Lake House",
            old_start_str="2026-09-01",
            old_end_str="2026-09-05",
            new_start_str="2026-09-02",
            new_end_str="2026-09-07",
            new_num_people=4,
        )
        self.assertEqual(updated["start_date"], "2026-09-02")
        self.assertEqual(updated["end_date"], "2026-09-07")
        self.assertEqual(updated["num_people"], 4)
        self.assertEqual(updated["nights"], 5)

        # Cancel booking
        cancelled = self.db.cancel_booking(
            "Lake House", "2026-09-02", "2026-09-07"
        )
        self.assertEqual(cancelled["booker_name"], "Tom Keller")
        self.assertEqual(len(self.db.list_bookings()), 1)

    def test_search_available_apartments(self) -> None:
        self.db.add_apartment("Small Studio", "Gasse 2, Vienna", 2, 70.0)
        self.db.add_apartment("Family Villa", "Parkring 8, Vienna", 6, 200.0)
        self.db.add_apartment("Booked Flat", "Ring 1, Vienna", 4, 110.0)

        self.db.create_booking(
            "Booked Flat", "2026-10-01", "2026-10-06", "Clara", 2
        )

        # Search for 4 people from 2026-10-02 to 2026-10-05:
        # Small Studio is too small (max 2), Booked Flat is occupied -> only Family Villa
        available = self.db.search_available_apartments(
            "2026-10-02", "2026-10-05", 4
        )
        self.assertEqual(len(available), 1)
        self.assertEqual(available[0]["name"], "Family Villa")
        self.assertEqual(available[0]["total_price"], 600.0)


class TestTabAutocompletion(unittest.TestCase):
    """Tests for Tab key autocompletion of commands and apartment names."""

    def test_find_tab_completions(self) -> None:
        apartments = ["Alpine Chalet", "Alpine View", "Sunny Loft"]
        self.assertEqual(
            find_tab_completions("alp", apartments),
            ["Alpine Chalet", "Alpine View"],
        )
        self.assertEqual(
            find_tab_completions("loft", apartments),
            ["Sunny Loft"],
        )
        self.assertEqual(
            find_tab_completions("booking c", BOOKER_COMMAND_COMPLETIONS),
            ["booking create", "booking change", "booking cancel"],
        )

    def test_read_line_with_tab_completion_and_cycling(self) -> None:
        apartments = ["Alpine Chalet", "Alpine View", "Sunny Loft"]
        # User types 'A', 'l', 'p', then presses Tab twice to select the second match ("Alpine View"), then Enter
        keystrokes = iter(["A", "l", "p", "\t", "\t", "\r"])
        out = io.StringIO()
        result = read_line_with_tab_completion(
            prompt_text="Apartment name: ",
            completions=apartments,
            get_char=lambda: next(keystrokes),
            output_stream=out,
        )
        self.assertEqual(result, "Alpine View")

        # User types 'b', 'o', 'o', 'k', 'i', 'n', 'g', ' ', 'c', 'r', presses Tab -> "booking create"
        cmd_keys = iter(list("booking cr") + ["\t", "\r"])
        cmd_result = read_line_with_tab_completion(
            prompt_text="[Booker] > ",
            completions=BOOKER_COMMAND_COMPLETIONS,
            get_char=lambda: next(cmd_keys),
            output_stream=io.StringIO(),
        )
        self.assertEqual(cmd_result, "booking create")

        # Verify typing normal characters stays on a single line and never reprints the prompt
        normal_keys = iter(["h", "e", "l", "p", "\r"])
        normal_out = io.StringIO()
        normal_result = read_line_with_tab_completion(
            prompt_text="[Booker] > ",
            completions=BOOKER_COMMAND_COMPLETIONS,
            get_char=lambda: next(normal_keys),
            output_stream=normal_out,
        )
        self.assertEqual(normal_result, "help")
        self.assertEqual(normal_out.getvalue(), "[Booker] > help\n")

    def test_tab_binding_matches_readline_backend(self) -> None:
        # Python 3.13+ exposes readline.backend; older versions only mention libedit in __doc__.
        for fake_readline, binding in (
            (SimpleNamespace(backend="readline"), "tab: complete"),
            (SimpleNamespace(backend="editline"), "bind ^I rl_complete"),
            (SimpleNamespace(__doc__="Command line editing using GNU readline."), "tab: complete"),
            (SimpleNamespace(__doc__="Command line editing using libedit readline."), "bind ^I rl_complete"),
        ):
            with self.subTest(binding=binding), patch("apartment_booking.cli.readline", fake_readline):
                self.assertEqual(tab_completion_binding(), binding)

    def test_terminal_prompts_never_reuse_previous_completions(self) -> None:
        db = BookingDatabase(":memory:")
        self.addCleanup(db.close)
        cli = ApartmentBookingCLI(db=db, output_stream=io.StringIO())
        terminal = MagicMock()
        terminal.isatty.return_value = True
        for backend, binding in (("readline", "tab: complete"), ("editline", "bind ^I rl_complete")):
            with self.subTest(backend=backend):
                fake_readline = MagicMock(backend=backend)
                with patch("apartment_booking.cli.readline", fake_readline), \
                        patch("apartment_booking.cli.msvcrt", None), \
                        patch("sys.stdin", terminal), \
                        patch("builtins.input", side_effect=[" apartment view ", "Alpine"]):
                    self.assertEqual(cli._prompt("> ", MANAGER_COMMAND_COMPLETIONS), "apartment view")
                    command_completer = fake_readline.set_completer.call_args.args[0]
                    self.assertEqual(cli._prompt("Apartment name: "), "Alpine")
                    name_completer = fake_readline.set_completer.call_args.args[0]

                    fake_readline.get_line_buffer.return_value = "apartment v"
                    self.assertEqual(command_completer("apartment v", 0), "apartment view")
                    self.assertIsNone(command_completer("apartment v", 1))
                    # Free-text prompts get an empty completer, never commands or file names.
                    self.assertIsNone(name_completer("apartment v", 0))
                fake_readline.parse_and_bind.assert_called_with(binding)


class TestApartmentBookingCLI(unittest.TestCase):
    """End-to-end console workflow tests."""

    def test_full_cli_session(self) -> None:
        db = BookingDatabase(":memory:")
        inputs = iter(
            [
                # Start as system manager
                "system manager",
                "help",
                # Add two apartments (Country, City, Street and house number)
                "apartment add",
                "Sunny Flat",
                "Germany",
                "Munich",
                "Main St 1",
                "4",
                "100",
                "apartment add",
                "Cozy Studio",
                "Austria",
                "Vienna",
                "Side St 2",
                "2",
                "65",
                # Update Sunny Flat price
                "apartment update",
                "Sunny Flat",
                "120",
                # View apartments
                "apartment view",
                # Switch to apartment booker
                "role",
                "apartment booker",
                # Try booking with invalid September 31 date -> fails immediately with clear error
                "booking create",
                "Sunny Flat",
                "2026-09-31",
                # Create a valid booking (using September 30)
                "booking create",
                "Sunny Flat",
                "2026-09-28",
                "2026-09-30",
                "Alice",
                "3",
                # View bookings
                "booking view",
                # Change the booking
                "booking change",
                "Sunny Flat",
                "2026-09-28",
                "2026-09-30",
                "2026-11-02",
                "2026-11-06",
                "4",
                # Search available apartments and book from search results
                "apartment search",
                "2026-11-03",
                "2026-11-05",
                "2",
                "Cozy Studio",
                "Bob",
                # Cancel Alice's booking
                "booking cancel",
                "Sunny Flat",
                "2026-11-02",
                "2026-11-06",
                # Switch back to manager and remove Cozy Studio
                "role",
                "system manager",
                "apartment remove",
                "Cozy Studio",
                # Exit
                "exit",
            ]
        )
        output = io.StringIO()
        cli = ApartmentBookingCLI(
            db=db,
            input_fn=lambda _prompt: next(inputs),
            output_stream=output,
        )
        cli.run()

        text = output.getvalue()
        self.assertIn("AVAILABLE COMMANDS", text)
        self.assertIn("Apartment 'Sunny Flat' at 'Germany, Munich, Main St 1' added", text)
        self.assertIn("Updated price for apartment 'Sunny Flat' from 100.00 EUR to 120.00 EUR", text)
        self.assertIn("September 2026 only has 30 days (day 31 is not possible)", text)
        self.assertIn("Apartment 'Sunny Flat' is booked for Alice", text)
        self.assertIn("Booking for 'Sunny Flat' updated to 2026-11-02 -> 2026-11-06 for 4 people", text)
        self.assertIn("Apartment 'Cozy Studio' is booked for Bob", text)
        self.assertIn("Booking for apartment 'Sunny Flat' from 2026-11-02 to 2026-11-06 (Booker: Alice) has been cancelled", text)
        self.assertIn("Apartment 'Cozy Studio' has been removed", text)
        db.close()

    def test_role_specific_help_and_dynamic_table_alignment(self) -> None:
        db = BookingDatabase(":memory:")
        db.add_apartment(
            "Sebastianos main base",
            "Italia, Bolzano, Via Sebastiano 15",
            10,
            400.0,
        )
        db.add_apartment(
            "Toms Residence",
            "Italia, Bolzano, Via Druso 304",
            2,
            50.0,
        )
        db.create_booking(
            "Sebastianos main base",
            "2026-10-19",
            "2026-11-20",
            "Sebastiano Druda",
            5,
        )
        db.create_booking(
            "Toms Residence",
            "2026-10-19",
            "2026-10-31",
            "Tom Springer",
            1,
        )

        # Check System Manager help only shows manager commands
        mgr_out = io.StringIO()
        cli_mgr = ApartmentBookingCLI(db=db, output_stream=mgr_out)
        cli_mgr.role = "system manager"
        cli_mgr.cmd_help()
        mgr_help = mgr_out.getvalue()
        self.assertIn("System Manager Commands:", mgr_help)
        self.assertIn("apartment add", mgr_help)
        self.assertNotIn("Apartment Booker Commands:", mgr_help)
        self.assertNotIn("booking create", mgr_help)

        # Check Apartment Booker help only shows booker commands
        booker_out = io.StringIO()
        cli_booker = ApartmentBookingCLI(db=db, output_stream=booker_out)
        cli_booker.role = "apartment booker"
        cli_booker.cmd_help()
        booker_help = booker_out.getvalue()
        self.assertIn("Apartment Booker Commands:", booker_help)
        self.assertIn("booking create", booker_help)
        self.assertNotIn("System Manager Commands:", booker_help)
        self.assertNotIn("apartment add", booker_help)

        # Check dynamic table alignment for booking view
        table_out = io.StringIO()
        cli_table = ApartmentBookingCLI(db=db, output_stream=table_out)
        cli_table.cmd_booking_view()
        table_lines = [
            line
            for line in table_out.getvalue().splitlines()
            if "|" in line
        ]
        self.assertEqual(len(table_lines), 3)  # header + 2 rows
        pipe_positions = [
            [idx for idx, ch in enumerate(line) if ch == "|"]
            for line in table_lines
        ]
        self.assertEqual(pipe_positions[0], pipe_positions[1])
        self.assertEqual(pipe_positions[1], pipe_positions[2])
        db.close()


if __name__ == "__main__":
    unittest.main()
