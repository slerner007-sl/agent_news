"""Static regional business context used by filters and insight generation."""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REGION_CONTEXT_PATH = PROJECT_ROOT / "config" / "region_context.md"

REGION_ALIASES = {
    "Самарская область": ("самар", "тольятти", "сызран", "новокуйбышевск"),
    "Ленинградская область": ("ленинград", "ленобл", "мурино", "всеволож"),
    "Калининградская область": ("калининград", "балтийск", "советск", "черняховск"),
    "Ульяновская область": ("ульянов", "димитровград"),
}


def _read_context() -> str:
    if not REGION_CONTEXT_PATH.exists():
        return ""
    return REGION_CONTEXT_PATH.read_text(encoding="utf-8")


def _split_sections(text: str) -> tuple[str, dict[str, str]]:
    preamble_parts: list[str] = []
    sections: dict[str, str] = {}
    current_title: str | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if match:
            if current_title:
                sections[current_title] = "\n".join(current_lines).strip()
            elif current_lines:
                preamble_parts.extend(current_lines)
            current_title = match.group(1).strip()
            current_lines = [line]
            continue
        current_lines.append(line)

    if current_title:
        sections[current_title] = "\n".join(current_lines).strip()
    elif current_lines:
        preamble_parts.extend(current_lines)

    return "\n".join(preamble_parts).strip(), sections


def _match_region(gosb: dict | None, sections: dict[str, str]) -> str | None:
    haystack = " ".join(
        str((gosb or {}).get(key) or "")
        for key in ("name", "region", "keywords", "system_prompt")
    ).lower()
    for title in sections:
        aliases = REGION_ALIASES.get(title, ())
        if title.lower().replace(" область", "") in haystack:
            return title
        if any(alias in haystack for alias in aliases):
            return title
    return None


def get_region_context_for_gosb(gosb: dict | None, max_chars: int = 2800) -> str:
    text = _read_context()
    if not text:
        return "-"

    preamble, sections = _split_sections(text)
    title = _match_region(gosb, sections)
    parts = []
    if preamble:
        parts.append(preamble)
    if title and sections.get(title):
        parts.append(sections[title])
    elif sections:
        parts.append("Нет точного регионального раздела; используй только явные совпадения по региону.")

    return "\n\n".join(parts)[:max_chars] or "-"
