import os
import subprocess
import sys
from pathlib import Path

import pytest

from apartment_booking.models import BookingStatus
from apartment_booking.services.apartments import ApartmentService
from apartment_booking.services.bookings import BookingService
from apartment_booking.storage.database import Database

ROOT = Path(__file__).resolve().parents[2]


def launch(path, inputs):
    env = {
        **os.environ,
        "APARTMENT_BOOKING_DB": str(path),
        "NO_COLOR": "1",
        "COLUMNS": "90",
        "PYTHONIOENCODING": "utf-8",
    }
    return subprocess.run(
        [sys.executable, "-m", "apartment_booking"],
        input="\n".join(inputs) + "\n" if inputs else "",
        text=True,
        encoding="utf-8",
        capture_output=True,
        cwd=ROOT,
        env=env,
        timeout=20,
    )


def test_scripted_demo_journey_and_restart(tmp_path):
    path = tmp_path / "journey.db"
    result = launch(
        path,
        [
            "4",
            "1",
            "0",  # demo
            "1",
            "1",
            "0",
            "0",  # view apartments
            "3",
            "2027-06-12",
            "2027-06-14",
            "6",  # unavailable
            "3",
            "2027-06-12",
            "2027-06-14",
            "1",  # available
            "2",
            "1",
            "4",
            "2",
            "1",
            "0",  # view and cancel Alex
            "3",
            "2027-06-12",
            "2027-06-14",
            "1",
            "0",  # released availability
        ],
    )
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr
    for expected in (
        "SUCCESS: Sample data loaded",
        "Mountain View",
        "AVAILABLE: 0 apartment(s)",
        "AVAILABLE: 2 apartment(s)",
        "SUCCESS: Booking cancelled",
        "AVAILABLE: 3 apartment(s)",
        "Goodbye",
    ):
        assert expected in result.stdout
    assert "\x1b[" not in result.stdout
    db = Database(path)
    assert len(ApartmentService(db).list()) == 5
    bookings = BookingService(db).list()
    assert len(bookings) == 6
    assert (
        next(b for b in bookings if b.guest_name == "Alex Morgan").status
        == BookingStatus.CANCELLED
    )
    restarted = launch(path, ["2", "1", "0", "0"])
    assert restarted.returncode == 0
    assert "cancelled" in restarted.stdout
    assert BookingService(db).list() == bookings


@pytest.mark.parametrize("inputs", [[], ["1", "2", "Name"], ["4", "2"]])
def test_eof_at_menu_or_mid_action_saves_nothing(tmp_path, inputs):
    path = tmp_path / "eof.db"
    result = launch(path, inputs)
    assert result.returncode == 0, result.stderr
    assert "Goodbye" in result.stdout
    assert "Traceback" not in result.stderr
    assert ApartmentService(Database(path)).list("all") == []


def test_reset_typo_and_confirmation_persisted(tmp_path):
    path = tmp_path / "reset.db"
    result = launch(
        path,
        [
            "1",
            "2",
            "Original",
            "City",
            "2",
            "20",
            "1",
            "0",
            "4",
            "2",
            "RESET ",
            "0",
            "0",
        ],
    )
    assert result.returncode == 0, result.stderr
    db = Database(path)
    assert [a.name for a in ApartmentService(db).list()] == ["Original"]
    reset = launch(path, ["4", "2", "RESET", "0", "0"])
    assert reset.returncode == 0, reset.stderr
    assert len(ApartmentService(db).list()) == 5
    assert len(BookingService(db).list()) == 6
