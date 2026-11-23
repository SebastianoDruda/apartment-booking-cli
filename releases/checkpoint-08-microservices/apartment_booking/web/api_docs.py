"""OpenAPI contract and examples used by the local API explorer."""

from __future__ import annotations


def _text(example: str, description: str = "") -> dict:
    return {"type": "string", "example": example, "description": description}


def _count(example: int) -> dict:
    return {"oneOf": [{"type": "integer", "minimum": 1}, {"type": "string"}], "example": example}


def openapi_document() -> dict:
    """Describe transport fields; validation and all writes remain in BookingDatabase."""
    name = _text("API Demo", "Apartment name, matched case-insensitively.")
    start = _text("2026-11-10", "Check-in date. All CLI date formats are accepted.")
    end = _text("2026-11-15", "Check-out date, later than check-in.")
    price = {"oneOf": [{"type": "number", "exclusiveMinimum": 0}, {"type": "string"}],
             "example": 120, "description": "Finite positive EUR price; CLI price strings are accepted."}
    identity = {"apartment_name": name, "start_date": start, "end_date": end}
    paths: dict = {}

    def operation(method, path, summary, tag, fields=None, *, query=None, path_name=False, created=False):
        result = {
            "summary": summary, "tags": [tag],
            "responses": {
                "201" if created else "200": {
                    "description": "Success; the existing database result is wrapped in data.",
                    "content": {"application/json": {"schema": {
                        "type": "object", "required": ["data"], "properties": {"data": {}}
                    }}},
                },
                **{str(status): {"description": description, "content": {"application/json": {
                    "schema": {"$ref": "#/components/schemas/Error"}
                }}} for status, description in (
                    (400, "Invalid or missing input"), (404, "Record or route not found"),
                    (409, "Duplicate apartment or overlapping booking"), (413, "Body exceeds 64 KiB"),
                    (415, "JSON content type required"), (500, "Unexpected server error"),
                    (503, "Database unavailable; resolve storage access and retry"),
                )},
            },
        }
        parameters = []
        if path_name:
            parameters.append({"name": "name", "in": "path", "required": True, "schema": name})
        for key, schema in (query or {}).items():
            parameters.append({"name": key, "in": "query", "required": True, "schema": schema})
        if parameters:
            result["parameters"] = parameters
        if fields:
            result["requestBody"] = {"required": True, "content": {"application/json": {
                "schema": {"type": "object", "required": list(fields),
                           "additionalProperties": False, "properties": fields},
                "example": {key: schema["example"] for key, schema in fields.items()},
            }}}
        paths.setdefault(path, {})[method.lower()] = result

    operation("GET", "/api/health", "Check server and database readiness", "Overview")
    operation("GET", "/", "Read the API route overview", "Overview")
    operation("GET", "/api/apartments", "List apartments", "Apartments")
    operation("POST", "/api/apartments", "Create an apartment", "Apartments", {
        "name": name, "country": _text("Italy"), "city": _text("Rome"),
        "street_and_number": _text("Example 1"), "max_people": _count(3), "price_per_night": price,
    }, created=True)
    operation("PATCH", "/api/apartments/{name}/price", "Update the nightly price", "Apartments",
              {"price_per_night": price}, path_name=True)
    operation("DELETE", "/api/apartments/{name}", "Remove an apartment and all its bookings", "Apartments",
              path_name=True)
    operation("GET", "/api/bookings", "List bookings", "Bookings")
    operation("POST", "/api/bookings", "Create a booking", "Bookings", {
        **identity, "booker_name": _text("Demo Guest"), "num_people": _count(2),
    }, created=True)
    operation("PATCH", "/api/bookings", "Change booking dates and guest count", "Bookings", {
        **identity, "new_start_date": _text("2026-11-11"), "new_end_date": _text("2026-11-16"),
        "num_people": _count(3),
    })
    operation("DELETE", "/api/bookings", "Cancel a booking using its current dates", "Bookings", identity)
    operation("GET", "/api/availability", "Search available apartments", "Availability",
              query={"start_date": start, "end_date": end, "num_people": _count(2)})
    return {
        "openapi": "3.1.0",
        "info": {"title": "Apartment Booking API", "version": "1.0.0",
                 "description": "Local, unauthenticated API sharing the original CLI's SQLite business rules."},
        "servers": [{"url": "/"}], "paths": paths,
        "components": {"schemas": {"Error": {
            "type": "object", "required": ["error"], "properties": {"error": {
                "type": "object", "required": ["code", "message"],
                "properties": {"code": {"type": "string"}, "message": {"type": "string"}},
            }},
        }}},
    }
