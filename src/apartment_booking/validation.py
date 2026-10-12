"""Shared, terminal-independent input validation."""

import re
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

from apartment_booking.errors import ValidationError

MAX_CENTS = 2**63 - 1


def text(value: str, field: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 80:
        raise ValidationError(f"{field} must contain 1–80 characters.")
    value = value.strip()
    if any(not char.isprintable() for char in value):
        raise ValidationError(f"{field} must not contain control characters.")
    return value


def integer(value: int, field: str, maximum: int = 20) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValidationError(f"{field} must be a whole number from 1 to {maximum}.")
    return value


def cents(value: int) -> int:
    return integer(value, "Nightly price in cents", MAX_CENTS)


def price(value: str) -> int:
    """Convert an ordinary decimal EUR amount into exact integer cents."""
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", value):
        raise ValidationError(
            "Enter a positive EUR price, e.g. 125.50 (max 2 decimals)."
        )
    try:
        amount = Decimal(value) * 100
        if amount > MAX_CENTS:
            raise ValidationError("Nightly price is too large.")
        return cents(int(amount))
    except InvalidOperation as exc:
        raise ValidationError("Enter a valid EUR price, e.g. 125.50.") from exc


def iso_date(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValidationError("Use YYYY-MM-DD, e.g. 2027-06-10.")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(
            "Enter a real calendar date in YYYY-MM-DD format."
        ) from exc
    return value


def period(check_in: str, check_out: str) -> tuple[str, str]:
    start, end = iso_date(check_in), iso_date(check_out)
    if end <= start:
        raise ValidationError("Check-out must be later than check-in.")
    return start, end


def uuid_string(value: str) -> str:
    try:
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError
    except ValueError as exc:
        raise ValidationError("Fixture IDs must be canonical UUID strings.") from exc
    return value


def timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")
