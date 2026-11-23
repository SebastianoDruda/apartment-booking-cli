"""Read-your-writes across the command and query sides.

A command response carries ``X-Consistency-Token: <aggregate>:<id>@<version>``,
naming the row version the write produced. A client that wants to see its own
write sends the token back in ``X-Wait-For`` on its next read; the query service
then waits (briefly) until the read model holds that version or a newer one, and
answers with ``X-Consistency: fresh`` or, after the timeout, ``stale``.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable

TOKEN_HEADER = "X-Consistency-Token"
WAIT_HEADER = "X-Wait-For"
STATUS_HEADER = "X-Consistency"
AGGREGATES = ("apartment", "booking")
MAX_TOKENS = 20

_TOKEN = re.compile(r"^(apartment|booking):([1-9][0-9]{0,17})@([1-9][0-9]{0,8})$")


def format_token(aggregate: str, entity_id: int, version: int) -> str:
    if aggregate not in AGGREGATES:
        raise ValueError(f"Unknown aggregate: {aggregate}")
    return f"{aggregate}:{entity_id}@{version}"


def parse_tokens(header: str | None) -> list[tuple[str, int, int]]:
    """Parse a comma-separated ``X-Wait-For`` header into (aggregate, id, version) tuples."""
    if not header or not header.strip():
        return []
    parts = [part.strip() for part in header.split(",") if part.strip()]
    if len(parts) > MAX_TOKENS:
        raise ValueError(f"{WAIT_HEADER} accepts at most {MAX_TOKENS} tokens.")
    tokens = []
    for part in parts:
        match = _TOKEN.match(part)
        if match is None:
            raise ValueError(f"{WAIT_HEADER} tokens look like apartment:12@3 or booking:7@2.")
        tokens.append((match.group(1), int(match.group(2)), int(match.group(3))))
    return tokens


def wait_until_visible(
    tokens: list[tuple[str, int, int]],
    current_version: Callable[[str, int], int | None],
    timeout: float,
    interval: float = 0.02,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    """Return True once every token's version is visible, False when ``timeout`` expires."""
    deadline = clock() + timeout
    pending = list(tokens)
    while True:
        pending = [
            (aggregate, entity_id, version) for aggregate, entity_id, version in pending
            if (current_version(aggregate, entity_id) or 0) < version
        ]
        if not pending:
            return True
        if clock() >= deadline:
            return False
        sleep(interval)
