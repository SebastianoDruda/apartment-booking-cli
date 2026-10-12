import pytest

from apartment_booking import validation
from apartment_booking.cli.display import money
from apartment_booking.errors import ValidationError


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1", 100),
        ("125.50", 12550),
        ("0.01", 1),
        ("12.3", 1230),
        ("90071992547409.93", 9007199254740993),
    ],
)
def test_prices_are_exact(raw, expected):
    assert validation.price(raw) == expected
    assert money(expected) == f"EUR {expected // 100}.{expected % 100:02d}"


@pytest.mark.parametrize(
    "raw",
    ["", "0", "-1", "NaN", "Infinity", "1.001", "1e3", "1,20", "12.", ".10", "9" * 80],
)
def test_invalid_prices(raw):
    with pytest.raises(ValidationError):
        validation.price(raw)


@pytest.mark.parametrize("value", [0, -1, 21, 1.5, True, "2", None])
def test_integer_rules(value):
    with pytest.raises(ValidationError):
        validation.integer(value, "Capacity")


@pytest.mark.parametrize(
    "value", ["", "  ", "x" * 81, None, "hello\x1b[31m", "two\nlines"]
)
def test_names_reject_empty_long_or_control_characters(value):
    with pytest.raises(ValidationError):
        validation.text(value, "Name")


def test_trim_and_leap_date():
    assert validation.text("  Lake House  ", "Name") == "Lake House"
    assert validation.iso_date("2028-02-29") == "2028-02-29"


@pytest.mark.parametrize(
    "value",
    [
        "2027-02-29",
        "2027-13-01",
        "2027-04-31",
        "20270610",
        "2027-6-10",
        "2027-W23-1",
        "0000-01-01",
        None,
    ],
)
def test_invalid_dates(value):
    with pytest.raises(ValidationError):
        validation.iso_date(value)


@pytest.mark.parametrize(
    "start,end", [("2027-06-10", "2027-06-10"), ("2027-06-11", "2027-06-10")]
)
def test_invalid_period(start, end):
    with pytest.raises(ValidationError, match="later"):
        validation.period(start, end)


@pytest.mark.parametrize("value", ["bad", None, 12, "10000000000040008000000000000001"])
def test_invalid_uuid(value):
    with pytest.raises(ValidationError, match="UUID"):
        validation.uuid_string(value)
