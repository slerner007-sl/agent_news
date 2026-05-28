"""
insights.py — управленческие инсайты поверх уже отобранных новостей.

Новости отвечают на вопрос "что произошло"; инсайты отвечают на вопрос
"что руководителю ГОСБа стоит проверить или передать в работу".
"""

from __future__ import annotations

from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_PATH = _REPO_ROOT / "src"
if str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))

import argparse
from datetime import datetime
import json
import os
import re
from html import escape
from typing import Iterable

from agent_news.db import (
    get_active_gosbs,
    get_conn,
    get_knowledge_context,
    init_db,
    save_insight,
)
from agent_news.holdings_loader import holdings_display_for_gosb
from agent_news.llm_filter import _openclaw_json


INSIGHT_TYPES = {
    "client_signal",
    "risk_signal",
    "metric_signal",
    "lpr_signal",
    "competitor_signal",
    "no_action",
}
PRIORITIES = {"high", "medium", "low"}
PRIORITY_RANK = {"high": 3, "medium": 2, "low": 1}
MIN_CONFIDENCE = float(os.getenv("INSIGHT_MIN_CONFIDENCE", "0.75"))
BATCH_SIZE = int(os.getenv("INSIGHT_BATCH_SIZE", "12"))
MAX_ITEMS = int(os.getenv("INSIGHT_MAX_ITEMS", "0"))
INSIGHTS_THREAD_ID = os.getenv("INSIGHTS_THREAD_ID", "").strip()
INSIGHTS_THREAD_IDS = os.getenv("INSIGHTS_THREAD_IDS", "").strip()
INSIGHTS_CHAT_ID = os.getenv("INSIGHTS_CHAT_ID", "").strip()
REPORTS_DIR = Path(os.getenv("INSIGHT_REPORTS_DIR", _REPO_ROOT / "agents/reflection_insights_agent/workspace/reports"))
DAILY_CONTEXT_DAYS = int(os.getenv("INSIGHT_DAILY_CONTEXT_DAYS", "7"))


def _chunked(items: list[dict], size: int) -> Iterable[list[dict]]:
    for start in range(0, len(items), size):
        yield items[start:start + size]


def _parse_thread_ids(value: str) -> dict[str, str]:
    value = (value or "").strip()
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return {str(k).strip(): str(v).strip() for k, v in parsed.items() if str(k).strip() and str(v).strip()}

    result: dict[str, str] = {}
    for part in re.split(r"[;\n]+", value):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            key, thread_id = part.split("=", 1)
        elif ":" in part:
            key, thread_id = part.split(":", 1)
        else:
            continue
        key = key.strip()
        thread_id = thread_id.strip()
        if key and thread_id:
            result[key] = thread_id
    return result


def _thread_id_for_insight(insight: dict) -> str:
    mapping = _parse_thread_ids(INSIGHTS_THREAD_IDS)
    gosb_name = str(insight.get("gosb_name") or "").strip()
    return mapping.get(gosb_name) or INSIGHTS_THREAD_ID


def _clean_text(value, limit: int = 1000) -> str:
    return " ".join(str(value or "").split())[:limit]


def _truncate_text(value, max_length: int) -> str:
    text = str(value or "")
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def _normalize_priority(value) -> str:
    priority = str(value or "low").strip().lower()
    return priority if priority in PRIORITIES else "low"


def _normalize_type(value) -> str:
    insight_type = str(value or "no_action").strip().lower()
    return insight_type if insight_type in INSIGHT_TYPES else "no_action"


