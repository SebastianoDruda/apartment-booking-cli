"""Read-only access to the views built by the projector.

No business rules live here: the projector has already joined bookings with
their apartments and computed nights and totals. Availability is answered from
the same two views.
"""

from __future__ import annotations

from typing import Any

from pymongo import ASCENDING
from pymongo.database import Database

from apartment_booking.database import calculate_total_price, validate_date_range
from dimora.projector.projector import APARTMENTS, BOOKINGS

VISIBLE_BOOKING = {
    "status": "active",
    "apartment_removed": False,
    "apartment_name": {"$type": "string"},
}


def apartment(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": doc["_id"],
        "name": doc["name"],
        "address": doc["address"],
        "max_people": doc["max_people"],
        "price_per_night": doc["price_per_night"],
    }


def booking(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": doc["_id"],
        "apartment_id": doc["apartment_id"],
        "booker_name": doc["booker_name"],
        "start_date": doc["start_date"],
        "end_date": doc["end_date"],
        "num_people": doc["num_people"],
        "apartment_name": doc["apartment_name"],
        "apartment_address": doc["apartment_address"],
        "apartment_max_people": doc["apartment_max_people"],
        "price_per_night": doc["price_per_night"],
        "nights": doc["nights"],
        "total_price": doc["total_price"],
    }


class ReadModel:
    def __init__(self, db: Database) -> None:
        self.db = db

    def ping(self) -> None:
        self.db.command("ping")

    def list_apartments(self) -> list[dict[str, Any]]:
        cursor = self.db[APARTMENTS].find({"removed": False}).sort("name_key", ASCENDING)
        return [apartment(doc) for doc in cursor]

    def list_bookings(self) -> list[dict[str, Any]]:
        cursor = self.db[BOOKINGS].find(VISIBLE_BOOKING).sort(
            [("start_date", ASCENDING), ("apartment_name_key", ASCENDING)]
        )
        return [booking(doc) for doc in cursor]

    def search_available_apartments(self, start_date_str: str, end_date_str: str,
                                    num_people: int) -> list[dict[str, Any]]:
        start_iso, end_iso, nights = validate_date_range(start_date_str, end_date_str)
        people = int(num_people)
        if people <= 0:
            raise ValueError("Number of people must be at least 1.")

        # ISO dates compare correctly as strings.
        busy = self.db[BOOKINGS].distinct("apartment_id", {
            "status": "active", "start_date": {"$lt": end_iso}, "end_date": {"$gt": start_iso},
        })
        cursor = self.db[APARTMENTS].find({
            "removed": False, "max_people": {"$gte": people}, "_id": {"$nin": busy},
        }).sort([("price_per_night", ASCENDING), ("name_key", ASCENDING)])

        results = []
        for doc in cursor:
            item = apartment(doc)
            item.update({
                "nights": nights,
                "total_price": calculate_total_price(nights, item["price_per_night"]),
                "start_date": start_iso,
                "end_date": end_iso,
            })
            results.append(item)
        return results

    def current_version(self, aggregate: str, entity_id: int) -> int | None:
        collection = APARTMENTS if aggregate == "apartment" else BOOKINGS
        doc = self.db[collection].find_one({"_id": entity_id}, {"version": 1})
        return doc["version"] if doc else None
