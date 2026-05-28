"""Web API for the Agent News dispatcher.

Read-mostly FastAPI wrapper over the existing SQLite database at
``data/news_bot.db``. Designed to live on the same VPS as the OpenClaw
agent so the React dashboard in ``web/`` can show the same news,
insights and feedback that the Telegram digest already uses.
"""

from .app import create_app

__all__ = ["create_app"]
