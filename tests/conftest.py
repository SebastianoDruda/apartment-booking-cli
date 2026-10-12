from datetime import date
from pathlib import Path

import pytest

from apartment_booking.services.apartments import ApartmentService
from apartment_booking.services.bookings import BookingService
from apartment_booking.services.demo import DemoService
from apartment_booking.storage.database import Database

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("APARTMENT_BOOKING_DB", str(tmp_path / "operator.db"))
    monkeypatch.setenv("NO_COLOR", "1")


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "test.db")
    database.initialize()
    return database


@pytest.fixture
def apartments(db):
    return ApartmentService(db, today=lambda: date(2027, 6, 12))


@pytest.fixture
def bookings(db):
    return BookingService(db)


@pytest.fixture
def apartment(apartments):
    return apartments.add("Mountain View", "Bolzano", 4, 12500)


@pytest.fixture
def demo(db):
    return DemoService(db, ROOT / "data/demo.json")
