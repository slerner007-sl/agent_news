"""Server-Sent Events endpoint for real-time dashboard updates.

Polls the database every few seconds and emits events when new rows
appear in raw_news, insights, feedback, or sent_news.
"""

from __future__ import annotations

import asyncio
import json
import time

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from .. import repository
from ..security import require_auth

router = APIRouter(prefix="/events", tags=["events"])

POLL_INTERVAL = 4  # seconds
KEEPALIVE_INTERVAL = 15  # seconds


async def _event_stream():
    """Yield SSE messages when the database changes."""
    marks = repository.get_watermarks()
    last_keepalive = time.monotonic()

    while True:
        await asyncio.sleep(POLL_INTERVAL)

        try:
            new_marks = repository.get_watermarks()
        except Exception:
            # DB temporarily unavailable — skip this tick
            continue

        events: list[dict] = []
        for key in ("news", "insights", "feedback", "sent"):
            if new_marks[key] > marks[key]:
                events.append({
                    "type": f"{key}:new",
                    "prev": marks[key],
                    "current": new_marks[key],
                    "count": new_marks[key] - marks[key],
                })
        marks = new_marks

        for evt in events:
            data = json.dumps(evt, ensure_ascii=False)
            yield f"event: {evt['type']}\ndata: {data}\n\n"

        now = time.monotonic()
        if not events and (now - last_keepalive) >= KEEPALIVE_INTERVAL:
            yield ": keepalive\n\n"
            last_keepalive = now


@router.get("/stream")
async def stream(username: str = Depends(require_auth)):
    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )
