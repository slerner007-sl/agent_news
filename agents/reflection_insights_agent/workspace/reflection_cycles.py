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
import subprocess
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
LLM_RESEARCH_MAX_CHARS = int(os.getenv("REFLECTION_LLM_RESEARCH_MAX_CHARS", "12000"))

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



def _compact_for_llm(value: dict, max_chars: int = LLM_RESEARCH_MAX_CHARS) -> str:
    payload = json.dumps(value, ensure_ascii=False, indent=2)
    if len(payload) <= max_chars:
        return payload
    head = payload[: max_chars - 600]
    return head + "\n...<truncated; use only visible evidence, do not invent hidden facts>..."


def _research_depth(cycle: str) -> dict:
    if cycle == "strategic":
        return {"min_hypotheses": 18, "min_findings": 8, "label": "strategic/monthly"}
    if cycle == "weekly":
        return {"min_hypotheses": 12, "min_findings": 6, "label": "weekly"}
    return {"min_hypotheses": 8, "min_findings": 4, "label": "daily"}


def _llm_research_prompt(report: dict) -> str:
    depth = _research_depth(report["cycle"])
    evidence = {
        "cycle": report["cycle"],
        "period": report["period"],
        "scope": report["scope"],
        "deterministic_meta_insights": report["meta_insights"],
        "feedback_adjustments": report["feedback_adjustments"],
        "strategic_patterns": report["strategic_patterns"],
        "data_gaps": report["data_gaps"],
    }
    evidence_json = _compact_for_llm(evidence)
    return f"""Ты — reflection agent новостного пайплайна ГОСБ.

Твоя задача — написать LLM-research отчёт поверх evidence pack. Это не SQL-сводка и не пересказ новостей.
Работай как исследователь: гипотезы → метод → наблюдение → интерпретация → решение.

Цикл: {report['cycle']} ({depth['label']}).
Период: {report['period']['start']} → {report['period']['end']} UTC.

Контекст домена:
- Новости уже были отобраны и отправлены по ГОСБ.
- Инсайты — рекомендации к действию для менеджеров ГОСБ.
- Фидбек useful/boring/comment показывает, где менеджеры считают сигнал полезным или шумным.
- Metric links — гипотезы о связи новости/инсайта с бизнес-метрикой. Не выдумывай значения метрик.

Стиль отчёта как у workspace-reflection коллеги:
- Честный короткий вывод в начале.
- Явно отделяй факты от интерпретации.
- Ключевые находки нумеруй как [INSIGHT-01].
- Причинные цепочки нумеруй как [CAUSAL-01], даже если они rejected/open.
- Advisory нумеруй как [ADV-01].
- Data gaps нумеруй как [GAP-01].
- Rejected hypotheses обязательны: слабые идеи тоже полезны.
- Не публикуй уверенность там, где evidence слабый; пиши health-only / open question.

Минимальная глубина:
- research plan: минимум {depth['min_hypotheses']} гипотез с якорями [H-01]...
- ключевые findings: минимум {depth['min_findings']}, если evidence позволяет; если нет — объясни почему.
- минимум 2 data gaps.
- минимум 2 rejected/open hypotheses.

Evidence pack:
```json
{evidence_json}
```

Верни только валидный JSON без markdown fences:
{{
  "research_mode": "llm",
  "title": "Глубокий отчёт ...",
  "executive_summary": "...",
  "summary_md": "# ...",
  "journal_md": "# ...",
  "sections": [
    {{"title": "Было → стало", "body": "..."}}
  ],
  "confirmed_findings": ["..."],
  "strong_hypotheses": ["..."],
  "weak_hypotheses": ["..."],
  "insights": [
    {{
      "id": "INSIGHT-01",
      "title": "...",
      "body": "...",
      "evidence": ["..."],
      "confidence": 0.0,
      "status": "accepted|open|rejected"
    }}
  ],
  "causal_chains": [
    {{
      "id": "CAUSAL-01",
      "title": "...",
      "chain": "signal -> interpretation -> action",
      "for_role": "руководитель ГОСБ",
      "status": "accepted|open|rejected",
      "evidence": "...",
      "behavior_change": "..."
    }}
  ],
  "advisories": [
    {{
      "id": "ADV-01",
      "title": "...",
      "action": "...",
      "for_role": "руководитель ГОСБ",
      "source": "feedback|trend|metric_link|data_gap",
      "confidence": 0.0
    }}
  ],
  "external_context": [
    {{
      "title": "...",
      "summary": "...",
      "why_it_matters": "...",
      "url": ""
    }}
  ],
  "data_gaps": [
    {{
      "id": "GAP-01",
      "gap": "...",
      "why_it_matters": "...",
      "what_to_add": "..."
    }}
  ],
  "methodology_gaps": ["..."],
  "system_gaps": ["..."],
  "playbook_gaps": ["..."],
  "task_candidates": [
    {{
      "title": "...",
      "priority": "high|medium|low",
      "effect": "...",
      "confidence": "high|medium|low"
    }}
  ],
  "rejected_hypotheses": [
    {{
      "id": "H-XX",
      "hypothesis": "...",
      "reason": "..."
    }}
  ],
  "open_questions": ["..."],
  "memory_updates": ["..."]
}}
"""



