from collections.abc import Callable
from typing import TypeVar

from rich.console import Console

from apartment_booking.errors import ValidationError

T = TypeVar("T")


class CancelAction(Exception):
    """The operator explicitly returned from a form."""


class Prompts:
    def __init__(self, console: Console) -> None:
        self.console = console

    def read(self, label: str, *, strip: bool = True) -> str:
        # Render user-supplied current values literally, never as Rich markup.
        self.console.print(label, end="", markup=False, highlight=False)
        value = self.console.input()
        return value.strip() if strip else value

    def choice(self, label: str, maximum: int) -> int:
        while True:
            raw = self.read(label)
            if (
                len(raw) <= len(str(maximum))
                and raw.isascii()
                and raw.isdigit()
                and 0 <= int(raw) <= maximum
            ):
                return int(raw)
            self.console.print(f"ERROR: Enter a number from 0 to {maximum}.")

    def field(
        self, label: str, parse: Callable[[str], T], current: str | None = None
    ) -> T:
        suffix = f" [{current}; blank keeps current]" if current is not None else ""
        while True:
            raw = self.read(f"{label}{suffix} (0. Back): ")
            if raw == "0":
                raise CancelAction
            if raw == "" and current is not None:
                raw = current
            try:
                return parse(raw)
            except (ValueError, ValidationError) as exc:
                self.console.print(f"ERROR: {exc}", markup=False, highlight=False)

    def confirm(self) -> bool:
        return self.choice("0. Cancel   1. Confirm: ", 1) == 1
