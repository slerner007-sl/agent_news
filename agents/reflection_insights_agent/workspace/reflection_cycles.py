"""
reflection_cycles.py — periodic research cycles for the reflection agent.

Daily insight generation still lives in insights.py. This module adds higher-level
research cycles: weekly meta-insights and strategic/monthly memory updates.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from html import escape
from pathlib import Path
from typing import Iterable
import argparse
import json
import os
import re
import sys

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_PATH = _REPO_ROOT / "src"
if str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))

from agent_news.db import get_conn, init_db


CYCLE_DAYS = {
    "daily": 1,
    "weekly": 7,
    "strategic": 30,
}
REPORTS_DIR = Path(os.getenv(
    "REFLECTION_CYCLE_REPORTS_DIR",
    _REPO_ROOT / "agents/reflection_insights_agent/workspace/reports/cycles",
))
RUNTIME_MEMORY_PATH = Path(os.getenv(
    "REFLECTION_MEMORY_PATH",
    _REPO_ROOT / "agents/reflection_insights_agent/workspace/memory/runtime_memory.md",
))

STOPWORDS = {
    "это", "как", "что", "для", "или", "при", "над", "под", "без", "уже", "еще",
    "после", "будет", "будут", "самаре", "самара", "области", "область", "россии",
    "россия", "году", "лет", "млн", "млрд", "рублей", "руб", "новый", "новая",
    "новые", "свои", "свой", "из-за", "the", "and", "with", "from",
}


def _now() -> datetime:
    return datetime.utcnow().replace(microsecond=0)


def _db_time(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _period(cycle: str, days: int | None = None) -> dict:
    if cycle not in CYCLE_DAYS:
        raise ValueError(f"Unknown reflection cycle: {cycle}")
    end = _now()
    span_days = int(days or CYCLE_DAYS[cycle])
    start = end - timedelta(days=span_days)
    return {
        "cycle": cycle,
        "days": span_days,
        "start": _db_time(start),
        "end": _db_time(end),
    }


def _rows(sql: str, params: tuple = ()) -> list[dict]:
    with get_conn() as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _safe_slug(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "").strip()).strip(".-")
    return safe[:120] or "cycle"


def _count_by(rows: Iterable[dict], key: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        value = str(row.get(key) or "unknown")
        counts[value] += 1
    return dict(counts.most_common())


def _top_titles(rows: list[dict], limit: int = 3) -> list[str]:
    titles = []
    for row in rows:
        title = str(row.get("title") or "").strip()
        if title and title not in titles:
            titles.append(title)
        if len(titles) >= limit:
            break
    return titles


def _tokenize_titles(rows: Iterable[dict]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        text = str(row.get("title") or "").lower()
        for token in re.findall(r"[а-яёa-z0-9]{4,}", text):
            if token in STOPWORDS:
                continue
            counts[token] += 1
    return counts


def _feedback_counts(rows: Iterable[dict]) -> dict[str, int]:
    return _count_by(rows, "action")


def _ratio(part: int, total: int) -> float:
    return float(part) / float(total) if total else 0.0


def _collect_cycle_data(period: dict) -> dict:
    start = period["start"]
    end = period["end"]
    init_db()
    sent_news = _rows(
        """
        SELECT
            s.gosb_id,
            g.name AS gosb_name,
            s.news_id,
            s.run_id,
            s.sent_at,
            r.title,
            r.source,
            r.url,
            COALESCE(s.summary, '') AS sent_summary,
            COALESCE(nc.category, 'unknown') AS category,
            COALESCE(nc.impact, 'unknown') AS impact,
            COALESCE(nc.confidence, 0) AS confidence,
            COALESCE(nc.summary, '') AS classifier_summary
        FROM sent_news s
        JOIN raw_news r ON r.id = s.news_id
        JOIN gosb_config g ON g.id = s.gosb_id
        LEFT JOIN news_classification nc
            ON nc.gosb_id = s.gosb_id
           AND nc.news_id = s.news_id
           AND nc.mode = 'live'
        WHERE s.sent_at >= ?
          AND s.sent_at <= ?
        ORDER BY s.sent_at DESC, s.id DESC
        """,
        (start, end),
    )
    insights = _rows(
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
            i.created_at
        FROM insights i
        JOIN gosb_config g ON g.id = i.gosb_id
        WHERE i.created_at >= ?
          AND i.created_at <= ?
        ORDER BY i.created_at DESC, i.id DESC
        """,
        (start, end),
    )
    news_feedback = _rows(
        """
        SELECT
            f.action,
            COALESCE(f.comment, '') AS comment,
            f.created_at,
            f.gosb_id,
            g.name AS gosb_name,
            f.news_id,
            r.title,
            COALESCE(nc.category, 'unknown') AS category,
            COALESCE(nc.impact, 'unknown') AS impact
        FROM feedback f
        JOIN raw_news r ON r.id = f.news_id
        LEFT JOIN gosb_config g ON g.id = f.gosb_id
        LEFT JOIN news_classification nc
            ON nc.gosb_id = f.gosb_id
           AND nc.news_id = f.news_id
           AND nc.mode = 'live'
        WHERE f.created_at >= ?
          AND f.created_at <= ?
        ORDER BY f.created_at DESC, f.id DESC
        """,
        (start, end),
    )
    insight_feedback = _rows(
        """
        SELECT
            f.action,
            COALESCE(f.comment, '') AS comment,
            f.created_at,
            f.gosb_id,
            g.name AS gosb_name,
            f.insight_id,
            i.title,
            i.insight_type,
            i.priority
        FROM insight_feedback f
        JOIN insights i ON i.id = f.insight_id
        LEFT JOIN gosb_config g ON g.id = f.gosb_id
        WHERE f.created_at >= ?
          AND f.created_at <= ?
        ORDER BY f.created_at DESC, f.id DESC
        """,
        (start, end),
    )
    metric_links = _rows(
        """
        SELECT
            l.metric_key,
            COALESCE(l.metric_name, '') AS metric_name,
            COALESCE(l.impact, '') AS impact,
            COALESCE(l.confidence, 0) AS confidence,
            i.id AS insight_id,
            i.insight_type,
            g.name AS gosb_name
        FROM insight_metric_links l
        JOIN insights i ON i.id = l.insight_id
        JOIN gosb_config g ON g.id = i.gosb_id
        WHERE i.created_at >= ?
          AND i.created_at <= ?
        ORDER BY l.metric_key, i.id
        """,
        (start, end),
    )
    return {
        "sent_news": sent_news,
        "insights": insights,
        "news_feedback": news_feedback,
        "insight_feedback": insight_feedback,
        "metric_links": metric_links,
    }


