"""FastAPI factory for the Agent News dashboard.

The app is intentionally small: it exposes the existing SQLite database
as JSON for the React frontend in ``web/``. All business logic
(parsing, classification, sending) stays in the cron/bot pipelines —
this layer is read-only.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .. import db as _db
from .routes import chat, events, feedback, gosbs, insights, knowledge, news, stats


def _cors_origins() -> list[str]:
    raw = os.getenv(
        "AGENT_NEWS_WEB_CORS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000",
    )
    return [item.strip() for item in raw.split(",") if item.strip()]


def create_app() -> FastAPI:
    app = FastAPI(
        title="Agent News Dashboard API",
        version="0.1.0",
        description=(
            "Interactive API on top of the OpenClaw / Agent News SQLite database. "
            "Powers the React dashboard in web/. Supports feedback, knowledge "
            "upload, SSE real-time events, and chat with the OpenClaw agent."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for module in (news, insights, gosbs, feedback, knowledge, stats, events, chat):
        app.include_router(module.router, prefix="/api/v1")

    @app.get("/health")
    def health() -> JSONResponse:
        path: Path = _db.DB_PATH
        ok = path.exists()
        return JSONResponse(
            content={
                "status": "ok" if ok else "no_database",
                "db_path": str(path),
                "db_exists": ok,
                "db_size_bytes": path.stat().st_size if ok else 0,
            },
            status_code=200 if ok else 503,
        )

    @app.get("/")
    def root() -> dict[str, str]:
        return {"service": "agent-news-web", "docs": "/docs", "health": "/health"}

    return app


app = create_app()
