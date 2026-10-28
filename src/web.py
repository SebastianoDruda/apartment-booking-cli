"""Local HTTP presentation layer for the existing booking database.

Start with: python -m flask --app src.web:create_app run --no-debugger --no-reload --port 8000
"""

from __future__ import annotations

import logging
import os
import sqlite3
from time import perf_counter

from flask import Flask, current_app, g, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from src.api_docs import openapi_document
from src.database import (
    BookingDatabase, BookingConflictError, DEFAULT_DB_PATH, RecordNotFoundError,
    format_address, parse_price_input,
)


def parameters(*fields: str, query: bool = False) -> dict:
    """Validate the HTTP envelope; business validation stays in BookingDatabase."""
    if query:
        values = request.args.to_dict()
        if any(len(request.args.getlist(key)) != 1 for key in request.args):
            raise ValueError("Query parameters must appear exactly once.")
    else:
        values = request.get_json()
        if not isinstance(values, dict):
            raise ValueError("The JSON body must be an object.")
    missing = sorted(set(fields) - values.keys())
    unknown = sorted(values.keys() - set(fields))
    if missing:
        raise ValueError("Missing fields: " + ", ".join(missing) + ".")
    if unknown:
        raise ValueError("Unknown fields: " + ", ".join(unknown) + ".")
    return values


def text_value(values: dict, field: str) -> str:
    value = values[field]
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string.")
    return value.strip()


def integer_value(values: dict, field: str) -> int:
    value = values[field]
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(f"{field} must be a whole number.")
    try:
        value = int(value)
    except ValueError as error:
        raise ValueError(f"{field} must be a whole number.") from error
    if not -(2 ** 63) <= value < 2 ** 63:
        raise ValueError(f"{field} is outside the supported integer range.")
    return value


def price_value(values: dict) -> float:
    value = values["price_per_night"]
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError("price_per_night must be a number or price string.")
    return parse_price_input(str(value))


def get_database() -> BookingDatabase:
    """Use a request-local wrapper; never share SQLite connections across threads."""
    if "booking_database" not in g:
        g.booking_database = BookingDatabase(current_app.config["DATABASE_PATH"])
    return g.booking_database


def error_response(code: str, message: str, status: int):
    return jsonify(error={"code": code, "message": message}), status