def _normalize_confidence(value) -> float:
    try:
        confidence = float(value or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    return max(0.0, min(1.0, confidence))


def _normalize_indexes(value, batch_size: int) -> list[int]:
    if not isinstance(value, list):
        value = [value]
    indexes: list[int] = []
    for item in value[:8]:
        try:
            idx = int(item)
        except (TypeError, ValueError):
            continue
        if 0 <= idx < batch_size and idx not in indexes:
            indexes.append(idx)
    return indexes


def _normalize_metric_links(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    links = []
    for raw in value[:8]:
        if not isinstance(raw, dict):
            continue
        metric_key = _clean_text(raw.get("metric_key") or raw.get("metric_name"), 160)
        if not metric_key:
            continue
        links.append({
            "metric_key": metric_key,
            "metric_name": _clean_text(raw.get("metric_name"), 220),
            "impact": _clean_text(raw.get("impact") or "context", 40),
            "confidence": _normalize_confidence(raw.get("confidence")),
            "reason": _clean_text(raw.get("reason"), 500),
        })
    return links


def _quality_gate(item: dict) -> bool:
    if item["insight_type"] == "no_action":
        return False
    if item["priority"] not in {"high", "medium"}:
        return False
    if item["confidence"] < MIN_CONFIDENCE:
        return False
    if len(item["why_it_matters"]) < 20:
        return False
    if len(item["suggested_action"]) < 20:
        return False
    if not item["news_ids"]:
        return False
    return True


def _dedupe_key(item: dict) -> str:
    text = f"{item['title']} {item['suggested_action']}".lower()
    text = re.sub(r"[^а-яёa-z0-9]+", " ", text)
    return " ".join(text.split())[:260]



def _safe_run_id(run_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(run_id or "").strip()).strip(".-")
    return safe[:120] or "run"


def _run_report_dir(run_id: str) -> Path:
    return Path(REPORTS_DIR) / _safe_run_id(run_id)


def _count_actions(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        action = str(row.get("action") or "unknown")
        counts[action] = counts.get(action, 0) + 1
    return counts


def _group_by(rows: list[dict], key: str) -> dict[int, list[dict]]:
    grouped: dict[int, list[dict]] = {}
    for row in rows:
        value = row.get(key)
        if value is None:
            continue
        grouped.setdefault(int(value), []).append(row)
    return grouped


def _collect_run_scope(run_id: str) -> dict:
    with get_conn() as conn:
        sent_total = conn.execute(
            "SELECT COUNT(*) AS c FROM sent_news WHERE run_id = ?",
            (run_id,),
        ).fetchone()["c"]
        gosbs = [
            dict(row)
            for row in conn.execute(
                """
                SELECT g.id AS gosb_id, g.name AS gosb_name, COUNT(*) AS sent_news
                FROM sent_news s
                JOIN gosb_config g ON g.id = s.gosb_id
                WHERE s.run_id = ?
                GROUP BY g.id, g.name
                ORDER BY sent_news DESC, g.name
                """,
                (run_id,),
            ).fetchall()
        ]
        classifications = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                    COALESCE(nc.category, 'unknown') AS category,
                    COALESCE(nc.impact, 'unknown') AS impact,
                    COUNT(*) AS count
                FROM sent_news s
                LEFT JOIN news_classification nc
                    ON nc.gosb_id = s.gosb_id
                   AND nc.news_id = s.news_id
                   AND nc.mode = 'live'
                WHERE s.run_id = ?
                GROUP BY COALESCE(nc.category, 'unknown'), COALESCE(nc.impact, 'unknown')
                ORDER BY count DESC, category
                """,
                (run_id,),
            ).fetchall()
        ]
    return {
        "sent_news_total": int(sent_total or 0),
        "gosbs": gosbs,
        "classifications": classifications,
    }


def _collect_news_feedback(run_id: str) -> list[dict]:
    with get_conn() as conn:
        return [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                    f.action,
                    COALESCE(f.comment, '') AS comment,
                    COALESCE(f.username, '') AS username,
                    f.created_at,
                    r.title AS news_title,
                    r.source,
                    g.name AS gosb_name
                FROM sent_news s
                JOIN raw_news r ON r.id = s.news_id
                JOIN gosb_config g ON g.id = s.gosb_id
                JOIN feedback f
                    ON f.news_id = s.news_id
                   AND (f.gosb_id IS NULL OR f.gosb_id = s.gosb_id)
                WHERE s.run_id = ?
                ORDER BY f.created_at DESC
                """,
                (run_id,),
            ).fetchall()
        ]


def _collect_weak_signal_rows(run_id: str) -> list[dict]:
    with get_conn() as conn:
        return [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                    r.id AS news_id,
                    r.title,
                    r.source,
                    r.url,
                    COALESCE(s.summary, '') AS summary,
                    COALESCE(nc.category, '') AS category,
                    COALESCE(nc.impact, '') AS impact,
                    COALESCE(nc.confidence, 0) AS confidence,
                    COALESCE(nc.reject_reason, '') AS reject_reason,
                    g.name AS gosb_name
                FROM sent_news s
                JOIN raw_news r ON r.id = s.news_id
                JOIN gosb_config g ON g.id = s.gosb_id
                LEFT JOIN news_classification nc
                    ON nc.gosb_id = s.gosb_id
                   AND nc.news_id = s.news_id
                   AND nc.mode = 'live'
                WHERE s.run_id = ?
                  AND NOT EXISTS (
                      SELECT 1
                      FROM insight_news_links l
                      JOIN insights i ON i.id = l.insight_id
                      WHERE i.run_id = s.run_id
                        AND i.gosb_id = s.gosb_id
                        AND l.news_id = s.news_id
                  )
                ORDER BY COALESCE(nc.confidence, 0) DESC, r.id
                LIMIT 30
                """,
                (run_id,),
            ).fetchall()
        ]


def _collect_insight_rows(run_id: str) -> list[dict]:
    with get_conn() as conn:
        insight_rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                    i.id,
                    i.gosb_id,
                    g.name AS gosb_name,
                    i.run_id,
                    i.title,
                    i.insight_type,
                    i.priority,
                    i.confidence,
                    COALESCE(i.why_it_matters, '') AS why_it_matters,
                    COALESCE(i.suggested_action, '') AS suggested_action,
                    COALESCE(i.owner_hint, '') AS owner_hint,
                    COALESCE(i.evidence, '') AS evidence,
                    COALESCE(i.status, '') AS status,
                    i.created_at
                FROM insights i
                JOIN gosb_config g ON g.id = i.gosb_id
                WHERE i.run_id = ?
                ORDER BY
                    CASE i.priority WHEN 'high' THEN 3 WHEN 'medium' THEN 2 ELSE 1 END DESC,
                    i.confidence DESC,
                    i.id
                """,
                (run_id,),
            ).fetchall()
        ]
        metric_rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                    l.insight_id,
                    l.metric_key,
                    COALESCE(l.metric_name, '') AS metric_name,
                    COALESCE(l.impact, '') AS impact,
                    COALESCE(l.confidence, 0) AS confidence,
                    COALESCE(l.reason, '') AS reason
                FROM insight_metric_links l
                JOIN insights i ON i.id = l.insight_id
                WHERE i.run_id = ?
                ORDER BY l.insight_id, l.metric_key
                """,
                (run_id,),
            ).fetchall()
        ]
        news_rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                    l.insight_id,
                    r.id AS news_id,
                    r.title,
                    r.source,
                    r.url
                FROM insight_news_links l
                JOIN insights i ON i.id = l.insight_id
                JOIN raw_news r ON r.id = l.news_id
                WHERE i.run_id = ?
                ORDER BY l.insight_id, r.id
                """,
                (run_id,),
            ).fetchall()
        ]
        feedback_rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                    f.insight_id,
                    f.action,
                    COALESCE(f.comment, '') AS comment,
                    COALESCE(f.username, '') AS username,
                    f.created_at
                FROM insight_feedback f
                JOIN insights i ON i.id = f.insight_id
                WHERE i.run_id = ?
                ORDER BY f.created_at DESC
                """,
                (run_id,),
            ).fetchall()
        ]

    metrics_by_insight = _group_by(metric_rows, "insight_id")
    news_by_insight = _group_by(news_rows, "insight_id")
    feedback_by_insight = _group_by(feedback_rows, "insight_id")

    cards = []
    for row in insight_rows:
        insight_id = int(row["id"])
        metrics = metrics_by_insight.get(insight_id, [])
        news = news_by_insight.get(insight_id, [])
        feedback = feedback_by_insight.get(insight_id, [])
        confidence = float(row.get("confidence") or 0)
        evidence_grade = "A" if confidence >= 0.85 and metrics and len(news) >= 2 else "B" if confidence >= 0.8 and news else "C"
        cards.append({
            "id": insight_id,
            "gosb_id": row["gosb_id"],
            "gosb_name": row["gosb_name"],
            "title": row["title"],
            "type": row["insight_type"],
            "priority": row["priority"],
            "confidence": confidence,
            "evidence_grade": evidence_grade,
            "why_it_matters": row["why_it_matters"],
            "suggested_action": row["suggested_action"],
            "owner_hint": row["owner_hint"],
            "evidence": row["evidence"],
            "status": row["status"],
            "created_at": row["created_at"],
            "metric_links": metrics,
            "source_news": news,
            "feedback": {
                "counts": _count_actions(feedback),
                "comments": [item for item in feedback if item.get("comment")],
            },
        })
    return cards


def _build_data_gaps(scope: dict, insights: list[dict], news_feedback: list[dict], weak_signals: list[dict]) -> list[str]:
    gaps: list[str] = []
    if not scope.get("sent_news_total"):
        gaps.append("В run нет отправленных новостей; рефлексия не может проверить качество отбора.")
    if not insights:
        gaps.append("Не сформировано ни одного инсайта; нужно проверить пороги качества или входной контекст.")
    no_metric_count = sum(1 for item in insights if not item.get("metric_links"))
    if no_metric_count:
        gaps.append(f"{no_metric_count} инсайт(ов) без привязки к метрике; нужна доразметка методологии или более явное обоснование.")
    if not news_feedback and not any(item.get("feedback", {}).get("counts") for item in insights):
        gaps.append("Нет экспертных реакций по новостям/инсайтам для этого run; калибровка качества ограничена.")
    if len(weak_signals) >= 10:
        gaps.append("Много отправленных новостей не стали инсайтами; стоит проверить шум в отборе или повысить требования к отправке.")
    return gaps


def build_reflection_report(run_id: str) -> dict:
    init_db()
    scope = _collect_run_scope(run_id)
    insights = _collect_insight_rows(run_id)
    news_feedback = _collect_news_feedback(run_id)
    weak_signals = _collect_weak_signal_rows(run_id)
    data_gaps = _build_data_gaps(scope, insights, news_feedback, weak_signals)
    return {
        "run_id": run_id,
        "generated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "scope": scope,
        "insights": insights,
        "feedback": {
            "news_counts": _count_actions(news_feedback),
            "news_comments": [item for item in news_feedback if item.get("comment")],
            "insight_counts": _count_actions([
                {"action": action}
                for insight in insights
                for action, count in insight.get("feedback", {}).get("counts", {}).items()
                for _ in range(count)
            ]),
        },
        "data_gaps": data_gaps,
        "not_promoted_to_insight": weak_signals,
    }


def _action_counts_text(counts: dict[str, int]) -> str:
    if not counts:
        return "нет реакций"
    return ", ".join(f"{key}: {value}" for key, value in sorted(counts.items()))


def _reflection_summary_markdown(report: dict) -> str:
    scope = report["scope"]
    insights = report["insights"]
    lines = [
        f"# Reflection Report: {report['run_id']}",
        "",
        f"- Generated at: {report['generated_at']}",
        f"- Sent news: {scope.get('sent_news_total', 0)}",
        f"- Insight cards: {len(insights)}",
        f"- News feedback: {_action_counts_text(report['feedback']['news_counts'])}",
        f"- Insight feedback: {_action_counts_text(report['feedback']['insight_counts'])}",
        "",
        "## Executive Summary",
    ]
    if insights:
        top = insights[:3]
        for item in top:
            lines.append(
                f"- [{item['priority']}/{item['evidence_grade']}] {item['gosb_name']}: {item['title']} "
                f"(confidence {item['confidence']:.2f})"
            )
    else:
        lines.append("- No insight cards passed the quality gate.")

    lines.extend(["", "## Run Scope"])
    if scope.get("gosbs"):
        lines.extend([
            "| GOSB | Sent news |",
            "| --- | ---: |",
        ])
        for row in scope["gosbs"]:
            lines.append(f"| {row['gosb_name']} | {row['sent_news']} |")
    else:
        lines.append("No sent news found for this run.")

    lines.extend(["", "## Insight Cards"])
    if insights:
        lines.extend([
            "| ID | GOSB | Priority | Type | Confidence | Insight |",
            "| ---: | --- | --- | --- | ---: | --- |",
        ])
        for item in insights:
            title = str(item["title"]).replace("|", "\\|")
            lines.append(
                f"| {item['id']} | {item['gosb_name']} | {item['priority']} | {item['type']} | "
                f"{item['confidence']:.2f} | {title} |"
            )
    else:
        lines.append("No insight cards.")

    lines.extend(["", "## Metric Hypotheses"])
    if insights:
        for item in insights:
            if item["metric_links"]:
                for metric in item["metric_links"]:
                    metric_name = metric.get("metric_name") or metric.get("metric_key")
                    lines.append(
                        f"- Insight {item['id']}: {metric_name} "
                        f"({metric.get('impact') or 'context'}, confidence {float(metric.get('confidence') or 0):.2f})"
                    )
            else:
                lines.append(f"- Insight {item['id']}: no defensible metric link found.")
    else:
        lines.append("- No metric hypotheses.")

    lines.extend(["", "## Feedback Themes"])
    lines.append(f"- News reactions: {_action_counts_text(report['feedback']['news_counts'])}")
    lines.append(f"- Insight reactions: {_action_counts_text(report['feedback']['insight_counts'])}")
    comments = report["feedback"].get("news_comments", [])[:5]
    for comment in comments:
        lines.append(f"- News comment from {comment.get('username') or 'unknown'}: {comment.get('comment')}")

    lines.extend(["", "## Data Gaps"])
    if report["data_gaps"]:
        lines.extend(f"- {gap}" for gap in report["data_gaps"])
    else:
        lines.append("- No critical data gaps detected.")

    lines.extend(["", "## Not Promoted To Insight"])
    weak_signals = report.get("not_promoted_to_insight", [])[:10]
    if weak_signals:
        for item in weak_signals:
            lines.append(
                f"- {item['gosb_name']}: {item['title']} "
                f"({item.get('category') or 'unknown'}, {float(item.get('confidence') or 0):.2f})"
            )
    else:
        lines.append("- Every sent news item was attached to at least one insight or there were no sent items.")

    lines.extend(["", "## Next Actions"])
    if insights:
        for item in insights[:5]:
            lines.append(f"- Insight {item['id']}: {item['suggested_action']}")
    else:
        lines.append("- Re-run reflection after enough sent news and feedback accumulate.")

    lines.append("")
    return "\n".join(lines)


def _reflection_journal_markdown(report: dict) -> str:
    lines = [
        f"# Reflection Journal: {report['run_id']}",
        "",
        "## Hypothesis Plan",
        "- Проверить, какие отправленные новости могут повлиять на клиентов, риски, LPR/GR, конкурентов или управленческие метрики ГОСБа.",
        "- Для каждого сильного сигнала связать рекомендацию с новостным доказательством и доступной метрикой, если связь объяснима.",
        "- Отдельно зафиксировать слабые сигналы, фидбек и пробелы данных.",
        "",
        "## Evidence Entries",
    ]
    if report["insights"]:
        for item in report["insights"]:
            titles = "; ".join(news["title"] for news in item.get("source_news", [])[:3]) or "source news missing"
            metrics = "; ".join(
                (metric.get("metric_name") or metric.get("metric_key") or "metric")
                for metric in item.get("metric_links", [])
            ) or "metric link not established"
            lines.extend([
                f"### Insight {item['id']}: {item['title']}",
                f"- Hypothesis: {item['why_it_matters']}",
                f"- Method: compared sent news, classification context, metric links and expert feedback for {item['gosb_name']}.",
                f"- Evidence: {titles}",
                f"- Metric check: {metrics}",
                f"- Interpretation: confidence {item['confidence']:.2f}, evidence grade {item['evidence_grade']}.",
                f"- Decision: {item['suggested_action']}",
                "",
            ])
    else:
        lines.extend(["- No insight passed the quality gate.", ""])

    lines.extend(["## Rejected Or Weak Signals"])
    weak_signals = report.get("not_promoted_to_insight", [])
    if weak_signals:
        for item in weak_signals[:15]:
            lines.append(
                f"- {item['gosb_name']}: {item['title']} was not promoted; "
                f"category={item.get('category') or 'unknown'}, confidence={float(item.get('confidence') or 0):.2f}."
            )
    else:
        lines.append("- No separate weak signals recorded.")

    lines.extend(["", "## Data Gaps"])
    if report["data_gaps"]:
        lines.extend(f"- {gap}" for gap in report["data_gaps"])
    else:
        lines.append("- No critical data gaps detected.")

    lines.append("")
    return "\n".join(lines)


def write_reflection_report(run_id: str) -> dict:
    report = build_reflection_report(run_id)
    report_dir = _run_report_dir(run_id)
    report_dir.mkdir(parents=True, exist_ok=True)

    summary_path = report_dir / "summary.md"
    json_path = report_dir / "insights.json"
    journal_path = report_dir / "journal.md"

    summary_path.write_text(_reflection_summary_markdown(report), encoding="utf-8")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    journal_path.write_text(_reflection_journal_markdown(report), encoding="utf-8")

    return {
        "report_dir": str(report_dir),
        "summary_path": str(summary_path),
        "json_path": str(json_path),
        "journal_path": str(journal_path),
        "insights_count": len(report["insights"]),
    }


def _recent_context_for_gosb(gosb_id: int, run_id: str, days: int = DAILY_CONTEXT_DAYS) -> str:
    modifier = f"-{max(1, int(days or 1))} days"
    with get_conn() as conn:
        prior_insights = [
            dict(row)
            for row in conn.execute(
                """
                SELECT title, insight_type, priority, confidence, created_at
                FROM insights
                WHERE gosb_id = ?
                  AND COALESCE(run_id, '') != COALESCE(?, '')
                  AND created_at >= datetime('now', ?)
                ORDER BY created_at DESC
                LIMIT 12
                """,
                (gosb_id, run_id, modifier),
            ).fetchall()
        ]
        category_rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT COALESCE(nc.category, 'unknown') AS category, COUNT(*) AS c
                FROM sent_news s
                LEFT JOIN news_classification nc
                    ON nc.gosb_id = s.gosb_id
                   AND nc.news_id = s.news_id
                   AND nc.mode = 'live'
                WHERE s.gosb_id = ?
                  AND COALESCE(s.run_id, '') != COALESCE(?, '')
                  AND s.sent_at >= datetime('now', ?)
                GROUP BY COALESCE(nc.category, 'unknown')
                ORDER BY c DESC
                LIMIT 8
                """,
                (gosb_id, run_id, modifier),
            ).fetchall()
        ]
        feedback_rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT f.action, COUNT(*) AS c
                FROM sent_news s
                JOIN feedback f
                    ON f.news_id = s.news_id
                   AND (f.gosb_id IS NULL OR f.gosb_id = s.gosb_id)
                WHERE s.gosb_id = ?
                  AND COALESCE(s.run_id, '') != COALESCE(?, '')
                  AND f.created_at >= datetime('now', ?)
                GROUP BY f.action
                ORDER BY c DESC
                """,
                (gosb_id, run_id, modifier),
            ).fetchall()
        ]

    parts: list[str] = []
    if category_rows:
        parts.append("Категории прошлых дней: " + "; ".join(f"{row['category']}={row['c']}" for row in category_rows))
    if feedback_rows:
        parts.append("Фидбек прошлых дней: " + "; ".join(f"{row['action']}={row['c']}" for row in feedback_rows))
    if prior_insights:
        lines = [
            f"- {row['priority']}/{row['insight_type']}: {row['title']} (confidence {float(row['confidence'] or 0):.2f})"
            for row in prior_insights
        ]
        parts.append("Недавние инсайты:\n" + "\n".join(lines))
    return "\n".join(parts)

def get_sent_news_for_run(gosb_id: int, run_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                r.id,
                r.title,
                r.body,
                r.source,
                r.url,
                s.summary,
                nc.category,
                nc.impact,
                nc.confidence,
                nc.rule_hits
            FROM sent_news s
            JOIN raw_news r ON r.id = s.news_id
            LEFT JOIN news_classification nc
                ON nc.gosb_id = s.gosb_id
               AND nc.news_id = s.news_id
               AND nc.mode = 'live'
            WHERE s.gosb_id = ?
              AND s.run_id = ?
            ORDER BY s.sent_at, r.id
        """, (gosb_id, run_id)).fetchall()
    return [dict(row) for row in rows]


