"""Exercise the built Compose service using an isolated, disposable data volume.

Run after `docker compose build`: python tests/docker_smoke.py
"""

from __future__ import annotations

import subprocess
import tempfile
import uuid
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    # Never use the user's normal Compose project or its booking data.
    compose = ["docker", "compose", "--project-name", "booking-smoke-" + uuid.uuid4().hex[:12]]

    def run(*args: str, input_text: str = "", expected_status: int = 0) -> str:
        result = subprocess.run(
            [*compose, *args], cwd=PROJECT_ROOT, input=input_text,
            text=True, capture_output=True, timeout=90,
        )
        if result.returncode != expected_status:
            raise RuntimeError(f"Docker command failed: {args}\n{result.stdout}\n{result.stderr}")
        return result.stdout + result.stderr

    try:
        run("config", "--quiet")
        # Verify non-root execution and that the runtime image contains no host data/tests.
        run("run", "--rm", "-T", "booking", "python", "-c",
            "import os; from pathlib import Path; "
            "assert os.getuid() != 0; "
            "assert not Path('/app/apartment_booking.db').exists(); "
            "assert not Path('/app/tests').exists(); "
            "assert not Path('/app/.git').exists(); "
            "assert os.environ['APARTMENT_BOOKING_DB_PATH'] == '/data/apartment_booking.db'")
        output = run("run", "--rm", "-T", "booking", input_text=(
            "2\napartment add\nDocker Demo\nItaly\nRome\nExample 1\n2\n100\n"
            "role\n1\nbooking create\nDocker Demo\n2027-08-10\n2027-08-12\nDemo Guest\n2\nexit\n"
        ))
        assert "is booked for Demo Guest" in output, output
        assert "200.00 EUR" in output, output
        # A new container must find records created by the removed first container.
        output = run("run", "--rm", "-T", "booking", "python", "src/main.py",
                     input_text="1\nbooking view\nexit\n")
        assert "Demo Guest" in output and "200.00 EUR" in output, output
        # Verify the documented stopped-service backup procedure.
        run("create", "booking")
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "backup.db"
            run("cp", "booking:/data/apartment_booking.db", str(backup))
            assert backup.read_bytes().startswith(b"SQLite format 3\x00")
            restore = (
                "import os, sqlite3; from pathlib import Path; "
                "p=Path(os.environ['APARTMENT_BOOKING_DB_PATH']); "
                "assert not p.exists(), 'Destination database already exists; import cancelled'; "
                "source=sqlite3.connect('file:/restore.db?mode=ro', uri=True); "
                "destination=sqlite3.connect(p); source.backup(destination); "
                "destination.close(); source.close()"
            )
            import_args = ("run", "--rm", "-T", "--volume", f"{backup}:/restore.db:ro",
                           "--env", "APARTMENT_BOOKING_DB_PATH=/data/imported.db",
                           "booking", "python", "-c", restore)
            run(*import_args)
            output = run(*import_args, expected_status=1)
            assert "import cancelled" in output, output
            output = run("run", "--rm", "-T", "--env", "APARTMENT_BOOKING_DB_PATH=/data/imported.db",
                         "booking", input_text="1\nbooking view\nexit\n")
            assert "Demo Guest" in output, output
        output = run("run", "--rm", "-T", "--env", "APARTMENT_BOOKING_DB_PATH=/missing/booking.db",
                     "booking", expected_status=1)
        assert "Database operation failed" in output and "Traceback" not in output, output
        print("Docker smoke checks passed: non-root image, both launchers, persistent bookings, backup/import and startup errors.")
    finally:
        # --volumes is safe only here: this random project was created by this test.
        run("down", "--volumes", "--remove-orphans")


if __name__ == "__main__":
    main()
