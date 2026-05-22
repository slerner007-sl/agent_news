"""
parser.py — сбор новостей из RSS-источников
"""

import feedparser
import socket
from datetime import datetime
from db import save_raw_news
from samara_sources import RSS_SOURCES

# таймаут 5 секунд на каждый источник
socket.setdefaulttimeout(5)


def parse_rss(source: dict) -> list:
    items = []
    try:
        feed = feedparser.parse(source["url"])
        for entry in feed.entries:
            items.append({
                "url":          entry.get("link", ""),
                "title":        entry.get("title", "").strip(),
                "body":         entry.get("summary", ""),
                "source":       f"rss:{source['name']}",
                "published_at": entry.get("published", datetime.now().isoformat()),
            })
        print(f"✅ {source['name']}: {len(items)} новостей")
    except Exception as e:
        print(f"❌ {source['name']}: ошибка — {e}")
    return items


def collect_all_news() -> int:
    all_items = []
    for source in RSS_SOURCES:
        items = parse_rss(source)
        all_items.extend(items)

    saved = save_raw_news(all_items)
    print(f"\n📰 Собрано: {len(all_items)} | Новых в БД: {saved}")
    return saved


if __name__ == "__main__":
    collect_all_news()
