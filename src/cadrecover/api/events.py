"""Server-Sent Events from the `events` table (owner: agent C).

Each message carries `id: <event_id>`, so a browser's EventSource resumes with `Last-Event-ID` and receives
only newer rows. The table is append-only and the cursor is its AUTOINCREMENT id, so a reconnect rebuilds the
same state. New rows are found by polling the DB; comment lines keep idle proxies from closing the stream.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Awaitable, Callable

from cadrecover.api import queries
from cadrecover.api.models import EventOut

SSE_RETRY_MS = 2000


def format_event(ev: EventOut) -> str:
    return f"id: {ev.event_id}\ndata: {json.dumps(ev.model_dump(), separators=(',', ':'))}\n\n"


def parse_cursor(value: str | None) -> int | None:
    """A Last-Event-ID / `after` value -> int, or None if absent or not a non-negative integer."""
    if value is None or not value.strip().isdigit():
        return None
    return int(value.strip())


async def event_stream(open_ro: Callable, *, cursor: int, run_id: str | None = None, kind: str | None = None,
                       limit: int | None = None, poll_s: float = 0.5, keepalive_s: float = 15.0,
                       is_disconnected: Callable[[], Awaitable[bool]] | None = None) -> AsyncIterator[str]:
    """Yield SSE frames for events with id > cursor, then wait for more. Ends after `limit` events (if set)."""

    def fetch(after: int) -> list[EventOut]:
        con = open_ro()
        try:
            return queries.events(con, after=after, limit=200, run_id=run_id, kind=kind)
        finally:
            con.close()

    yield f"retry: {SSE_RETRY_MS}\n\n"
    sent, last_write = 0, time.monotonic()
    while True:
        if is_disconnected is not None and await is_disconnected():
            return
        batch = await asyncio.to_thread(fetch, cursor)
        for ev in batch:
            yield format_event(ev)
            cursor, sent, last_write = ev.event_id, sent + 1, time.monotonic()
            if limit is not None and sent >= limit:
                return
        if batch:
            continue  # drain the backlog before sleeping
        if time.monotonic() - last_write >= keepalive_s:
            yield ": keep-alive\n\n"
            last_write = time.monotonic()
        await asyncio.sleep(poll_s)
