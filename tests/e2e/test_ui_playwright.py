"""Playwright End-to-End (E2E) tests for the Apartment Booking Web UI.

Each test runs against a real multithreaded WSGI server bound to an ephemeral
localhost port (127.0.0.1:0) backed by an isolated temporary SQLite database.
"""

from __future__ import annotations

import logging
import os
import tempfile
import threading
import unittest
from pathlib import Path
from werkzeug.serving import make_server

from apartment_booking.web import create_app

try:
    from playwright.sync_api import expect, sync_playwright
except ImportError:  # pragma: no cover
    expect = None
    sync_playwright = None


@unittest.skipIf(sync_playwright is None, "Playwright is not installed. Run: pip install -r requirements/e2e.txt")
class TestBookingWebUIPlaywright(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._playwright = sync_playwright().start()
        headless = os.environ.get("PLAYWRIGHT_HEADLESS", "1").strip().lower() not in {"0", "false", "no"}
        cls._browser = cls._playwright.chromium.launch(headless=headless)

    @classmethod
    def tearDownClass(cls) -> None:
        if getattr(cls, "_browser", None) is not None:
            cls._browser.close()
        if getattr(cls, "_playwright", None) is not None:
            cls._playwright.stop()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path = Path(self.temp_dir.name) / "playwright_e2e.db"

        self.app = create_app({"TESTING": False, "DATABASE_PATH": str(self.db_path)})
        self.app.logger.disabled = True
        logging.getLogger("werkzeug").disabled = True

        self.server = make_server("127.0.0.1", 0, self.app, threaded=True)
        self.port = self.server.server_port
        self.base_url = f"http://127.0.0.1:{self.port}"

        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.addCleanup(self._stop_server)

        self.context = self._browser.new_context(viewport={"width": 1440, "height": 900})
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()

    def _stop_server(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=5)

    def _register_apartment_via_ui(
        self,
        name: str,
        country: str,
        city: str,
        street: str,
        max_people: int,
        price: str,
    ) -> None:
        self.page.locator("#nav-inventory").click()
        self.page.locator("#apt-name").fill(name)
        self.page.locator("#apt-country").fill(country)
        self.page.locator("#apt-city").fill(city)
        self.page.locator("#apt-street").fill(street)
        self.page.locator("#apt-max-people").fill(str(max_people))
        self.page.locator("#apt-price").fill(price)
        self.page.locator("#add-apartment-submit").click()
        expect(self.page.locator("#status-banner")).to_be_visible()
        expect(self.page.locator("#status-banner-code")).to_have_text("201 CREATED")

    def test_01_dashboard_loads_health_and_help_modal(self) -> None:
        # Both "/" (browser Accept: text/html) and "/ui" must load the Stitch Web UI
        self.page.goto(f"{self.base_url}/")
        expect(self.page).to_have_title("Apartment Booking Console — Hospitality Operations Dashboard")
        expect(self.page.locator("#health-text")).to_have_text("System Healthy • SQLite OK")

        # Switch roles using the sidebar role switcher
        self.page.locator("#role-manager-btn").click()
        expect(self.page.locator("#active-role-badge")).to_have_text("Role 2: System Manager")
        expect(self.page.locator("#inventory-view")).to_be_visible()

        self.page.locator("#role-booker-btn").click()
        expect(self.page.locator("#active-role-badge")).to_have_text("Role 1: Apartment Booker")
        expect(self.page.locator("#search-view")).to_be_visible()

        # Open and close Quick Help & Rules modal
        self.page.locator("#help-btn").click()
        expect(self.page.locator("#help-modal")).to_be_visible()
        expect(self.page.locator("#help-modal-title")).to_have_text("Quick Help & Business Rules")
        self.page.locator("#help-modal-done").click()
        expect(self.page.locator("#help-modal")).to_be_hidden()

    def test_02_system_manager_apartment_lifecycle_and_duplicate_conflict(self) -> None:
        self.page.goto(f"{self.base_url}/ui")
        self.page.locator("#nav-inventory").click()

        # Fill form and verify live address preview pill
        self.page.locator("#apt-name").fill("Alpine Sun Penthouse")
        self.page.locator("#apt-country").fill("Austria")
        self.page.locator("#apt-city").fill("Innsbruck")
        self.page.locator("#apt-street").fill("Maria-Theresien-Straße 45")
        expect(self.page.locator("#address-preview-display")).to_have_text(
            "Austria, Innsbruck, Maria-Theresien-Straße 45"
        )
        self.page.locator("#apt-max-people").fill("4")
        self.page.locator("#apt-price").fill("140.00")
        self.page.locator("#add-apartment-submit").click()

        expect(self.page.locator("#status-banner-code")).to_have_text("201 CREATED")
        expect(self.page.locator("#inventory-table-body")).to_contain_text("Alpine Sun Penthouse")
        expect(self.page.locator("#inventory-table-body")).to_contain_text("€140.00 EUR")

        # Duplicate apartment (case-insensitive) must trigger 409 Conflict banner
        self.page.locator("#apt-name").fill("ALPINE SUN PENTHOUSE")
        self.page.locator("#apt-country").fill("Austria")
        self.page.locator("#apt-city").fill("Innsbruck")
        self.page.locator("#apt-street").fill("Other Street 1")
        self.page.locator("#add-apartment-submit").click()
        expect(self.page.locator("#status-banner-code")).to_contain_text("409")

        # Update nightly price via modal (PATCH /api/apartments/<name>/price)
        row = self.page.locator('tr[data-inventory-row="Alpine Sun Penthouse"]')
        row.locator('button[data-action="update-price"]').click()
        expect(self.page.locator("#price-modal")).to_be_visible()
        self.page.locator("#new-price-input").fill("165.50")
        self.page.locator("#confirm-price-btn").click()

        expect(self.page.locator("#price-modal")).to_be_hidden()
        expect(self.page.locator("#status-banner-code")).to_have_text("200 OK")
        expect(row).to_contain_text("€165.50 EUR")

    def test_03_booker_search_availability_and_instant_book(self) -> None:
        self.page.goto(f"{self.base_url}/ui")
        self._register_apartment_via_ui(
            name="City Loft",
            country="Italy",
            city="Rome",
            street="Via Corso 12",
            max_people=4,
            price="120.00",
        )

        # Navigate to Search & Instant Book view
        self.page.locator("#nav-search").click()
        self.page.locator("#avail-start-date").fill("2026-11-10")
        self.page.locator("#avail-end-date").fill("2026-11-15")
        self.page.locator("#avail-num-people").fill("2")
        self.page.locator("#avail-search-btn").click()

        expect(self.page.locator("#avail-count-badge")).to_have_text("1 Available")
        card = self.page.locator('article[data-apartment-card="City Loft"]')
        expect(card).to_be_visible()
        expect(card).to_contain_text("€600.00 EUR")

        # Click "Book This Apartment" -> opens Instant Book modal
        card.locator('button[data-book-apartment="City Loft"]').click()
        expect(self.page.locator("#instant-book-modal")).to_be_visible()
        self.page.locator("#instant-booker-name").fill("Elena Rostova")
        self.page.locator("#instant-book-confirm").click()

        expect(self.page.locator("#instant-book-modal")).to_be_hidden()
        expect(self.page.locator("#status-banner-code")).to_have_text("201 CREATED")
        expect(self.page.locator("#status-banner-message")).to_contain_text("Elena Rostova")

        # Because City Loft is now booked for 2026-11-10 -> 2026-11-15, availability is now 0
        expect(self.page.locator("#avail-count-badge")).to_have_text("0 Available")

    def test_04_booker_create_overlap_change_and_cancel_booking(self) -> None:
        self.page.goto(f"{self.base_url}/ui")
        self._register_apartment_via_ui(
            name="Canal Suite",
            country="Netherlands",
            city="Amsterdam",
            street="Prinsengracht 20",
            max_people=3,
            price="150.00",
        )

        # Switch to Create & Manage Bookings view
        self.page.locator("#nav-bookings").click()
        self.page.locator("#booking-apartment-select").select_option("Canal Suite")
        self.page.locator("#booking-booker-name").fill("Marcus Vance")
        self.page.locator("#booking-start-date").fill("2026-12-01")
        self.page.locator("#booking-end-date").fill("2026-12-05")
        self.page.locator("#booking-num-people").fill("2")

        # Verify live pricing preview (4 nights * 150 = 600.00)
        expect(self.page.locator("#calc-nights")).to_have_text("4 nights")
        expect(self.page.locator("#calc-total")).to_have_text("€600.00 EUR")

        self.page.locator("#create-booking-submit").click()
        expect(self.page.locator("#status-banner-code")).to_have_text("201 CREATED")
        expect(self.page.locator("#bookings-table-body")).to_contain_text("Marcus Vance")
        expect(self.page.locator("#bookings-table-body")).to_contain_text(
            "Netherlands, Amsterdam, Prinsengracht 20"
        )
        expect(self.page.locator("#bookings-table-body")).to_contain_text("Max 3")
        expect(self.page.locator("#bookings-table-body")).to_contain_text("2 / 3")
        expect(self.page.locator("#bookings-table-body")).to_contain_text("€600.00 EUR")
        expect(self.page.locator("#bookings-table-body")).not_to_contain_text("undefined")

        # Attempting an overlapping booking must fail with 409 Conflict
        self.page.locator("#booking-booker-name").fill("Overlap Guest")
        self.page.locator("#booking-start-date").fill("2026-12-03")
        self.page.locator("#booking-end-date").fill("2026-12-07")
        self.page.locator("#create-booking-submit").click()
        expect(self.page.locator("#status-banner-code")).to_contain_text("409")

        # Change existing booking (PATCH /api/bookings)
        booking_row = self.page.locator("#bookings-table-body tr").first
        booking_row.locator('button[data-action="change-booking"]').click()
        expect(self.page.locator("#change-booking-modal")).to_be_visible()

        self.page.locator("#change-start-date").fill("2026-12-02")
        self.page.locator("#change-end-date").fill("2026-12-08")
        self.page.locator("#change-num-people").fill("3")
        expect(self.page.locator("#change-recalc-total")).to_contain_text("€900.00 EUR")
        self.page.locator("#confirm-change-booking-btn").click()

        expect(self.page.locator("#change-booking-modal")).to_be_hidden()
        expect(self.page.locator("#status-banner-code")).to_have_text("200 OK")
        expect(self.page.locator("#bookings-table-body")).to_contain_text("2026-12-02 → 2026-12-08 (6n)")
        expect(self.page.locator("#bookings-table-body")).to_contain_text("€900.00 EUR")

        # Cancel booking (DELETE /api/bookings) -> completely removed from overview
        updated_row = self.page.locator("#bookings-table-body tr").first
        updated_row.locator('button[data-action="cancel-booking"]').click()
        expect(self.page.locator("#cancel-booking-modal")).to_be_visible()
        self.page.locator("#confirm-cancel-booking-btn").click()

        expect(self.page.locator("#cancel-booking-modal")).to_be_hidden()
        expect(self.page.locator("#status-banner-code")).to_have_text("200 OK")
        expect(self.page.locator("#bookings-count-badge")).to_have_text("0 Active Bookings")
        expect(self.page.locator("#bookings-table-body")).to_contain_text("No active bookings found in SQLite.")

    def test_05_directory_global_overview_and_cascading_apartment_removal(self) -> None:
        self.page.goto(f"{self.base_url}/ui")
        self._register_apartment_via_ui(
            name="Danube Panorama",
            country="Hungary",
            city="Budapest",
            street="Vaci utca 34",
            max_people=3,
            price="100.00",
        )

        # Create a booking for Danube Panorama
        self.page.locator("#nav-bookings").click()
        self.page.locator("#booking-apartment-select").select_option("Danube Panorama")
        self.page.locator("#booking-booker-name").fill("Sophie Dubois")
        self.page.locator("#booking-start-date").fill("2027-01-10")
        self.page.locator("#booking-end-date").fill("2027-01-13")
        self.page.locator("#booking-num-people").fill("2")
        self.page.locator("#create-booking-submit").click()
        expect(self.page.locator("#status-banner-code")).to_have_text("201 CREATED")

        # Check Apartments Directory & view toggle
        self.page.locator("#nav-directory").click()
        expect(self.page.locator("#directory-table-body")).to_contain_text("Danube Panorama")
        self.page.locator("#dir-view-cards-btn").click()
        expect(self.page.locator("#dir-cards-wrapper")).to_be_visible()

        # Check Global Bookings Overview KPIs, address/capacity columns & JSON Inspector
        self.page.locator("#nav-overview").click()
        expect(self.page.locator("#kpi-active-bookings")).to_have_text("1")
        expect(self.page.locator("#kpi-total-revenue")).to_have_text("€300.00 EUR")
        expect(self.page.locator("#kpi-avg-stay")).to_have_text("3.0 Nights")
        expect(self.page.locator("#kpi-total-apartments")).to_have_text("1 Units")
        expect(self.page.locator("#overview-table-body")).to_contain_text(
            "Hungary, Budapest, Vaci utca 34"
        )
        expect(self.page.locator("#overview-table-body")).to_contain_text("2 / Max 3")
        expect(self.page.locator("#overview-table-body")).not_to_contain_text("undefined")

        self.page.locator("#overview-table-body button[data-action='inspect-booking']").first.click()
        expect(self.page.locator("#inspector-modal")).to_be_visible()
        expect(self.page.locator("#inspector-json-pre")).to_contain_text("Sophie Dubois")
        self.page.locator("#inspector-modal-done").click()

        # Remove apartment in System Manager and verify cascading deletion of bookings
        self.page.locator("#nav-inventory").click()
        row = self.page.locator('tr[data-inventory-row="Danube Panorama"]')
        row.locator('button[data-action="remove-apartment"]').click()
        expect(self.page.locator("#delete-apartment-modal")).to_be_visible()
        self.page.locator("#confirm-delete-apartment-btn").click()

        expect(self.page.locator("#delete-apartment-modal")).to_be_hidden()
        expect(self.page.locator("#status-banner-code")).to_have_text("200 OK")
        expect(self.page.locator("#inventory-count-badge")).to_have_text("0 Units Managed")

        self.page.locator("#nav-overview").click()
        expect(self.page.locator("#kpi-active-bookings")).to_have_text("0")


if __name__ == "__main__":
    unittest.main()
