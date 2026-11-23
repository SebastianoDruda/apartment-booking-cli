"""HTTP interface of the query service: every GET of the public API."""

from __future__ import annotations

from pathlib import Path

import apartment_booking.web
from flask import Flask, g, jsonify, render_template, request
from pymongo.errors import ConnectionFailure

from apartment_booking.web.api_docs import openapi_document
from dimora.common.consistency import STATUS_HEADER, WAIT_HEADER, parse_tokens, wait_until_visible
from dimora.common.http import create_service_app, integer_value, json_data, parameters, text_value
from dimora.query.read_model import ReadModel

# The browser API explorer of the original edition, served unchanged.
EXPLORER = Path(apartment_booking.web.__file__).resolve().parent

ROUTES = [
    {"path": "/api/apartments", "methods": ["GET"], "service": "query"},
    {"path": "/api/apartments", "methods": ["POST"], "service": "apartment"},
    {"path": "/api/apartments/<name>/price", "methods": ["PATCH"], "service": "apartment"},
    {"path": "/api/apartments/<name>", "methods": ["DELETE"], "service": "apartment"},
    {"path": "/api/bookings", "methods": ["GET"], "service": "query"},
    {"path": "/api/bookings", "methods": ["POST", "PATCH", "DELETE"], "service": "reservation"},
    {"path": "/api/availability", "methods": ["GET"], "service": "query"},
    {"path": "/api/health", "methods": ["GET"], "service": "query"},
    {"path": "/api/openapi.json", "methods": ["GET"], "service": "query"},
]


def create_app(read_model: ReadModel, consistency_timeout: float = 3.0) -> Flask:
    app = create_service_app(
        "query", unavailable=(ConnectionFailure,),
        template_folder=str(EXPLORER / "templates"), static_folder=str(EXPLORER / "static"),
    )

    @app.before_request
    def wait_for_own_writes():
        """Honour X-Wait-For so a client reads the result of its own last write."""
        tokens = parse_tokens(request.headers.get(WAIT_HEADER))
        if tokens:
            fresh = wait_until_visible(tokens, read_model.current_version, consistency_timeout)
            g.consistency = "fresh" if fresh else "stale"

    @app.after_request
    def report_consistency(response):
        if "consistency" in g:
            response.headers[STATUS_HEADER] = g.consistency
        return response

    @app.get("/health")
    @app.get("/api/health")
    def health():
        read_model.ping()
        return jsonify(data={"status": "ok", "database": "ok"})

    @app.get("/api")
    def overview():
        return jsonify(data={
            "name": "Dimora HTTP API (event-driven edition)",
            "usage": "GET reads the read model. POST, PATCH and DELETE go to the command services.",
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
        return json_data(read_model.list_apartments())

    @app.get("/api/bookings")
    def list_bookings():
        return json_data(read_model.list_bookings())

    @app.get("/api/availability")
    def availability():
        values = parameters("start_date", "end_date", "num_people", query=True)
        return json_data(read_model.search_available_apartments(
            text_value(values, "start_date"), text_value(values, "end_date"),
            integer_value(values, "num_people"),
        ))

    return app
