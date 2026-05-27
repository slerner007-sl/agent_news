"""
LLM-first news filtering.

This module is intentionally separate from llm_filter.py so the live cron keeps
the old behavior until we explicitly switch it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from typing import Iterable

from .db import (
    get_active_gosbs,
    get_conn,
    get_unsent_news,
    init_db,
    mark_as_sent,
    save_news_classification,
    get_knowledge_context,
    save_news_metric_links,
)
from .llm_filter import OPENCLAW_MODEL, _openclaw_json
from .holdings_loader import holding_terms_for_gosb, holdings_display_for_gosb

BATCH_SIZE = int(os.getenv("NEWS_V2_BATCH_SIZE", "20"))
MAX_ITEMS = int(os.getenv("NEWS_V2_MAX_ITEMS", "0"))
MIN_CONFIDENCE = float(os.getenv("NEWS_V2_MIN_CONFIDENCE", "0.65"))
DIGEST_LIMIT = int(os.getenv("NEWS_V2_DIGEST_LIMIT", "0"))

DEFAULT_REGION_TERMS = (
    "самара",
    "самарск",
    "тольятти",
    "сызран",
    "жигулевск",
    "новокуйбышевск",
)
MIN_REGION_TERM_LENGTH = 4

STRONG_TERMS = (
    "сбер",
    "сбербанк",
    "банк",
    "банковск",
    "кредит",
    "ипотек",
    "вклад",
    "депозит",
    "карта",
    "платеж",
    "перевод",
    "цб",
    "ключев",
    "ставк",
    "мошеннич",
    "афер",
    "кибер",
    "фишинг",
    "хищен",
    "арбитраж",
    "банкрот",
    "налог",
    "инвест",
    "производств",
    "завод",
    "промышлен",
    "малый бизнес",
    "мсп",
    "застрой",
    "недвиж",
    "экспорт",
    "импортозамещ",
)


REGION_TERM_STOPLIST = (
    "сбербанк",
    "сбер",
    "банк",
    "банковск",
    "кредит",
    "ипотека",
    "вклад",
    "депозит",
    "цб рф",
    "ключевая ставка",
    "мошенник",
    "финанс",
    "застройщик",
    "ключевая",
    "ставка",
    "область",
    "регион",
    "город",
)

KNOWN_REGION_MARKERS = (
    "самара",
    "самарск",
    "тольятти",
    "63.ru",
    "news63ru",
    "samarap",
    "волга ньюс",
    "коммерсантъ самара",
    "ленинград",
    "ленобл",
    "47news",
    "online47",
    "lenobl",
    "lenobladminka",
    "drozdenko",
    "калининград",
    "rugrad",
    "клопс",
    "newkaliningrad",
    "gov39",
    "government_kgd",
    "kaliningradru",
    "besprozvannih",
    "ульяновск",
    "ульяновская",
    "ulpressa",
    "ulpravda",
    "ulgovru",
)


OWNED_SOURCE_MARKERS = {
    "Самарский ГОСБ": (
        "волга ньюс",
        "коммерсантъ самара",
        "федорищев",
        "самарская область",
        "63.ru",
        "63．ru",
        "news63ru",
        "самара новости",
        "samarap",
    ),
    "Ленинградский ГОСБ": (
        "ленинградская область",
        "47news",
        "online47",
        "дрозденко",
        "админка ленобласти",
        "ленобласть",
        "lenobl",
        "lenobladminka",
    ),
    "Калининградский ГОСБ": (
        "калининградская область",
        "новый калининград",
        "беспрозванных",
        "правительство калининградской области",
        "клопс",
        "rugrad",
        "калининград.ru",
        "newkaliningrad",
        "government_kgd",
        "kaliningradru",
    ),
    "Ульяновский ГОСБ": (
        "ульяновская область",
        "улпресса",
        "ulpressa",
        "ulpravda",
        "ulpravda.ru",
        "ulgovru",
    ),
}

NOISE_TERMS = (
    "спорт",
    "матч",
    "футбол",
    "хоккей",
    "чемпионат",
    "кубок",
    "бодибилдинг",
    "фитнес",
    "концерт",
    "афиша",
    "погода",
    "дожд",
    "жара",
    "похолод",
    "розыгрыш",
    "приз",
    "яхт",
    "алкогол",
    "последний звонок",
)

CATEGORIES = (
    "fraud",
    "banking",
    "regulation",
    "business",
    "client_holding",
    "regional_economy",
    "lpr",
    "noise",
    "other",
)

IMPACTS = ("high", "medium", "low", "none")
METRIC_IMPACTS = ("positive", "negative", "risk", "context", "none")


@dataclass
class RuleSignal:
    score: int
    hits: list[str]
    obvious_noise: bool


def _text(news: dict) -> str:
    return f"{news.get('title') or ''}\n{news.get('body') or ''}\n{news.get('source') or ''}".lower()


def _json_list(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return [str(value)]
    if isinstance(parsed, list):
        return [str(item) for item in parsed if str(item).strip()]
    return [str(parsed)]


def _normalized_terms(values: Iterable[str]) -> tuple[str, ...]:
    terms: set[str] = set()
    for value in values:
        value = str(value or "").lower().strip()
        if not value:
            continue
        for part in re.split(r"[,;/\n]+", value):
            part = " ".join(part.split())
            if len(part) >= MIN_REGION_TERM_LENGTH:
                terms.add(part)
            for word in re.findall(r"[а-яёa-z0-9-]+", part):
                if len(word) >= MIN_REGION_TERM_LENGTH:
                    terms.add(word)
    return tuple(sorted(
        term for term in terms
        if term not in REGION_TERM_STOPLIST
    ))


def _region_terms(gosb: dict | None) -> tuple[str, ...]:
    if not gosb:
        return DEFAULT_REGION_TERMS
    terms = _normalized_terms([gosb.get("region", ""), *_json_list(gosb.get("keywords"))])
    return terms or DEFAULT_REGION_TERMS


def _keywords_display(gosb: dict) -> str:
    keywords = _json_list(gosb.get("keywords"))
    return ", ".join(keywords[:40]) if keywords else "-"


def _hit_terms(text: str, terms: Iterable[str]) -> list[str]:
    return [term for term in terms if term in text]


def _source_owner_hits(source: str, gosb: dict | None) -> tuple[list[str], list[str]]:
    source = (source or "").lower()
    gosb_name = str((gosb or {}).get("name") or "")
    own_hits: list[str] = []
    foreign_hits: list[str] = []
    for owner, markers in OWNED_SOURCE_MARKERS.items():
        hits = [marker for marker in markers if marker in source]
        if not hits:
            continue
        if owner == gosb_name:
            own_hits.extend(hits)
        else:
            foreign_hits.extend(hits)
    return own_hits, foreign_hits


def score_news(news: dict, gosb: dict | None = None) -> RuleSignal:
    text = _text(news)
    own_source_hits, foreign_source_hits = _source_owner_hits(news.get("source") or "", gosb)
    region_hits = _hit_terms(text, _region_terms(gosb)) + own_source_hits
    strong_hits = _hit_terms(text, STRONG_TERMS)
    holding_hits = _hit_terms(text, holding_terms_for_gosb(str((gosb or {}).get("name") or "")))
    noise_hits = _hit_terms(text, NOISE_TERMS)
    region_terms = set(_region_terms(gosb))
    own_source_terms = set(own_source_hits)
    foreign_hits = [
        term for term in _hit_terms(text, KNOWN_REGION_MARKERS)
        if term not in region_terms and term not in own_source_terms
    ] + foreign_source_hits

    score = 0
    score += 3 * len(strong_hits)
    score += 6 * min(5, len(holding_hits))
    score += 5 * min(3, len(region_hits))
    score -= 3 * len(noise_hits)
    score -= 8 * min(3, len(foreign_hits))

    obvious_noise = bool((noise_hits and not strong_hits and not holding_hits) or foreign_source_hits or (foreign_hits and not region_hits))
    hits = []
    hits.extend(f"strong:{term}" for term in strong_hits)
    hits.extend(f"holding:{term}" for term in holding_hits)
    hits.extend(f"region:{term}" for term in region_hits)
    hits.extend(f"noise:{term}" for term in noise_hits)
    hits.extend(f"foreign:{term}" for term in foreign_hits)
    return RuleSignal(score=score, hits=hits, obvious_noise=obvious_noise)


def prepare_candidates(
    news_items: list[dict],
    gosb: dict | None = None,
    max_items: int = MAX_ITEMS,
) -> tuple[list[dict], list[dict]]:
    candidates = []
    skipped = []

    for news in news_items:
        signal = score_news(news, gosb)
        enriched = dict(news)
        enriched["_rule_score"] = signal.score
        enriched["_rule_hits"] = signal.hits

        body = (news.get("body") or "").strip()
        title = (news.get("title") or "").strip()
        if not title and len(body) < 40:
            enriched["_skip_reason"] = "empty_or_too_short"
            skipped.append(enriched)
            continue

        if signal.obvious_noise:
            enriched["_skip_reason"] = "obvious_noise"
            skipped.append(enriched)
            continue

        candidates.append(enriched)

    candidates.sort(key=lambda item: (item["_rule_score"], item.get("collected_at") or ""), reverse=True)
    if max_items and max_items > 0:
        return candidates[:max_items], skipped
    return candidates, skipped


def _chunked(items: list[dict], size: int) -> Iterable[list[dict]]:
    for start in range(0, len(items), size):
        yield items[start:start + size]


def _load_feedback_context(limit: int = 10) -> str:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT f.action, COALESCE(f.comment, '') AS comment, r.title
            FROM feedback f
            LEFT JOIN raw_news r ON r.id = f.news_id
            ORDER BY f.created_at DESC
            LIMIT ?
        """, (limit,)).fetchall()

    if not rows:
        return "Пока нет пользовательской обратной связи."

    lines = []
    for row in rows:
        title = (row["title"] or "Без заголовка")[:180]
        comment = (row["comment"] or "").strip()
        suffix = f" Комментарий: {comment[:120]}" if comment else ""
        lines.append(f"- {row['action']}: {title}.{suffix}")
    return "\n".join(lines)


