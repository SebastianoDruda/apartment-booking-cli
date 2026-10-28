"""Local HTTP presentation layer for the existing booking database.

Start with: python -m flask --app src.web:create_app run --no-debugger --no-reload --port 8000
"""

from __future__ import annotations

import logging
import os
import sqlite3
from time import perf_counter

from flask import Flask, current_app, g, jsonify, request
from werkzeug.exceptions import HTTPException

from src.database import BookingDatabase, DEFAULT_DB_PATH


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
            "routes": routes,
        })

    @app.get("/api/health")
    def health():
        # Reuse a read-only business operation to verify that the database is accessible.
        get_database().list_apartments()
        return jsonify(data={"status": "ok", "database": "ok"})

    return app
