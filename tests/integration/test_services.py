from dataclasses import replace
from datetime import date

import pytest

from apartment_booking.errors import (
    BookingConflictError,
    NotFoundError,
    OperationNotAllowedError,
    ValidationError,
)
from apartment_booking.models import BookingStatus
from apartment_booking.services.apartments import ApartmentService
from apartment_booking.services.bookings import BookingService
from apartment_booking.storage.database import Database
from apartment_booking.storage.repositories import Repository


def create(bookings, apartment_id, start="2027-06-10", end="2027-06-15", guests=2):
    return bookings.create(apartment_id, "Alex Morgan", guests, start, end)


def test_initialization_and_persistence(db, apartments, bookings, apartment):
    booking = create(bookings, apartment.id)
    restarted = Database(db.path)
    restarted.initialize()
    assert ApartmentService(restarted).list() == [apartment]
    assert BookingService(restarted).list() == [booking]
    with restarted.connection() as connection:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        assert {r[0] for r in tables} == {"apartments", "bookings"}
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


@pytest.mark.parametrize(
    "fields",
    [
        ("", "Bolzano", 2, 100),
        ("Room", "", 2, 100),
        ("Room", "City", 0, 100),
        ("Room", "City", 21, 100),
        ("Room", "City", 2, 0),
        ("Room", "City", 2, True),
    ],
)
def test_invalid_apartment_no_write(apartments, fields):
    with pytest.raises(ValidationError):
        apartments.add(*fields)
    assert apartments.list("all") == []


def test_update_and_capacity_guard(apartments, bookings, apartment):
    create(bookings, apartment.id, guests=4)
    with pytest.raises(OperationNotAllowedError, match="Capacity"):
        apartments.update(apartment.id, "Changed", apartment.city, 3, 9000)
    assert apartments.list() == [apartment]
    updated = apartments.update(apartment.id, " New name ", "Trento", 5, 9500)
    assert updated == replace(
        apartment, name="New name", city="Trento", capacity=5, nightly_price_cents=9500
    )
    assert apartments.list() == [updated]


@pytest.mark.parametrize(
    "start,end", [("2027-06-10", "2027-06-15"), ("2027-07-10", "2027-07-15")]
)
def test_archive_blocked_identifies_booking(
    apartments, bookings, apartment, start, end
):
    booking = create(bookings, apartment.id, start, end)
    with pytest.raises(
        OperationNotAllowedError, match=f"{booking.guest_name}: {start} to {end}"
    ):
        apartments.archive(apartment.id)
    assert apartments.list() == [apartment]
    assert bookings.list() == [booking]


@pytest.mark.parametrize("end", ["2027-06-11", "2027-06-12"])
def test_past_or_checkout_today_allows_reduction_and_archive(
    apartments, bookings, apartment, end
):
    booking = create(bookings, apartment.id, end=end, guests=4)
    apartments.update(apartment.id, apartment.name, apartment.city, 1, 12500)
    archived = apartments.archive(apartment.id)
    assert archived.is_active is False
    assert apartments.list() == []
    assert apartments.list("archived") == [archived]
    assert apartments.list("all") == [archived]
    assert bookings.list() == [booking]
    assert bookings.available("2027-08-01", "2027-08-03") == []
    with pytest.raises(OperationNotAllowedError, match="archived"):
        create(bookings, apartment.id)
    with pytest.raises(OperationNotAllowedError, match="archived"):
        apartments.update(apartment.id, "New", "City", 4, 100)
    with pytest.raises(OperationNotAllowedError, match="archived"):
        apartments.archive(apartment.id)
    with pytest.raises(OperationNotAllowedError, match="archived"):
        bookings.change(booking.id, "Alex", 1, "2027-08-01", "2027-08-02")


@pytest.mark.parametrize(
    "start,end,conflict",
    [
        ("12", "16", True),
        ("08", "12", True),
        ("09", "17", True),
        ("10", "15", True),
        ("11", "14", True),
        ("15", "18", False),
        ("08", "10", False),
    ],
)
def test_overlap_matrix(apartment, bookings, start, end, conflict):
    first = create(bookings, apartment.id)
    start, end = f"2027-06-{start}", f"2027-06-{end}"
    if conflict:
        with pytest.raises(BookingConflictError):
            create(bookings, apartment.id, start, end)
        assert bookings.list() == [first]
        assert bookings.available(start, end) == []
    else:
        assert bookings.available(start, end) == [apartment]
        create(bookings, apartment.id, start, end)
        assert len(bookings.list()) == 2


