from dataclasses import dataclass
from enum import StrEnum


class BookingStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class Apartment:
    id: str
    name: str
    city: str
    capacity: int
    nightly_price_cents: int
    is_active: bool
    created_at: str


@dataclass(frozen=True)
class Booking:
    id: str
    apartment_id: str
    guest_name: str
    guest_count: int
    check_in: str
    check_out: str
    status: BookingStatus
    created_at: str
    updated_at: str