def _metric_links_for_news(gosb_id: int, news_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT metric_key, metric_name, impact, confidence, reason
            FROM news_metric_links
            WHERE gosb_id = ? AND news_id = ? AND mode = 'live'
            ORDER BY confidence DESC
            LIMIT 5
        """, (gosb_id, news_id)).fetchall()
    return [dict(row) for row in rows]


def _build_prompt(gosb: dict, batch: list[dict], recent_context: str = "") -> str:
    news_list = "\n\n".join(
        (
            f"[{idx}] id={news['id']}\n"
            f"Заголовок: {news.get('title') or '-'}\n"
            f"Источник: {news.get('source') or '-'}\n"
            f"Категория V2: {news.get('category') or '-'}; impact={news.get('impact') or '-'}; confidence={news.get('confidence') or '-'}\n"
            f"Сводка V2: {news.get('summary') or '-'}\n"
            f"Связанные метрики V2: {json.dumps(news.get('_metric_links') or [], ensure_ascii=False)}\n"
            f"Текст: {(news.get('body') or '')[:900]}"
        )
        for idx, news in enumerate(batch)
    )

    return f"""Ты — интеллектуальный помощник для управляющего ГОСБ банка.
ГОСБ — это головное отделение банка, которое отвечает за определенный регион страны.
Кластер — это совокупность нескольких ГОСБ, расположенных в определенной части страны.

В этой задаче ты — агент управленческой рефлексии для {gosb['name']}.

Твоя задача: из уже отобранных новостей выделить качественные рекомендации к действию для руководителя ГОСБа.
Новости уже прошли фильтр релевантности. Не пересказывай каждую новость. Не придумывай действия, если пользы нет.

Регион ГОСБа: {gosb.get('region') or '-'}.
Закрепленные клиентские холдинги: {holdings_display_for_gosb(gosb['name'])}.

Контекст прошлых дней для поиска повторов и трендов, не для механического копирования:
{recent_context or '-'}

Метрики из темы метрик:
{get_knowledge_context("metrics", limit=10, max_chars=3200)}

Документы из Базы знаний: методология, бизнес-процессы, правила реагирования:
{get_knowledge_context("methodology", limit=8, max_chars=3200)}

Правила качества:
- Верни инсайт только если есть проверяемое действие: проверить клиента/холдинг, передать сигнал РМ/КМ, посмотреть метрику, оценить риск, подготовить контакт с ЛПР.
- Формулируй как: "На основе такой-то новости считаю, что такая-то метрика может измениться таким-то образом; рекомендую следующие шаги...".
- Для каждого управленческого инсайта сначала постарайся подобрать бизнес-метрику из справочника или из "Связанные метрики V2" у новостей. Заполняй metric_links при любой объяснимой связи: прямое влияние, риск изменения, контекст для мониторинга или метрика, которую стоит проверить.
- Если точной метрики нет, используй ближайшую релевантную бизнес-метрику из доступного контекста только когда можешь явно объяснить связь в reason. Оставляй metric_links пустым только после такой проверки.
- Если в Базе знаний есть документы с бизнес-процессами или методологией, опирайся на них при выборе рекомендуемых действий.
- Можно объединять несколько новостей в один инсайт, если они про один сигнал.
- Если новость просто фон, используй no_action или не включай ее в insights.
- Не формулируй приказ. Пиши как рекомендацию: "проверить", "передать сигнал", "оценить", "сопоставить".
- Не придумывай метрики и факты, которых нет в новости/контексте. Если после проверки подходящей метрики нет, оставь metric_links пустым.
- Возвращай все качественные инсайты, а не фиксированное число.
- Учитывай, что эксперты будут размечать эти рекомендации; делай evidence и suggested_action достаточно конкретными для оценки.

Типы:
client_signal — клиент/холдинг/крупный бизнес/стройка/производство;
risk_signal — суды, банкротства, долги, проверки, мошенничество, операционные риски;
metric_signal — связь с конкретной метрикой из справочника;
lpr_signal — губернатор, органы власти, региональные программы, GR;
competitor_signal — активность конкурентов/банковского рынка;
no_action — действие не нужно.

Новости:
{news_list}

Верни только валидный JSON без markdown:
{{
  "insights": [
    {{
      "news_indexes": [0, 2],
      "title": "короткий заголовок инсайта",
      "type": "client_signal|risk_signal|metric_signal|lpr_signal|competitor_signal|no_action",
      "priority": "high|medium|low",
      "confidence": 0.0,
      "why_it_matters": "почему это важно для ГОСБа",
      "suggested_action": "рекомендуемые шаги: анализ, встреча, контакт с клиентом/РМ/КМ/GR, проверка риска и т.д.",
      "owner_hint": "руководитель ГОСБа|РМ|КМ|GR|риски|аналитик",
      "evidence": "на основе какой новости или группы новостей сделан вывод",
      "metric_links": [
        {{"metric_key": "номер/название из справочника", "metric_name": "название", "impact": "positive|negative|risk|context|none", "confidence": 0.0, "reason": "как и почему метрика может измениться"}}
      ]
    }}
  ]
}}"""


def _fallback_insights(gosb: dict, batch: list[dict], reason: str) -> list[dict]:
    insights = []
    for idx, news in enumerate(batch):
        category = str(news.get("category") or "")
        impact = str(news.get("impact") or "")
        if category not in {"client_holding", "business", "fraud", "regulation"} and impact != "high":
            continue
        insights.append({
            "news_indexes": [idx],
            "title": _clean_text(news.get("title"), 160),
            "type": "risk_signal" if category == "fraud" else "client_signal",
            "priority": "medium",
            "confidence": 0.76,
            "why_it_matters": "Новость прошла fallback-оценку как потенциально значимый управленческий сигнал.",
            "suggested_action": "Проверить связь новости с клиентами, холдингами или профильными метриками ГОСБа.",
            "owner_hint": "аналитик",
            "evidence": reason,
            "metric_links": [],
        })
    return insights


def classify_insight_batch(gosb: dict, batch: list[dict], disable_llm: bool = False, recent_context: str = "") -> tuple[list[dict], dict]:
    if disable_llm:
        return _fallback_insights(gosb, batch, "insight_llm_disabled"), {"source": "rules"}

    prompt = _build_prompt(gosb, batch, recent_context=recent_context)
    try:
        raw = _openclaw_json(prompt)
        raw_items = raw.get("insights", [])
        if not isinstance(raw_items, list):
            raise ValueError("LLM response has no insights list")
        return raw_items, raw
    except Exception as exc:
        reason = f"insight_llm_error: {str(exc)[:180]}"
        print(f"  ⚠️  Insight batch fallback: {reason}")
        return _fallback_insights(gosb, batch, reason), {"source": "fallback", "error": reason}


def normalize_insight(raw: dict, batch: list[dict]) -> dict | None:
    if not isinstance(raw, dict):
        return None
    indexes = _normalize_indexes(raw.get("news_indexes"), len(batch))
    news_ids = [int(batch[idx]["id"]) for idx in indexes]
    item = {
        "news_indexes": indexes,
        "news_ids": news_ids,
        "title": _clean_text(raw.get("title"), 220),
        "insight_type": _normalize_type(raw.get("type")),
        "priority": _normalize_priority(raw.get("priority")),
        "confidence": _normalize_confidence(raw.get("confidence")),
        "why_it_matters": _clean_text(raw.get("why_it_matters"), 900),
        "suggested_action": _clean_text(raw.get("suggested_action"), 900),
        "owner_hint": _clean_text(raw.get("owner_hint"), 160),
        "evidence": _clean_text(raw.get("evidence"), 700),
        "metric_links": _normalize_metric_links(raw.get("metric_links")),
    }
    if not item["title"] and indexes:
        item["title"] = _clean_text(batch[indexes[0]].get("title"), 220)
    return item


def generate_insights(
    run_id: str,
    batch_size: int = BATCH_SIZE,
    max_items: int = MAX_ITEMS,
    disable_llm: bool = False,
    write_report: bool = True,
) -> int:
    init_db()
    gosbs = [dict(row) for row in get_active_gosbs()]
    total_saved = 0
    print(f"🧭 Генерируем инсайты для {len(gosbs)} ГОСБов...")

    for gosb in gosbs:
        news_items = get_sent_news_for_run(gosb["id"], run_id)
        if max_items and max_items > 0:
            news_items = news_items[:max_items]
        for news in news_items:
            news["_metric_links"] = _metric_links_for_news(gosb["id"], news["id"])

        recent_context = _recent_context_for_gosb(gosb["id"], run_id)
        print(f"📍 {gosb['name']}: новостей для рефлексии {len(news_items)}")
        seen: set[str] = set()
        saved_for_gosb = 0

        for batch in _chunked(news_items, batch_size):
            raw_items, raw_response = classify_insight_batch(gosb, batch, disable_llm=disable_llm, recent_context=recent_context)
            normalized = []
            for raw in raw_items:
                item = normalize_insight(raw, batch)
                if item is None or not _quality_gate(item):
                    continue
                key = _dedupe_key(item)
                if key in seen:
                    continue
                seen.add(key)
                normalized.append(item)

            normalized.sort(
                key=lambda item: (PRIORITY_RANK[item["priority"]], item["confidence"]),
                reverse=True,
            )
            for item in normalized:
                insight_id = save_insight(
                    gosb_id=gosb["id"],
                    run_id=run_id,
                    title=item["title"],
                    insight_type=item["insight_type"],
                    priority=item["priority"],
                    confidence=item["confidence"],
                    why_it_matters=item["why_it_matters"],
                    suggested_action=item["suggested_action"],
                    owner_hint=item["owner_hint"],
                    evidence=item["evidence"],
                    news_ids=item["news_ids"],
                    metric_links=item["metric_links"],
                    source={"news_indexes": item["news_indexes"]},
                    llm_raw_json=raw_response,
                )
                if insight_id:
                    saved_for_gosb += 1
                    total_saved += 1

        print(f"  ✅ Инсайтов сохранено: {saved_for_gosb}")

    print(f"✅ Инсайты готовы: {total_saved}")
    if write_report:
        report_info = write_reflection_report(run_id)
        print(f"📝 Отчёт рефлексии: {report_info['summary_path']}")
    return total_saved


def get_insights_for_run(run_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT i.*, g.name AS gosb_name, g.chat_id
            FROM insights i
            JOIN gosb_config g ON g.id = i.gosb_id
            WHERE i.run_id = ?
              AND i.status = 'proposed'
            ORDER BY
              CASE i.priority WHEN 'high' THEN 3 WHEN 'medium' THEN 2 ELSE 1 END DESC,
              i.confidence DESC,
              i.id
        """, (run_id,)).fetchall()
    return [dict(row) for row in rows]


