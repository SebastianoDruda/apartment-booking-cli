import io

import pytest
from rich.console import Console

from apartment_booking.__main__ import main
from apartment_booking.cli.menu import Menu
from apartment_booking.cli.prompts import Prompts
from apartment_booking.models import BookingStatus


def run_menu(monkeypatch, apartments, bookings, demo, inputs):
    output = io.StringIO()
    monkeypatch.setattr("sys.stdin", io.StringIO("\n".join(inputs) + "\n"))
    menu = Menu(
        Console(file=output, width=90, color_system=None), apartments, bookings, demo
    )
    menu.run()
    return output.getvalue()


def test_full_menu_crud(monkeypatch, apartments, bookings, demo):
    output = run_menu(
        monkeypatch,
        apartments,
        bookings,
        demo,
        [
            "wrong",
            "1",
            "2",  # apartments -> add
            "",
            "[red]Room",
            "City",
            "many",
            "21",
            "4",
            "NaN",
            "0.00",
            "100.50",
            "1",
            "1",
            "2",
            "3",
            "0",  # view all, archived, back
            "3",
            "1",
            "New name",
            "",
            "",
            "",
            "1",  # update
            "0",
            "2",
            "2",
            "1",  # main -> bookings -> create
            "Guest",
            "5",
            "2",
            "bad",
            "2027-06-10",
            "2027-06-09",
            "2027-06-15",
            "1",
            "3",
            "1",
            "New guest",
            "",
            "",
            "2027-06-16",
            "1",  # change
            "1",
            "4",
            "1",
            "1",  # view, cancel
            "0",
            "1",
            "4",
            "1",
            "1",
            "1",
            "2",
            "0",
            "0",  # archive, view all
            "4",
            "3",
            "0",
            "0",  # storage, exit
        ],
    )
    apartment = apartments.list("all")[0]
    booking = bookings.list()[0]
    assert (
        apartment.name,
        apartment.city,
        apartment.capacity,
        apartment.nightly_price_cents,
        apartment.is_active,
    ) == ("New name", "City", 4, 10050, False)
    assert (booking.guest_name, booking.check_out, booking.status) == (
        "New guest",
        "2027-06-16",
        BookingStatus.CANCELLED,
    )
    assert "SUCCESS: Apartment updated." in output
    assert "SUCCESS: Booking changed." in output
    assert "archived" in output
    assert "ERROR:" in output
    assert "[red]Room" in output  # user content is never treated as Rich markup


def test_demo_menu_search_cancel_and_reset(monkeypatch, apartments, bookings, demo):
    output = run_menu(
        monkeypatch,
        apartments,
        bookings,
        demo,
        [
            "4",
            "1",
            "3",
            "1",
            "0",  # load, info, refused reimport -> back
            "2",
            "RESET ",
            "0",  # incorrect reset must cancel
            "3",
            "2027-06-12",
            "2027-06-14",
            "6",  # unavailable
            "3",
            "2027-06-12",
            "2027-06-14",
            "",  # available default guests
            "2",
            "1",
            "4",
            "2",
            "1",
            "0",  # view and cancel Alex
            "3",
            "2027-06-12",
            "2027-06-14",
            "1",  # now three
            "4",
            "2",
            "RESET",
            "0",
            "0",  # successful reset
        ],
    )
    assert "Reset cancelled." in output
    assert "AVAILABLE: 0 apartment(s)" in output
    assert "AVAILABLE: 2 apartment(s)" in output
    assert "AVAILABLE: 3 apartment(s)" in output
    assert "SUCCESS: Database reset:" in output
    assert demo.counts() == (5, 6)
    assert len(bookings.list(confirmed_only=True)) == 5


def test_conflict_retry_and_declined_confirmations(
    monkeypatch, apartments, bookings, demo, apartment
):
    first = bookings.create(apartment.id, "Existing", 2, "2027-06-10", "2027-06-15")
    output = run_menu(
        monkeypatch,
        apartments,
        bookings,
        demo,
        [
            "2",
            "2",
            "1",
            "Conflict",
            "1",
            "2027-06-12",
            "2027-06-14",
            "1",  # retry
            "1",
            "Adjacent",
            "1",
            "2027-06-15",
            "2027-06-18",
            "1",
            "4",
            "1",
            "0",  # decline cancellation
            "3",
            "0",  # back from selection
            "0",
            "1",
            "2",
            "0",  # back from form
            "2",
            "Unsaved",
            "City",
            "2",
            "50",
            "0",  # decline add
            "4",
            "1",
            "1",
            "0",  # archive blocked; back
            "0",
            "0",
        ],
    )
    assert bookings.list()[0] == first
    assert len(bookings.list()) == 2
    assert apartments.list() == [apartment]
    assert "UNAVAILABLE" in output
    assert "No changes were saved." in output
    assert "confirmed bookings prevent" in output


def test_empty_views_and_selections(monkeypatch, apartments, bookings, demo):
    output = run_menu(
        monkeypatch,
        apartments,
        bookings,
        demo,
        [
            "1",
            "1",
            "1",
            "0",
            "3",
            "4",
            "0",  # empty apartment views/selection
            "2",
            "1",
            "2",
            "3",
            "4",
            "0",  # empty booking views/selection
            "3",
            "0",
            "0",  # cancel search, exit
        ],
    )
    assert "No apartments" in output
    assert "No bookings" in output
    assert demo.counts() == (0, 0)


def test_numbered_prompt_rejects_invalid_and_oversized_input(monkeypatch):
    output = io.StringIO()
    monkeypatch.setattr("sys.stdin", io.StringIO("9" * 5000 + "\n-1\n2.0\n999\n2\n"))
    assert Prompts(Console(file=output)).choice("Choose: ", 3) == 2
    assert output.getvalue().count("ERROR:") == 4


@pytest.mark.parametrize("exception", [EOFError, KeyboardInterrupt])
def test_main_gracefully_handles_interrupts(monkeypatch, capsys, exception):
    def interrupt(self):
        raise exception

    monkeypatch.setattr(Menu, "run", interrupt)
    assert main() == 0
    captured = capsys.readouterr()
    assert "Goodbye" in captured.out
    assert "Traceback" not in captured.err


def test_main_exit_and_empty_database(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("0\n"))
    assert main() == 0
    assert "Goodbye" in capsys.readouterr().out


def test_main_bad_storage_path(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("APARTMENT_BOOKING_DB", str(tmp_path))
    assert main() == 1
    captured = capsys.readouterr()
    assert "ERROR:" in captured.err
    assert "Traceback" not in captured.err


def test_main_unexpected_failure_is_diagnostic(monkeypatch, capsys):
    def fail(self):
        raise RuntimeError("programming error")

    monkeypatch.setattr(Menu, "run", fail)
    assert main() == 1
    captured = capsys.readouterr()
    assert "Unexpected application failure" in captured.err
    assert "Traceback" in captured.err
    assert "RuntimeError: programming error" in captured.err