def _trend_threshold(cycle: str) -> int:
    if cycle == "daily":
        return 2
    if cycle == "weekly":
        return 3
    return 5


def _build_meta_insights(cycle: str, data: dict) -> list[dict]:
    threshold = _trend_threshold(cycle)
    meta: list[dict] = []
    by_gosb_category: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in data["sent_news"]:
        by_gosb_category[(row["gosb_name"], row["category"])].append(row)

    for (gosb_name, category), rows in sorted(by_gosb_category.items(), key=lambda item: len(item[1]), reverse=True):
        if category == "unknown" or len(rows) < threshold:
            continue
        meta.append({
            "kind": "news_trend",
            "title": f"{gosb_name}: за период {len(rows)} новостей категории {category}",
            "evidence": _top_titles(rows),
            "interpretation": "Повторяемость сигнала важнее одиночной новости: это кандидат на недельный тренд.",
            "recommendation": "Проверить, есть ли закрепленные клиенты/метрики, которые регулярно попадают в этот контур.",
            "confidence": min(0.95, 0.55 + len(rows) * 0.06),
        })

    by_gosb_insight_type: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in data["insights"]:
        by_gosb_insight_type[(row["gosb_name"], row["insight_type"])].append(row)

    for (gosb_name, insight_type), rows in sorted(by_gosb_insight_type.items(), key=lambda item: len(item[1]), reverse=True):
        if len(rows) < max(2, threshold - 1):
            continue
        meta.append({
            "kind": "insight_trend",
            "title": f"{gosb_name}: {len(rows)} инсайт(ов) типа {insight_type}",
            "evidence": _top_titles(rows),
            "interpretation": "Несколько рекомендаций одного типа за период могут означать устойчивую тему, а не разовый повод.",
            "recommendation": "Собрать эти инсайты в один управленческий follow-up и проверить динамику в следующем цикле.",
            "confidence": min(0.93, 0.6 + len(rows) * 0.05),
        })

    title_terms = _tokenize_titles(data["sent_news"])
    for term, count in title_terms.most_common(8):
        if count < threshold:
            continue
        examples = [row for row in data["sent_news"] if term in str(row.get("title") or "").lower()]
        meta.append({
            "kind": "term_trend",
            "title": f"Повторяющаяся тема: {term} ({count} упоминаний)",
            "evidence": _top_titles(examples),
            "interpretation": "Тема повторяется в заголовках отправленных новостей и может быть кластером для анализа.",
            "recommendation": "Проверить, является ли тема клиентским, рисковым или GR-сигналом, а не информационным шумом.",
            "confidence": min(0.9, 0.5 + count * 0.05),
        })

    return meta[:15]


