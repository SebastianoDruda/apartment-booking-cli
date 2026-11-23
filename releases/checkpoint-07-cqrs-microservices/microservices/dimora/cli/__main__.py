"""Start the CLI against the gateway: ``python -m dimora.cli``.

Set ``DIMORA_API_URL`` to the gateway address (default http://127.0.0.1:8080).
"""

from __future__ import annotations

import os

from apartment_booking.cli import ApartmentBookingCLI
from dimora.cli.client import GatewayClient

DEFAULT_API_URL = "http://127.0.0.1:8080"


def main() -> None:
    client = GatewayClient(os.environ.get("DIMORA_API_URL", "").strip() or DEFAULT_API_URL)
    cli = ApartmentBookingCLI(db=client)
    try:
        cli.run()
    finally:
        client.close()


if __name__ == "__main__":
    main()
