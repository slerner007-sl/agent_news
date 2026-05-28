"""Smoke test for the web API.

Runs the FastAPI app in-process against a temporary SQLite database
seeded with one news / classification / insight / feedback row, and
verifies every read endpoint plus the Basic-auth gate.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fastapi.testclient import TestClient  # noqa: E402

import agent_news.db as _db  # noqa: E402


def _seed_db(path: Path) -> None:
    _db.DB_PATH = path
    _db.init_db()
    with _db.get_conn() as conn:
        conn.execute(
            "INSERT INTO gosb_config(name, chat_id, region, keywords, system_prompt, active) "
            "VALUES (?, ?, ?, ?, ?, 1)",
            ("Samara GOSB", "-100", "Самара", '["банк"]', "prompt"),
        )
        conn.execute(
            "INSERT INTO raw_news(url, title, body, source, published_at, collected_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("http://example/n1", "Test news", "Body", "samara", "2026-05-27", "2026-05-27"),
        )
        conn.execute(
            "INSERT INTO news_classification(gosb_id, news_id, mode, relevant, category, confidence, summary) "
            "VALUES (1, 1, 'samara_news', 1, 'bank', 0.9, 'Test summary')",
        )
        conn.execute(
            "INSERT INTO sent_news(gosb_id, news_id, summary, run_id) VALUES (1, 1, 'summ', 'run-1')",
        )
        conn.execute(
            "INSERT INTO insights(gosb_id, run_id, title, insight_type, priority, confidence, "
            "why_it_matters, suggested_action) VALUES "
            "(1, 'run-1', 'Сигнал', 'client_signal', 'high', 0.9, 'why', 'do this')",
        )
        conn.execute(
            "INSERT INTO feedback(gosb_id, news_id, user_id, username, action, comment) "
            "VALUES (1, 1, 'u1', 'tester', 'useful', 'great')",
        )


def main() -> int:
    tmp = Path(tempfile.mkdtemp()) / "news_bot.db"
    _seed_db(tmp)

    # No auth — anonymous access.
    for var in ("AGENT_NEWS_WEB_USER", "AGENT_NEWS_WEB_PASSWORD"):
        os.environ.pop(var, None)

    from agent_news.web import create_app

    client = TestClient(create_app())

    assert client.get("/health").json()["db_exists"] is True

    totals = client.get("/api/v1/stats/summary?since_hours=24").json()["totals"]
    assert totals["news_total"] == 1
    assert totals["insights_total"] == 1
    assert totals["feedback_total"] == 1

    news_resp = client.get("/api/v1/news?limit=5").json()
    assert news_resp["total"] == 1
    assert news_resp["items"][0]["classifications"][0]["category"] == "bank"

    relevant_resp = client.get("/api/v1/news?only_relevant=true&gosb_id=1").json()
    assert relevant_resp["total"] == 1

    insight = client.get("/api/v1/insights?priority=high").json()["items"][0]
    assert insight["title"] == "Сигнал"
    assert insight["gosb_name"] == "Samara GOSB"

    assert client.get("/api/v1/gosbs").json()["items"][0]["region"] == "Самара"
    assert client.get("/api/v1/feedback").json()["total"] == 1
    assert client.get("/api/v1/knowledge").json()["total"] == 0

    # Now enforce basic auth.
    os.environ["AGENT_NEWS_WEB_USER"] = "radar"
    os.environ["AGENT_NEWS_WEB_PASSWORD"] = "s3cret"

    secured = TestClient(create_app())
    assert secured.get("/api/v1/news").status_code == 401
    assert secured.get("/api/v1/news", auth=("radar", "wrong")).status_code == 401
    assert secured.get("/api/v1/news", auth=("radar", "s3cret")).status_code == 200
    # /health stays open for monitoring.
    assert secured.get("/health").status_code == 200

    print("web api ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
