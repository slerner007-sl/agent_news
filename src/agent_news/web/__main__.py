"""Entry point: ``python -m agent_news.web``.

Reads host/port from environment so the same command works inside and
outside Docker:

* ``AGENT_NEWS_WEB_HOST`` (default ``0.0.0.0``)
* ``AGENT_NEWS_WEB_PORT`` (default ``8765``)

Port 8765 is chosen to stay clear of OpenClaw services that may already
run on the VPS.
"""

from __future__ import annotations

import os


def main() -> None:
    import uvicorn

    host = os.getenv("AGENT_NEWS_WEB_HOST", "0.0.0.0")
    port = int(os.getenv("AGENT_NEWS_WEB_PORT", "8765"))
    reload_flag = os.getenv("AGENT_NEWS_WEB_RELOAD", "false").lower() in {"1", "true", "yes"}

    uvicorn.run(
        "agent_news.web.app:app",
        host=host,
        port=port,
        reload=reload_flag,
        log_level=os.getenv("AGENT_NEWS_WEB_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
