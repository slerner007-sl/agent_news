"""
Compare legacy keyword+LLM filter with V2 LLM-first filter.

Safe by design: does not write sent_news and does not send Telegram messages.
"""

from __future__ import annotations

import argparse
import json

from db import get_active_gosbs, get_unsent_news
from llm_filter import filter_news_for_gosb
from llm_filter_v2 import (
    BATCH_SIZE,
    MAX_ITEMS,
    MIN_CONFIDENCE,
    classify_batch,
    prepare_candidates,
)


def _legacy_candidates(gosb: dict, news_items: list[dict]) -> list[dict]:
    keywords = json.loads(gosb["keywords"])
    result = []
    for news in news_items:
        text = (news["title"] + " " + (news.get("body") or "")).lower()
        hits = [kw for kw in keywords if kw.lower() in text]
        if hits:
            item = dict(news)
            item["_legacy_hits"] = hits
            result.append(item)
    return result


def _chunked(items: list[dict], size: int):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def _title(news: dict | None) -> str:
    if not news:
        return "-"
    return (news.get("title") or "").replace("\n", " ")[:180]


def _print_news(label: str, items: list[tuple[dict, dict | None]], limit: int = 20) -> None:
    print(f"\n{label}: {len(items)}")
    for news, meta in items[:limit]:
        if meta:
            print(
                f"- id={news['id']} [{meta.get('category')}/{meta.get('impact')}/"
                f"{meta.get('confidence', 0):.2f}] {_title(news)}"
            )
            summary = (meta.get("summary") or meta.get("reject_reason") or "").strip()
            if summary:
                print(f"  -> {summary[:260]}")
        else:
            print(f"- id={news['id']} {_title(news)}")


def compare_filters(
    since_hours: int,
    limit: int,
    batch_size: int,
    min_confidence: float,
    no_llm: bool,
) -> None:
    gosbs = [dict(row) for row in get_active_gosbs()]
    print(f"Active GOSB count: {len(gosbs)}")

    for gosb in gosbs:
        news_items = [dict(row) for row in get_unsent_news(gosb["id"], since_hours=since_hours)]
        news_by_id = {news["id"]: news for news in news_items}
        print("\n" + "=" * 80)
        print(f"GOSB: {gosb['name']}")
        print(f"News window: {since_hours}h; unsent news: {len(news_items)}")

        legacy_candidates = _legacy_candidates(gosb, news_items)
        print(f"Legacy keyword candidates: {len(legacy_candidates)}")
        if legacy_candidates:
            for news in legacy_candidates[:10]:
                print(f"  legacy-candidate id={news['id']} hits={news['_legacy_hits']} {_title(news)}")

        legacy_relevant = filter_news_for_gosb(gosb, news_items)
        legacy_relevant_by_id = {
            item["news"]["id"]: item for item in legacy_relevant
        }

        v2_candidates, v2_skipped = prepare_candidates(news_items, max_items=limit)
        print(f"V2 candidates for LLM: {len(v2_candidates)}; rule-skipped: {len(v2_skipped)}")

        v2_results_by_id = {}
        for batch in _chunked(v2_candidates, batch_size):
            classified, _raw = classify_batch(gosb, batch, disable_llm=no_llm)
            for item in classified:
                news = batch[item["index"]]
                item = dict(item)
                item["final_relevant"] = bool(item["relevant"]) and item["confidence"] >= min_confidence
                v2_results_by_id[news["id"]] = item

        v2_relevant_by_id = {
            news_id: item
            for news_id, item in v2_results_by_id.items()
            if item["final_relevant"]
        }

        legacy_ids = set(legacy_relevant_by_id)
        v2_ids = set(v2_relevant_by_id)
        both_ids = sorted(legacy_ids & v2_ids)
        legacy_only_ids = sorted(legacy_ids - v2_ids)
        v2_only_ids = sorted(v2_ids - legacy_ids)

        print("\nSUMMARY")
        print(f"Legacy selected: {len(legacy_ids)}")
        print(f"V2 selected: {len(v2_ids)}")
        print(f"Both selected: {len(both_ids)}")
        print(f"Legacy only: {len(legacy_only_ids)}")
        print(f"V2 only: {len(v2_only_ids)}")

        _print_news("Both", [(news_by_id[i], v2_results_by_id.get(i)) for i in both_ids])
        _print_news("Legacy only", [(news_by_id[i], None) for i in legacy_only_ids])
        _print_news("V2 only", [(news_by_id[i], v2_results_by_id.get(i)) for i in v2_only_ids])

        rejected = [
            (news_by_id[news_id], item)
            for news_id, item in v2_results_by_id.items()
            if not item["final_relevant"]
        ]
        rejected.sort(key=lambda pair: pair[1].get("confidence", 0), reverse=True)
        _print_news("V2 rejected sample", rejected[:10])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since-hours", type=int, default=24)
    parser.add_argument("--limit", type=int, default=MAX_ITEMS)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--min-confidence", type=float, default=MIN_CONFIDENCE)
    parser.add_argument("--no-llm", action="store_true")
    args = parser.parse_args()

    compare_filters(
        since_hours=args.since_hours,
        limit=args.limit,
        batch_size=args.batch_size,
        min_confidence=args.min_confidence,
        no_llm=args.no_llm,
    )


if __name__ == "__main__":
    main()
