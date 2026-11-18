"""HTTP interface of the apartment service (writes only; reads go to the query service)."""

from __future__ import annotations

from collections.abc import Callable

import psycopg
from flask import Flask, jsonify

from apartment_booking.database import format_address
from dimora.apartment.store import ApartmentStore
from dimora.common.consistency import format_token
from dimora.common.http import (
    create_service_app, integer_value, json_data, parameters, price_value, text_value,
)


def create_app(store: ApartmentStore, on_write: Callable[[], None] = lambda: None) -> Flask:
    """``on_write`` runs after every committed change; it wakes the outbox relay."""
    app = create_service_app(
        "apartment",
        unavailable=(psycopg.OperationalError,),
        conflicts=(psycopg.IntegrityError,),
    )

    def written(result: dict, version: int, status: int = 200):
        on_write()
        return json_data(result, status, token=format_token("apartment", result["id"], version))

    @app.get("/health")
    def health():
        return jsonify(data={"status": "ok", "database": "ok",
                             "pending_events": store.pending_count()})

    @app.post("/api/apartments")
    def add_apartment():
        values = parameters("name", "country", "city", "street_and_number", "max_people", "price_per_night")
        address = format_address(text_value(values, "country"), text_value(values, "city"),
                                 text_value(values, "street_and_number"))
        result, version = store.add_apartment(
            text_value(values, "name"), address, integer_value(values, "max_people"), price_value(values)
        )
        return written(result, version, 201)

    @app.patch("/api/apartments/<path:name>/price")
    def update_apartment_price(name):
        values = parameters("price_per_night")
        return written(*store.update_apartment_price(name, price_value(values)))

    @app.delete("/api/apartments/<path:name>")
    def remove_apartment(name):
        return written(*store.remove_apartment(name))

    return app
