"""The original CLI, driven through GatewayClient against a small fake gateway."""

import io
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

from apartment_booking.cli import ApartmentBookingCLI
from apartment_booking.database import BookingConflictError, RecordNotFoundError
from dimora.cli.client import GatewayClient, GatewayUnavailableError


class FakeGateway(BaseHTTPRequestHandler):
    """Just enough of the public API to exercise the client."""

    apartments: dict
    bookings: list
    seen_headers: list

    def log_message(self, *args):
        pass

    def _send(self, status, payload, headers=None):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        self.seen_headers.append(("GET", self.path, self.headers.get("X-Wait-For")))
        url = urlsplit(self.path)
        extra = {"X-Consistency": "fresh"} if self.headers.get("X-Wait-For") else {}
        if url.path == "/api/apartments":
            return self._send(200, {"data": list(self.apartments.values())}, extra)
        if url.path == "/api/bookings":
            return self._send(200, {"data": self.bookings}, extra)
        if url.path == "/api/availability":
            query = parse_qs(url.query)
            people = int(query["num_people"][0])
            free = [dict(a, nights=2, total_price=a["price_per_night"] * 2,
                         start_date=query["start_date"][0], end_date=query["end_date"][0])
                    for a in self.apartments.values() if a["max_people"] >= people]
            return self._send(200, {"data": free}, extra)
        return self._send(404, {"error": {"code": "not_found", "message": "Not here."}})

    def do_POST(self):
        self.seen_headers.append(("POST", self.path, self.headers.get("X-Wait-For")))
        body = self._body()
        if self.path == "/api/apartments":
            if body["name"].lower() in {name.lower() for name in self.apartments}:
                return self._send(409, {"error": {"code": "conflict",
                                                  "message": f"Apartment '{body['name']}' already exists."}})
            apartment = {"id": len(self.apartments) + 1, "name": body["name"],
                         "address": f"{body['country']}, {body['city']}, {body['street_and_number']}",
                         "max_people": int(body["max_people"]), "price_per_night": float(body["price_per_night"])}
            self.apartments[body["name"]] = apartment
            return self._send(201, {"data": apartment},
                              {"X-Consistency-Token": f"apartment:{apartment['id']}@1"})
        apartment = self.apartments.get(body["apartment_name"])
        if apartment is None:
            return self._send(404, {"error": {"code": "not_found",
                                              "message": f"Apartment '{body['apartment_name']}' does not exist."}})
        booking = {"id": 1, "apartment_id": apartment["id"], "apartment_name": apartment["name"],
                   "apartment_address": apartment["address"], "apartment_max_people": apartment["max_people"],
                   "price_per_night": apartment["price_per_night"], "booker_name": body["booker_name"],
                   "start_date": body["start_date"], "end_date": body["end_date"], "nights": 2,
                   "num_people": body["num_people"], "total_price": apartment["price_per_night"] * 2}
        self.bookings.append(booking)
        return self._send(201, {"data": booking}, {"X-Consistency-Token": "booking:1@1"})

    def do_PATCH(self):
        name = unquote(self.path.split("/")[3])
        body = self._body()
        apartment = self.apartments[name]
        result = dict(apartment, old_price_per_night=apartment["price_per_night"],
                      price_per_night=float(body["price_per_night"]))
        apartment["price_per_night"] = result["price_per_night"]
        self._send(200, {"data": result}, {"X-Consistency-Token": f"apartment:{apartment['id']}@2"})

    def do_DELETE(self):
        if self.path.startswith("/api/apartments/"):
            name = unquote(self.path.split("/")[3])
            removed = self.apartments.pop(name)
            return self._send(200, {"data": removed}, {"X-Consistency-Token": f"apartment:{removed['id']}@3"})
        return self._send(500, {"error": {"code": "internal_error", "message": "Boom."}})


class GatewayClientTests(unittest.TestCase):
    def setUp(self):
        handler = type("Handler", (FakeGateway,), {"apartments": {}, "bookings": [], "seen_headers": []})
        self.handler = handler
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.serving = True
        self.client = GatewayClient(f"http://127.0.0.1:{self.server.server_port}/")

    def tearDown(self):
        self.stop_server()

    def stop_server(self):
        if self.serving:
            self.serving = False
            self.server.shutdown()
            self.server.server_close()

    def add(self, name="Casa Aurora"):
        return self.client.add_apartment(name, "Italia, Amalfi, Via Roma 1, scala B", 4, 180.0)

    def test_address_round_trips_through_the_three_api_fields(self):
        self.assertEqual(self.add()["address"], "Italia, Amalfi, Via Roma 1, scala B")
        with self.assertRaises(ValueError):
            self.client.add_apartment("X", "no commas", 1, 1.0)

    def test_errors_become_the_domain_exceptions_the_cli_expects(self):
        self.add()
        with self.assertRaises(BookingConflictError):
            self.add()
        with self.assertRaises(RecordNotFoundError):
            self.client.create_booking("Ghost", "2027-03-01", "2027-03-03", "Anna", 2)
        with self.assertRaises(GatewayUnavailableError) as raised:
            self.client.cancel_booking("Casa Aurora", "2027-03-01", "2027-03-03")
        self.assertIn("HTTP 500", str(raised.exception))

    def test_reads_wait_for_the_clients_own_writes(self):
        self.add()
        self.client.list_apartments()
        self.client.list_apartments()
        gets = [header for method, _path, header in self.handler.seen_headers if method == "GET"]
        self.assertEqual(gets, ["apartment:1@1", None])

    def test_lookups_match_names_case_insensitively(self):
        self.add()
        self.client.create_booking("Casa Aurora", "2027-03-01", "2027-03-03", "Anna", 2)
        self.assertEqual(self.client.get_apartment_by_name("casa aurora")["id"], 1)
        self.assertIsNone(self.client.get_apartment_by_name("  "))
        self.assertEqual(self.client.get_booking("CASA AURORA", "01.03.2027", "2027/03/03")["booker_name"], "Anna")
        self.assertIsNone(self.client.get_booking("Casa Aurora", "2027-03-02", "2027-03-03"))

    def test_unreachable_gateway_explains_how_to_start_it(self):
        self.stop_server()
        with self.assertRaises(GatewayUnavailableError) as raised:
            self.client.list_apartments()
        self.assertIn("docker compose up", str(raised.exception))

    def test_the_original_cli_runs_unchanged_on_the_client(self):
        script = iter([
            "2", "apartment add", "Casa Aurora", "Italia", "Amalfi", "Via Roma 1", "4", "180",
            "apartment update", "Casa Aurora", "200",
            "role", "1", "apartment search", "2027-03-01", "2027-03-03", "2", "Casa Aurora", "Anna Huber",
            "booking view", "exit",
        ])
        output = io.StringIO()
        ApartmentBookingCLI(db=self.client, input_fn=lambda _prompt: next(script), output_stream=output).run()
        text = output.getvalue()
        self.assertIn("Apartment 'Casa Aurora' at 'Italia, Amalfi, Via Roma 1' added", text)
        self.assertIn("from 180.00 EUR to 200.00 EUR", text)
        self.assertIn("is booked for Anna Huber", text)
        self.assertIn("400.00 EUR", text)


if __name__ == "__main__":
    unittest.main()
