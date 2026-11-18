"""Flask scaffolding shared by the HTTP services.

Request parsing and the JSON envelope come from the original Flask interface
(``apartment_booking.web.app``), so every edition validates input and reports
errors with the same codes and messages.
"""

from __future__ import annotations

import logging
from time import perf_counter

from flask import Flask, g, jsonify, request
from werkzeug.exceptions import HTTPException

from apartment_booking.database import BookingConflictError, RecordNotFoundError
from dimora.common.consistency import TOKEN_HEADER
from apartment_booking.web.app import (  # noqa: F401 - re-exported for the services
    error_response, integer_value, parameters, price_value, text_value,
)

MAX_BODY_BYTES = 64 * 1024


class ServiceUnavailable(Exception):
    """A backing store (PostgreSQL or MongoDB) cannot be reached right now."""


def create_service_app(name: str, unavailable: tuple[type[BaseException], ...] = (),
                       conflicts: tuple[type[BaseException], ...] = (), **flask_options) -> Flask:
    """Create a Flask app with JSON errors, request logging and no-store caching.

    ``unavailable`` lists driver exceptions that mean "storage down" (503) and
    ``conflicts`` those that mean a constraint rejected the write (409).
    """
    app = Flask(name, **flask_options)
    app.config.update(DEBUG=False, MAX_CONTENT_LENGTH=MAX_BODY_BYTES)
    app.json.compact = False
    log = logging.getLogger(f"dimora.{name}.http")

    @app.before_request
    def record_start():
        g.request_started = perf_counter()

    @app.after_request
    def log_response(response):
        elapsed = (perf_counter() - g.get("request_started", perf_counter())) * 1000
        # Log the route template, never bodies or guest names.
        route = request.url_rule.rule if request.url_rule else "<unmatched>"
        if route != "/health":
            log.info("%s %s status=%s duration_ms=%.1f", request.method, route,
                     response.status_code, elapsed)
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.errorhandler(ValueError)
    def invalid_input(error):
        return error_response("invalid_request", str(error), 400)

    @app.errorhandler(RecordNotFoundError)
    def record_not_found(error):
        return error_response("not_found", str(error), 404)

    @app.errorhandler(BookingConflictError)
    def booking_conflict(error):
        return error_response("conflict", str(error), 409)

    def storage_unavailable(_error):
        log.exception("Storage operation failed")
        response, status = error_response(
            "database_unavailable", "Database unavailable. Check storage access or retry shortly.", 503
        )
        response.headers["Retry-After"] = "1"
        return response, status

    for exception in (ServiceUnavailable, *unavailable):
        app.register_error_handler(exception, storage_unavailable)

    def constraint_conflict(_error):
        log.warning("Constraint conflict", exc_info=True)
        return error_response("conflict", "The operation conflicts with stored data.", 409)

    for exception in conflicts:
        app.register_error_handler(exception, constraint_conflict)

    @app.errorhandler(HTTPException)
    def http_error(error):
        # Keep protocol headers such as Allow on 405 and answer every error in JSON.
        response = error.get_response()
        response.data = app.json.dumps({"error": {
            "code": error.name.lower().replace(" ", "_"), "message": error.description,
        }})
        response.content_type = "application/json"
        return response

    @app.errorhandler(Exception)
    def unexpected_error(_error):
        log.exception("Unexpected request failure")
        return error_response("internal_error", "An unexpected server error occurred.", 500)

    return app


def json_data(payload, status: int = 200, token: str | None = None):
    """Wrap ``payload`` in the ``{"data": ...}`` envelope, optionally with a consistency token."""
    response = jsonify(data=payload)
    response.status_code = status
    if token:
        response.headers[TOKEN_HEADER] = token
    return response


def serve(app: Flask, port: int, threads: int = 8) -> None:
    """Run the app on waitress, a production WSGI server without native dependencies."""
    from waitress import serve as waitress_serve

    waitress_serve(app, host="0.0.0.0", port=port, threads=threads, ident="dimora")