def _insight_news_titles(insight_id: int) -> list[str]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT r.title, r.source
            FROM insight_news_links l
            JOIN raw_news r ON r.id = l.news_id
            WHERE l.insight_id = ?
            ORDER BY r.id
            LIMIT 4
        """, (insight_id,)).fetchall()
    return [f"{row['title']} ({row['source'] or '-'})" for row in rows]


def _insight_metric_lines(insight_id: int) -> list[str]:
    impact_labels = {
        "positive": "может улучшиться",
        "negative": "может ухудшиться",
        "risk": "риск ухудшения",
        "context": "контекст",
        "none": "связь не определена",
    }
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT metric_key, metric_name, impact, confidence, reason
            FROM insight_metric_links
            WHERE insight_id = ?
            ORDER BY confidence DESC, id
            LIMIT 5
        """, (insight_id,)).fetchall()
    lines = []
    for row in rows:
        name = row["metric_name"] or row["metric_key"]
        impact = impact_labels.get(str(row["impact"] or "context"), str(row["impact"] or "context"))
        reason = _truncate_text(row["reason"] or "", 180)
        suffix = f": {reason}" if reason else ""
        lines.append(f"- {name} — {impact}{suffix}")
    return lines


def build_insight_keyboard(insight_id: int, useful: int = 0, boring: int = 0, comments: int = 0) -> dict:
    return {
        "inline_keyboard": [[
            {"text": f"✅ {useful}", "callback_data": f"iuseful:{insight_id}"},
            {"text": f"👎 {boring}", "callback_data": f"iboring:{insight_id}"},
            {"text": f"💬 {comments}", "callback_data": f"icomment:{insight_id}"},
        ]]
    }