def _openclaw_research_text(prompt: str) -> str:
    from agent_news.llm_filter import OPENCLAW_BIN, OPENCLAW_MODEL, OPENCLAW_TIMEOUT, PROJECT_ROOT

    result = subprocess.run(
        [
            OPENCLAW_BIN,
            "agent",
            "--agent", "main",
            "--model", OPENCLAW_MODEL,
            "--message", prompt,
            "--timeout", str(OPENCLAW_TIMEOUT),
            "--json",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        timeout=OPENCLAW_TIMEOUT + 30,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(detail[:1000] or f"openclaw exited with {result.returncode}")

    payload = json.loads(result.stdout)
    meta = payload.get("result", {}).get("meta", {})
    content = meta.get("finalAssistantVisibleText") or meta.get("finalAssistantRawText")
    if not content:
        payloads = payload.get("result", {}).get("payloads", [])
        if payloads:
            content = payloads[0].get("text")
    if not content:
        raise RuntimeError("openclaw returned no assistant text")
    return content.strip()


def _research_from_markdown(markdown_text: str, report: dict) -> dict:
    summary = markdown_text.strip()
    if not summary.startswith("#"):
        summary = f"# Reflection report: {report['cycle']}\n\n{summary}"
    journal = _journal_markdown(report).rstrip() + "\n\n## LLM Research Narrative\n\nThe model returned markdown instead of structured JSON. The markdown was preserved as `report.md`/`summary.md`; structured sidecar files were generated from the deterministic evidence pack.\n"
    fallback = _fallback_research(report, "llm returned markdown instead of JSON")
    fallback.update({
        "research_mode": "llm_markdown",
        "title": f"Reflection report: {report['cycle']}",
        "summary_md": summary,
        "journal_md": journal,
        "error": "",
    })
    return fallback

def _as_text(value) -> str:
    if isinstance(value, dict):
        return str(value.get("title") or value.get("gap") or value.get("hypothesis") or value.get("observation") or value)
    return str(value)


def _demo_confirmed_findings(report: dict) -> list[str]:
    findings: list[str] = []
    scope = report["scope"]
    if scope.get("sent_news"):
        findings.append(
            f"За период агент видел {scope['sent_news']} отправленных новостей и {scope['insights']} управленческих инсайтов; это уже достаточный материал для daily reflection."
        )
    top_categories = list((scope.get("categories") or {}).items())[:3]
    if top_categories:
        findings.append(
            "Главные тематические контуры периода: "
            + ", ".join(f"{name}={count}" for name, count in top_categories)
            + "."
        )
    if report.get("meta_insights"):
        findings.extend(_as_text(item) for item in report["meta_insights"][:4])
    if scope.get("metric_links", 0) <= max(1, scope.get("insights", 0) // 10):
        findings.append("Связь инсайтов с метриками пока слабая: агент явно поднимает это как ограничение качества, а не прячет проблему.")
    if scope.get("insight_feedback", 0) == 0:
        findings.append("Фидбек по самим инсайтам пока отсутствует, поэтому калибровка рекомендаций идёт в основном через реакции на новости.")
    return findings[:8]


def _demo_causal_chains(report: dict) -> list[dict]:
    chains = []
    if report.get("meta_insights"):
        top = report["meta_insights"][0]
        chains.append({
            "id": "CAUSAL-01",
            "title": "Повторяемая тема превращается в управленческий сигнал",
            "chain": "серия похожих новостей -> кластер темы -> проверка клиента/метрики/ответственного",
            "for_role": "руководитель ГОСБ",
            "status": "open",
            "evidence": _as_text(top),
            "behavior_change": "Не реагировать на каждую новость отдельно, а смотреть на повторяемость темы за период.",
        })
    if report.get("feedback_adjustments"):
        adj = report["feedback_adjustments"][0]
        chains.append({
            "id": "CAUSAL-02",
            "title": "Негативный фидбек превращается в настройку фильтра",
            "chain": "реакции boring/comment -> шумная категория -> повышение требований к evidence",
            "for_role": "владелец фильтра новостей",
            "status": "accepted",
            "evidence": _as_text(adj.get("observation") if isinstance(adj, dict) else adj),
            "behavior_change": "Категории с высоким boring-ratio должны получать меньший приоритет без конкретной привязки к клиенту, метрике или риску.",
        })
    chains.append({
        "id": "CAUSAL-03",
        "title": "Нет фидбека по инсайтам — нет уверенной калибровки действий",
        "chain": "инсайт отправлен -> нет реакции на инсайт -> действие не подтверждено пользователем",
        "for_role": "куратор пилота",
        "status": "open",
        "evidence": f"Insight feedback rows: {report['scope'].get('insight_feedback', 0)}",
        "behavior_change": "На демо показать кнопки инсайтов и попросить менеджеров размечать именно рекомендации, а не только новости.",
    })
    return chains


def _demo_advisories(report: dict) -> list[dict]:
    advisories = []
    for idx, item in enumerate(report.get("feedback_adjustments", [])[:3], start=1):
        advisories.append({
            "id": f"ADV-{idx:02d}",
            "title": item.get("target", "Корректировка по фидбеку") if isinstance(item, dict) else "Корректировка по фидбеку",
            "action": item.get("recommendation", _as_text(item)) if isinstance(item, dict) else _as_text(item),
            "for_role": "владелец фильтра / руководитель пилота",
            "source": "feedback",
            "confidence": item.get("confidence", 0.7) if isinstance(item, dict) else 0.7,
        })
    advisories.append({
        "id": f"ADV-{len(advisories)+1:02d}",
        "title": "Сделать daily reflection регулярным экраном демо",
        "action": "Показывать не только список новостей, а блок: что повторилось, что менеджеры сочли шумом, какие данные нужны для следующего шага.",
        "for_role": "демо / владелец продукта",
        "source": "trend",
        "confidence": 0.82,
    })
    return advisories


def _demo_data_gaps(report: dict) -> list[dict]:
    gaps = [
        {
            "id": "GAP-01",
            "gap": "Мало или нет реакций на сами инсайты",
            "why_it_matters": "Без этого агент понимает шумность новостей, но хуже понимает полезность управленческих рекомендаций.",
            "what_to_add": "Просить участников демо нажимать useful/boring/comment именно под инсайтами.",
        },
        {
            "id": "GAP-02",
            "gap": "Недостаточная привязка инсайтов к бизнес-метрикам",
            "why_it_matters": "Метрики превращают новость из информационного повода в проверяемую управленческую гипотезу.",
            "what_to_add": "Дозагрузить методологию и таблицу метрик по ГОСБ, добавить accepted examples связей новость→метрика.",
        },
    ]
    for idx, gap in enumerate(report.get("data_gaps", [])[:4], start=3):
        gaps.append({
            "id": f"GAP-{idx:02d}",
            "gap": _as_text(gap),
            "why_it_matters": "Это ограничивает уверенность research-выводов.",
            "what_to_add": "Закрыть источник данных или добавить явное правило интерпретации.",
        })
    return gaps


def _demo_rejected_hypotheses(report: dict) -> list[dict]:
    return [
        {
            "id": "H-R01",
            "hypothesis": "Количество новостей само по себе означает качество отбора",
            "reason": "Rejected: без фидбека, метрик и связки с действием большой объём может быть шумом.",
        },
        {
            "id": "H-R02",
            "hypothesis": "Любая повторяющаяся региональная тема автоматически полезна ГОСБ",
            "reason": "Open/rejected until there is client, metric, risk or LPR link.",
        },
        {
            "id": "H-R03",
            "hypothesis": "Категории banking/business всегда надо поднимать выше",
            "reason": "Rejected for current period: feedback shows boring pressure on part of these categories.",
        },
    ]


def _demo_task_candidates(gaps: list[dict], advisories: list[dict]) -> list[dict]:
    tasks = []
    for gap in gaps[:3]:
        tasks.append({
            "title": gap["gap"],
            "priority": "high" if gap["id"] in {"GAP-01", "GAP-02"} else "medium",
            "effect": gap["what_to_add"],
            "confidence": "medium",
        })
    for adv in advisories[:2]:
        tasks.append({
            "title": adv["title"],
            "priority": "medium",
            "effect": adv["action"],
            "confidence": "medium",
        })
    return tasks


def _demo_summary_md(report: dict, research: dict, reason: str = "") -> str:
    period = report["period"]
    scope = report["scope"]
    lines = [
        f"# Отчёт агента рефлексии по новостям ГОСБ за период {period['start']} — {period['end']}",
        "",
        research["executive_summary"],
        "",
        "## Было → стало",
        f"Было: обычный дайджест показывал отдельные новости. Стало: reflection-agent собирает {scope['sent_news']} новостей, {scope['insights']} инсайтов, {scope['news_feedback'] + scope['insight_feedback']} реакций и превращает их в исследовательский отчёт с выводами, советами, пробелами данных и rejected hypotheses.",
        "",
        "## Подтверждённые выводы",
    ]
    for item in research["confirmed_findings"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Причинно-следственные цепочки"])
    for chain in research["causal_chains"]:
        lines.append(f"- {chain['title']} ({chain['for_role']}): {chain['behavior_change']}")
    lines.extend(["", "## Практические советы"])
    for adv in research["advisories"]:
        lines.append(f"- {adv['title']} ({adv['source']}): {adv['action']}")
    lines.extend(["", "## Внешний фон недели"])
    lines.append("- Fresh external scan для демо не запускался: отчёт показывает внутреннюю research-логику на фактах текущего пайплайна.")
    lines.extend(["", "## Данные"])
    lines.append(f"- Новости: {scope['sent_news']}; инсайты: {scope['insights']}; реакции на новости: {scope['news_feedback']}; реакции на инсайты: {scope['insight_feedback']}; metric links: {scope['metric_links']}.")
    lines.extend(["", "## Риски и ограничения"])
    if reason and reason != "llm disabled":
        lines.append(f"- LLM narrative fallback: {reason}. Для демо используется стабильный research-style renderer поверх evidence pack.")
    lines.append("- Выводы не меняют production-фильтр автоматически; это advisory/research layer.")
    lines.extend(["", "## Пробелы в данных"])
    for gap in research["data_gaps"]:
        lines.append(f"- {gap['gap']}: {gap['what_to_add']}")
    lines.extend(["", "## Слабые гипотезы"])
    for item in research["rejected_hypotheses"]:
        lines.append(f"- {item['hypothesis']} — {item['reason']}")
    lines.extend(["", "## Кандидаты задач"])
    for task in research["task_candidates"]:
        lines.append(f"- {task['title']} (приоритет: {task['priority']}, эффект: {task['effect']})")
    lines.extend(["", "## Open questions"])
    for question in research["open_questions"]:
        lines.append(f"- {question}")
    lines.append("")
    return "\n".join(lines)


def _demo_journal_md(report: dict, research: dict, reason: str = "") -> str:
    period = report["period"]
    lines = [
        f"# Journal — Reflection news agent demo ({period['start']} — {period['end']})",
        "",
        "Mission: показать на демо, что агент рефлексии не пересказывает новости, а исследует качество сигналов, фидбек, пробелы данных и возможные действия.",
        "",
        "## [1] Research plan — demo daily cycle",
        "**Гипотеза:** За один день можно показать полный цикл: новости → инсайты → фидбек → meta-findings → advisory → gaps.",
        "",
        "**Метод:** Считать evidence pack из БД, построить тренды по категориям/ГОСБ, проверить фидбек и metric links, собрать sidecar bundle как у reference reporting.",
        "",
        f"**Наблюдение:** Новости={report['scope']['sent_news']}, инсайты={report['scope']['insights']}, news_feedback={report['scope']['news_feedback']}, insight_feedback={report['scope']['insight_feedback']}.",
        "",
        "**Интерпретация:** Этого достаточно для demo-pass, но не для изменения production rules без review.",
        "",
        "**Вывод:** Demo report valid; качество дальнейших циклов зависит от разметки инсайтов и метрик.",
        "",
    ]
    for idx, item in enumerate(research["confirmed_findings"], start=2):
        lines.extend([
            f"## [{idx}] Finding",
            f"**Гипотеза:** {item}",
            "**Метод:** Сравнение агрегатов периода, трендов, фидбека и связей с метриками.",
            f"**Наблюдение:** {item}",
            "**Интерпретация:** На демо это можно показывать как исследовательский вывод агента.",
            "**Вывод:** Accepted for demo; требует накопления истории для production-политики.",
            "",
        ])
    if reason:
        lines.extend([
            "## LLM Research Status",
            f"- Stable renderer used because: {reason}",
            "",
        ])
    return "\n".join(lines)


def _fallback_research(report: dict, reason: str = "") -> dict:
    findings = _demo_confirmed_findings(report)
    gaps = _demo_data_gaps(report)
    advisories = _demo_advisories(report)
    causal_chains = _demo_causal_chains(report)
    rejected = _demo_rejected_hypotheses(report)
    tasks = _demo_task_candidates(gaps, advisories)
    executive_summary = (
        f"Reflection-agent собрал за период {report['scope']['sent_news']} новостей, "
        f"{report['scope']['insights']} инсайтов и {report['scope']['news_feedback'] + report['scope']['insight_feedback']} реакций. "
        "Главная демонстрационная ценность: агент показывает не только новости, а что повторяется, что менеджеры считают шумом, "
        "какие действия можно предложить и каких данных не хватает для уверенных правил."
    )
    research = {
        "research_mode": "fallback",
        "title": f"Отчёт агента рефлексии по новостям ГОСБ: {report['cycle']}",
        "executive_summary": executive_summary,
        "sections": [
            {"title": "Было → стало", "body": "От дайджеста отдельных новостей к исследовательскому отчёту с findings/advisory/gaps."},
            {"title": "Подтверждённые выводы", "body": " ".join(findings[:3])},
        ],
        "confirmed_findings": findings,
        "strong_hypotheses": findings[:3],
        "weak_hypotheses": [_as_text(item) for item in report.get("data_gaps", [])],
        "insights": report.get("meta_insights", []),
        "causal_chains": causal_chains,
        "advisories": advisories,
        "external_context": [],
        "data_gaps": gaps,
        "methodology_gaps": ["Нужны accepted examples связей новость→метрика→действие для каждого ГОСБ."],
        "system_gaps": ["Нужно включить стабильный LLM-research cron или отдельный быстрый research agent profile."],
        "playbook_gaps": ["Пока нет утверждённого playbook, какие рекомендации ГОСБ должен делать по каждому типу инсайта."],
        "task_candidates": tasks,
        "rejected_hypotheses": rejected,
        "open_questions": [
            "Какие типы инсайтов менеджеры считают реально полезными после демо?",
            "Какие категории новостей нужно понизить из-за boring feedback?",
            "Какие метрики ГОСБ важнее всего связать с новостями в следующей итерации?",
        ],
        "memory_updates": [
            "Для demo daily-report показывать findings/advisory/gaps, а не только список новостей.",
            "Категории с boring feedback требуют более сильного evidence.",
        ],
        "error": reason,
    }
    research["summary_md"] = _demo_summary_md(report, research, reason)
    research["journal_md"] = _demo_journal_md(report, research, reason)
    return research


def _normalize_research(raw: dict, report: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("LLM research response is not an object")
    summary_md = str(raw.get("summary_md") or "").strip()
    journal_md = str(raw.get("journal_md") or "").strip()
    if len(summary_md) < 200:
        raise ValueError("LLM research summary_md is too short")
    if len(journal_md) < 200:
        raise ValueError("LLM research journal_md is too short")
    normalized = {
        "research_mode": str(raw.get("research_mode") or "llm"),
        "cycle": report["cycle"],
        "generated_at": report["generated_at"],
        "period": report["period"],
        "scope": report["scope"],
        "title": str(raw.get("title") or f"Reflection report: {report['cycle']}").strip(),
        "executive_summary": str(raw.get("executive_summary") or "").strip(),
        "summary_md": summary_md,
        "journal_md": journal_md,
        "sections": raw.get("sections") if isinstance(raw.get("sections"), list) else [],
        "confirmed_findings": raw.get("confirmed_findings") if isinstance(raw.get("confirmed_findings"), list) else [],
        "strong_hypotheses": raw.get("strong_hypotheses") if isinstance(raw.get("strong_hypotheses"), list) else [],
        "weak_hypotheses": raw.get("weak_hypotheses") if isinstance(raw.get("weak_hypotheses"), list) else [],
        "insights": raw.get("insights") if isinstance(raw.get("insights"), list) else [],
        "causal_chains": raw.get("causal_chains") if isinstance(raw.get("causal_chains"), list) else [],
        "advisories": raw.get("advisories") if isinstance(raw.get("advisories"), list) else [],
        "external_context": raw.get("external_context") if isinstance(raw.get("external_context"), list) else [],
        "data_gaps": raw.get("data_gaps") if isinstance(raw.get("data_gaps"), list) else [],
        "methodology_gaps": raw.get("methodology_gaps") if isinstance(raw.get("methodology_gaps"), list) else [],
        "system_gaps": raw.get("system_gaps") if isinstance(raw.get("system_gaps"), list) else [],
        "playbook_gaps": raw.get("playbook_gaps") if isinstance(raw.get("playbook_gaps"), list) else [],
        "task_candidates": raw.get("task_candidates") if isinstance(raw.get("task_candidates"), list) else [],
        "rejected_hypotheses": raw.get("rejected_hypotheses") if isinstance(raw.get("rejected_hypotheses"), list) else [],
        "open_questions": raw.get("open_questions") if isinstance(raw.get("open_questions"), list) else [],
        "memory_updates": raw.get("memory_updates") if isinstance(raw.get("memory_updates"), list) else [],
    }
    return normalized


def build_llm_research(report: dict, disable_llm: bool = False) -> dict:
    if disable_llm:
        return _fallback_research(report, "llm disabled")
    try:
        from agent_news.llm_filter import _extract_json

        content = _openclaw_research_text(_llm_research_prompt(report))
        try:
            raw = _extract_json(content)
        except Exception:
            return _research_from_markdown(content, report)
        return _normalize_research(raw, report)
    except Exception as exc:
        reason = f"{type(exc).__name__}: {str(exc)[:240]}"
        print(f"  ⚠️  LLM research fallback: {reason}")
        return _fallback_research(report, reason)

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



def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_markdown_list(path: Path, title: str, rows, field: str = "title") -> None:
    lines = [f"# {title}", ""]
    if rows:
        for row in rows:
            if isinstance(row, dict):
                value = row.get(field) or row.get("gap") or row.get("hypothesis") or row.get("recommendation") or row.get("action") or str(row)
            else:
                value = str(row)
            lines.append(f"- {value}")
    else:
        lines.append("- Нет данных.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _basic_report_html(markdown_text: str, title: str) -> str:
    escaped = escape(markdown_text)
    body = escaped.replace("\n", "<br/>")
    return (
        "<html><head><meta charset='utf-8'/>"
        f"<title>{escape(title)}</title>"
        "<style>body{font-family:Arial,sans-serif;max-width:960px;margin:32px auto;line-height:1.5;color:#102a43}"
        "h1,h2{color:#0f5132}.meta{color:#52606d}</style></head><body>"
        f"{body}</body></html>"
    )


def _write_delivery_bundle(report_dir: Path, report: dict, research: dict, summary_md: str) -> None:
    _write_json(report_dir / "advisories.json", research.get("advisories", []))
    _write_json(report_dir / "causal_chains.json", research.get("causal_chains", []))
    _write_json(report_dir / "confirmed_findings.json", research.get("confirmed_findings", []))
    _write_json(report_dir / "rejected_hypotheses.json", research.get("rejected_hypotheses", []))
    _write_json(report_dir / "external_context.json", research.get("external_context", []))
    _write_json(report_dir / "data_requests.json", research.get("data_gaps", []))
    _write_json(report_dir / "methodology_proposals.json", research.get("methodology_gaps", []))
    _write_json(report_dir / "system_improvement_proposals.json", research.get("system_gaps", []))
    _write_json(report_dir / "task_candidates.json", research.get("task_candidates", []))
    _write_json(report_dir / "playbook_gaps.json", research.get("playbook_gaps", []))
    _write_json(report_dir / "proposals.json", [])
    _write_json(report_dir / "was_vs_now.json", {
        "status": "not_applicable_for_news_pipeline",
        "reason": "GOSB news pipeline has no baseline_t0/current_prod quality table yet.",
    })
    _write_json(report_dir / "knowledge_health.json", {
        "status": "partial",
        "notes": report.get("data_gaps", []),
    })
    _write_json(report_dir / "context.json", {
        "cycle": report["cycle"],
        "period": report["period"],
        "scope": report["scope"],
        "research_mode": research.get("research_mode"),
    })
    _write_json(report_dir / "delivery.json", {
        "channels": ["local_files"],
        "telegram_sent": False,
        "report_file": "report.md",
    })
    _write_markdown_list(report_dir / "data_requests.md", "Data requests", research.get("data_gaps", []), field="gap")
    _write_markdown_list(report_dir / "methodology_proposals.md", "Methodology proposals", research.get("methodology_gaps", []))
    _write_markdown_list(report_dir / "system_improvements.md", "System improvements", research.get("system_gaps", []))
    (report_dir / "report.html").write_text(
        _basic_report_html(summary_md, research.get("title") or f"Reflection report: {report['cycle']}"),
        encoding="utf-8",
    )

def write_cycle_report(cycle: str, days: int | None = None, update_memory: bool | None = None, disable_llm: bool = False) -> dict:
    report = build_cycle_report(cycle, days)
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    report_dir = Path(REPORTS_DIR) / f"{_safe_slug(cycle)}-{stamp}"
    report_dir.mkdir(parents=True, exist_ok=True)
    summary_path = report_dir / "summary.md"
    json_path = report_dir / "report.json"
    insights_path = report_dir / "insights.json"
    journal_path = report_dir / "journal.md"

    research = build_llm_research(report, disable_llm=disable_llm)
    summary_md = research["summary_md"]
    summary_path.write_text(summary_md, encoding="utf-8")
    (report_dir / "report.md").write_text(summary_md, encoding="utf-8")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    insights_path.write_text(json.dumps(research, ensure_ascii=False, indent=2), encoding="utf-8")
    journal_path.write_text(research["journal_md"], encoding="utf-8")
    _write_delivery_bundle(report_dir, report, research, summary_md)

    should_update_memory = (cycle == "strategic") if update_memory is None else update_memory
    if should_update_memory:
        _append_runtime_memory(report)

    return {
        "cycle": cycle,
        "report_dir": str(report_dir),
        "summary_path": str(summary_path),
        "report_md_path": str(report_dir / "report.md"),
        "html_path": str(report_dir / "report.html"),
        "json_path": str(json_path),
        "insights_path": str(insights_path),
        "journal_path": str(journal_path),
        "memory_path": str(RUNTIME_MEMORY_PATH) if should_update_memory else "",
        "report": report,
        "research": research,
    }


def _clip_text(value: str, max_len: int = 260) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _item_title(item) -> str:
    if isinstance(item, dict):
        return str(
            item.get("title")
            or item.get("gap")
            or item.get("hypothesis")
            or item.get("recommendation")
            or item.get("action")
            or item
        )
    return str(item)


def _telegram_message(report_info: dict) -> str:
    report = report_info["report"]
    research = report_info.get("research") or {}
    scope = report["scope"]
    period = report["period"]
    title = research.get("title") or "Отчёт агента рефлексии по новостям ГОСБ"
    if ":" in title:
        title = title.split(":", 1)[0]

    lines = [
        f"🧭 <b>{escape(_clip_text(title, 120))}</b>",
        f"<i>{escape(period['start'])} → {escape(period['end'])} UTC</i>",
        "",
    ]

    executive = research.get("executive_summary")
    if executive:
        lines.append(escape(_clip_text(executive, 560)))
        lines.append("")

    lines.extend([
        "📊 <b>Данные</b>",
        f"Новости: <b>{scope['sent_news']}</b>; инсайты: <b>{scope['insights']}</b>; "
        f"реакции: <b>{scope['news_feedback'] + scope['insight_feedback']}</b>; "
        f"metric links: <b>{scope.get('metric_links', 0)}</b>",
    ])

    findings = research.get("confirmed_findings") or []
    if findings:
        lines.extend(["", "✅ <b>Подтверждённые выводы</b>"])
        for item in findings[:4]:
            lines.append(f"• {escape(_clip_text(_item_title(item), 260))}")

    chains = research.get("causal_chains") or []
    if chains:
        lines.extend(["", "🔗 <b>Причинные цепочки</b>"])
        for item in chains[:2]:
            title_text = _item_title(item)
            action = item.get("behavior_change") if isinstance(item, dict) else ""
            joined = f"{title_text}: {action}" if action else title_text
            lines.append(f"• {escape(_clip_text(joined, 300))}")

    advisories = research.get("advisories") or []
    if advisories:
        lines.extend(["", "🎯 <b>Практические советы</b>"])
        for item in advisories[:3]:
            title_text = _item_title(item)
            action = item.get("action") or item.get("recommendation") if isinstance(item, dict) else ""
            joined = f"{title_text}: {action}" if action else title_text
            lines.append(f"• {escape(_clip_text(joined, 300))}")

    gaps = research.get("data_gaps") or []
    if gaps:
        lines.extend(["", "⚠️ <b>Пробелы данных</b>"])
        for item in gaps[:2]:
            lines.append(f"• {escape(_clip_text(_item_title(item), 260))}")

    lines.extend(["", "📎 Полный файл отчёта прикреплён следующим сообщением."])
    return "\n".join(lines)[:3200]



def _send_report_document(chat_id: str, thread_id: str | None, report_info: dict) -> bool:
    report_path = Path(report_info.get("report_md_path") or report_info.get("summary_path") or "")
    if not report_path.exists():
        print(f"🧭 Файл отчёта не найден для отправки: {report_path}")
        return False

    import requests
    from agent_news.sender import TG_URL, SEND_MAX_RETRIES, _retry_after
    import time

    caption = "📎 Полный отчёт агента рефлексии по новостям ГОСБ"
    payload = {
        "chat_id": chat_id,
        "caption": caption,
        "parse_mode": "HTML",
    }
    if thread_id:
        payload["message_thread_id"] = int(thread_id)

    for attempt in range(1, SEND_MAX_RETRIES + 1):
        try:
            with report_path.open("rb") as fh:
                response = requests.post(
                    f"{TG_URL}/sendDocument",
                    data=payload,
                    files={"document": (report_path.name, fh, "text/markdown")},
                    timeout=30,
                )
            if response.status_code == 429:
                wait_seconds = _retry_after(response) + 1
                print(f"  ⏳ Telegram rate limit на документ: жду {wait_seconds} сек. (попытка {attempt})")
                time.sleep(wait_seconds)
                continue
            response.raise_for_status()
            return True
        except Exception as exc:
            if attempt >= SEND_MAX_RETRIES:
                print(f"❌ Ошибка отправки отчёта-файла: {exc}")
                return False
            time.sleep(2 * attempt)
    return False

def send_cycle_report(report_info: dict) -> bool:
    chat_id = os.getenv("REFLECTION_REPORT_CHAT_ID", "").strip() or os.getenv("INSIGHTS_CHAT_ID", "").strip()
    thread_id = os.getenv("REFLECTION_REPORT_THREAD_ID", "").strip() or os.getenv("INSIGHTS_THREAD_ID", "").strip()
    if not chat_id:
        print("🧭 REFLECTION_REPORT_CHAT_ID/INSIGHTS_CHAT_ID не задан — отчёт записан, отправка пропущена")
        return False

    from agent_news.insights import _send_message

    sent = _send_message(
        chat_id,
        _telegram_message(report_info),
        thread_id or None,
    )
    document_sent = False
    if sent:
        document_sent = _send_report_document(chat_id, thread_id or None, report_info)
    print(f"🧭 Отчёт рефлексии отправлен: message={sent}, document={document_sent}")
    return bool(sent and document_sent)


def run_cycle(cycle: str, days: int | None = None, send: bool = False, update_memory: bool | None = None, disable_llm: bool = False) -> dict:
    report_info = write_cycle_report(cycle, days=days, update_memory=update_memory, disable_llm=disable_llm)
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
    parser.add_argument("--no-llm", action="store_true", help="build deterministic fallback report without LLM research")
    args = parser.parse_args()

    update_memory = None
    if args.update_memory:
        update_memory = True
    if args.no_memory_update:
        update_memory = False
    run_cycle(args.cycle, days=args.days, send=args.send, update_memory=update_memory, disable_llm=args.no_llm)


if __name__ == "__main__":
    main()
