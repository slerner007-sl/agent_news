"""
Load per-GOSB client holdings from config/holdings.txt.

Format:
    GOSB name|Holding name|alias 1; alias 2|inn 1; inn 2|source label
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_HOLDINGS_FILE = PROJECT_ROOT / "config" / "holdings.txt"
HOLDINGS_FILE_ENV = "NEWS_HOLDINGS_FILE"
MIN_TERM_LENGTH = 4
GENERIC_TERMS = {
    "гк", "ооо", "ао", "зао", "пао", "ип", "группа", "компания", "компаний",
    "холдинг", "холдинг ммб", "общество", "ограниченной", "ответственностью",
}


@dataclass(frozen=True)
class Holding:
    gosb: str
    name: str
    aliases: tuple[str, ...] = ()
    inns: tuple[str, ...] = ()
    source: str = ""


def _clean(value: str | None) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def _split_many(value: str) -> tuple[str, ...]:
    return tuple(
        item
        for item in (_clean(part) for part in re.split(r"[;,]", value or ""))
        if item and item != "-"
    )


def parse_holding_line(line: str) -> Holding:
    parts = [_clean(part) for part in line.split("|")]
    if len(parts) < 2:
        raise ValueError("expected 'GOSB|Holding name|aliases|inns|source'")
    while len(parts) < 5:
        parts.append("")
    gosb, name, aliases, inns, source = parts[:5]
    if not gosb or not name:
        raise ValueError("GOSB and holding name are required")
    return Holding(gosb=gosb, name=name, aliases=_split_many(aliases), inns=_split_many(inns), source=source)


def load_holdings(path: str | Path | None = None) -> list[Holding]:
    holdings_path = Path(path or os.getenv(HOLDINGS_FILE_ENV) or DEFAULT_HOLDINGS_FILE)
    if not holdings_path.exists():
        return []

    holdings: list[Holding] = []
    for line_number, raw_line in enumerate(holdings_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            holdings.append(parse_holding_line(line))
        except ValueError as exc:
            print(f"⚠️  Холдинг пропущен: {holdings_path}:{line_number}: {exc}")
    return holdings


@lru_cache(maxsize=16)
def _cached_holdings(path_value: str) -> tuple[Holding, ...]:
    return tuple(load_holdings(path_value or None))


def get_holdings(path: str | Path | None = None) -> tuple[Holding, ...]:
    path_value = str(path or os.getenv(HOLDINGS_FILE_ENV) or DEFAULT_HOLDINGS_FILE)
    return _cached_holdings(path_value)


def holdings_for_gosb(gosb_name: str, path: str | Path | None = None) -> list[Holding]:
    gosb_name = _clean(gosb_name)
    return [holding for holding in get_holdings(path) if holding.gosb == gosb_name]


def _simplify_company_name(value: str) -> list[str]:
    text = _clean(value).lower().replace("ё", "е")
    text = re.sub(r"_ммб.*$", "", text)
    text = re.sub(r"\bхолдинг[_\s-]*ммб.*$", "", text)
    text = text.replace("_", " ")
    text = re.sub(r"[\"'«»()]+", " ", text)
    text = re.sub(r"\b(общество с ограниченной ответственностью|ооо|акционерное общество|ао|зао|пао)\b", " ", text)
    text = " ".join(text.split())

    if not text or text in GENERIC_TERMS:
        return []
    return [text]


def terms_for_holdings(holdings: list[Holding] | tuple[Holding, ...]) -> tuple[str, ...]:
    terms: set[str] = set()
    for holding in holdings:
        for value in (holding.name, *holding.aliases, *holding.inns):
            for term in _simplify_company_name(value):
                if len(term) >= MIN_TERM_LENGTH and term not in GENERIC_TERMS:
                    terms.add(term)
    return tuple(sorted(terms, key=lambda term: (-len(term), term)))


def holding_terms_for_gosb(gosb_name: str, path: str | Path | None = None) -> tuple[str, ...]:
    return terms_for_holdings(holdings_for_gosb(gosb_name, path))


def holdings_display_for_gosb(gosb_name: str, limit: int = 30, path: str | Path | None = None) -> str:
    names = [holding.name for holding in holdings_for_gosb(gosb_name, path)]
    if not names:
        return "-"
    shown = names[:limit]
    suffix = f" и еще {len(names) - limit}" if len(names) > limit else ""
    return ", ".join(shown) + suffix
