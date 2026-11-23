"""Flask scaffolding shared by the HTTP services.

Request parsing and the JSON envelope come from the original Flask interface
(``apartment_booking.web.app``), so every edition validates input and reports
errors with the same codes and messages.
"""

from __future__ import annotations

import faulthandler
import logging
import os
import signal
import threading
from collections.abc import Callable
from time import monotonic, perf_counter, sleep

from flask import Flask, g, jsonify, request
from werkzeug.exceptions import HTTPException
from werkzeug.wsgi import ClosingIterator

from apartment_booking.database import BookingConflictError, RecordNotFoundError
from dimora.common.consistency import (
    STATUS_HEADER, TOKEN_HEADER, WAIT_HEADER, parse_tokens, wait_until_visible,
)
from apartment_booking.web.app import (  # noqa: F401 - re-exported for the services
    error_response, integer_value, parameters, price_value, text_value,
)

MAX_BODY_BYTES = 64 * 1024


class ServiceUnavailable(Exception):
    """A backing store (PostgreSQL) cannot be reached right now."""


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


def read_your_writes(app: Flask, current_version: Callable[[str, int], int | None],
                     timeout: float) -> None:
    """Honour ``X-Wait-For`` on reads, and report the outcome in ``X-Consistency``.

    ``current_version(aggregate, id)`` returns the version this service holds,
    or ``None`` when it does not know the row yet.
    """

    @app.before_request
    def wait_for_own_writes():
        if request.method != "GET":
            return
        tokens = parse_tokens(request.headers.get(WAIT_HEADER))
        if tokens:
            fresh = wait_until_visible(tokens, current_version, timeout)
            g.consistency = "fresh" if fresh else "stale"

    @app.after_request
    def report_consistency(response):
        if "consistency" in g:
            response.headers[STATUS_HEADER] = g.consistency
        return response


def json_data(payload, status: int = 200, token: str | None = None):
    """Wrap ``payload`` in the ``{"data": ...}`` envelope, optionally with a consistency token."""
    response = jsonify(data=payload)
    response.status_code = status
    if token:
        response.headers[TOKEN_HEADER] = token
    return response


class GracefulShutdown:
    """WSGI middleware that lets a stopping service finish its requests first.

    On SIGTERM (``docker stop``, a restart, a scale-down) the service stops
    accepting connections, so the gateway sends new requests to another replica
    (it opens one connection per request), and finishes what is already in flight.
    Once no request is running and no connection is busy (a request may still be
    queued for a worker thread, or a response still being written), or ``grace``
    seconds have passed, the process exits.
    Without it, a POST that was in flight when the container stopped would be lost:
    the gateway may not send a non-idempotent request again.
    """

    def __init__(self, wsgi_app, grace: float = 8.0, exit=os._exit) -> None:
        self.wsgi_app = wsgi_app
        self.grace = grace
        self.exit = exit
        self.active = 0
        self.lock = threading.Lock()
        self.draining = threading.Event()

    def __call__(self, environ, start_response):
        with self.lock:
            self.active += 1
        try:
            result = self.wsgi_app(environ, start_response)
        except BaseException:
            self._finished()
            raise
        return ClosingIterator(result, self._finished)

    def _finished(self) -> None:
        with self.lock:
            self.active -= 1

    def start_draining(self, close_listener: Callable[[], None],
                       busy_connections: Callable[[], int] = lambda: 0) -> None:
        """Called from the SIGTERM handler: do as little as possible here."""
        if self.draining.is_set():
            return
        self.draining.set()
        threading.Thread(target=self._drain, args=(close_listener, busy_connections),
                         name="graceful-shutdown", daemon=True).start()

    def _drain(self, close_listener: Callable[[], None], busy_connections: Callable[[], int],
               interval: float = 0.05) -> None:
        log = logging.getLogger("dimora.http")
        started = monotonic()
        close_listener()
        log.info("Stopping: %s request(s) in flight, %s connection(s) busy",
                 self.active, busy_connections())
        while monotonic() < started + self.grace:
            with self.lock:
                idle = self.active == 0
            if idle and busy_connections() == 0:
                break
            sleep(interval)
        if self.active:
            log.warning("Requests still running after %.0f s; thread stacks follow", self.grace)
            faulthandler.dump_traceback(all_threads=True)
        sleep(0.2)  # let the server write the last responses
        log.info("Stopped after %.1f s with %s request(s) unfinished", monotonic() - started, self.active)
        self.exit(0)


def serve(app: Flask, port: int, threads: int = 16, connection_limit: int = 1000) -> None:
    """Run the app on waitress, a production WSGI server without native dependencies.

    ``connection_limit`` stays well above what the gateway keeps open, so a replica
    that takes over the traffic of a stopped one keeps accepting connections.
    """
    from waitress import wasyncore
    from waitress.channel import HTTPChannel
    from waitress.server import create_server

    graceful = GracefulShutdown(app.wsgi_app)
    app.wsgi_app = graceful
    server = create_server(app, host="0.0.0.0", port=port, threads=threads,
                           connection_limit=connection_limit, ident="dimora")

    def close_in_loop() -> None:
        # Runs inside the server loop (see below), so the descriptor can be closed
        # safely. First take in the connections the kernel has already queued: their
        # request may be on its way. Then close the listening socket: new connections
        # are refused, and the gateway retries them on another replica.
        for _ in range(1024):
            open_channels = len(server._map)
            try:
                server.handle_accept()
            except OSError:
                break
            if len(server._map) == open_channels:
                break
        wasyncore.dispatcher.close(server)  # the listener only; the trigger stays

    def stop_accepting() -> None:
        server.trigger.pull_trigger(close_in_loop)

    def busy_connections() -> int:
        """Connections with a request being read or queued, or a response not yet sent."""
        try:
            return sum(
                isinstance(channel, HTTPChannel) and bool(
                    channel.requests or channel.request is not None
                    or channel.total_outbufs_len or channel.close_when_flushed)
                for channel in list(server._map.values())
            )
        except RuntimeError:  # the server loop changed the map meanwhile; look again
            return 1

    signal.signal(signal.SIGTERM, lambda *_: graceful.start_draining(stop_accepting, busy_connections))
    server.run()
