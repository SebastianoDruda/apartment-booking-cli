"""HTTP client with the same methods as ``BookingDatabase``.

The original terminal interface (``apartment_booking.cli``) only talks to an
object with BookingDatabase's methods. This client provides them over the
gateway, so the CLI runs unchanged while every change it makes goes through the
command services and produces events. Writing to a database directly would
bypass the events, and the other services would never learn about the change.
"""

from __future__ import annotations

import json
from typing import Any
from collections.abc import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from apartment_booking.database import BookingConflictError, RecordNotFoundError, validate_date_range
from dimora.common.consistency import STATUS_HEADER, TOKEN_HEADER, WAIT_HEADER

MAX_PENDING_TOKENS = 10


class GatewayUnavailableError(ValueError):
    """The gateway cannot be reached or a service behind it is down.

    A ValueError subclass, so the CLI prints it as an ``[Error]`` line and keeps running.
    """


class GatewayClient:
    def __init__(self, base_url: str, timeout: float = 10.0,
                 opener: Callable[..., Any] = urlopen) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._open = opener
        # Versions written by this client that the next read must already include.
        self.pending_tokens: list[str] = []

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, payload: dict | None = None,
                 query: dict | None = None) -> Any:
        url = self.base_url + path + (f"?{urlencode(query)}" if query else "")
        headers = {"Accept": "application/json"}
        body = None
        if payload is not None:
            body = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        if method == "GET" and self.pending_tokens:
            headers[WAIT_HEADER] = ", ".join(self.pending_tokens)

        try:
            response = self._open(Request(url, data=body, method=method, headers=headers),
                                  timeout=self.timeout)
        except HTTPError as error:
            response = error
        except (URLError, OSError) as error:
            reason = getattr(error, "reason", error)
            raise GatewayUnavailableError(
                f"Cannot reach the Dimora gateway at {self.base_url} ({reason}). "
                "Start the stack with 'docker compose up --detach --wait' in microservices/."
            ) from None

        with response:
            status = response.status
            response_headers = response.headers
            try:
                result = json.load(response)
            except ValueError:
                result = {}

        if status >= 400:
            self._raise_for(status, result)
        if method == "GET":
            if response_headers.get(STATUS_HEADER):
                self.pending_tokens.clear()
        elif response_headers.get(TOKEN_HEADER):
            self.pending_tokens = [*self.pending_tokens, response_headers[TOKEN_HEADER]][-MAX_PENDING_TOKENS:]
        return result.get("data") if isinstance(result, dict) else None

    def _raise_for(self, status: int, result: Any) -> None:
        error = result.get("error", {}) if isinstance(result, dict) else {}
        message = error.get("message") or f"The gateway answered HTTP {status}."
        if status == 404 and error.get("code") == "not_found":
            raise RecordNotFoundError(message)
        if status == 409:
            raise BookingConflictError(message)
        if status in (400, 404, 405, 413, 415):
            raise ValueError(message)
        raise GatewayUnavailableError(f"{message} (HTTP {status})")

    def close(self) -> None:
        """Nothing to release: every request uses its own connection."""

    # ------------------------------------------------------------------
    # Apartments
    # ------------------------------------------------------------------

    def list_apartments(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/apartments")

    def get_apartment_by_name(self, name: str) -> dict[str, Any] | None:
        wanted = name.strip().casefold()
        if not wanted:
            return None
        return next((apartment for apartment in self.list_apartments()
                     if apartment["name"].casefold() == wanted), None)

    def add_apartment(self, name: str, address: str, max_people: int,
                      price_per_night: float) -> dict[str, Any]:
        # The CLI has already joined the address as "Country, City, Street"; the API
        # takes the three parts and joins them again the same way.
        parts = address.split(", ", 2)
        if len(parts) != 3:
            raise ValueError("Address must look like 'Country, City, Street and house number'.")
        country, city, street = parts
        return self._request("POST", "/api/apartments", {
            "name": name, "country": country, "city": city, "street_and_number": street,
            "max_people": max_people, "price_per_night": price_per_night,
        })

    def update_apartment_price(self, name: str, new_price_per_night: float) -> dict[str, Any]:
        return self._request("PATCH", f"/api/apartments/{quote(name.strip(), safe='')}/price",
                             {"price_per_night": new_price_per_night})

    def remove_apartment(self, name: str) -> dict[str, Any]:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Apartment name cannot be empty.")
        return self._request("DELETE", f"/api/apartments/{quote(clean_name, safe='')}")

    # ------------------------------------------------------------------
    # Bookings
    # ------------------------------------------------------------------

    def list_bookings(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/bookings")

    def get_booking(self, apartment_name: str, start_date_str: str,
                    end_date_str: str) -> dict[str, Any] | None:
        start_iso, end_iso, _ = validate_date_range(start_date_str, end_date_str)
        wanted = apartment_name.strip().casefold()
        return next((booking for booking in self.list_bookings()
                     if booking["apartment_name"].casefold() == wanted
                     and booking["start_date"] == start_iso and booking["end_date"] == end_iso), None)

    def create_booking(self, apartment_name: str, start_date_str: str, end_date_str: str,
                       booker_name: str, num_people: int) -> dict[str, Any]:
        return self._request("POST", "/api/bookings", {
            "apartment_name": apartment_name, "start_date": start_date_str, "end_date": end_date_str,
            "booker_name": booker_name, "num_people": num_people,
        })

    def change_booking(self, apartment_name: str, old_start_str: str, old_end_str: str,
                       new_start_str: str, new_end_str: str, new_num_people: int) -> dict[str, Any]:
        return self._request("PATCH", "/api/bookings", {
            "apartment_name": apartment_name, "start_date": old_start_str, "end_date": old_end_str,
            "new_start_date": new_start_str, "new_end_date": new_end_str, "num_people": new_num_people,
        })

    def cancel_booking(self, apartment_name: str, start_date_str: str,
                       end_date_str: str) -> dict[str, Any]:
        return self._request("DELETE", "/api/bookings", {
            "apartment_name": apartment_name, "start_date": start_date_str, "end_date": end_date_str,
        })

    def search_available_apartments(self, start_date_str: str, end_date_str: str,
                                    num_people: int) -> list[dict[str, Any]]:
        return self._request("GET", "/api/availability", query={
            "start_date": start_date_str, "end_date": end_date_str, "num_people": num_people,
        })
