"""MongoDB implementation of the read store, shared by the projector and the query service."""

from __future__ import annotations

from typing import Any

from pymongo import ASCENDING, MongoClient
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from dimora.projector.projector import APARTMENTS, BOOKINGS


def connect(url: str, database: str) -> Database:
    client = MongoClient(url, serverSelectionTimeoutMS=3000, connectTimeoutMS=3000,
                         appname="dimora", tz_aware=True)
    return client[database]


def ensure_indexes(db: Database) -> None:
    db[APARTMENTS].create_index([("removed", ASCENDING), ("name_key", ASCENDING)])
    db[APARTMENTS].create_index([("removed", ASCENDING), ("price_per_night", ASCENDING)])
    db[BOOKINGS].create_index([("status", ASCENDING), ("start_date", ASCENDING)])
    db[BOOKINGS].create_index([("apartment_id", ASCENDING)])


class MongoReadStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    def upsert_if_newer(self, collection: str, doc_id: int, version: int, fields: dict[str, Any]) -> bool:
        try:
            self.db[collection].update_one(
                {"_id": doc_id, "version": {"$lt": version}},
                {"$set": {**fields, "version": version}},
                upsert=True,
            )
        except DuplicateKeyError:
            # The document exists with the same or a newer version: nothing to do.
            return False
        return True

    def get(self, collection: str, doc_id: int) -> dict[str, Any] | None:
        return self.db[collection].find_one({"_id": doc_id})

    def set_fields(self, collection: str, doc_id: int, fields: dict[str, Any]) -> None:
        self.db[collection].update_one({"_id": doc_id}, {"$set": fields})

    def set_booking_apartment_fields(self, apartment_id: int, fields: dict[str, Any]) -> None:
        self.db[BOOKINGS].update_many({"apartment_id": apartment_id}, {"$set": fields})