def _build_prompt(gosb: dict, batch: list[dict]) -> str:
    news_list = "\n\n".join(
        (
            f"[{idx}] id={news['id']}\n"
            f"Заголовок: {news.get('title') or '-'}\n"
            f"Источник: {news.get('source') or '-'}\n"
            f"Rule score: {news.get('_rule_score', 0)}; hits: {', '.join(news.get('_rule_hits') or []) or '-'}\n"
            f"Текст: {(news.get('body') or '')[:900]}"
        )
        for idx, news in enumerate(batch)
    )

    return f"""Ты — интеллектуальный помощник для управляющего ГОСБ банка.
ГОСБ — это головное отделение банка, которое отвечает за определенный регион страны.
Кластер — это совокупность нескольких ГОСБ, расположенных в определенной части страны.

В этой задаче ты — редактор банковского регионального дайджеста для {gosb['name']}.

Цель: отобрать новости, которые реально полезны региональному банку.
Регион/территория ГОСБа: {gosb.get('region') or '-'}.
Локальные ориентиры из конфига: {_keywords_display(gosb)}.
Закрепленные клиентские холдинги этого ГОСБа: {holdings_display_for_gosb(gosb['name'])}.

Считать релевантным:
- новости о закрепленных клиентских холдингах этого ГОСБа: сделки, стройки, инвестиции, производство, суды, банкротства, проверки, собственники, расширение/сокращение бизнеса;
- банковский сектор, Сбер, конкуренты, карты, платежи, вклады, кредиты, ипотека;
- мошенничество, киберриски, нелегальный трафик, схемы хищения денег;
- ЦБ РФ, ключевая ставка, регулирование, налоги, судебные и банкротные риски;
- крупный бизнес, промышленность, инвестиции, производство, застройщики, МСП, если есть понятная связь с клиентами/кредитованием/рисками банка;
- повестка ЛПР/органов власти, если она влияет на экономику региона или клиентов банка.

Считать шумом:
- спорт, погода, развлечения, розыгрыши, поздравления, алкогольные ограничения, бытовая городская повестка;
- новости только с географией региона ГОСБа без банковского, экономического или риск-содержания.

Метрики из темы метрик:
{get_knowledge_context("metrics", limit=10, max_chars=3200)}

Методология из отдельной темы:
{get_knowledge_context("methodology", limit=8, max_chars=2600)}

Если новость влияет на конкретную метрику из контекста выше, заполни metric_links. Не придумывай метрики, которых нет в загруженном контексте.

Недавняя обратная связь пользователей:
{_load_feedback_context()}

Новости:
{news_list}

Верни только валидный JSON без markdown. Для каждой новости верни решение.
Схема строго такая:
{{
  "items": [
    {{
      "index": 0,
      "relevant": true,
      "category": "fraud|banking|regulation|business|client_holding|regional_economy|lpr|noise|other",
      "impact": "high|medium|low|none",
      "confidence": 0.0,
      "summary": "1-2 предложения, почему это важно для банка",
      "reject_reason": "если relevant=false, коротко почему",
      "metric_links": [
        {{"metric_key": "ключ/название метрики из контекста", "metric_name": "человекочитаемое название", "impact": "positive|negative|risk|context|none", "confidence": 0.0, "reason": "почему новость связана с метрикой"}}
      ]
    }}
  ]
}}"""


