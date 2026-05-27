"""
insights.py — управленческие инсайты поверх уже отобранных новостей.

Новости отвечают на вопрос "что произошло"; инсайты отвечают на вопрос
"что руководителю ГОСБа стоит проверить или передать в работу".
"""

from __future__ import annotations

import argparse
import json
import os
import re
from html import escape
from typing import Iterable

from db import (
    get_active_gosbs,
    get_conn,
    get_knowledge_context,
    init_db,
    save_insight,
)
from holdings_loader import holdings_display_for_gosb
from llm_filter import _openclaw_json


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


def _build_prompt(gosb: dict, batch: list[dict]) -> str:
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

    return f"""Ты — агент управленческой рефлексии для {gosb['name']}.

Твоя задача: из уже отобранных новостей выделить качественные рекомендации к действию для руководителя ГОСБа.
Новости уже прошли фильтр релевантности. Не пересказывай каждую новость. Не придумывай действия, если пользы нет.

Регион ГОСБа: {gosb.get('region') or '-'}.
Закрепленные клиентские холдинги: {holdings_display_for_gosb(gosb['name'])}.

Метрики из темы метрик:
{get_knowledge_context("metrics", limit=10, max_chars=3200)}

Документы из Базы знаний: методология, бизнес-процессы, правила реагирования:
{get_knowledge_context("methodology", limit=8, max_chars=3200)}

Правила качества:
- Верни инсайт только если есть проверяемое действие: проверить клиента/холдинг, передать сигнал РМ/КМ, посмотреть метрику, оценить риск, подготовить контакт с ЛПР.
- Формулируй как: "На основе такой-то новости считаю, что такая-то метрика может измениться таким-то образом; рекомендую следующие шаги...".
- Если в Базе знаний есть документы с бизнес-процессами или методологией, опирайся на них при выборе рекомендуемых действий.
- Можно объединять несколько новостей в один инсайт, если они про один сигнал.
- Если новость просто фон, используй no_action или не включай ее в insights.
- Не формулируй приказ. Пиши как рекомендацию: "проверить", "передать сигнал", "оценить", "сопоставить".
- Не придумывай метрики и факты, которых нет в новости/контексте. Если подходящей метрики нет, оставь metric_links пустым.
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


def classify_insight_batch(gosb: dict, batch: list[dict], disable_llm: bool = False) -> tuple[list[dict], dict]:
    if disable_llm:
        return _fallback_insights(gosb, batch, "insight_llm_disabled"), {"source": "rules"}

    prompt = _build_prompt(gosb, batch)
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

        print(f"📍 {gosb['name']}: новостей для рефлексии {len(news_items)}")
        seen: set[str] = set()
        saved_for_gosb = 0

        for batch in _chunked(news_items, batch_size):
            raw_items, raw_response = classify_insight_batch(gosb, batch, disable_llm=disable_llm)
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
    from sender import send_message

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
    args = parser.parse_args()

    generate_insights(args.run_id, disable_llm=args.no_llm)
    if args.send:
        send_insights(args.run_id)


if __name__ == "__main__":
    main()
