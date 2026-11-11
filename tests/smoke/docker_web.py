"""Exercise real HTTP and CLI clients against a disposable Compose project.

Build both images first: docker compose build
Run: python tests/smoke/docker_web.py
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    compose = ["docker", "compose", "--project-name", "booking-http-test-" + uuid.uuid4().hex[:12]]
    # Docker selects a free loopback-only port; never use the user's web service/volume.
    env = dict(os.environ, BOOKING_WEB_PORT="0")

    def run(*args: str, input_text: str = "") -> str:
        result = subprocess.run([*compose, *args], cwd=root, env=env, input=input_text,
                                text=True, capture_output=True, timeout=120)
        if result.returncode:
            raise RuntimeError(f"Compose failed: {args}\n{result.stdout}\n{result.stderr}")
        return result.stdout

    try:
        run("up", "-d", "--wait", "web")
        address = run("port", "web", "8000").strip()
        assert address.startswith("127.0.0.1:"), address
        base = "http://" + address

        def http(path: str, method: str = "GET", payload: dict | None = None, status: int = 200):
            body = json.dumps(payload).encode() if payload is not None else None
            request = Request(base + path, data=body, method=method,
                              headers={"Content-Type": "application/json"})
            try:
                response = urlopen(request, timeout=10)
            except HTTPError as error:
                response = error
            with response:
                result = json.load(response)
                assert response.status == status, (path, response.status, result)
                return result

        assert http("/api/health")["data"]["status"] == "ok"
        assert "routes" in http("/")["data"]
        assert http("/api/openapi.json")["openapi"] == "3.1.0"
        # Verify documentation and Web UI assets were included by the restricted build context.
        for path in ("/docs", "/static/api_docs.js", "/static/api_docs.css", "/ui", "/static/ui.js", "/static/ui.css"):
            with urlopen(base + path, timeout=10) as response:
                assert response.status == 200, path
        run("exec", "-T", "web", "python", "-c", "import os; assert os.getuid() != 0")
        assert "Debug mode: off" in run("logs", "web")
        # The CLI creates data that the HTTP interface must immediately see.
        run("run", "--rm", "-T", "booking", input_text=(
            "2\napartment add\nShared Demo\nItaly\nRome\nExample 1\n3\n100\nexit\n"
        ))
        assert http("/api/apartments")["data"][0]["name"] == "Shared Demo"
        reservation = dict(apartment_name="Shared Demo", start_date="2026-11-10", end_date="2026-11-15",
                           booker_name="HTTP Guest", num_people=2)
        assert http("/api/bookings", "POST", reservation, 201)["data"]["total_price"] == 500
        http("/api/bookings", "POST", reservation, 409)
        assert http("/api/availability?start_date=2026-11-10&end_date=2026-11-15&num_people=2")["data"] == []
        output = run("run", "--rm", "-T", "booking", input_text="1\nbooking view\nexit\n")
        assert "HTTP Guest" in output and "500.00 EUR" in output
        http("/api/apartments/Shared%20Demo/price", "PATCH", {"price_per_night": 120})
        # Restart the HTTP process; the volume and booking must survive.
        run("restart", "web")
        # An ephemeral host port may be reassigned when Docker restarts the container.
        address = run("port", "web", "8000").strip()
        assert address.startswith("127.0.0.1:"), address
        base = "http://" + address
        deadline = time.monotonic() + 20
        while True:
            try:
                http("/api/health")
                break
            except (URLError, ConnectionError):
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.2)
        assert http("/api/bookings")["data"][0]["total_price"] == 600
        http("/api/bookings", "PATCH", dict(
            apartment_name="Shared Demo", start_date="2026-11-10", end_date="2026-11-15",
            new_start_date="2026-11-11", new_end_date="2026-11-16", num_people=3,
        ))
        http("/api/bookings", "DELETE", dict(
            apartment_name="Shared Demo", start_date="2026-11-11", end_date="2026-11-16",
        ))
        http("/api/apartments/Shared%20Demo", "DELETE")
        assert http("/api/apartments")["data"] == []
        assert http("/api/bookings")["data"] == []
        print("HTTP Docker checks passed: loopback binding, health, non-root execution, CLI/API shared storage, conflicts and restart persistence.")
    except Exception:
        print(run("logs", "--tail", "60", "web"))
        raise
    finally:
        # This destroys only the random, disposable project created above.
        run("down", "--volumes", "--remove-orphans")


if __name__ == "__main__":
    main()