def _normalize_metric_links(value) -> list[dict]:
    if not isinstance(value, list):
        return []

    links = []
    for raw in value[:5]:
        if not isinstance(raw, dict):
            continue
        metric_key = str(raw.get("metric_key") or raw.get("metric_name") or "").strip()
        if not metric_key:
            continue
        impact = str(raw.get("impact") or "context").strip()
        if impact not in METRIC_IMPACTS:
            impact = "context"
        try:
            confidence = float(raw.get("confidence") or 0)
        except (TypeError, ValueError):
            confidence = 0.0
        links.append({
            "metric_key": metric_key[:160],
            "metric_name": str(raw.get("metric_name") or "").strip()[:220],
            "impact": impact,
            "confidence": max(0.0, min(1.0, confidence)),
            "reason": str(raw.get("reason") or "").strip()[:500],
        })
    return links


def _normalize_item(item: dict, batch_size: int) -> dict | None:
    try:
        idx = int(item.get("index"))
    except (TypeError, ValueError):
        return None
    if idx < 0 or idx >= batch_size:
        return None

    category = str(item.get("category") or "other").strip()
    if category not in CATEGORIES:
        category = "other"

    impact = str(item.get("impact") or "none").strip()
    if impact not in IMPACTS:
        impact = "none"

    try:
        confidence = float(item.get("confidence") or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    return {
        "index": idx,
        "relevant": bool(item.get("relevant")),
        "category": category,
        "impact": impact,
        "confidence": confidence,
        "summary": str(item.get("summary") or "").strip(),
        "reject_reason": str(item.get("reject_reason") or "").strip(),
        "metric_links": _normalize_metric_links(item.get("metric_links")),
    }


def _fallback_classify(batch: list[dict], reason: str) -> list[dict]:
    results = []
    for idx, news in enumerate(batch):
        score = int(news.get("_rule_score") or 0)
        hits = news.get("_rule_hits") or []
        strong = any(str(hit).startswith("strong:") for hit in hits)
        holding = any(str(hit).startswith("holding:") for hit in hits)
        relevant = (strong or holding) and score >= 5
        results.append({
            "index": idx,
            "relevant": relevant,
            "category": "client_holding" if holding and relevant else ("other" if relevant else "noise"),
            "impact": "low" if relevant else "none",
            "confidence": 0.55 if relevant else 0.4,
            "summary": "Новость прошла строгий rule-fallback после ошибки LLM." if relevant else "",
            "reject_reason": reason if not relevant else "",
            "metric_links": [],
        })
    return results


def classify_batch(gosb: dict, batch: list[dict], disable_llm: bool = False) -> tuple[list[dict], dict]:
    if disable_llm:
        return _fallback_classify(batch, "llm_disabled"), {"source": "rules"}

    prompt = _build_prompt(gosb, batch)
    try:
        raw = _openclaw_json(prompt)
        raw_items = raw.get("items", [])
        if not isinstance(raw_items, list):
            raise ValueError("LLM response has no items list")
        normalized = []
        seen = set()
        for raw_item in raw_items:
            item = _normalize_item(raw_item, len(batch))
            if item is not None:
                normalized.append(item)
                seen.add(item["index"])
        for idx in range(len(batch)):
            if idx not in seen:
                normalized.append({
                    "index": idx,
                    "relevant": False,
                    "category": "other",
                    "impact": "none",
                    "confidence": 0.0,
                    "summary": "",
                    "reject_reason": "LLM не вернул решение по новости",
                    "metric_links": [],
                })
        return normalized, raw
    except Exception as exc:
        reason = f"llm_error: {str(exc)[:180]}"
        print(f"  ⚠️  V2 batch fallback: {reason}")
        return _fallback_classify(batch, reason), {"source": "fallback", "error": reason}


def run_filter_v2(
    mode: str = "shadow",
    since_hours: int = 24,
    limit: int = MAX_ITEMS,
    batch_size: int = BATCH_SIZE,
    min_confidence: float = MIN_CONFIDENCE,
    disable_llm: bool = False,
    run_id: str | None = None,
) -> bool:
    if mode not in {"shadow", "dry-run", "live"}:
        raise ValueError("mode must be shadow, dry-run, or live")

    init_db()
    gosbs = get_active_gosbs()
    print(f"🔎 V2 фильтр: mode={mode}, gosbs={len(gosbs)}, llm={'off' if disable_llm else 'on'}")

    for gosb_row in gosbs:
        gosb = dict(gosb_row)
        news_items = [dict(n) for n in get_unsent_news(gosb["id"], since_hours=since_hours)]
        candidates, skipped = prepare_candidates(news_items, gosb, max_items=limit)
        print(
            f"📍 {gosb['name']}: свежих {len(news_items)}, "
            f"к LLM {len(candidates)}, rule-skip {len(skipped)}"
        )

        relevant_items = []
        for batch in _chunked(candidates, batch_size):
            classified, raw = classify_batch(gosb, batch, disable_llm=disable_llm)
            by_index = {item["index"]: item for item in classified}

            for idx, news in enumerate(batch):
                item = by_index.get(idx) or {
                    "relevant": False,
                    "category": "other",
                    "impact": "none",
                    "confidence": 0.0,
                    "summary": "",
                    "reject_reason": "Нет решения классификатора",
                    "metric_links": [],
                }
                is_relevant = bool(item["relevant"]) and item["confidence"] >= min_confidence
                save_news_classification(
                    gosb_id=gosb["id"],
                    news_id=news["id"],
                    mode=mode,
                    model=OPENCLAW_MODEL if not disable_llm else "rules",
                    relevant=is_relevant,
                    category=item["category"],
                    impact=item["impact"],
                    confidence=item["confidence"],
                    summary=item["summary"],
                    reject_reason=item["reject_reason"],
                    rule_score=int(news.get("_rule_score") or 0),
                    rule_hits=news.get("_rule_hits") or [],
                    llm_raw_json=raw,
                )
                save_news_metric_links(
                    gosb_id=gosb["id"],
                    news_id=news["id"],
                    mode=mode,
                    metric_links=item.get("metric_links") if is_relevant else [],
                )
                if is_relevant:
                    relevant_items.append((news, item))

        relevant_items.sort(
            key=lambda pair: (
                pair[1].get("impact") == "high",
                pair[1].get("confidence", 0),
                pair[0].get("_rule_score", 0),
            ),
            reverse=True,
        )
        selected = relevant_items[:DIGEST_LIMIT] if DIGEST_LIMIT and DIGEST_LIMIT > 0 else relevant_items
        limit_label = str(DIGEST_LIMIT) if DIGEST_LIMIT and DIGEST_LIMIT > 0 else "без лимита"
        print(
            f"  ✅ V2 релевантных: {len(relevant_items)}; "
            f"выбрано для дайджеста: {len(selected)} (лимит: {limit_label})"
        )

        if mode == "live":
            for news, item in selected:
                mark_as_sent(gosb["id"], news["id"], item["summary"], run_id=run_id)
            print(f"  📤 Live: записано в sent_news {len(selected)}")
        else:
            for news, item in selected[:10]:
                print(
                    f"  • [{item['category']}/{item['impact']}/{item['confidence']:.2f}] "
                    f"{news.get('title')}"
                )

    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Run V2 news classifier")
    parser.add_argument("--mode", choices=("shadow", "dry-run", "live"), default="shadow")
    parser.add_argument("--since-hours", type=int, default=24)
    parser.add_argument("--limit", type=int, default=MAX_ITEMS)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--min-confidence", type=float, default=MIN_CONFIDENCE)
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()

    run_filter_v2(
        mode=args.mode,
        since_hours=args.since_hours,
        limit=args.limit,
        batch_size=args.batch_size,
        min_confidence=args.min_confidence,
        disable_llm=args.no_llm,
        run_id=args.run_id,
    )


if __name__ == "__main__":
    main()
