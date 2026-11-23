"""HTTP interface of the apartment service: every apartment read and write.

It also serves the entry points of the API itself (health, overview, OpenAPI
contract and the browser explorer), which the gateway routes here.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import apartment_booking.web
import psycopg
from flask import Flask, jsonify, render_template

from apartment_booking.database import format_address
from apartment_booking.web.api_docs import openapi_document
from dimora.apartment.store import ApartmentStore
from dimora.common.consistency import format_token
from dimora.common.http import (
    create_service_app, integer_value, json_data, parameters, price_value, read_your_writes,
    text_value,
)

# The browser API explorer of the original edition, served unchanged.
EXPLORER = Path(apartment_booking.web.__file__).resolve().parent

ROUTES = [
    {"path": "/api/apartments", "methods": ["GET", "POST"], "service": "apartment"},
    {"path": "/api/apartments/<name>/price", "methods": ["PATCH"], "service": "apartment"},
    {"path": "/api/apartments/<name>", "methods": ["DELETE"], "service": "apartment"},
    {"path": "/api/bookings", "methods": ["GET", "POST", "PATCH", "DELETE"], "service": "reservation"},
    {"path": "/api/availability", "methods": ["GET"], "service": "reservation"},
    {"path": "/api/health", "methods": ["GET"], "service": "apartment"},
    {"path": "/api/openapi.json", "methods": ["GET"], "service": "apartment"},
]


def create_app(store: ApartmentStore, on_write: Callable[[], None] = lambda: None,
               consistency_timeout: float = 3.0) -> Flask:
    """``on_write`` runs after every committed change; it wakes the outbox relay."""
    app = create_service_app(
        "apartment",
        unavailable=(psycopg.OperationalError,),
        conflicts=(psycopg.IntegrityError,),
        template_folder=str(EXPLORER / "templates"), static_folder=str(EXPLORER / "static"),
    )
    read_your_writes(app, store.current_version, consistency_timeout)

    def written(result: dict, version: int, status: int = 200):
        on_write()
        return json_data(result, status, token=format_token("apartment", result["id"], version))

    @app.get("/health")
    def health():
        return jsonify(data={"status": "ok", "database": "ok",
                             "pending_events": store.pending_count()})

    @app.get("/api/health")
    def api_health():
        store.ping()
        return jsonify(data={"status": "ok", "database": "ok"})

    @app.get("/api")
    def overview():
        return jsonify(data={
            "name": "Dimora HTTP API (microservices edition)",
            "usage": "Each resource is served, reads and writes alike, by the service that owns it.",
            "authentication": "None. Local development only; do not expose publicly.",
            "documentation": "/docs",
            "openapi": "/api/openapi.json",
            "routes": ROUTES,
        })

    @app.get("/docs")
    def documentation():
        response = app.make_response(render_template("api_docs.html"))
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/api/openapi.json")
    def openapi():
        return jsonify(openapi_document())

    @app.get("/api/apartments")
    def list_apartments():
        return json_data(store.list_apartments())

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
