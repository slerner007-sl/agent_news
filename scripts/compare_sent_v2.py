"""
Classify already sent legacy digest items with V2.

Safe: no writes and no Telegram sending.
"""

from _bootstrap import bootstrap

bootstrap()

from agent_news.db import get_active_gosbs, get_conn
from agent_news.llm_filter_v2 import BATCH_SIZE, MIN_CONFIDENCE, classify_batch


def _chunked(items, size):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def main():
    gosb = dict(get_active_gosbs()[0])
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT r.*, s.summary AS legacy_summary, s.sent_at
            FROM sent_news s
            JOIN raw_news r ON r.id = s.news_id
            WHERE s.gosb_id = ?
            ORDER BY s.sent_at DESC
        """, (gosb["id"],)).fetchall()

    news_items = [dict(row) for row in rows]
    print(f"Legacy sent items: {len(news_items)}")
    accepted = []
    rejected = []

    for batch in _chunked(news_items, BATCH_SIZE):
        classified, _raw = classify_batch(gosb, batch, disable_llm=False)
        for item in classified:
            news = batch[item["index"]]
            keep = bool(item["relevant"]) and item["confidence"] >= MIN_CONFIDENCE
            target = accepted if keep else rejected
            target.append((news, item))

    print(f"V2 would keep: {len(accepted)}")
    for news, item in accepted:
        print(
            f"+ id={news['id']} [{item['category']}/{item['impact']}/{item['confidence']:.2f}] "
            f"{(news.get('title') or '')[:180]}"
        )
        print(f"  -> {(item.get('summary') or '')[:260]}")

    print(f"\nV2 would reject: {len(rejected)}")
    for news, item in rejected:
        print(
            f"- id={news['id']} [{item['category']}/{item['impact']}/{item['confidence']:.2f}] "
            f"{(news.get('title') or '')[:180]}"
        )
        print(f"  -> {(item.get('reject_reason') or '')[:260]}")


if __name__ == "__main__":
    main()