def create_app(config: dict | None = None) -> Flask:
    """Create an independent app; tests supply an isolated DATABASE_PATH."""
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE_PATH=os.environ.get("APARTMENT_BOOKING_DB_PATH") or str(DEFAULT_DB_PATH),
        DEBUG=False,
        MAX_CONTENT_LENGTH=64 * 1024,
    )
    if config:
        app.config.update(config)
    app.json.compact = False
    app.logger.setLevel(logging.INFO)

    @app.before_request
    def record_start():
        g.request_started = perf_counter()

    @app.after_request
    def log_response(response):
        elapsed = (perf_counter() - g.get("request_started", perf_counter())) * 1000
        # Log the route template, not bodies or guest names.
        route = request.url_rule.rule if request.url_rule else "<unmatched>"
        app.logger.info("%s %s status=%s duration_ms=%.1f", request.method, route,
                        response.status_code, elapsed)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.teardown_appcontext
    def close_database(_error):
        database = g.pop("booking_database", None)
        if database is not None:
            database.close()

    @app.errorhandler(ValueError)
    def invalid_input(error):
        return error_response("invalid_request", str(error), 400)

    @app.errorhandler(RecordNotFoundError)
    def record_not_found(error):
        return error_response("not_found", str(error), 404)

    @app.errorhandler(BookingConflictError)
    def booking_conflict(error):
        return error_response("conflict", str(error), 409)

    @app.errorhandler(sqlite3.OperationalError)
    def database_unavailable(error):
        app.logger.exception("Database operation failed")
        response, status = error_response(
            "database_unavailable", "Database unavailable. Check storage access or retry shortly.", 503
        )
        response.headers["Retry-After"] = "1"
        return response, status

    @app.errorhandler(sqlite3.IntegrityError)
    def integrity_conflict(error):
        app.logger.warning("Database integrity conflict", exc_info=True)
        return error_response("conflict", "The operation conflicts with stored data.", 409)

    @app.errorhandler(HTTPException)
    def http_error(error):
        # Preserve protocol headers such as Allow on 405 and return JSON for all errors.
        response = error.get_response()
        response.data = app.json.dumps({"error": {
            "code": error.name.lower().replace(" ", "_"), "message": error.description,
        }})
        response.content_type = "application/json"
        return response

    @app.errorhandler(Exception)
    def unexpected_error(error):
        app.logger.exception("Unexpected request failure")
        return error_response("internal_error", "An unexpected server error occurred.", 500)

    @app.get("/")
    def overview():
        routes = [
            {"path": rule.rule, "methods": sorted(rule.methods - {"HEAD", "OPTIONS"})}
            for rule in app.url_map.iter_rules() if rule.endpoint != "static"
        ]
        return jsonify(data={
            "name": "Apartment Booking HTTP API",
            "usage": "GET reads data. Send JSON with POST, PATCH or DELETE to make changes.",
            "authentication": "None. Local development only; do not expose publicly.",
            "documentation": "/docs",
            "openapi": "/api/openapi.json",
            "routes": routes,
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

    @app.get("/api/health")
    def health():
        # Reuse a read-only business operation to verify that the database is accessible.
        get_database().list_apartments()
        return jsonify(data={"status": "ok", "database": "ok"})

    @app.get("/api/apartments")
    def list_apartments():
        return jsonify(data=get_database().list_apartments())

    @app.post("/api/apartments")
    def add_apartment():
        values = parameters("name", "country", "city", "street_and_number", "max_people", "price_per_night")
        address = format_address(text_value(values, "country"), text_value(values, "city"),
                                 text_value(values, "street_and_number"))
        result = get_database().add_apartment(
            text_value(values, "name"), address, integer_value(values, "max_people"), price_value(values)
        )
        return jsonify(data=result), 201

    @app.patch("/api/apartments/<path:name>/price")
    def update_apartment_price(name):
        values = parameters("price_per_night")
        return jsonify(data=get_database().update_apartment_price(name, price_value(values)))

    @app.delete("/api/apartments/<path:name>")
    def remove_apartment(name):
        return jsonify(data=get_database().remove_apartment(name))

    @app.get("/api/bookings")
    def list_bookings():
        return jsonify(data=get_database().list_bookings())

    @app.post("/api/bookings")
    def create_booking():
        values = parameters("apartment_name", "start_date", "end_date", "booker_name", "num_people")
        result = get_database().create_booking(
            text_value(values, "apartment_name"), text_value(values, "start_date"),
            text_value(values, "end_date"), text_value(values, "booker_name"),
            integer_value(values, "num_people"),
        )
        return jsonify(data=result), 201

    @app.patch("/api/bookings")
    def change_booking():
        values = parameters("apartment_name", "start_date", "end_date",
                            "new_start_date", "new_end_date", "num_people")
        result = get_database().change_booking(
            text_value(values, "apartment_name"), text_value(values, "start_date"),
            text_value(values, "end_date"), text_value(values, "new_start_date"),
            text_value(values, "new_end_date"), integer_value(values, "num_people"),
        )
        return jsonify(data=result)

    @app.delete("/api/bookings")
    def cancel_booking():
        values = parameters("apartment_name", "start_date", "end_date")
        return jsonify(data=get_database().cancel_booking(
            text_value(values, "apartment_name"), text_value(values, "start_date"),
            text_value(values, "end_date"),
        ))

    @app.get("/api/availability")
    def availability():
        values = parameters("start_date", "end_date", "num_people", query=True)
        return jsonify(data=get_database().search_available_apartments(
            text_value(values, "start_date"), text_value(values, "end_date"),
            integer_value(values, "num_people"),
        ))

    return app