def _build_feedback_adjustments(data: dict) -> list[dict]:
    adjustments: list[dict] = []

    by_category: dict[str, list[dict]] = defaultdict(list)
    for row in data["news_feedback"]:
        by_category[row.get("category") or "unknown"].append(row)

    for category, rows in sorted(by_category.items(), key=lambda item: len(item[1]), reverse=True):
        counts = _feedback_counts(rows)
        total = sum(counts.values())
        if total < 3 or category == "unknown":
            continue
        boring_ratio = _ratio(counts.get("boring", 0), total)
        useful_ratio = _ratio(counts.get("useful", 0), total)
        if boring_ratio >= 0.6:
            adjustments.append({
                "target": f"news_category:{category}",
                "observation": f"Фидбек по категории {category}: {counts}",
                "recommendation": "Снизить приоритет похожих новостей или требовать более конкретную привязку к клиенту/метрике.",
                "confidence": round(boring_ratio, 2),
            })
        elif useful_ratio >= 0.5:
            adjustments.append({
                "target": f"news_category:{category}",
                "observation": f"Фидбек по категории {category}: {counts}",
                "recommendation": "Сохранить или усилить этот тип сигнала в фильтре.",
                "confidence": round(useful_ratio, 2),
            })

    by_insight_type: dict[str, list[dict]] = defaultdict(list)
    for row in data["insight_feedback"]:
        by_insight_type[row.get("insight_type") or "unknown"].append(row)

    for insight_type, rows in sorted(by_insight_type.items(), key=lambda item: len(item[1]), reverse=True):
        counts = _feedback_counts(rows)
        total = sum(counts.values())
        if total < 2 or insight_type == "unknown":
            continue
        boring_ratio = _ratio(counts.get("boring", 0), total)
        useful_ratio = _ratio(counts.get("useful", 0), total)
        if boring_ratio >= 0.5:
            adjustments.append({
                "target": f"insight_type:{insight_type}",
                "observation": f"Менеджеры чаще игнорируют/отклоняют {insight_type}: {counts}",
                "recommendation": "Понизить приоритет или усилить evidence для этого типа инсайтов.",
                "confidence": round(boring_ratio, 2),
            })
        elif useful_ratio >= 0.5:
            adjustments.append({
                "target": f"insight_type:{insight_type}",
                "observation": f"Менеджеры положительно оценивают {insight_type}: {counts}",
                "recommendation": "Оставить приоритет и использовать эти примеры как positive pattern.",
                "confidence": round(useful_ratio, 2),
            })

    return adjustments[:12]


