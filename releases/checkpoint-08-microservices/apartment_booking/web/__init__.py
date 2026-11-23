"""Flask HTTP interface: routes, OpenAPI contract, templates and static assets.

Start with: python -m flask --app apartment_booking.web:create_app run --no-debugger --no-reload --port 8000
"""

from apartment_booking.web.app import create_app

__all__ = ["create_app"]
