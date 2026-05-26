#!/usr/bin/env python3
"""Render the current bot selection prompt as a dark Telegram-friendly PNG."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH = 1080
PADDING = 64
INNER = WIDTH - PADDING * 2
BG = "#15171b"
PANEL = "#1f2329"
BLUE = "#3f6f9f"
BLUE_2 = "#5482ad"
TEXT = "#f2f5f8"
MUTED = "#c8d0da"
LINE = "#333941"

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
REGULAR = FONT_DIR / "DejaVuSans.ttf"
BOLD = FONT_DIR / "DejaVuSans-Bold.ttf"


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


TITLE_FONT = font(BOLD, 44)
H_FONT = font(BOLD, 31)
BODY_FONT = font(REGULAR, 27)
BULLET_FONT = font(REGULAR, 25)
SMALL_FONT = font(REGULAR, 22)


def wrap_text(text: str, chars: int) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            lines.append("")
            continue
        lines.extend(textwrap.wrap(raw, width=chars, break_long_words=False, replace_whitespace=False) or [""])
    return lines


def line_height(draw: ImageDraw.ImageDraw, fnt: ImageFont.FreeTypeFont) -> int:
    box = draw.textbbox((0, 0), "АБВabc123", font=fnt)
    return box[3] - box[1] + 12


def draw_wrapped(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, fnt, fill: str, chars: int, spacing: int = 0) -> int:
    lh = line_height(draw, fnt) + spacing
    for line in wrap_text(text, chars):
        if not line:
            y += lh // 2
            continue
        draw.text((x, y), line, font=fnt, fill=fill)
        y += lh
    return y


def parse_prompt(prompt: str):
    title = "Текущий промт отбора"
    body = prompt.strip()
    if body.startswith("Текущий промт отбора:"):
        body = body.split(":", 1)[1].strip()

    sections = []
    current = {"title": "Роль и цель", "body": [], "bullets": []}
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.endswith(":") and not line.startswith("-"):
            if current["body"] or current["bullets"]:
                sections.append(current)
            current = {"title": line[:-1], "body": [], "bullets": []}
            continue
        if line.startswith("-"):
            current["bullets"].append(line[1:].strip())
        else:
            current["body"].append(line)
    if current["body"] or current["bullets"]:
        sections.append(current)
    return title, sections


def measure_height(prompt: str) -> int:
    img = Image.new("RGB", (WIDTH, 100), BG)
    draw = ImageDraw.Draw(img)
    _, sections = parse_prompt(prompt)
    y = PADDING + 76 + 26
    for idx, section in enumerate(sections, start=1):
        y += line_height(draw, H_FONT) + 8
        for paragraph in section["body"]:
            y += len(wrap_text(paragraph, 54)) * line_height(draw, BODY_FONT) + 8
        for bullet in section["bullets"]:
            y += len(wrap_text(bullet, 55)) * line_height(draw, BULLET_FONT) + 18
        y += 32
    y += 220
    return max(900, y + PADDING)


def render(prompt: str, output: Path) -> None:
    title, sections = parse_prompt(prompt)
    height = measure_height(prompt)
    img = Image.new("RGB", (WIDTH, height), BG)
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle((0, 0, WIDTH, height), radius=0, fill=BG)
    draw.rectangle((0, 0, 18, height), fill=BLUE)
    draw.text((PADDING, PADDING), title, font=TITLE_FONT, fill=TEXT)
    draw.text((PADDING, PADDING + 58), "Как бот решает, какие новости полезны для ГОСБа", font=SMALL_FONT, fill=MUTED)

    y = PADDING + 112
    for idx, section in enumerate(sections, start=1):
        if idx > 1:
            draw.line((PADDING, y, WIDTH - PADDING, y), fill=LINE, width=2)
            y += 28
        draw.text((PADDING, y), f"{idx}. {section['title']}", font=H_FONT, fill=TEXT)
        y += line_height(draw, H_FONT) + 8
        for paragraph in section["body"]:
            y = draw_wrapped(draw, PADDING, y, paragraph, BODY_FONT, MUTED, 54)
            y += 8
        for bullet in section["bullets"]:
            bullet_y = y
            draw.text((PADDING + 6, bullet_y), "•", font=BULLET_FONT, fill=TEXT)
            y = draw_wrapped(draw, PADDING + 34, y, bullet, BULLET_FONT, TEXT, 55)
            y += 8
        y += 16

    box_top = y + 10
    box_bottom = min(height - PADDING, box_top + 150)
    draw.rounded_rectangle((PADDING, box_top, WIDTH - PADDING, box_bottom), radius=14, fill=BLUE)
    draw.text((PADDING + 32, box_top + 26), "Метрики и методология", font=H_FONT, fill=TEXT)
    draw_wrapped(
        draw,
        PADDING + 32,
        box_top + 72,
        "Файлы из темы метрик и методология из отдельной темы добавляются в контекст V2 и помогают связать новости с конкретными показателями.",
        BODY_FONT,
        TEXT,
        55,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    img.save(output, "PNG", optimize=True)


if __name__ == "__main__":
    out = Path(sys.argv[1])
    prompt = sys.stdin.read()
    render(prompt, out)