def _build_strategic_patterns(data: dict) -> list[dict]:
    patterns: list[dict] = []

    metric_counts: Counter[str] = Counter()
    metric_names: dict[str, str] = {}
    for row in data["metric_links"]:
        key = str(row.get("metric_key") or "").strip()
        if not key:
            continue
        metric_counts[key] += 1
        metric_names[key] = row.get("metric_name") or key

    for key, count in metric_counts.most_common(10):
        if count < 2:
            continue
        patterns.append({
            "kind": "metric_dependency",
            "title": f"Метрика повторяется в инсайтах: {metric_names[key]} ({count} связей)",
            "interpretation": "Повторная привязка одной метрики может означать устойчивую зависимость в региональном контуре.",
            "recommendation": "Проверить фактическую динамику метрики и добавить явное правило/пример в память агента.",
            "confidence": min(0.92, 0.55 + count * 0.07),
        })

    title_terms = _tokenize_titles(data["sent_news"])
    for term, count in title_terms.most_common(12):
        if count < 4:
            continue
        patterns.append({
            "kind": "recurring_entity_or_theme",
            "title": f"Скрытый повторяющийся паттерн: {term} ({count} упоминаний)",
            "interpretation": "Повторение темы за месяц может быть устойчивым клиентским, регуляторным или отраслевым сигналом.",
            "recommendation": "Сопоставить тему с клиентскими холдингами, рисками и обратной связью менеджеров.",
            "confidence": min(0.9, 0.5 + count * 0.05),
        })

    return patterns[:12]


def _build_data_gaps(cycle: str, data: dict) -> list[str]:
    gaps: list[str] = []
    if not data["sent_news"]:
        gaps.append("За период нет отправленных новостей; цикл не может сформировать тренды.")
    if not data["insights"]:
        gaps.append("За период нет сохраненных инсайтов; weekly/strategic слой видит только новости.")
    if not data["news_feedback"] and not data["insight_feedback"]:
        gaps.append("Нет фидбека за период; корректировка приоритетов ограничена.")
    if cycle in {"weekly", "strategic"} and len(data["sent_news"]) < 5:
        gaps.append("Мало отправленных новостей для надежных трендов.")
    if cycle == "strategic" and not data["metric_links"]:
        gaps.append("Нет связей инсайтов с метриками; стратегические зависимости пока слабо наблюдаемы.")
    return gaps


def build_cycle_report(cycle: str, days: int | None = None) -> dict:
    period = _period(cycle, days)
    data = _collect_cycle_data(period)
    meta_insights = _build_meta_insights(cycle, data)
    feedback_adjustments = _build_feedback_adjustments(data)
    strategic_patterns = _build_strategic_patterns(data) if cycle == "strategic" else []
    return {
        "cycle": cycle,
        "generated_at": _now().isoformat() + "Z",
        "period": period,
        "scope": {
            "sent_news": len(data["sent_news"]),
            "insights": len(data["insights"]),
            "news_feedback": len(data["news_feedback"]),
            "insight_feedback": len(data["insight_feedback"]),
            "metric_links": len(data["metric_links"]),
            "gosbs": _count_by(data["sent_news"], "gosb_name"),
            "categories": _count_by(data["sent_news"], "category"),
            "insight_types": _count_by(data["insights"], "insight_type"),
        },
        "meta_insights": meta_insights,
        "feedback_adjustments": feedback_adjustments,
        "strategic_patterns": strategic_patterns,
        "data_gaps": _build_data_gaps(cycle, data),
    }