def format_insight_message(insight: dict) -> str:
    priority_label = "высокий" if insight["priority"] == "high" else "средний"
    news_titles = _insight_news_titles(insight["id"])
    metric_lines = _insight_metric_lines(insight["id"])
    evidence = insight.get("evidence") or "; ".join(news_titles)
    metrics_block = ""
    if metric_lines:
        metrics_block = "\n\n<b>Связанные метрики:</b>\n" + escape("\n".join(metric_lines))
    return (
        f"🧭 <b>Инсайт · {escape(insight['gosb_name'])}</b>\n"
        f"<b>{escape(insight['title'])}</b>\n"
        f"<i>Приоритет: {priority_label} | тип: {escape(insight['insight_type'])} | уверенность: {float(insight['confidence']):.2f}</i>\n\n"
        f"<b>Почему важно:</b> {escape(_truncate_text(insight.get('why_it_matters') or '', 700))}"
        f"{metrics_block}\n\n"
        f"<b>Что проверить:</b> {escape(_truncate_text(insight.get('suggested_action') or '', 800))}\n"
        f"<b>Кому:</b> {escape(insight.get('owner_hint') or 'аналитик')}\n\n"
        f"<b>Основание:</b> {escape(_truncate_text(evidence, 650))}"
    )


def _send_message(chat_id, text, thread_id=None, reply_markup=None):
    from agent_news.sender import send_message

    return send_message(chat_id, text, thread_id, reply_markup=reply_markup)


