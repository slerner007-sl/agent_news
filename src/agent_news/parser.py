"""
parser.py - collect news from RSS feeds and public Telegram channels.
"""

import feedparser
import html
import os
import requests
import socket
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from .db import save_raw_news
from .sources_loader import RSS_SOURCES, TG_SOURCES, WPAPI_SOURCES

# таймаут 5 секунд на каждый источник
socket.setdefaulttimeout(5)

TG_TIMEOUT = 12
TG_MAX_AGE_HOURS = int(os.getenv("TG_MAX_AGE_HOURS", "36"))
TG_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class TelegramPageParser(HTMLParser):
    """Extract posts from public t.me/s channel pages."""

    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.posts = []
        self.current = None
        self.message_depth = 0
        self.in_text = False
        self.text_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "")
        is_void = tag in self.VOID_TAGS
        starts_message = (
            tag == "div"
            and attrs.get("data-post")
            and "tgme_widget_message" in classes
        )

        if starts_message:
            self.current = {
                "data_post": attrs.get("data-post"),
                "url": None,
                "published_at": None,
                "text_parts": [],
            }
            self.message_depth = 1
            self.in_text = False
            self.text_depth = 0
            return

        if not self.current:
            return

        if not is_void:
            self.message_depth += 1

        if tag == "a" and "tgme_widget_message_date" in classes:
            self.current["url"] = attrs.get("href") or self.current.get("url")

        if tag == "time" and attrs.get("datetime"):
            self.current["published_at"] = attrs["datetime"]

        starts_text = tag == "div" and "tgme_widget_message_text" in classes
        if starts_text:
            self.in_text = True
            self.text_depth = 1
            return

        if self.in_text:
            if tag == "br":
                self.current["text_parts"].append("\n")
            elif tag == "img" and attrs.get("alt"):
                self.current["text_parts"].append(attrs["alt"])
            elif not is_void:
                self.text_depth += 1

    def handle_endtag(self, tag):
        is_void = tag in self.VOID_TAGS

        if self.current and self.in_text and not is_void:
            self.text_depth -= 1
            if self.text_depth <= 0:
                self.in_text = False

        if self.current and not is_void:
            self.message_depth -= 1
            if self.message_depth <= 0:
                self._finish_post()

    def handle_data(self, data):
        if self.current and self.in_text:
            self.current["text_parts"].append(data)

    def _finish_post(self):
        text = _clean_text("".join(self.current.get("text_parts", [])))
        if text:
            data_post = self.current.get("data_post") or ""
            url = self.current.get("url") or (f"https://t.me/{data_post}" if data_post else "")
            self.posts.append({
                "url": url,
                "text": text,
                "published_at": self.current.get("published_at") or datetime.now().isoformat(),
            })

        self.current = None
        self.message_depth = 0
        self.in_text = False
        self.text_depth = 0


def _clean_text(text: str) -> str:
    lines = []
    for line in (text or "").replace("\xa0", " ").splitlines():
        line = " ".join(line.split())
        if line:
            lines.append(line)
    return "\n".join(lines).strip()


def _make_title(text: str) -> str:
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "Telegram-пост")
    if len(first_line) <= 140:
        return first_line
    return first_line[:137].rstrip() + "..."


def _is_recent_telegram_post(published_at: str) -> bool:
    if TG_MAX_AGE_HOURS <= 0:
        return True
    try:
        dt = datetime.fromisoformat((published_at or "").replace("Z", "+00:00"))
    except ValueError:
        return True
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=TG_MAX_AGE_HOURS)
    return dt >= cutoff


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


def _strip_html(value: str) -> str:
    parser = HTMLTextParser()
    parser.feed(value or "")
    return _clean_text("".join(parser.parts))


class HTMLTextParser(HTMLParser):
    """Convert small HTML fragments from JSON APIs to plain text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"br", "p", "div", "li"}:
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


def _rendered(value) -> str:
    if isinstance(value, dict):
        value = value.get("rendered", "")
    return html.unescape(str(value or ""))


def parse_wpapi(source: dict) -> list:
    items = []
    try:
        response = requests.get(
            source["url"],
            headers={"User-Agent": TG_USER_AGENT},
            timeout=TG_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            payload = payload.get("items") or payload.get("posts") or []

        for post in payload:
            if not isinstance(post, dict):
                continue
            title = _strip_html(_rendered(post.get("title")))
            body = _strip_html(_rendered(post.get("excerpt")) or _rendered(post.get("content")))
            url = post.get("link") or post.get("url") or ""
            if not url or not title:
                continue
            items.append({
                "url": url,
                "title": title,
                "body": body,
                "source": f"wpapi:{source['name']}",
                "published_at": post.get("date_gmt") or post.get("date") or datetime.now().isoformat(),
            })

        print(f"✅ {source['name']} (WP API): {len(items)} новостей")
    except Exception as e:
        print(f"❌ {source['name']} (WP API): ошибка — {e}")
    return items


def parse_telegram(source: dict) -> list:
    items = []
    try:
        response = requests.get(
            source["url"],
            headers={"User-Agent": TG_USER_AGENT},
            timeout=TG_TIMEOUT,
        )
        response.raise_for_status()

        parser = TelegramPageParser()
        parser.feed(response.text)

        for post in parser.posts:
            if not _is_recent_telegram_post(post["published_at"]):
                continue
            text = post["text"]
            items.append({
                "url": post["url"],
                "title": _make_title(text),
                "body": text,
                "source": f"tg:{source['name']}",
                "published_at": post["published_at"],
            })

        print(f"✅ {source['name']} (Telegram): {len(items)} свежих постов из {len(parser.posts)}")
    except Exception as e:
        print(f"❌ {source['name']} (Telegram): ошибка — {e}")
    return items


def collect_all_news() -> int:
    all_items = []

    for source in RSS_SOURCES:
        items = parse_rss(source)
        all_items.extend(items)

    for source in WPAPI_SOURCES:
        items = parse_wpapi(source)
        all_items.extend(items)

    for source in TG_SOURCES:
        items = parse_telegram(source)
        all_items.extend(items)

    saved = save_raw_news(all_items)
    print(f"\n📰 Собрано: {len(all_items)} | Новых в БД: {saved}")
    return saved


if __name__ == "__main__":
    collect_all_news()