def _summary_markdown(report: dict) -> str:
    scope = report["scope"]
    lines = [
        f"# Reflection Cycle Report: {report['cycle']}",
        "",
        f"- Generated at: {report['generated_at']}",
        f"- Period: {report['period']['start']} → {report['period']['end']} UTC",
        f"- Sent news: {scope['sent_news']}",
        f"- Insights: {scope['insights']}",
        f"- News feedback: {scope['news_feedback']}",
        f"- Insight feedback: {scope['insight_feedback']}",
        "",
        "## Executive Summary",
    ]
    if report["meta_insights"]:
        for item in report["meta_insights"][:5]:
            lines.append(f"- {item['title']} (confidence {item['confidence']:.2f})")
    else:
        lines.append("- No strong meta-insights for this period.")

    lines.extend(["", "## Meta-Insights"])
    if report["meta_insights"]:
        for item in report["meta_insights"]:
            evidence = "; ".join(item.get("evidence") or [])
            lines.extend([
                f"### {item['title']}",
                f"- Interpretation: {item['interpretation']}",
                f"- Recommendation: {item['recommendation']}",
                f"- Evidence: {evidence or 'not enough explicit examples'}",
                "",
            ])
    else:
        lines.append("No meta-insights.")

    lines.extend(["", "## Feedback Adjustments"])
    if report["feedback_adjustments"]:
        for item in report["feedback_adjustments"]:
            lines.append(f"- {item['target']}: {item['observation']} → {item['recommendation']}")
    else:
        lines.append("- No feedback-based priority changes.")

    lines.extend(["", "## Strategic Patterns"])
    if report["strategic_patterns"]:
        for item in report["strategic_patterns"]:
            lines.append(f"- {item['title']}: {item['recommendation']}")
    else:
        lines.append("- Strategic patterns are only generated for the strategic cycle or when enough data exists.")

    lines.extend(["", "## Data Gaps"])
    if report["data_gaps"]:
        lines.extend(f"- {gap}" for gap in report["data_gaps"])
    else:
        lines.append("- No critical data gaps detected.")

    lines.extend(["", "## Next Actions"])
    if report["feedback_adjustments"]:
        lines.append("- Review feedback adjustments before changing production filter weights.")
    if report["meta_insights"]:
        lines.append("- Use top meta-insights as hypotheses for the next digest cycle.")
    if report["cycle"] == "strategic":
        lines.append("- Review runtime memory updates and promote stable rules manually when they prove useful.")
    lines.append("")
    return "\n".join(lines)


def _journal_markdown(report: dict) -> str:
    lines = [
        f"# Reflection Cycle Journal: {report['cycle']}",
        "",
        "## Method",
        "- Compare sent news, saved insights, feedback and metric links inside the period.",
        "- Promote repeated signals to meta-insights only when count and evidence justify it.",
        "- Treat feedback adjustments as hypotheses, not automatic production changes.",
        "",
        "## Observations",
    ]
    for item in report["meta_insights"]:
        lines.append(f"- {item['kind']}: {item['title']} -> {item['interpretation']}")
    if not report["meta_insights"]:
        lines.append("- No repeated signal crossed the threshold.")

    lines.extend(["", "## Decisions"])
    for item in report["feedback_adjustments"]:
        lines.append(f"- {item['target']}: {item['recommendation']}")
    if report["cycle"] == "strategic":
        for item in report["strategic_patterns"]:
            lines.append(f"- {item['kind']}: {item['recommendation']}")
    if not report["feedback_adjustments"] and not report["strategic_patterns"]:
        lines.append("- No automatic strategy update proposed.")

    lines.extend(["", "## Data Gaps"])
    if report["data_gaps"]:
        lines.extend(f"- {gap}" for gap in report["data_gaps"])
    else:
        lines.append("- No critical data gaps detected.")
    lines.append("")
    return "\n".join(lines)


def _append_runtime_memory(report: dict) -> None:
    RUNTIME_MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "",
        f"## Strategic cycle {report['generated_at']}",
        f"- Period: {report['period']['start']} -> {report['period']['end']} UTC",
    ]
    for item in report["strategic_patterns"][:8]:
        lines.append(f"- Pattern: {item['title']} | {item['recommendation']}")
    for item in report["feedback_adjustments"][:8]:
        lines.append(f"- Feedback adjustment: {item['target']} | {item['recommendation']}")
    if report["data_gaps"]:
        lines.append(f"- Data gaps: {'; '.join(report['data_gaps'])}")
    with RUNTIME_MEMORY_PATH.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def write_cycle_report(cycle: str, days: int | None = None, update_memory: bool | None = None) -> dict:
    report = build_cycle_report(cycle, days)
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    report_dir = Path(REPORTS_DIR) / f"{_safe_slug(cycle)}-{stamp}"
    report_dir.mkdir(parents=True, exist_ok=True)
    summary_path = report_dir / "summary.md"
    json_path = report_dir / "report.json"
    journal_path = report_dir / "journal.md"

    summary_path.write_text(_summary_markdown(report), encoding="utf-8")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    journal_path.write_text(_journal_markdown(report), encoding="utf-8")

    should_update_memory = (cycle == "strategic") if update_memory is None else update_memory
    if should_update_memory:
        _append_runtime_memory(report)

    return {
        "cycle": cycle,
        "report_dir": str(report_dir),
        "summary_path": str(summary_path),
        "json_path": str(json_path),
        "journal_path": str(journal_path),
        "memory_path": str(RUNTIME_MEMORY_PATH) if should_update_memory else "",
        "report": report,
    }


