"""In-memory stand-ins for the stores, the broker and the read model."""

from __future__ import annotations

import copy
from typing import Any

from dimora.projector.projector import BOOKINGS


class InMemoryReadStore:
    """Behaves like MongoReadStore, including its version guard."""

    def __init__(self) -> None:
        self.collections: dict[str, dict[int, dict[str, Any]]] = {}
        self.fail_after_upsert = False

    def _collection(self, name: str) -> dict[int, dict[str, Any]]:
        return self.collections.setdefault(name, {})

    def upsert_if_newer(self, collection: str, doc_id: int, version: int, fields: dict[str, Any]) -> bool:
        docs = self._collection(collection)
        current = docs.get(doc_id)
        if current is not None and current["version"] >= version:
            return False
        docs[doc_id] = {**(current or {"_id": doc_id}), **copy.deepcopy(fields), "version": version}
        if self.fail_after_upsert:
            self.fail_after_upsert = False
            raise ConnectionError("read store went away")
        return True

    def get(self, collection: str, doc_id: int) -> dict[str, Any] | None:
        doc = self._collection(collection).get(doc_id)
        return copy.deepcopy(doc) if doc else None

    def set_fields(self, collection: str, doc_id: int, fields: dict[str, Any]) -> None:
        if doc_id in self._collection(collection):
            self._collection(collection)[doc_id].update(copy.deepcopy(fields))

    def set_booking_apartment_fields(self, apartment_id: int, fields: dict[str, Any]) -> None:
        for doc in self._collection(BOOKINGS).values():
            if doc["apartment_id"] == apartment_id:
                doc.update(copy.deepcopy(fields))


class RecordingPublisher:
    def __init__(self, fail_on: int | None = None) -> None:
        self.published = []
        self.fail_on = fail_on
        self.closed = 0

    def publish(self, event) -> None:
        if self.fail_on is not None and len(self.published) == self.fail_on:
            raise ConnectionError("broker unreachable")
        self.published.append(event)

    def keep_alive(self) -> None:
        pass

    def close(self) -> None:
        self.closed += 1
