"""Repository over the agent_news SQLite database.

All web API queries go through this module so the existing runtime code in
``src/agent_news`` keeps owning the schema.  Read queries use a read-only
connection; write operations (feedback, knowledge upload) use a separate
read-write connection with WAL mode and busy_timeout to coexist with the
cron / bot pipelines that write to the same database.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from .. import db as _db


def _db_path() -> Path:
    return _db.DB_PATH


def _connect() -> sqlite3.Connection:
    """Read-only connection for all GET queries."""
    path = _db_path()
    if not path.exists():
        raise FileNotFoundError(
            f"Agent News database not found at {path}. "
            "Run the digest pipeline at least once or point AGENT_NEWS_DB at the right file."
        )
    uri = f"file:{path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _connect_rw() -> sqlite3.Connection:
    """Read-write connection for feedback / knowledge writes.

    Uses WAL journal mode and a 5-second busy timeout so concurrent
    writes from the cron pipeline or Telegram plugin don't cause
    immediate SQLITE_BUSY errors.
    """
    path = _db_path()
    if not path.exists():
        raise FileNotFoundError(
            f"Agent News database not found at {path}. "
            "Run the digest pipeline at least once or point AGENT_NEWS_DB at the right file."
        )
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA journal_mode = WAL")
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


# ---------------------------------------------------------------------------
# Feedback writes (replicates toggle logic from openclaw-feedback plugin)
# ---------------------------------------------------------------------------

def save_feedback(
    news_id: int,
    user_id: str,
    username: str,
    action: str,
    comment: str | None = None,
) -> dict[str, Any]:
    """Save news feedback with toggle semantics.

    * useful / boring: same user + same action = remove (toggle off),
      different action = update, new = insert.
    * comment: always insert (multiple comments allowed).

    Returns ``{"status": "inserted"|"updated"|"removed", "action": ...}``.
    """
    if action not in ("useful", "boring", "comment"):
        raise ValueError(f"Invalid action: {action}")

    with _connect_rw() as conn:
        if action == "comment":
            conn.execute(
                "INSERT INTO feedback (news_id, user_id, username, action, comment) "
                "VALUES (?, ?, ?, ?, ?)",
                (news_id, user_id, username, action, comment),
            )
            return {"status": "inserted", "action": action}

        existing = conn.execute(
            "SELECT id, action FROM feedback WHERE news_id = ? AND user_id = ? "
            "AND action IN ('useful', 'boring')",
            (news_id, user_id),
        ).fetchone()

        if existing is None:
            conn.execute(
                "INSERT INTO feedback (news_id, user_id, username, action) "
                "VALUES (?, ?, ?, ?)",
                (news_id, user_id, username, action),
            )
            return {"status": "inserted", "action": action}

        if existing["action"] == action:
            conn.execute("DELETE FROM feedback WHERE id = ?", (existing["id"],))
            return {"status": "removed", "action": action}

        conn.execute(
            "UPDATE feedback SET action = ?, username = ? WHERE id = ?",
            (action, username, existing["id"]),
        )
        return {"status": "updated", "action": action}


def save_insight_feedback(
    insight_id: int,
    user_id: str,
    username: str,
    action: str,
    comment: str | None = None,
) -> dict[str, Any]:
    """Same toggle logic as save_feedback but for insight_feedback table."""
    if action not in ("useful", "boring", "comment"):
        raise ValueError(f"Invalid action: {action}")

    with _connect_rw() as conn:
        if action == "comment":
            conn.execute(
                "INSERT INTO insight_feedback (insight_id, user_id, username, action, comment) "
                "VALUES (?, ?, ?, ?, ?)",
                (insight_id, user_id, username, action, comment),
            )
            return {"status": "inserted", "action": action}

        existing = conn.execute(
            "SELECT id, action FROM insight_feedback WHERE insight_id = ? AND user_id = ? "
            "AND action IN ('useful', 'boring')",
            (insight_id, user_id),
        ).fetchone()

        if existing is None:
            conn.execute(
                "INSERT INTO insight_feedback (insight_id, user_id, username, action) "
                "VALUES (?, ?, ?, ?)",
                (insight_id, user_id, username, action),
            )
            return {"status": "inserted", "action": action}

        if existing["action"] == action:
            conn.execute("DELETE FROM insight_feedback WHERE id = ?", (existing["id"],))
            return {"status": "removed", "action": action}

        conn.execute(
            "UPDATE insight_feedback SET action = ?, username = ? WHERE id = ?",
            (action, username, existing["id"]),
        )
        return {"status": "updated", "action": action}


def get_feedback_counts(news_id: int) -> dict[str, int]:
    with _connect() as conn:
        useful = conn.execute(
            "SELECT COUNT(*) FROM feedback WHERE news_id = ? AND action = 'useful'",
            (news_id,),
        ).fetchone()[0]
        boring = conn.execute(
            "SELECT COUNT(*) FROM feedback WHERE news_id = ? AND action = 'boring'",
            (news_id,),
        ).fetchone()[0]
        comments = conn.execute(
            "SELECT COUNT(*) FROM feedback WHERE news_id = ? AND action = 'comment'",
            (news_id,),
        ).fetchone()[0]
    return {"useful": useful, "boring": boring, "comments": comments}


def get_insight_feedback_counts(insight_id: int) -> dict[str, int]:
    with _connect() as conn:
        useful = conn.execute(
            "SELECT COUNT(*) FROM insight_feedback WHERE insight_id = ? AND action = 'useful'",
            (insight_id,),
        ).fetchone()[0]
        boring = conn.execute(
            "SELECT COUNT(*) FROM insight_feedback WHERE insight_id = ? AND action = 'boring'",
            (insight_id,),
        ).fetchone()[0]
        comments = conn.execute(
            "SELECT COUNT(*) FROM insight_feedback WHERE insight_id = ? AND action = 'comment'",
            (insight_id,),
        ).fetchone()[0]
    return {"useful": useful, "boring": boring, "comments": comments}


# ---------------------------------------------------------------------------
# Knowledge writes (replicates dedup logic from openclaw-feedback plugin)
# ---------------------------------------------------------------------------

def save_knowledge_document(
    kind: str,
    content_text: str,
    source_type: str = "text",
    sender_id: str | None = None,
    username: str | None = None,
    file_name: str | None = None,
    mime_type: str | None = None,
    source_key: str | None = None,
) -> dict[str, Any]:
    """Save a knowledge document with SHA256-based deduplication.

    * Same source_key + same content_hash → skip (duplicate).
    * Same source_key + different hash → replace (update).
    * New source_key → insert.
    """
    if kind not in ("metrics", "methodology"):
        raise ValueError(f"Invalid kind: {kind}")

    content_hash = hashlib.sha256(content_text.encode()).hexdigest()
    if not source_key:
        source_key = file_name or content_hash[:16]

    with _connect_rw() as conn:
        # Check for exact duplicate
        dup = conn.execute(
            "SELECT id FROM knowledge_documents "
            "WHERE kind = ? AND source_key = ? AND content_hash = ?",
            (kind, source_key, content_hash),
        ).fetchone()
        if dup:
            return {"status": "duplicate", "id": dup["id"]}

        # Delete previous versions with same source_key
        prev = conn.execute(
            "SELECT id FROM knowledge_documents WHERE kind = ? AND source_key = ?",
            (kind, source_key),
        ).fetchone()

        if prev:
            conn.execute(
                "DELETE FROM knowledge_documents WHERE kind = ? AND source_key = ?",
                (kind, source_key),
            )

        conn.execute(
            "INSERT INTO knowledge_documents "
            "(kind, sender_id, username, source_type, file_name, mime_type, "
            " content_text, source_key, content_hash, revision, is_current) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1)",
            (kind, sender_id, username, source_type, file_name, mime_type,
             content_text, source_key, content_hash),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        status = "updated" if prev else "inserted"

    return {"status": status, "id": new_id}


# ---------------------------------------------------------------------------
# SSE: high-water marks for change detection
# ---------------------------------------------------------------------------

def get_watermarks() -> dict[str, int]:
    """Return current max IDs for tables that SSE monitors."""
    with _connect() as conn:
        news_max = conn.execute("SELECT COALESCE(MAX(id), 0) FROM raw_news").fetchone()[0]
        insights_max = conn.execute("SELECT COALESCE(MAX(id), 0) FROM insights").fetchone()[0]
        feedback_max = conn.execute("SELECT COALESCE(MAX(id), 0) FROM feedback").fetchone()[0]
        sent_max = conn.execute("SELECT COALESCE(MAX(id), 0) FROM sent_news").fetchone()[0]
    return {
        "news": news_max,
        "insights": insights_max,
        "feedback": feedback_max,
        "sent": sent_max,
    }
