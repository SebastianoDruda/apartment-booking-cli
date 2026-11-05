"""Interactive console interface for the Apartment Booking System with Tab autocompletion."""

from __future__ import annotations

import sqlite3
import sys
from typing import Callable, Sequence, TextIO

try:
    import msvcrt
except ImportError:  # pragma: no cover - non-Windows fallback
    msvcrt = None  # type: ignore[assignment]

try:
    import readline
except ImportError:  # pragma: no cover - Windows standard library
    readline = None  # type: ignore[assignment]

from apartment_booking.database import (
    BookingDatabase,
    DEFAULT_DB_PATH,
    format_address,
    parse_date,
    validate_date_range,
    parse_price_input,
)

ROLE_BOOKER = "apartment booker"
ROLE_MANAGER = "system manager"


def database_error_message(error: sqlite3.Error) -> str:
    """Explain expected storage failures without exposing a traceback to the user."""
    return (
        f"[Error] Database operation failed: {error}. "
        "Close other database writers, check that the database folder is writable, "
        "and try again."
    )


MANAGER_COMMAND_COMPLETIONS = [
    "apartment add",
    "apartment update",
    "apartment remove",
    "apartment view",
    "booking view",
    "help",
    "role",
    "exit",
]

BOOKER_COMMAND_COMPLETIONS = [
    "booking create",
    "booking view",
    "booking change",
    "booking cancel",
    "apartment view",
    "apartment search",
    "help",
    "role",
    "exit",
]

ROLE_COMPLETIONS = [
    ROLE_BOOKER,
    ROLE_MANAGER,
    "exit",
]


def find_tab_completions(query: str, candidates: Sequence[str]) -> list[str]:
    """Return matching completion candidates for a given partial input string.

    Prefix matches (case-insensitive) are returned first, followed by substring matches.
    """
    cleaned = " ".join(query.strip().lower().split())
    if not cleaned:
        return list(candidates)

    prefix_matches = [c for c in candidates if c.lower().startswith(cleaned)]
    substring_matches = [
        c
        for c in candidates
        if cleaned in c.lower() and not c.lower().startswith(cleaned)
    ]
    return prefix_matches + substring_matches


def read_line_with_tab_completion(
    prompt_text: str,
    completions: Sequence[str] = (),
    get_char: Callable[[], str] | None = None,
    output_stream: TextIO | None = None,
) -> str:
    """Read a line from the console supporting Tab autocompletion and Backspace editing.

    Writes characters in-place on the same line without re-printing the prompt.
    Pressing Tab autocompletes from `completions` and cycles through multiple matches
    on repeated Tab presses.
    """
    stream = output_stream if output_stream is not None else sys.stdout
    read_ch = get_char if get_char is not None else msvcrt.getwch  # type: ignore[union-attr]

    stream.write(prompt_text)
    stream.flush()

    buffer: list[str] = []
    tab_matches: list[str] | None = None
    tab_index = 0

    def replace_buffer(new_text: str) -> None:
        nonlocal buffer
        old_len = len(buffer)
        if old_len > 0:
            stream.write("\b" * old_len + " " * old_len + "\b" * old_len)
        stream.write(new_text)
        stream.flush()
        buffer = list(new_text)

    while True:
        ch = read_ch()

        # Enter key
        if ch in ("\r", "\n"):
            stream.write("\n")
            stream.flush()
            return "".join(buffer)

        # Ctrl+C
        if ch == "\x03":
            stream.write("\n")
            stream.flush()
            raise KeyboardInterrupt

        # Ctrl+D or Ctrl+Z (EOF)
        if ch in ("\x04", "\x1a"):
            stream.write("\n")
            stream.flush()
            raise EOFError

        # Tab key -> autocomplete / cycle matches in-place
        if ch == "\t":
            if not completions:
                continue
            if tab_matches is None:
                matches = find_tab_completions("".join(buffer), completions)
                if matches:
                    tab_matches = matches
                    tab_index = 0
                    replace_buffer(tab_matches[0])
            else:
                tab_index = (tab_index + 1) % len(tab_matches)
                replace_buffer(tab_matches[tab_index])
            continue

        # Backspace
        if ch in ("\x08", "\x7f"):
            if buffer:
                buffer.pop()
                tab_matches = None
                stream.write("\b \b")
                stream.flush()
            continue

        # Ignore Windows extended key sequences (arrow keys, function keys, etc.)
        if ch in ("\x00", "\xe0"):
            read_ch()
            continue

        # Regular printable characters: echo only the single character in-place
        if ch >= " ":
            buffer.append(ch)
            tab_matches = None
            stream.write(ch)
            stream.flush()


