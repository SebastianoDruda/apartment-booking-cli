"""HTTP interface of the reservation service (writes only; reads go to the query service)."""

from __future__ import annotations

from collections.abc import Callable

import psycopg
from flask import Flask, jsonify

from dimora.common.consistency import format_token
from dimora.common.http import create_service_app, integer_value, json_data, parameters, text_value
from dimora.reservation.store import ReservationStore


def create_app(store: ReservationStore, on_write: Callable[[], None] = lambda: None) -> Flask:
    """``on_write`` runs after every committed change; it wakes the outbox relay."""
    app = create_service_app(
        "reservation",
        unavailable=(psycopg.OperationalError,),
        conflicts=(psycopg.IntegrityError,),
    )

    def written(result: dict, version: int, status: int = 200):
        on_write()
        return json_data(result, status, token=format_token("booking", result["id"], version))

    @app.get("/health")
    def health():
        return jsonify(data={"status": "ok", "database": "ok",
                             "pending_events": store.pending_count(),
                             "known_apartments": store.known_apartments()})

    @app.post("/api/bookings")
    def create_booking():
        values = parameters("apartment_name", "start_date", "end_date", "booker_name", "num_people")
        return written(*store.create_booking(
            text_value(values, "apartment_name"), text_value(values, "start_date"),
            text_value(values, "end_date"), text_value(values, "booker_name"),
            integer_value(values, "num_people"),
        ), status=201)

    @app.patch("/api/bookings")
    def change_booking():
        values = parameters("apartment_name", "start_date", "end_date",
                            "new_start_date", "new_end_date", "num_people")
        return written(*store.change_booking(
            text_value(values, "apartment_name"), text_value(values, "start_date"),
            text_value(values, "end_date"), text_value(values, "new_start_date"),
            text_value(values, "new_end_date"), integer_value(values, "num_people"),
        ))

    @app.delete("/api/bookings")
    def cancel_booking():
        values = parameters("apartment_name", "start_date", "end_date")
        return written(*store.cancel_booking(
            text_value(values, "apartment_name"), text_value(values, "start_date"),
            text_value(values, "end_date"),
        ))

    return app
