"""Locust journey for the apartment booking API's primary business workflow."""

from __future__ import annotations

from uuid import uuid4

from locust import HttpUser, between, events, task
from locust.exception import StopUser


MAX_FAILURE_RATIO = 0.01
MAX_AVERAGE_RESPONSE_MS = 500
MAX_P95_RESPONSE_MS = 1_000


@events.quitting.add_listener
def enforce_service_level_objectives(environment, **_kwargs):
    """Make a headless run fail when the API misses its load-test SLOs."""
    stats = environment.stats.total
    if not stats.num_requests:
        environment.process_exit_code = 1
        return

    p95 = stats.get_response_time_percentile(0.95) or 0
    if (
        stats.fail_ratio > MAX_FAILURE_RATIO
        or stats.avg_response_time > MAX_AVERAGE_RESPONSE_MS
        or p95 > MAX_P95_RESPONSE_MS
    ):
        environment.process_exit_code = 1


class BookingLifecycleUser(HttpUser):
    """Browse inventory and complete the booking lifecycle as one customer."""

    wait_time = between(0.2, 0.8)

    def on_start(self):
        identifier = uuid4().hex
        self.apartment_name = f"Locust Apartment {identifier}"
        self.booker_name = f"Locust Guest {identifier}"
        self.current_start = "2030-06-10"
        self.current_end = "2030-06-15"
        self.booking_active = False

        with self.client.post(
            "/api/apartments",
            name="POST /api/apartments [fixture]",
            json={
                "name": self.apartment_name,
                "country": "Italy",
                "city": "Bolzano",
                "street_and_number": f"Load Test {identifier[:8]}",
                "max_people": 4,
                "price_per_night": 120,
            },
            catch_response=True,
        ) as response:
            if not self._valid_data_response(response, 201):
                raise StopUser()

    def on_stop(self):
        if self.booking_active:
            self.client.delete(
                "/api/bookings",
                name="DELETE /api/bookings [cleanup]",
                json={
                    "apartment_name": self.apartment_name,
                    "start_date": self.current_start,
                    "end_date": self.current_end,
                },
            )
        self.client.delete(
            f"/api/apartments/{self.apartment_name}",
            name="DELETE /api/apartments/:name [cleanup]",
        )

    @staticmethod
    def _valid_data_response(response, expected_status: int) -> bool:
        if response.status_code != expected_status:
            response.failure(f"expected HTTP {expected_status}, got {response.status_code}")
            return False
        try:
            payload = response.json()
        except ValueError:
            response.failure("response was not JSON")
            return False
        if not isinstance(payload, dict) or "data" not in payload:
            response.failure("response did not contain the data envelope")
            return False
        response.success()
        return True

    def _recover_incomplete_booking(self):
        if not self.booking_active:
            return
        response = self.client.delete(
            "/api/bookings",
            name="DELETE /api/bookings [recovery]",
            json={
                "apartment_name": self.apartment_name,
                "start_date": self.current_start,
                "end_date": self.current_end,
            },
        )
        if response.status_code == 200:
            self.booking_active = False

    @task
    def complete_booking_journey(self):
        self._recover_incomplete_booking()
        self.current_start = "2030-06-10"
        self.current_end = "2030-06-15"

        with self.client.get(
            "/api/apartments", name="GET /api/apartments", catch_response=True
        ) as response:
            self._valid_data_response(response, 200)

        with self.client.get(
            "/api/availability",
            name="GET /api/availability",
            params={
                "start_date": self.current_start,
                "end_date": self.current_end,
                "num_people": 2,
            },
            catch_response=True,
        ) as response:
            self._valid_data_response(response, 200)

        with self.client.post(
            "/api/bookings",
            name="POST /api/bookings",
            json={
                "apartment_name": self.apartment_name,
                "start_date": self.current_start,
                "end_date": self.current_end,
                "booker_name": self.booker_name,
                "num_people": 2,
            },
            catch_response=True,
        ) as response:
            if not self._valid_data_response(response, 201):
                return
            self.booking_active = True

        with self.client.get(
            "/api/bookings", name="GET /api/bookings", catch_response=True
        ) as response:
            self._valid_data_response(response, 200)

        new_start = "2030-06-11"
        new_end = "2030-06-16"
        with self.client.patch(
            "/api/bookings",
            name="PATCH /api/bookings",
            json={
                "apartment_name": self.apartment_name,
                "start_date": self.current_start,
                "end_date": self.current_end,
                "new_start_date": new_start,
                "new_end_date": new_end,
                "num_people": 3,
            },
            catch_response=True,
        ) as response:
            if not self._valid_data_response(response, 200):
                return
            self.current_start = new_start
            self.current_end = new_end

        with self.client.delete(
            "/api/bookings",
            name="DELETE /api/bookings",
            json={
                "apartment_name": self.apartment_name,
                "start_date": self.current_start,
                "end_date": self.current_end,
            },
            catch_response=True,
        ) as response:
            if self._valid_data_response(response, 200):
                self.booking_active = False
