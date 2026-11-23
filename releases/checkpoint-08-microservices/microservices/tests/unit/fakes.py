"""In-memory stand-ins for the broker."""

from __future__ import annotations


class RecordingPublisher:
    def __init__(self, fail_on: int | None = None) -> None:
        self.published = []
        self.fail_on = fail_on
        self.closed = 0

    def publish(self, event) -> None:
        if self.fail_on is not None and len(self.published) == self.fail_on:
            raise ConnectionError("broker unreachable")
        self.published.append(event)

    def keep_alive(self) -> None:
        pass

    def close(self) -> None:
        self.closed += 1