def _telegram_message(report: dict, summary_path: str) -> str:
    scope = report["scope"]
    title = {
        "daily": "Ежедневная рефлексия",
        "weekly": "Еженедельная рефлексия",
        "strategic": "Стратегическая рефлексия",
    }.get(report["cycle"], "Рефлексия")
    lines = [
        f"🧭 <b>{escape(title)}</b>",
        f"<i>{escape(report['period']['start'])} → {escape(report['period']['end'])} UTC</i>",
        "",
        f"Новости: <b>{scope['sent_news']}</b>; инсайты: <b>{scope['insights']}</b>; фидбек: <b>{scope['news_feedback'] + scope['insight_feedback']}</b>",
    ]
    if report["meta_insights"]:
        lines.extend(["", "<b>Главные наблюдения</b>"])
        for item in report["meta_insights"][:5]:
            lines.append(f"• {escape(item['title'])}")
    if report["feedback_adjustments"]:
        lines.extend(["", "<b>Корректировки по фидбеку</b>"])
        for item in report["feedback_adjustments"][:3]:
            lines.append(f"• {escape(item['target'])}: {escape(item['recommendation'])}")
    if report["data_gaps"]:
        lines.extend(["", "<b>Пробелы данных</b>"])
        for gap in report["data_gaps"][:3]:
            lines.append(f"• {escape(gap)}")
    lines.extend(["", f"Файл отчёта на VPS: <code>{escape(summary_path)}</code>"])
    return "\n".join(lines)[:3900]


def send_cycle_report(report_info: dict) -> bool:
    chat_id = os.getenv("REFLECTION_REPORT_CHAT_ID", "").strip() or os.getenv("INSIGHTS_CHAT_ID", "").strip()
    thread_id = os.getenv("REFLECTION_REPORT_THREAD_ID", "").strip() or os.getenv("INSIGHTS_THREAD_ID", "").strip()
    if not chat_id:
        print("🧭 REFLECTION_REPORT_CHAT_ID/INSIGHTS_CHAT_ID не задан — отчёт записан, отправка пропущена")
        return False

    from agent_news.insights import _send_message

    sent = _send_message(
        chat_id,
        _telegram_message(report_info["report"], report_info["summary_path"]),
        thread_id or None,
    )
    print(f"🧭 Отчёт рефлексии отправлен: {sent}")
    return sent


def run_cycle(cycle: str, days: int | None = None, send: bool = False, update_memory: bool | None = None) -> dict:
    report_info = write_cycle_report(cycle, days=days, update_memory=update_memory)
    print(f"🧭 Цикл {cycle}: {report_info['summary_path']}")
    if report_info.get("memory_path"):
        print(f"🧠 Memory updated: {report_info['memory_path']}")
    if send:
        send_cycle_report(report_info)
    return report_info


def main() -> None:
    parser = argparse.ArgumentParser(description="Run periodic reflection research cycles")
    parser.add_argument("--cycle", choices=sorted(CYCLE_DAYS), required=True)
    parser.add_argument("--days", type=int, default=None)
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--update-memory", action="store_true")
    parser.add_argument("--no-memory-update", action="store_true")
    args = parser.parse_args()

    update_memory = None
    if args.update_memory:
        update_memory = True
    if args.no_memory_update:
        update_memory = False
    run_cycle(args.cycle, days=args.days, send=args.send, update_memory=update_memory)


if __name__ == "__main__":
    main()
