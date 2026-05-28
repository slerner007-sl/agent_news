"""
Load news sources from config/sources.txt.

Supported formats:
    rss:Name|URL|site
    rss:URL
    wpapi:Name|URL|site
    telegram:Name|username
    telegram:username
"""

import os
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCES_FILE = PROJECT_ROOT / "config" / "sources.txt"
SOURCES_FILE_ENV = "NEWS_SOURCES_FILE"


def _name_from_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.replace("www.", "")
    return host or url


def _site_from_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return ""


def _telegram_username(value: str) -> str:
    value = value.strip()
    if value.startswith("https://t.me/s/"):
        return value.rstrip("/").rsplit("/", 1)[-1]
    if value.startswith("https://t.me/"):
        return value.rstrip("/").rsplit("/", 1)[-1]
    return value.removeprefix("@").strip("/")


def _telegram_url(username_or_url: str) -> str:
    value = username_or_url.strip()
    if value.startswith("https://t.me/s/"):
        return value
    username = _telegram_username(value)
    return f"https://t.me/s/{username}"


def _split_source_line(line: str) -> tuple[str, list[str]]:
    if ":" not in line:
        raise ValueError("expected '<type>:<value>'")
    source_type, payload = line.split(":", 1)
    parts = [part.strip() for part in payload.split("|")]
    parts = [part for part in parts if part]
    if not parts:
        raise ValueError("empty source payload")
    return source_type.strip().lower(), parts


def _parse_source_line(line: str) -> tuple[str, dict]:
    source_type, parts = _split_source_line(line)

    if source_type in {"rss", "smi", "wpapi", "wordpress"}:
        if len(parts) == 1:
            url = parts[0]
            name = _name_from_url(url)
            site = _site_from_url(url)
        else:
            name = parts[0]
            url = parts[1]
            site = parts[2] if len(parts) >= 3 else _site_from_url(url)
        normalized_type = "wpapi" if source_type in {"wpapi", "wordpress"} else "rss"
        return normalized_type, {"name": name, "url": url, "site": site}

    if source_type in {"telegram", "tg"}:
        if len(parts) == 1:
            username = _telegram_username(parts[0])
            name = username
        else:
            name = parts[0]
            username = _telegram_username(parts[1])
        return "telegram", {
            "name": name,
            "username": username,
            "url": _telegram_url(username),
        }

    raise ValueError(f"unsupported source type '{source_type}'")


def _fallback_sources() -> tuple[list[dict], list[dict], list[dict]]:
    from .samara_sources import RSS_SOURCES, TG_SOURCES

    return list(RSS_SOURCES), list(TG_SOURCES), []


def load_sources(path: str | Path | None = None) -> tuple[list[dict], list[dict], list[dict]]:
    sources_path = Path(
        path or os.getenv(SOURCES_FILE_ENV) or DEFAULT_SOURCES_FILE
    )
    rss_sources: list[dict] = []
    tg_sources: list[dict] = []
    wpapi_sources: list[dict] = []
    errors: list[str] = []

    if sources_path.exists():
        for line_number, raw_line in enumerate(
            sources_path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                source_type, source = _parse_source_line(line)
            except ValueError as exc:
                errors.append(f"{sources_path}:{line_number}: {exc}")
                continue

            if source_type == "rss":
                rss_sources.append(source)
            elif source_type == "wpapi":
                wpapi_sources.append(source)
            elif source_type == "telegram":
                tg_sources.append(source)

    if rss_sources or tg_sources or wpapi_sources:
        for error in errors:
            print(f"⚠️  Источник пропущен: {error}")
        return rss_sources, tg_sources, wpapi_sources

    if errors:
        for error in errors:
            print(f"⚠️  Источник пропущен: {error}")
        print("⚠️  В config/sources.txt не осталось валидных источников, использую samara_sources.py")

    return _fallback_sources()


RSS_SOURCES, TG_SOURCES, WPAPI_SOURCES = load_sources()
