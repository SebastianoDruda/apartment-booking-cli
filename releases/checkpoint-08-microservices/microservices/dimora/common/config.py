"""Environment-based configuration.

Every setting has a default that works inside the Compose network, so the
services start without extra configuration; tests override them explicitly.
"""

from __future__ import annotations

import logging
import os

DEFAULT_RABBITMQ_URL = "amqp://dimora:dimora-local@rabbitmq:5672/%2F"


def setting(name: str, default: str) -> str:
    """Return an environment variable, falling back to ``default`` when unset or blank."""
    value = os.environ.get(name, "").strip()
    return value or default


def float_setting(name: str, default: float) -> float:
    try:
        return float(setting(name, str(default)))
    except ValueError as error:
        raise SystemExit(f"{name} must be a number.") from error


def rabbitmq_url() -> str:
    return setting("DIMORA_RABBITMQ_URL", DEFAULT_RABBITMQ_URL)


def postgres_dsn(service: str) -> str:
    """DSN of a command-side database, e.g. ``DIMORA_APARTMENT_DSN``."""
    name = f"DIMORA_{service.upper()}_DSN"
    value = setting(name, "")
    if not value:
        raise SystemExit(f"{name} is not set.")
    return value


def http_port() -> int:
    return int(setting("PORT", "8000"))


def http_threads() -> int:
    """Worker threads per service; a read that waits for an event holds one of them."""
    try:
        threads = int(setting("DIMORA_HTTP_THREADS", "16"))
    except ValueError as error:
        raise SystemExit("DIMORA_HTTP_THREADS must be a whole number.") from error
    if threads < 1:
        raise SystemExit("DIMORA_HTTP_THREADS must be at least 1.")
    return threads


def configure_logging(service: str) -> logging.Logger:
    """Log one line per record, with the service name, to standard output."""
    logging.basicConfig(
        level=setting("DIMORA_LOG_LEVEL", "INFO").upper(),
        format=f"%(asctime)s {service} %(levelname)s %(name)s: %(message)s",
    )
    # pika logs every connection attempt at INFO; keep the service logs readable.
    logging.getLogger("pika").setLevel(logging.WARNING)
    return logging.getLogger(f"dimora.{service}")