def test_other_apartment_and_cancelled_do_not_block(apartments, bookings, apartment):
    second = apartments.add("Another", "Trento", 2, 8000)
    first_booking = create(bookings, apartment.id)
    create(bookings, second.id)
    cancelled = bookings.cancel(first_booking.id)
    assert cancelled.status == BookingStatus.CANCELLED
    assert cancelled.created_at == first_booking.created_at
    assert cancelled.updated_at >= first_booking.updated_at
    assert bookings.available("2027-06-10", "2027-06-15") == [apartment]
    create(bookings, apartment.id)
    assert len(bookings.list()) == 3


def test_change_excludes_itself_and_failure_preserves_original(apartment, bookings):
    booking = create(bookings, apartment.id)
    updated = bookings.change(booking.id, "Jamie", 4, "2027-06-10", "2027-06-16")
    assert updated.guest_name == "Jamie"
    assert updated.guest_count == 4
    assert updated.apartment_id == apartment.id
    assert updated.created_at == booking.created_at
    other = create(bookings, apartment.id, "2027-06-16", "2027-06-20")
    with pytest.raises(BookingConflictError):
        bookings.change(updated.id, "Wrong", 1, "2027-06-15", "2027-06-17")
    assert bookings.list() == [updated, other]
    with pytest.raises(ValidationError):
        bookings.change(updated.id, "Wrong", 5, "2027-06-10", "2027-06-15")
    assert bookings.list() == [updated, other]


@pytest.mark.parametrize(
    "guest,count,start,end",
    [
        ("", 2, "2027-06-10", "2027-06-15"),
        ("Alex", 0, "2027-06-10", "2027-06-15"),
        ("Alex", 5, "2027-06-10", "2027-06-15"),
        ("Alex", 2, "2027-02-29", "2027-06-15"),
        ("Alex", 2, "2027-06-15", "2027-06-10"),
    ],
)
def test_invalid_booking_zero_writes(bookings, apartment, guest, count, start, end):
    with pytest.raises(ValidationError):
        bookings.create(apartment.id, guest, count, start, end)
    assert bookings.list() == []


def test_cancelled_is_immutable_and_allows_archive(apartments, bookings, apartment):
    booking = create(bookings, apartment.id)
    cancelled = bookings.cancel(booking.id)
    with pytest.raises(OperationNotAllowedError, match="already cancelled"):
        bookings.cancel(booking.id)
    with pytest.raises(OperationNotAllowedError, match="already cancelled"):
        bookings.change(booking.id, "Other", 1, "2027-07-01", "2027-07-02")
    assert bookings.list() == [cancelled]
    assert bookings.list(confirmed_only=True) == []
    apartments.archive(apartment.id)
    assert bookings.list() == [cancelled]


def test_availability_capacity_active_and_dates(apartments, bookings, apartment):
    small = apartments.add("Small", "City", 1, 1000)
    archived = apartments.add("Archived", "City", 10, 1000)
    apartments.archive(archived.id)
    create(bookings, apartment.id)
    assert bookings.available("2027-06-12", "2027-06-14") == [small]
    assert bookings.available("2027-06-15", "2027-06-18", 2) == [apartment]
    assert bookings.available("2027-06-12", "2027-06-14", 2) == []
    with pytest.raises(ValidationError):
        bookings.available("2027-06-10", "2027-06-10")
    with pytest.raises(ValidationError):
        bookings.available("2027-06-10", "2027-06-15", 0)


def test_missing_records_and_invalid_filter(db, apartments, bookings):
    for action in [
        lambda: apartments.archive("missing"),
        lambda: bookings.cancel("missing"),
        lambda: create(bookings, "missing"),
    ]:
        with pytest.raises(NotFoundError):
            action()
    with pytest.raises(ValidationError):
        apartments.list("bad")
    with db.connection() as connection:
        assert Repository(connection).counts() == (0, 0)


def test_injected_local_date_makes_rules_independent_of_fixture_year(
    db, bookings, apartment
):
    create(bookings, apartment.id)
    service = ApartmentService(db, today=lambda: date(2030, 1, 1))
    assert service.archive(apartment.id).is_active is False


def test_sql_and_markup_characters_are_literal_data(apartments, bookings):
    apartment = apartments.add("[red]'); DROP TABLE apartments;--", "City", 2, 100)
    booking = bookings.create(
        apartment.id, "[bold]Guest[/bold]", 1, "2020-01-01", "2020-01-02"
    )
    assert apartments.list() == [apartment]
    assert bookings.list() == [booking]