def send_insights(run_id: str) -> int:
    insights = get_insights_for_run(run_id)
    if not insights:
        print("🧭 Нет инсайтов для отправки")
        return 0

    buckets: dict[tuple[str, str], list[dict]] = {}
    skipped = 0
    for insight in insights:
        thread_id = _thread_id_for_insight(insight)
        if not thread_id:
            skipped += 1
            continue
        chat_id = INSIGHTS_CHAT_ID or insight["chat_id"]
        buckets.setdefault((chat_id, thread_id), []).append(insight)

    if not buckets:
        print("🧭 INSIGHTS_THREAD_ID/INSIGHTS_THREAD_IDS не заданы — отправка инсайтов пропущена")
        return 0

    sent = 0
    for (chat_id, thread_id), bucket in buckets.items():
        gosb_names = sorted({str(item.get("gosb_name") or "") for item in bucket})
        title = ", ".join(name for name in gosb_names if name) or "ГОСБ"
        _send_message(
            chat_id,
            f"🧭 <b>Инсайты к действиям · {escape(title)}</b>\\n<i>{len(bucket)} рекомендаций</i>",
            thread_id,
        )
        for insight in bucket:
            if _send_message(chat_id, format_insight_message(insight), thread_id, reply_markup=build_insight_keyboard(insight["id"])):
                sent += 1

    if skipped:
        print(f"🧭 Инсайтов без настроенного топика: {skipped}")
    print(f"🧭 Инсайты отправлены: {sent}/{len(insights)}")
    return sent


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and optionally send management insights")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--report-only", action="store_true", help="write reflection report without generating new insights")
    parser.add_argument("--no-report", action="store_true", help="skip reflection report generation")
    args = parser.parse_args()

    if args.report_only:
        report_info = write_reflection_report(args.run_id)
        print(f"📝 Отчёт рефлексии: {report_info['summary_path']}")
        return

    generate_insights(args.run_id, disable_llm=args.no_llm, write_report=not args.no_report)
    if args.send:
        send_insights(args.run_id)


if __name__ == "__main__":
    main()
