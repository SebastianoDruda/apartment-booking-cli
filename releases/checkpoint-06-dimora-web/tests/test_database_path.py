"""Check optional container storage configuration without touching local data."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestDatabasePath(unittest.TestCase):
    def test_unset_or_empty_path_keeps_original_default(self) -> None:
        for value in (None, ""):
            with self.subTest(value=value):
                env = os.environ.copy()
                env.pop("APARTMENT_BOOKING_DB_PATH", None)
                if value is not None:
                    env["APARTMENT_BOOKING_DB_PATH"] = value
                result = subprocess.run(
                    [sys.executable, "-c", "from apartment_booking.database import DEFAULT_DB_PATH; print(DEFAULT_DB_PATH)"],
                    cwd=PROJECT_ROOT, env=env, capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(Path(result.stdout.strip()), PROJECT_ROOT / "apartment_booking.db")

    def test_both_launchers_share_configured_database_across_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "custom storage.db"
            env = dict(os.environ, APARTMENT_BOOKING_DB_PATH=str(path))
            create = subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "main.py")],
                cwd=directory, env=env, capture_output=True, text=True, timeout=10,
                input="2\napartment add\nContainer Demo\nItaly\nRome\nExample 1\n2\n100\nexit\n",
            )
            self.assertEqual(create.returncode, 0, create.stderr)
            self.assertTrue(path.is_file())
            view = subprocess.run(
                [sys.executable, "-m", "apartment_booking"],
                cwd=PROJECT_ROOT, env=env, capture_output=True, text=True, timeout=10,
                input="1\napartment view\nexit\n",
            )
            self.assertEqual(view.returncode, 0, view.stderr)
            self.assertIn("Container Demo", view.stdout)
            conn = sqlite3.connect(path)
            try:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM apartments").fetchone()[0], 1)
            finally:
                conn.close()

    def test_missing_configured_parent_fails_without_creating_another_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing" / "booking.db"
            env = dict(os.environ, APARTMENT_BOOKING_DB_PATH=str(path))
            result = subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "main.py")],
                cwd=directory, env=env, input="", capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("Database operation failed", result.stderr)
            self.assertFalse(path.exists())
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_non_sqlite_configured_file_fails_without_traceback_or_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "notes.db"
            content = b"This text file is not a SQLite database.\n" * 20
            path.write_bytes(content)
            env = dict(os.environ, APARTMENT_BOOKING_DB_PATH=str(path))
            result = subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "main.py")],
                cwd=directory, env=env, input="", capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("Database operation failed", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(path.read_bytes(), content)


if __name__ == "__main__":
    unittest.main()
