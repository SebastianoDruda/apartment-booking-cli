"""End-to-end check of the microservices stack in a disposable Compose project.

Run from anywhere (Docker required):  python3 microservices/tests/system/stack_smoke.py

It builds the images, starts every container on random localhost ports and then
checks, through the gateway: the public API and its error contract, ownership
routing, read-your-writes across services, the outbox while RabbitMQ is down, a
consumer that starts late, the removal cascade, the CLI, the SQLite importer, the
dead-letter queue, a rebuild of the apartment copy, a restart without failed
requests when a service runs two replicas, and persistence across a restart. The
project and its volumes are removed at the end, so the normal stack is never touched.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[3]
COMPOSE_DIR = ROOT / "microservices"
sys.path.insert(0, str(ROOT))

from apartment_booking.database import BookingDatabase  # noqa: E402


class Stack:
    def __init__(self) -> None:
        self.project = "dimora-smoke-" + uuid.uuid4().hex[:10]
        self.env = dict(os.environ, DIMORA_PORT="0", DIMORA_RABBITMQ_UI_PORT="0")
        self.base = ""

    def compose(self, *args: str, input_text: str = "", timeout: int = 300) -> str:
        result = subprocess.run(
            ["docker", "compose", "--project-name", self.project, *args],
            cwd=COMPOSE_DIR, env=self.env, input=input_text, text=True,
            capture_output=True, timeout=timeout,
        )
        if result.returncode:
            raise RuntimeError(f"docker compose {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}")
        return result.stdout

    def refresh_address(self) -> None:
        address = self.compose("port", "gateway", "8080").strip()
        assert address.startswith("127.0.0.1:"), address
        self.base = "http://" + address

    def http(self, path: str, method: str = "GET", payload: dict | None = None,
             headers: dict | None = None) -> tuple[int, dict, object]:
        body = json.dumps(payload).encode() if payload is not None else None
        request = Request(self.base + path, data=body, method=method,
                          headers={"Content-Type": "application/json", **(headers or {})})
        try:
            response = urlopen(request, timeout=15)
        except HTTPError as error:
            response = error
        with response:
            raw = response.read()
            content = json.loads(raw) if response.headers.get_content_type() == "application/json" else raw
            return response.status, dict(response.headers), content

    def ok(self, path: str, method: str = "GET", payload: dict | None = None,
           status: int = 200, headers: dict | None = None):
        code, response_headers, content = self.http(path, method, payload, headers)
        assert code == status, (method, path, code, content)
        return response_headers, content


def wait_until(description: str, check, timeout: float = 60.0):
    deadline = time.monotonic() + timeout
    while True:
        result = check()
        if result:
            return result
        if time.monotonic() > deadline:
            raise AssertionError(f"Timed out waiting for {description}")
        time.sleep(0.5)


def names(stack: Stack, path: str = "/api/apartments") -> list[str]:
    return [item["name"] for item in stack.ok(path)[1]["data"]]


def booking_keys(stack: Stack) -> set[tuple[str, str, str]]:
    return {(b["apartment_name"], b["start_date"], b["end_date"]) for b in stack.ok("/api/bookings")[1]["data"]}


def make_import_fixture(folder: Path) -> Path:
    path = folder / "apartment_booking.db"
    database = BookingDatabase(path)
    database.add_apartment("Imported Villa", "Italia, Lecce, Via Duomo 3", 6, 210.0)
    database.add_apartment("Imported Studio", "Austria, Wien, Ring 1", 2, 95.0)
    database.create_booking("Imported Villa", "2027-07-01", "2027-07-04", "Giulia Neri", 4)
    database.close()
    # The service image runs as an unprivileged user: make the fixture readable.
    folder.chmod(0o755)
    path.chmod(0o644)
    return path


def main() -> None:
    stack = Stack()
    started = time.monotonic()
    fixture_dir = Path(tempfile.mkdtemp(prefix="dimora-import-"))
    failed = True
    try:
        make_import_fixture(fixture_dir)
        print("Building and starting the stack ...", flush=True)
        stack.compose("up", "--build", "--detach", "--wait", timeout=900)
        stack.refresh_address()

        # -------------------------------------------------------- import
        output = stack.compose("run", "--rm", "-T", "-v", f"{fixture_dir}:/import:ro", "importer")
        assert "Imported 2 apartment(s) and 1 booking(s)" in output, output
        wait_until("imported data in both services",
                   lambda: {"Imported Villa", "Imported Studio"} <= set(names(stack)) and booking_keys(stack))
        imported = stack.ok("/api/bookings")[1]["data"][0]
        assert (imported["booker_name"], imported["total_price"]) == ("Giulia Neri", 630.0), imported
        print("✓ SQLite import published to the reservation copy", flush=True)

        # -------------------------------------------------------- entry point and routing
        headers, data = stack.ok("/api/health")
        assert data["data"] == {"status": "ok", "database": "ok"}
        assert headers["X-Served-By"] == "apartment_service"
        # Ownership routing: reads go to the service that owns the data, like writes.
        assert stack.ok("/api/apartments")[0]["X-Served-By"] == "apartment_service"
        assert stack.ok("/api/bookings")[0]["X-Served-By"] == "reservation_service"
        search = "/api/availability?start_date=2027-01-10&end_date=2027-01-12&num_people=1"
        assert stack.ok(search)[0]["X-Served-By"] == "reservation_service"
        services = {route["service"] for route in stack.ok("/api")[1]["data"]["routes"]}
        assert services == {"apartment", "reservation"}, services
        page_headers, page = stack.ok("/")
        assert b"Dimora" in page and "Content-Security-Policy" in page_headers
        assert stack.ok("/api/openapi.json")[1]["openapi"] == "3.1.0"
        assert b"api_docs.js" in stack.ok("/docs")[1]
        stack.ok("/static/api_docs.js")
        print("✓ Gateway serves the web client, the explorer and the API", flush=True)

        # -------------------------------------------------------- commands and read-your-writes
        apartment = {"name": "Smoke Loft", "country": "Italia", "city": "Roma",
                     "street_and_number": "Via Appia 9", "max_people": 3, "price_per_night": 100}
        headers, created = stack.ok("/api/apartments", "POST", apartment, status=201)
        assert headers["X-Served-By"] == "apartment_service"
        token = headers["X-Consistency-Token"]
        headers, listed = stack.ok("/api/apartments", headers={"X-Wait-For": token})
        assert headers["X-Consistency"] == "fresh", headers
        assert "Smoke Loft" in [item["name"] for item in listed["data"]]
        # The reservation service waits until the apartment event has reached its copy.
        headers, _ = stack.ok("/api/bookings", headers={"X-Wait-For": token})
        assert headers["X-Consistency"] == "fresh", headers

        # Booked straight after creation: the reservation service waits for the event.
        booking = {"apartment_name": "smoke loft", "start_date": "2027-05-01", "end_date": "2027-05-04",
                   "booker_name": "Anna Huber", "num_people": 2}
        headers, made = stack.ok("/api/bookings", "POST", booking, status=201)
        assert headers["X-Served-By"] == "reservation_service"
        assert (made["data"]["apartment_name"], made["data"]["total_price"]) == ("Smoke Loft", 300.0)

        _, conflict = stack.ok("/api/bookings", "POST", {**booking, "start_date": "2027-05-03",
                                                         "end_date": "2027-05-06"}, status=409)
        assert conflict["error"]["message"] == (
            "Apartment 'Smoke Loft' is not available from 2027-05-03 to 2027-05-06 "
            "(dates overlap with an existing booking)."), conflict
        _, too_many = stack.ok("/api/bookings", "POST", {**booking, "start_date": "2027-06-01",
                                                         "end_date": "2027-06-02", "num_people": 4}, status=400)
        assert "maximum capacity: 3" in too_many["error"]["message"]
        stack.ok("/api/apartments", "POST", {**apartment, "name": "SMOKE LOFT"}, status=409)
        stack.ok("/api/bookings", "POST", {**booking, "apartment_name": "Ghost"}, status=404)
        stack.ok("/api/apartments", "POST", {"name": "x"}, status=400)
        print("✓ Commands keep the original validation and error contract", flush=True)

        # Price changes affect new bookings only.
        headers, _ = stack.ok("/api/apartments/Smoke%20Loft/price", "PATCH", {"price_per_night": 150})
        stack.ok("/api/bookings", headers={"X-Wait-For": headers["X-Consistency-Token"]})
        old = next(b for b in stack.ok("/api/bookings")[1]["data"] if b["booker_name"] == "Anna Huber")
        assert old["total_price"] == 300.0 and old["price_per_night"] == 100.0, old
        _, later = stack.ok("/api/bookings", "POST", {**booking, "start_date": "2027-06-01",
                                                      "end_date": "2027-06-03"}, status=201)
        assert later["data"]["total_price"] == 300.0 and later["data"]["price_per_night"] == 150.0

        # Change, cancel and availability.
        change = {"apartment_name": "Smoke Loft", "start_date": "2027-06-01", "end_date": "2027-06-03",
                  "new_start_date": "2027-06-10", "new_end_date": "2027-06-14", "num_people": 3}
        _, changed = stack.ok("/api/bookings", "PATCH", change)
        assert (changed["data"]["nights"], changed["data"]["old_start_date"]) == (4, "2027-06-01")
        headers, _ = stack.ok("/api/bookings", "DELETE", {"apartment_name": "Smoke Loft",
                                                          "start_date": "2027-06-10", "end_date": "2027-06-14"})
        stack.ok("/api/bookings", headers={"X-Wait-For": headers["X-Consistency-Token"]})
        assert ("Smoke Loft", "2027-06-10", "2027-06-14") not in booking_keys(stack)
        free = names(stack, "/api/availability?start_date=2027-06-10&end_date=2027-06-14&num_people=3")
        assert "Smoke Loft" in free and "Imported Studio" not in free, free
        busy = names(stack, "/api/availability?start_date=2027-05-02&end_date=2027-05-03&num_people=1")
        assert "Smoke Loft" not in busy, busy

        # Names with a slash survive the gateway and both services.
        slash = {**apartment, "name": "Loft/2"}
        stack.ok("/api/apartments", "POST", slash, status=201)
        stack.ok(f"/api/apartments/{quote('Loft/2', safe='')}/price", "PATCH", {"price_per_night": 80})
        stack.ok(f"/api/apartments/{quote('Loft/2', safe='')}", "DELETE")
        print("✓ Prices, changes, cancellations and availability behave as before", flush=True)

        # -------------------------------------------------------- outbox while RabbitMQ is down
        stack.compose("stop", "rabbitmq")
        offline = {**apartment, "name": "Offline Flat"}
        headers, _ = stack.ok("/api/apartments", "POST", offline, status=201)
        offline_token = headers["X-Consistency-Token"]
        assert "Offline Flat" in names(stack), "the apartment service answers from its own database"
        headers, _ = stack.ok("/api/bookings", headers={"X-Wait-For": offline_token})
        assert headers["X-Consistency"] == "stale", "no event can reach the copy while the broker is down"
        pending = json.loads(stack.compose(
            "exec", "-T", "apartment-service", "python", "-c",
            "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').read().decode())",
        ))["data"]["pending_events"]
        assert pending >= 1, pending
        stack.compose("start", "rabbitmq")
        wait_until("the event written while RabbitMQ was down", lambda: "Offline Flat" in names(
            stack, "/api/availability?start_date=2027-05-01&end_date=2027-05-04&num_people=1"), 90)
        print("✓ Writes succeed with RabbitMQ down; the outbox publishes them afterwards", flush=True)

        # -------------------------------------------------------- a consumer that starts late
        stack.compose("stop", "reservation-service")
        late = {**apartment, "name": "Late Flat"}
        stack.ok("/api/apartments", "POST", late, status=201)
        headers, _ = stack.ok("/api/apartments/Late%20Flat/price", "PATCH", {"price_per_night": 120})
        stack.compose("start", "reservation-service")
        wait_until("the reservation service after its restart",
                   lambda: stack.http("/api/bookings")[0] == 200, 90)
        headers, _ = stack.ok("/api/bookings", headers={"X-Wait-For": headers["X-Consistency-Token"]})
        assert headers["X-Consistency"] == "fresh", "both queued events reached the copy"
        stack.ok("/api/bookings", "POST", {**booking, "apartment_name": "Late Flat",
                                           "booker_name": "Late Reader"}, status=201)
        late_booking = next(b for b in stack.ok("/api/bookings")[1]["data"] if b["booker_name"] == "Late Reader")
        assert late_booking["price_per_night"] == 120.0, late_booking
        print("✓ Durable queues keep events for a consumer that starts later", flush=True)

        # -------------------------------------------------------- removal cascade
        headers, _ = stack.ok("/api/apartments/Smoke%20Loft", "DELETE")
        stack.ok("/api/bookings", headers={"X-Wait-For": headers["X-Consistency-Token"]})
        assert not any(key[0] == "Smoke Loft" for key in booking_keys(stack))
        # Every booking of the apartment is cancelled; the rows stay.
        wait_until("cancellations in the reservation database", lambda: stack.compose(
            "exec", "-T", "reservation-db", "psql", "-U", "dimora", "-d", "reservations", "-tAc",
            "SELECT count(*) FILTER (WHERE b.status = 'active'), count(*)"
            " FROM bookings b JOIN apartment_copies a ON a.id = b.apartment_id WHERE a.name = 'Smoke Loft'",
        ).strip() == "0|2")
        print("✓ Removing an apartment cancels its bookings", flush=True)

        # -------------------------------------------------------- the original CLI over HTTP
        output = stack.compose("run", "--rm", "-T", "cli", input_text=(
            "2\napartment add\nCLI Studio\nItalia\nTorino\nVia Po 1\n2\n90\napartment view\nexit\n"
        ))
        view = output.split("--- All Apartments ---", 1)[1]
        assert "CLI Studio" in view, output
        assert "CLI Studio" in names(stack)
        output = stack.compose("run", "--rm", "-T", "cli", input_text="1\nbooking view\nexit\n")
        assert "Late Reader" in output and "Giulia Neri" in output, output
        print("✓ The CLI reads its own writes through the gateway", flush=True)

        # -------------------------------------------------------- dead-letter queue
        stack.compose("exec", "-T", "apartment-service", "python", "-c", (
            "import os, pika; from dimora.common.messaging import connection_parameters;"
            " c = pika.BlockingConnection(connection_parameters(os.environ['DIMORA_RABBITMQ_URL']));"
            " c.channel().basic_publish('dimora.events', 'apartment.added', b'not an event'); c.close()"
        ))

        def dead_letters() -> int:
            listing = stack.compose("exec", "-T", "rabbitmq", "rabbitmqctl", "list_queues", "-q",
                                    "name", "messages")
            counts = dict(line.split() for line in listing.splitlines() if line.strip())
            return int(counts.get("dimora.dead-letter", 0))

        # The only consumer of apartment.* rejects the message into the dead-letter queue.
        wait_until("one dead letter", lambda: dead_letters() == 1)
        assert "CLI Studio" in names(stack), "consumers keep working after a bad message"
        print("✓ Malformed messages go to the dead-letter queue", flush=True)

        # -------------------------------------------------------- rebuild the apartment copy
        before = (sorted(names(stack)), booking_keys(stack))
        stack.compose("run", "--rm", "-T", "republish", "python", "-m", "dimora.tools.republish",
                      "--rebuild-copy")
        wait_until("the rebuilt apartment copy", lambda: (sorted(names(stack)), booking_keys(stack)) == before)
        print("✓ The apartment copy is rebuilt from republished events", flush=True)

        # -------------------------------------------------------- restart without failed requests
        stack.compose("up", "--detach", "--wait", "--scale", "reservation-service=2", timeout=600)
        time.sleep(6)  # nginx re-resolves the service name every 5 s and finds both replicas
        failures: list[int] = []
        done = threading.Event()

        def keep_reading() -> None:
            while not done.is_set():
                code = stack.http("/api/bookings")[0]
                if code != 200:
                    failures.append(code)

        reader = threading.Thread(target=keep_reading)
        reader.start()
        try:
            subprocess.run(["docker", "restart", f"{stack.project}-reservation-service-1"],
                           check=True, capture_output=True, timeout=120)
            time.sleep(2)
        finally:
            done.set()
            reader.join()
        assert not failures, f"requests failed while one replica restarted: {failures}"
        stack.compose("up", "--detach", "--wait", "--scale", "reservation-service=1", timeout=600)
        print("✓ With two replicas, restarting one fails no request", flush=True)

        # -------------------------------------------------------- security and persistence
        for service in ("apartment-service", "reservation-service", "gateway"):
            uid = stack.compose("exec", "-T", service, "id", "-u").strip()
            assert uid != "0", (service, uid)
        stack.compose("stop")
        stack.compose("up", "--detach", "--wait", timeout=600)
        stack.refresh_address()
        assert (sorted(names(stack)), booking_keys(stack)) == before
        print("✓ Containers run unprivileged and data survives a full restart", flush=True)

        failed = False
        print(f"Microservices stack smoke test passed in {time.monotonic() - started:.0f} s.")
    finally:
        if failed:
            try:
                print(stack.compose("logs", "--no-color", "--tail", "60"), file=sys.stderr)
            except Exception as error:  # noqa: BLE001
                print(f"Could not collect logs: {error}", file=sys.stderr)
        subprocess.run(["docker", "compose", "--project-name", stack.project, "down", "--volumes",
                        "--remove-orphans"], cwd=COMPOSE_DIR, env=stack.env, capture_output=True, timeout=300)
        for path in fixture_dir.iterdir():
            path.unlink()
        fixture_dir.rmdir()


if __name__ == "__main__":
    main()