class ApartmentBookingCLI:
    """Command-line controller for the Apartment Booking System."""

    def __init__(
        self,
        db: BookingDatabase | None = None,
        input_fn: Callable[[str], str] | None = None,
        output_stream: TextIO | None = None,
    ) -> None:
        self.db = db if db is not None else BookingDatabase(DEFAULT_DB_PATH)
        self._custom_input_fn = input_fn
        self.output_stream = output_stream if output_stream is not None else sys.stdout
        self.role: str | None = None

    def _print(self, message: str = "") -> None:
        print(message, file=self.output_stream)

    def _prompt(
        self, prompt_text: str, completions: Sequence[str] = ()
    ) -> str:
        """Prompt the user for input, using Tab autocompletion when running in an interactive terminal."""
        if self._custom_input_fn is not None:
            return self._custom_input_fn(prompt_text).strip()

        is_tty = hasattr(sys.stdin, "isatty") and sys.stdin.isatty()
        if is_tty and msvcrt is not None:
            return read_line_with_tab_completion(
                prompt_text=prompt_text,
                completions=completions,
                output_stream=self.output_stream,
            ).strip()

        if is_tty and readline is not None and completions:
            matches_cache: list[str] = []

            def completer(text: str, state: int) -> str | None:
                nonlocal matches_cache
                if state == 0:
                    line = readline.get_line_buffer()
                    matches_cache = find_tab_completions(line or text, completions)
                return matches_cache[state] if state < len(matches_cache) else None

            readline.set_completer_delims("")
            readline.set_completer(completer)
            readline.parse_and_bind("tab: complete")

        return input(prompt_text).strip()

    def _get_apartment_names(self) -> list[str]:
        """Return all existing apartment names for Tab autocompletion."""
        return [apt["name"] for apt in self.db.list_apartments()]

    @staticmethod
    def _parse_int(value_str: str, field_name: str) -> int:
        try:
            val = int(value_str.strip())
        except ValueError as exc:
            raise ValueError(f"{field_name} must be a whole number.") from exc
        if val <= 0:
            raise ValueError(f"{field_name} must be at least 1.")
        return val

    @staticmethod
    def _parse_price(value_str: str) -> float:
        return parse_price_input(value_str)

    # ------------------------------------------------------------------
    # Role Selection
    # ------------------------------------------------------------------

    def ask_role(self) -> bool:
        """Ask the user whether they are an apartment booker or a system manager.

        Returns True if a role was selected, or False if the user chose to exit.
        """
        while True:
            self._print("\nPlease select your role (Tip: press Tab to autocomplete):")
            self._print("  [1] apartment booker")
            self._print("  [2] system manager")
            try:
                answer = self._prompt(
                    "Are you an apartment booker or a system manager? ",
                    completions=ROLE_COMPLETIONS,
                ).lower()
            except (EOFError, KeyboardInterrupt):
                self._print("\nExiting Apartment Booking System. Goodbye!")
                return False

            if answer in ("exit", "quit", "q"):
                self._print("Exiting Apartment Booking System. Goodbye!")
                return False
            if answer in ("1", "apartment booker", "booker", "b"):
                self.role = ROLE_BOOKER
                self._print("\nLogged in as: Apartment Booker.")
                self._print(
                    "Type 'help' to see all available commands (press Tab to autocomplete commands and apartment names)."
                )
                return True
            if answer in ("2", "system manager", "manager", "m", "admin"):
                self.role = ROLE_MANAGER
                self._print("\nLogged in as: System Manager.")
                self._print(
                    "Type 'help' to see all available commands (press Tab to autocomplete commands and apartment names)."
                )
                return True

            self._print(
                "[Error] Invalid role. Please enter 'apartment booker' (or '1') "
                "or 'system manager' (or '2')."
            )

    # ------------------------------------------------------------------
    # Help & Tables
    # ------------------------------------------------------------------

    def _print_manager_commands(self) -> None:
        self._print("\nSystem Manager Commands:")
        self._print(
            "  apartment add      - Add a new apartment (name, country, city, street & house no., max people, price/night EUR)"
        )
        self._print(
            "  apartment update   - Update the price per night (EUR) of an apartment"
        )
        self._print(
            "  apartment remove   - Remove an apartment by entering its name"
        )
        self._print(
            "  apartment view     - View all apartments (without bookings) [alias: apartment list]"
        )
        self._print(
            "  booking view       - View all bookings together with the booked apartment [alias: booking list]"
        )

    def _print_booker_commands(self) -> None:
        self._print("\nApartment Booker Commands:")
        self._print(
            "  booking create     - Create a booking (apartment, dates, your name, number of people)"
        )
        self._print(
            "  booking view       - View all bookings together with the booked apartment [alias: booking list]"
        )
        self._print(
            "  booking change     - Change an existing booking's date range and number of people"
        )
        self._print(
            "  booking cancel     - Cancel a booking by apartment name and date range"
        )
        self._print(
            "  apartment view     - View all apartments (without bookings) [alias: apartment list]"
        )
        self._print(
            "  apartment search   - Search available apartments by date range & people, then book [alias: booking search]"
        )

    def _print_general_commands(self) -> None:
        self._print("\nGeneral Commands (Both Roles):")
        self._print(
            "  help               - Show all available commands for your current role"
        )
        self._print(
            "  role               - Switch between 'apartment booker' and 'system manager'"
        )
        self._print(
            "  exit               - Exit the application [alias: quit]"
        )

    def print_all_commands_overview(self) -> None:
        """Display an overview of all commands for both roles when starting the program."""
        self._print("\n" + "=" * 78)
        self._print("OVERVIEW OF ALL COMMANDS (BOTH ROLES)")
        self._print("Tip: Press the TAB key to autocomplete commands and apartment names!")
        self._print("=" * 78)
        self._print_manager_commands()
        self._print_booker_commands()
        self._print_general_commands()
        self._print("=" * 78)

    def cmd_help(self) -> None:
        """Display available commands specific to the active role."""
        current = self.role.title() if self.role else "None"
        self._print("\n" + "=" * 78)
        self._print(f"AVAILABLE COMMANDS (Current Role: {current})")
        self._print("Tip: Press the TAB key to autocomplete commands and apartment names!")
        self._print("=" * 78)

        if self.role == ROLE_MANAGER:
            self._print_manager_commands()
        else:
            self._print_booker_commands()

        self._print_general_commands()
        self._print("=" * 78)

    def _print_dynamic_table(
        self,
        headers: Sequence[str],
        rows: Sequence[Sequence[str]],
        right_align_cols: set[int] | None = None,
    ) -> None:
        """Print a table with column widths dynamically calculated from headers and cell contents."""
        right_cols = right_align_cols or set()
        col_widths = [
            max(len(str(headers[col_idx])), *(len(str(row[col_idx])) for row in rows))
            for col_idx in range(len(headers))
        ]

        header_line = " | ".join(
            f"{headers[i]:<{col_widths[i]}}" for i in range(len(headers))
        )
        sep = "-" * len(header_line)

        self._print(sep)
        self._print(header_line)
        self._print(sep)
        for row in rows:
            cells = [
                f"{row[i]:>{col_widths[i]}}"
                if i in right_cols
                else f"{row[i]:<{col_widths[i]}}"
                for i in range(len(headers))
            ]
            self._print(" | ".join(cells))
        self._print(sep)

    def _print_apartments_table(
        self, apartments: list[dict], show_total: bool = False
    ) -> None:
        if not apartments:
            self._print("No apartments found.")
            return

        if show_total:
            headers = [
                "Apartment Name",
                "Address (Country, City, Street)",
                "Max People",
                "Price/Night",
                "Total Price",
            ]
            rows = [
                [
                    str(apt["name"]),
                    str(apt["address"]),
                    str(apt["max_people"]),
                    f"{apt['price_per_night']:.2f} EUR",
                    f"{apt['total_price']:.2f} EUR ({apt['nights']}n)",
                ]
                for apt in apartments
            ]
            self._print_dynamic_table(headers, rows, right_align_cols={3, 4})
        else:
            headers = [
                "Apartment Name",
                "Address (Country, City, Street)",
                "Max People",
                "Price/Night",
            ]
            rows = [
                [
                    str(apt["name"]),
                    str(apt["address"]),
                    str(apt["max_people"]),
                    f"{apt['price_per_night']:.2f} EUR",
                ]
                for apt in apartments
            ]
            self._print_dynamic_table(headers, rows, right_align_cols={3})

    # ------------------------------------------------------------------
    # System Manager Commands
    # ------------------------------------------------------------------

    def cmd_apartment_add(self) -> None:
        """Add an apartment with standardized address (Country, City, Street and house number)."""
        self._print("\n--- Add New Apartment ---")
        name = self._prompt("Apartment name: ")
        country = self._prompt("Country: ")
        city = self._prompt("City: ")
        street = self._prompt("Street and house number: ")
        address = format_address(country, city, street)
        max_people_str = self._prompt("Maximum number of people: ")
        price_str = self._prompt("Price per night (euros): ")

        max_people = self._parse_int(max_people_str, "Maximum number of people")
        price = self._parse_price(price_str)

        apt = self.db.add_apartment(name, address, max_people, price)
        self._print(
            f"[Success] Apartment '{apt['name']}' at '{apt['address']}' added "
            f"(Max people: {apt['max_people']}, Price/night: {apt['price_per_night']:.2f} EUR)."
        )

    def cmd_apartment_update(self) -> None:
        """Update the price per night of an apartment (System Manager)."""
        self._print("\n--- Update Apartment Price ---")
        apt_names = self._get_apartment_names()
        name = self._prompt("Apartment name (Tab to autocomplete): ", completions=apt_names)
        if not name:
            raise ValueError("Apartment name cannot be empty.")

        existing = self.db.get_apartment_by_name(name)
        if existing is None:
            raise ValueError(f"Apartment '{name}' does not exist.")

        price_str = self._prompt(
            f"New price per night in euros (current: {existing['price_per_night']:.2f} EUR): "
        )
        new_price = self._parse_price(price_str)

        updated = self.db.update_apartment_price(name, new_price)
        self._print(
            f"[Success] Updated price for apartment '{updated['name']}' from "
            f"{updated['old_price_per_night']:.2f} EUR to {updated['price_per_night']:.2f} EUR per night."
        )

    def cmd_apartment_remove(self) -> None:
        """Remove an apartment by name (System Manager)."""
        self._print("\n--- Remove Apartment ---")
        apt_names = self._get_apartment_names()
        name = self._prompt("Apartment name (Tab to autocomplete): ", completions=apt_names)
        removed = self.db.remove_apartment(name)
        self._print(f"[Success] Apartment '{removed['name']}' has been removed.")

    # ------------------------------------------------------------------
    # Shared View Commands (System Manager & Apartment Booker)
    # ------------------------------------------------------------------

    def cmd_apartment_view(self) -> None:
        """View all apartments without bookings."""
        self._print("\n--- All Apartments ---")
        apartments = self.db.list_apartments()
        self._print_apartments_table(apartments, show_total=False)

    def cmd_booking_view(self) -> None:
        """View all bookings together with the booked apartment."""
        self._print("\n--- All Bookings ---")
        bookings = self.db.list_bookings()
        if not bookings:
            self._print("No bookings found.")
            return

        headers = [
            "Apartment",
            "Address",
            "Max Cap",
            "Price/Night",
            "Booker",
            "People",
            "From -> To",
            "Total Price",
        ]
        rows = [
            [
                str(b["apartment_name"]),
                str(b["apartment_address"]),
                str(b["apartment_max_people"]),
                f"{b['price_per_night']:.2f} EUR",
                str(b["booker_name"]),
                str(b["num_people"]),
                f"{b['start_date']} -> {b['end_date']}",
                f"{b['total_price']:.2f} EUR",
            ]
            for b in bookings
        ]
        self._print_dynamic_table(headers, rows, right_align_cols={3, 7})

    # ------------------------------------------------------------------
    # Apartment Booker Commands
    # ------------------------------------------------------------------

    def cmd_booking_create(self) -> None:
        """Create a new booking (Apartment Booker)."""
        self._print("\n--- Create Booking ---")
        apt_names = self._get_apartment_names()
        apartment_name = self._prompt(
            "Apartment name (Tab to autocomplete): ", completions=apt_names
        )
        start_date = self._prompt("From date (YYYY-MM-DD): ")
        parse_date(start_date)
        end_date = self._prompt("To date (YYYY-MM-DD): ")
        validate_date_range(start_date, end_date)
        booker_name = self._prompt("Your name: ")
        num_people_str = self._prompt("Number of people staying: ")

        num_people = self._parse_int(num_people_str, "Number of people")
        booking = self.db.create_booking(
            apartment_name=apartment_name,
            start_date_str=start_date,
            end_date_str=end_date,
            booker_name=booker_name,
            num_people=num_people,
        )
        self._print(
            f"[Success] Apartment '{booking['apartment_name']}' is booked for {booking['booker_name']} "
            f"({booking['num_people']} people) from {booking['start_date']} to {booking['end_date']} "
            f"({booking['nights']} nights, Total: {booking['total_price']:.2f} EUR)."
        )

    def cmd_booking_change(self) -> None:
        """Change an existing booking's date range and number of people (Apartment Booker)."""
        self._print("\n--- Change Booking ---")
        apt_names = self._get_apartment_names()
        apartment_name = self._prompt(
            "Apartment name (Tab to autocomplete): ", completions=apt_names
        )
        old_start = self._prompt("Current booked from date (YYYY-MM-DD): ")
        parse_date(old_start)
        old_end = self._prompt("Current booked to date (YYYY-MM-DD): ")
        old_start_iso, old_end_iso, _ = validate_date_range(old_start, old_end)

        existing = self.db.get_booking(apartment_name, old_start_iso, old_end_iso)
        if existing is None:
            raise ValueError(
                f"No booking found for apartment '{apartment_name}' "
                f"from {old_start_iso} to {old_end_iso}."
            )

        self._print(
            f"Found booking for {existing['booker_name']} at '{existing['apartment_name']}' "
            f"({existing['start_date']} to {existing['end_date']}, {existing['num_people']} people)."
        )
        new_start = self._prompt("New from date (YYYY-MM-DD): ")
        parse_date(new_start)
        new_end = self._prompt("New to date (YYYY-MM-DD): ")
        validate_date_range(new_start, new_end)
        new_people_str = self._prompt("New number of people staying: ")

        new_people = self._parse_int(new_people_str, "New number of people")
        updated = self.db.change_booking(
            apartment_name=apartment_name,
            old_start_str=old_start_iso,
            old_end_str=old_end_iso,
            new_start_str=new_start,
            new_end_str=new_end,
            new_num_people=new_people,
        )
        self._print(
            f"[Success] Booking for '{updated['apartment_name']}' updated to "
            f"{updated['start_date']} -> {updated['end_date']} for {updated['num_people']} people "
            f"({updated['nights']} nights, Total: {updated['total_price']:.2f} EUR)."
        )

    def cmd_booking_cancel(self) -> None:
        """Cancel a booking by apartment name and date range (Apartment Booker)."""
        self._print("\n--- Cancel Booking ---")
        apt_names = self._get_apartment_names()
        apartment_name = self._prompt(
            "Apartment name (Tab to autocomplete): ", completions=apt_names
        )
        start_date = self._prompt("Booked from date (YYYY-MM-DD): ")
        parse_date(start_date)
        end_date = self._prompt("Booked to date (YYYY-MM-DD): ")
        validate_date_range(start_date, end_date)

        cancelled = self.db.cancel_booking(apartment_name, start_date, end_date)
        self._print(
            f"[Success] Booking for apartment '{cancelled['apartment_name']}' "
            f"from {cancelled['start_date']} to {cancelled['end_date']} "
            f"(Booker: {cancelled['booker_name']}) has been cancelled."
        )

    def cmd_apartment_search(self) -> None:
        """Search available apartments for a date range and number of people, then book."""
        self._print("\n--- Search Available Apartments ---")
        start_date = self._prompt("From date (YYYY-MM-DD): ")
        parse_date(start_date)
        end_date = self._prompt("To date (YYYY-MM-DD): ")
        validate_date_range(start_date, end_date)
        num_people_str = self._prompt("Number of people staying: ")

        num_people = self._parse_int(num_people_str, "Number of people")
        available = self.db.search_available_apartments(start_date, end_date, num_people)

        if not available:
            self._print(
                f"No apartments are available for {num_people} people "
                f"from {start_date} to {end_date}."
            )
            return

        start_iso = available[0]["start_date"]
        end_iso = available[0]["end_date"]
        available_names = [apt["name"] for apt in available]
        self._print(
            f"\nAvailable apartments from {start_iso} to {end_iso} for {num_people} people:"
        )
        self._print_apartments_table(available, show_total=True)

        chosen_name = self._prompt(
            "\nEnter the name of the apartment you want to book (Tab to autocomplete, or Enter to skip): ",
            completions=available_names,
        )
        if not chosen_name or chosen_name.lower() in ("no", "n", "skip", "cancel"):
            self._print("Search finished without creating a booking.")
            return

        matched_apt = next(
            (apt for apt in available if apt["name"].lower() == chosen_name.lower()),
            None,
        )
        if matched_apt is None:
            raise ValueError(
                f"Apartment '{chosen_name}' is not in the list of available apartments for your search."
            )

        booker_name = self._prompt("Enter your name to complete the booking: ")
        booking = self.db.create_booking(
            apartment_name=matched_apt["name"],
            start_date_str=start_iso,
            end_date_str=end_iso,
            booker_name=booker_name,
            num_people=num_people,
        )
        self._print(
            f"[Success] Apartment '{booking['apartment_name']}' is booked for {booking['booker_name']} "
            f"({booking['num_people']} people) from {booking['start_date']} to {booking['end_date']} "
            f"({booking['nights']} nights, Total: {booking['total_price']:.2f} EUR)."
        )

    # ------------------------------------------------------------------
    # Command Execution Loop
    # ------------------------------------------------------------------

    def execute_command(self, raw_command: str) -> bool:
        """Execute a single command string.

        Returns True to keep running, or False to exit the loop.
        """
        cmd = " ".join(raw_command.strip().lower().split())
        if not cmd:
            return True

        if cmd in ("exit", "quit", "q"):
            self._print("Exiting Apartment Booking System. Goodbye!")
            return False

        if cmd == "help":
            self.cmd_help()
            return True

        if cmd in ("role", "switch", "switch role"):
            return self.ask_role()

        # Shared commands available to both System Manager and Apartment Booker
        if cmd in ("apartment view", "apartment list", "apartments"):
            self.cmd_apartment_view()
            return True

        if cmd in ("booking view", "booking list", "bookings"):
            self.cmd_booking_view()
            return True

        # System Manager only commands
        manager_commands = {
            "apartment add": self.cmd_apartment_add,
            "apartment update": self.cmd_apartment_update,
            "apartment remove": self.cmd_apartment_remove,
            "apartment delete": self.cmd_apartment_remove,
        }
        if cmd in manager_commands:
            if self.role != ROLE_MANAGER:
                self._print(
                    f"[Access Denied] Command '{cmd}' is only available for a System Manager. "
                    "Type 'role' to switch roles."
                )
                return True
            manager_commands[cmd]()
            return True

        # Apartment Booker only commands
        booker_commands = {
            "booking create": self.cmd_booking_create,
            "booking add": self.cmd_booking_create,
            "booking change": self.cmd_booking_change,
            "booking update": self.cmd_booking_change,
            "booking edit": self.cmd_booking_change,
            "booking cancel": self.cmd_booking_cancel,
            "booking remove": self.cmd_booking_cancel,
            "booking delete": self.cmd_booking_cancel,
            "apartment search": self.cmd_apartment_search,
            "booking search": self.cmd_apartment_search,
            "search": self.cmd_apartment_search,
        }
        if cmd in booker_commands:
            if self.role != ROLE_BOOKER:
                self._print(
                    f"[Access Denied] Command '{cmd}' is only available for an Apartment Booker. "
                    "Type 'role' to switch roles."
                )
                return True
            booker_commands[cmd]()
            return True

        self._print(
            f"[Error] Unknown command '{raw_command.strip()}'. Type 'help' to see all available commands."
        )
        return True

    def run(self) -> None:
        """Start the interactive console session."""
        self._print("=" * 78)
        self._print("                   WELCOME TO THE APARTMENT BOOKING SYSTEM")
        self._print("=" * 78)
        self.print_all_commands_overview()

        if not self.ask_role():
            return

        while True:
            if self.role == ROLE_MANAGER:
                role_label = "Manager"
                cmd_completions = MANAGER_COMMAND_COMPLETIONS
            else:
                role_label = "Booker"
                cmd_completions = BOOKER_COMMAND_COMPLETIONS

            try:
                raw_cmd = self._prompt(
                    f"\n[{role_label}] > ", completions=cmd_completions
                )
            except (EOFError, KeyboardInterrupt):
                self._print("\nExiting Apartment Booking System. Goodbye!")
                break

            try:
                should_continue = self.execute_command(raw_cmd)
                if not should_continue:
                    break
            except ValueError as err:
                self._print(f"[Error] {err}")
            except (sqlite3.OperationalError, sqlite3.IntegrityError) as err:
                self._print(database_error_message(err))
            except (EOFError, KeyboardInterrupt):
                self._print("\n[Cancelled] Operation aborted.")
