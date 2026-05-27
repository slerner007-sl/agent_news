"""Read-mostly repository over the agent_news SQLite database.

All web API queries go through this module so the existing runtime code in
``src/agent_news`` keeps owning the schema. We only ever open the database
read-only here — write operations stay in the cron / bot pipelines.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .. import db as _db


def _db_path() -> Path:
    return _db.DB_PATH


def _connect() -> sqlite3.Connection:
    path = _db_path()
    if not path.exists():
        raise FileNotFoundError(
            f"Agent News database not found at {path}. "
            "Run the digest pipeline at least once or point AGENT_NEWS_DB at the right file."
        )
    # Open read-only to avoid accidental writes from the web layer.
    uri = f"file:{path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}


def _rows(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [{k: r[k] for k in r.keys()} for r in rows]


def _maybe_json(value: Any) -> Any:
    if not value:
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value
    return value


# ---------------------------------------------------------------------------
# ГОСБ (regional bank branches)
# ---------------------------------------------------------------------------

def list_gosbs(active_only: bool = False) -> list[dict[str, Any]]:
    sql = "SELECT id, name, chat_id, thread_id, region, keywords, active, created_at FROM gosb_config"
    params: tuple[Any, ...] = ()
    if active_only:
        sql += " WHERE active = 1"
    sql += " ORDER BY id"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    out = _rows(rows)
    for item in out:
        item["keywords"] = _maybe_json(item.get("keywords"))
    return out


def get_gosb(gosb_id: int) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM gosb_config WHERE id = ?",
            (gosb_id,),
        ).fetchone()
    item = _row(row)
    if item:
        item["keywords"] = _maybe_json(item.get("keywords"))
    return item


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

def list_news(
    *,
    gosb_id: int | None = None,
    only_relevant: bool = False,
    since_hours: int | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    where: list[str] = []
    params: list[Any] = []
    join = ""

    if gosb_id is not None:
        join = (
            "LEFT JOIN sent_news s ON s.news_id = r.id AND s.gosb_id = ? "
            "LEFT JOIN news_classification c ON c.news_id = r.id AND c.gosb_id = ? "
        )
        params.extend([gosb_id, gosb_id])
        if only_relevant:
            where.append("(s.id IS NOT NULL OR (c.relevant = 1))")
    else:
        join = (
            "LEFT JOIN sent_news s ON s.news_id = r.id "
            "LEFT JOIN news_classification c ON c.news_id = r.id "
        )
        if only_relevant:
            where.append("(s.id IS NOT NULL OR c.relevant = 1)")

    if since_hours is not None:
        where.append("r.collected_at >= datetime('now', ? || ' hours')")
        params.append(f"-{int(since_hours)}")

    if search:
        where.append("(r.title LIKE ? OR r.body LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like])

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    base_select = f"""
        SELECT DISTINCT r.id, r.url, r.title, r.body, r.source,
               r.published_at, r.collected_at
        FROM raw_news r
        {join}
        {where_sql}
        ORDER BY COALESCE(r.published_at, r.collected_at) DESC
        LIMIT ? OFFSET ?
    """
    count_sql = f"SELECT COUNT(DISTINCT r.id) FROM raw_news r {join} {where_sql}"

    list_params = list(params) + [int(limit), int(offset)]

    with _connect() as conn:
        total = conn.execute(count_sql, params).fetchone()[0]
        rows = conn.execute(base_select, list_params).fetchall()
        items = _rows(rows)

        if items:
            ids = [item["id"] for item in items]
            placeholders = ",".join(["?"] * len(ids))
            cls_rows = conn.execute(
                f"""
                SELECT news_id, gosb_id, mode, relevant, category, impact,
                       confidence, summary, reject_reason, created_at
                FROM news_classification
                WHERE news_id IN ({placeholders})
                """,
                ids,
            ).fetchall()
            sent_rows = conn.execute(
                f"""
                SELECT news_id, gosb_id, summary, run_id, sent_at
                FROM sent_news
                WHERE news_id IN ({placeholders})
                """,
                ids,
            ).fetchall()
            fb_rows = conn.execute(
                f"""
                SELECT news_id, gosb_id, user_id, username, action, comment, created_at
                FROM feedback
                WHERE news_id IN ({placeholders})
                ORDER BY created_at DESC
                """,
                ids,
            ).fetchall()
        else:
            cls_rows = sent_rows = fb_rows = []

    by_news_cls: dict[int, list[dict[str, Any]]] = {}
    for r in cls_rows:
        by_news_cls.setdefault(r["news_id"], []).append({k: r[k] for k in r.keys()})
    by_news_sent: dict[int, list[dict[str, Any]]] = {}
    for r in sent_rows:
        by_news_sent.setdefault(r["news_id"], []).append({k: r[k] for k in r.keys()})
    by_news_fb: dict[int, list[dict[str, Any]]] = {}
    for r in fb_rows:
        by_news_fb.setdefault(r["news_id"], []).append({k: r[k] for k in r.keys()})

    for item in items:
        nid = item["id"]
        item["classifications"] = by_news_cls.get(nid, [])
        item["sent_to"] = by_news_sent.get(nid, [])
        item["feedback"] = by_news_fb.get(nid, [])

    return {"items": items, "total": int(total), "limit": int(limit), "offset": int(offset)}


def get_news(news_id: int) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM raw_news WHERE id = ?", (news_id,)).fetchone()
        if not row:
            return None
        item = _row(row)
        item["classifications"] = _rows(conn.execute(
            "SELECT * FROM news_classification WHERE news_id = ? ORDER BY created_at DESC",
            (news_id,),
        ).fetchall())
        item["sent_to"] = _rows(conn.execute(
            "SELECT * FROM sent_news WHERE news_id = ? ORDER BY sent_at DESC",
            (news_id,),
        ).fetchall())
        item["feedback"] = _rows(conn.execute(
            "SELECT * FROM feedback WHERE news_id = ? ORDER BY created_at DESC",
            (news_id,),
        ).fetchall())
        item["metric_links"] = _rows(conn.execute(
            "SELECT * FROM news_metric_links WHERE news_id = ? ORDER BY created_at DESC",
            (news_id,),
        ).fetchall())
    return item


# ---------------------------------------------------------------------------
# Insights
# ---------------------------------------------------------------------------

def list_insights(
    *,
    gosb_id: int | None = None,
    priority: str | None = None,
    insight_type: str | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    where: list[str] = []
    params: list[Any] = []
    if gosb_id is not None:
        where.append("i.gosb_id = ?")
        params.append(gosb_id)
    if priority:
        where.append("i.priority = ?")
        params.append(priority)
    if insight_type:
        where.append("i.insight_type = ?")
        params.append(insight_type)
    if status:
        where.append("i.status = ?")
        params.append(status)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    list_sql = f"""
        SELECT i.*, g.name AS gosb_name, g.region AS gosb_region
        FROM insights i
        LEFT JOIN gosb_config g ON g.id = i.gosb_id
        {where_sql}
        ORDER BY datetime(i.created_at) DESC
        LIMIT ? OFFSET ?
    """
    count_sql = f"SELECT COUNT(*) FROM insights i {where_sql}"

    with _connect() as conn:
        total = conn.execute(count_sql, params).fetchone()[0]
        rows = conn.execute(list_sql, list(params) + [int(limit), int(offset)]).fetchall()
        items = _rows(rows)
        if items:
            ids = [it["id"] for it in items]
            placeholders = ",".join(["?"] * len(ids))
            news_links = conn.execute(
                f"""
                SELECT l.insight_id, l.news_id, r.title, r.url, r.source,
                       COALESCE(r.published_at, r.collected_at) AS dt
                FROM insight_news_links l
                JOIN raw_news r ON r.id = l.news_id
                WHERE l.insight_id IN ({placeholders})
                """,
                ids,
            ).fetchall()
            metric_links = conn.execute(
                f"""
                SELECT * FROM insight_metric_links
                WHERE insight_id IN ({placeholders})
                """,
                ids,
            ).fetchall()
            fb_rows = conn.execute(
                f"""
                SELECT * FROM insight_feedback
                WHERE insight_id IN ({placeholders})
                ORDER BY created_at DESC
                """,
                ids,
            ).fetchall()
        else:
            news_links = metric_links = fb_rows = []

    by_news: dict[int, list[dict[str, Any]]] = {}
    for r in news_links:
        by_news.setdefault(r["insight_id"], []).append({k: r[k] for k in r.keys()})
    by_metric: dict[int, list[dict[str, Any]]] = {}
    for r in metric_links:
        by_metric.setdefault(r["insight_id"], []).append({k: r[k] for k in r.keys()})
    by_fb: dict[int, list[dict[str, Any]]] = {}
    for r in fb_rows:
        by_fb.setdefault(r["insight_id"], []).append({k: r[k] for k in r.keys()})

    for it in items:
        it["news_links"] = by_news.get(it["id"], [])
        it["metric_links"] = by_metric.get(it["id"], [])
        it["feedback"] = by_fb.get(it["id"], [])
        it["source"] = _maybe_json(it.get("source_json"))
        it.pop("llm_raw_json", None)

    return {"items": items, "total": int(total), "limit": int(limit), "offset": int(offset)}


# ---------------------------------------------------------------------------
# Feedback (read-only summary)
# ---------------------------------------------------------------------------

def list_feedback(
    *,
    gosb_id: int | None = None,
    action: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    where: list[str] = []
    params: list[Any] = []
    if gosb_id is not None:
        where.append("f.gosb_id = ?")
        params.append(gosb_id)
    if action:
        where.append("f.action = ?")
        params.append(action)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    list_sql = f"""
        SELECT f.id, f.gosb_id, f.news_id, f.user_id, f.username,
               f.action, f.comment, f.created_at,
               r.title AS news_title, r.url AS news_url,
               g.name AS gosb_name
        FROM feedback f
        LEFT JOIN raw_news r ON r.id = f.news_id
        LEFT JOIN gosb_config g ON g.id = f.gosb_id
        {where_sql}
        ORDER BY datetime(f.created_at) DESC
        LIMIT ? OFFSET ?
    """
    count_sql = f"SELECT COUNT(*) FROM feedback f {where_sql}"

    with _connect() as conn:
        total = conn.execute(count_sql, params).fetchone()[0]
        rows = conn.execute(list_sql, list(params) + [int(limit), int(offset)]).fetchall()

    return {
        "items": _rows(rows),
        "total": int(total),
        "limit": int(limit),
        "offset": int(offset),
    }


# ---------------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------------

def list_knowledge(*, kind: str | None = None, limit: int = 100, offset: int = 0) -> dict[str, Any]:
    where: list[str] = ["COALESCE(is_current, 1) = 1"]
    params: list[Any] = []
    if kind:
        where.append("kind = ?")
        params.append(kind)
    where_sql = "WHERE " + " AND ".join(where)

    list_sql = f"""
        SELECT id, kind, thread_id, conversation_id, sender_id, username,
               source_type, file_name, mime_type, source_key,
               substr(COALESCE(content_text,''), 1, 600) AS preview,
               length(COALESCE(content_text,'')) AS content_length,
               revision, created_at
        FROM knowledge_documents
        {where_sql}
        ORDER BY datetime(created_at) DESC
        LIMIT ? OFFSET ?
    """
    count_sql = f"SELECT COUNT(*) FROM knowledge_documents {where_sql}"

    with _connect() as conn:
        total = conn.execute(count_sql, params).fetchone()[0]
        rows = conn.execute(list_sql, list(params) + [int(limit), int(offset)]).fetchall()

    return {
        "items": _rows(rows),
        "total": int(total),
        "limit": int(limit),
        "offset": int(offset),
    }


def get_knowledge(doc_id: int) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM knowledge_documents WHERE id = ?",
            (doc_id,),
        ).fetchone()
    return _row(row)


# ---------------------------------------------------------------------------
# Stats / dashboard
# ---------------------------------------------------------------------------

def stats_summary(*, since_hours: int = 168) -> dict[str, Any]:
    """High-level counters for the dashboard.

    ``since_hours`` defaults to 7 days — same horizon the digest uses
    for "недавние новости".
    """
    since_param = f"-{int(since_hours)} hours"
    with _connect() as conn:
        totals = {
            "gosbs_total": conn.execute("SELECT COUNT(*) FROM gosb_config").fetchone()[0],
            "gosbs_active": conn.execute("SELECT COUNT(*) FROM gosb_config WHERE active = 1").fetchone()[0],
            "news_total": conn.execute("SELECT COUNT(*) FROM raw_news").fetchone()[0],
            "insights_total": conn.execute("SELECT COUNT(*) FROM insights").fetchone()[0],
            "feedback_total": conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0],
            "knowledge_total": conn.execute(
                "SELECT COUNT(*) FROM knowledge_documents WHERE COALESCE(is_current, 1) = 1"
            ).fetchone()[0],
        }
        recent = {
            "news_recent": conn.execute(
                "SELECT COUNT(*) FROM raw_news WHERE collected_at >= datetime('now', ?)",
                (since_param,),
            ).fetchone()[0],
            "sent_recent": conn.execute(
                "SELECT COUNT(*) FROM sent_news WHERE sent_at >= datetime('now', ?)",
                (since_param,),
            ).fetchone()[0],
            "insights_recent": conn.execute(
                "SELECT COUNT(*) FROM insights WHERE created_at >= datetime('now', ?)",
                (since_param,),
            ).fetchone()[0],
            "feedback_recent": conn.execute(
                "SELECT COUNT(*) FROM feedback WHERE created_at >= datetime('now', ?)",
                (since_param,),
            ).fetchone()[0],
        }
        priorities = _rows(conn.execute(
            """
            SELECT priority, COUNT(*) AS n
            FROM insights
            WHERE created_at >= datetime('now', ?)
            GROUP BY priority
            """,
            (since_param,),
        ).fetchall())
        feedback_breakdown = _rows(conn.execute(
            """
            SELECT action, COUNT(*) AS n
            FROM feedback
            WHERE created_at >= datetime('now', ?)
            GROUP BY action
            """,
            (since_param,),
        ).fetchall())
        latest_runs = _rows(conn.execute(
            """
            SELECT run_id, MIN(sent_at) AS started_at, MAX(sent_at) AS finished_at,
                   COUNT(DISTINCT gosb_id) AS gosbs, COUNT(*) AS messages
            FROM sent_news
            WHERE run_id IS NOT NULL AND run_id <> ''
            GROUP BY run_id
            ORDER BY MAX(sent_at) DESC
            LIMIT 10
            """,
        ).fetchall())
        timeline = _rows(conn.execute(
            """
            SELECT substr(collected_at, 1, 10) AS day, COUNT(*) AS n
            FROM raw_news
            WHERE collected_at >= datetime('now', ?)
            GROUP BY day
            ORDER BY day
            """,
            (since_param,),
        ).fetchall())

    return {
        "since_hours": int(since_hours),
        "totals": totals,
        "recent": recent,
        "insight_priority_breakdown": priorities,
        "feedback_breakdown": feedback_breakdown,
        "latest_runs": latest_runs,
        "news_timeline": timeline,
    }
