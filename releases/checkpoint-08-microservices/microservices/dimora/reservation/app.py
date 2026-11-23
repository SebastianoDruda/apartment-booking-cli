"""HTTP interface of the reservation service: every booking read and write.

The availability search is answered here too: it needs the bookings, and the
service's copy of the apartments holds everything else it shows.
"""

from __future__ import annotations

import psycopg
from flask import Flask, jsonify

from dimora.common.consistency import format_token
from dimora.common.http import (
    create_service_app, integer_value, json_data, parameters, read_your_writes, text_value,
)
from dimora.reservation.store import ReservationStore


def create_app(store: ReservationStore, consistency_timeout: float = 3.0) -> Flask:
    app = create_service_app(
        "reservation",
        unavailable=(psycopg.OperationalError,),
        conflicts=(psycopg.IntegrityError,),
    )
    # Bookings are written here, so a booking token is visible at once. An apartment
    # token waits until the apartment event has reached this service's copy.
    read_your_writes(app, store.current_version, consistency_timeout)

    def written(result: dict, version: int, status: int = 200):
        return json_data(result, status, token=format_token("booking", result["id"], version))

    @app.get("/health")
    def health():
        return jsonify(data={"status": "ok", "database": "ok",
                             "known_apartments": store.known_apartments()})

    @app.get("/api/bookings")
    def list_bookings():
        return json_data(store.list_bookings())

    @app.get("/api/availability")
    def availability():
        values = parameters("start_date", "end_date", "num_people", query=True)
        return json_data(store.search_available_apartments(
            text_value(values, "start_date"), text_value(values, "end_date"),
            integer_value(values, "num_people"),
        ))

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
