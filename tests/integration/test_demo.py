import json

import pytest

from apartment_booking.errors import (
    OperationNotAllowedError,
    StorageError,
    ValidationError,
)
from apartment_booking.services.demo import DemoService
from apartment_booking.storage.database import transaction


def snapshot(apartments, bookings):
    return apartments.list("all"), bookings.list()


def test_demo_load_reimport_and_reset(demo, apartments, bookings):
    assert demo.counts() == (0, 0)
    assert demo.load() == (5, 6)
    original = snapshot(apartments, bookings)
    assert len(bookings.list(confirmed_only=True)) == 5
    with pytest.raises(OperationNotAllowedError, match="empty"):
        demo.load()
    assert snapshot(apartments, bookings) == original
    apartments.add("Extra", "City", 2, 100)
    modified = snapshot(apartments, bookings)
    for confirmation in ("", "reset", "yes", "RESET "):
        with pytest.raises(OperationNotAllowedError, match="RESET"):
            demo.load(reset=True, confirmation=confirmation)
        assert snapshot(apartments, bookings) == modified
    assert demo.load(reset=True, confirmation="RESET") == (5, 6)
    assert {a.id for a in apartments.list()} == {a.id for a in original[0]}
    assert {b.id for b in bookings.list()} == {b.id for b in original[1]}
    assert demo.counts() == (5, 6)


@pytest.mark.parametrize(
    "corruption",
    [
        "json",
        "version",
        "boolean_version",
        "root",
        "list",
        "missing",
        "id",
        "duplicate_apartment",
        "duplicate_booking",
        "reference",
        "overlap",
        "capacity",
        "price",
        "status",
        "active",
        "type",
        "date",
        "blank",
        "encoding",
    ],
)
def test_invalid_fixture_preserves_database(
    db, demo, apartments, bookings, tmp_path, corruption
):
    demo.load()
    before = snapshot(apartments, bookings)
    raw = json.loads(demo.fixture.read_text(encoding="utf-8"))
    match corruption:
        case "version":
            raw["schema_version"] = 2
        case "boolean_version":
            raw["schema_version"] = True
        case "root":
            raw = []
        case "list":
            raw["apartments"] = {}
        case "missing":
            del raw["bookings"][0]["guest_name"]
        case "id":
            raw["apartments"][0]["id"] = "bad"
        case "duplicate_apartment":
            raw["apartments"].append(raw["apartments"][0])
        case "duplicate_booking":
            raw["bookings"].append(raw["bookings"][3])
        case "reference":
            raw["bookings"][0]["apartment_id"] = "30000000-0000-4000-8000-000000000001"
        case "overlap":
            raw["bookings"][1]["check_in"] = "2027-06-14"
        case "capacity":
            raw["bookings"][0]["guest_count"] = 20
        case "price":
            raw["apartments"][0]["nightly_price_cents"] = 1.5
        case "status":
            raw["bookings"][0]["status"] = "UNKNOWN"
        case "active":
            raw["apartments"][0]["is_active"] = 1
        case "type":
            raw["apartments"][0] = 1
        case "date":
            raw["bookings"][0]["check_in"] = "2027-02-29"
        case "blank":
            raw["apartments"][0]["name"] = "  "
    source = tmp_path / "broken.json"
    source.write_text(
        "{" if corruption == "json" else json.dumps(raw), encoding="utf-8"
    )
    if corruption == "encoding":
        source.write_bytes(b"\xff")
    with pytest.raises(ValidationError):
        DemoService(db, source).load(reset=True, confirmation="RESET")
    assert snapshot(apartments, bookings) == before


def test_missing_fixture_and_invalid_empty_import(db, tmp_path, demo):
    with pytest.raises(ValidationError, match="Cannot read"):
        DemoService(db, tmp_path / "missing.json").load()
    raw = json.loads(demo.fixture.read_text(encoding="utf-8"))
    raw["bookings"][1]["check_in"] = "2027-06-11"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValidationError):
        DemoService(db, path).load()
    assert demo.counts() == (0, 0)


def test_failure_after_deletion_and_partial_insert_rolls_back(
    db, demo, apartments, bookings
):
    apartments.add("Keep me", "City", 2, 100)
    before = snapshot(apartments, bookings)
    with db.connection() as connection, transaction(connection):
        connection.execute("""CREATE TRIGGER simulate_disk_failure
            BEFORE INSERT ON bookings
            BEGIN SELECT RAISE(ABORT, 'simulated storage failure'); END""")
    with pytest.raises(StorageError, match="simulated storage failure"):
        demo.load(reset=True, confirmation="RESET")
    assert snapshot(apartments, bookings) == before


def test_demo_known_availability(demo, bookings):
    demo.load()
    assert {a.name for a in bookings.available("2027-06-12", "2027-06-14")} == {
        "Garden Loft",
        "Old Town Terrace",
    }
    assert bookings.available("2027-06-12", "2027-06-14", 6) == []
    assert len(bookings.available("2027-08-01", "2027-08-03")) == 5
