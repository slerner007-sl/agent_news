#!/usr/bin/env python3
"""Extract text from small knowledge files dropped into Telegram topics."""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

MAX_TEXT = 24000


def _clip(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.splitlines() if line.strip())[:MAX_TEXT]


def _read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp1251"):
        try:
            return path.read_text(encoding=encoding, errors="strict")
        except UnicodeDecodeError:
            pass
    return path.read_text(encoding="utf-8", errors="replace")


def _read_csv(path: Path) -> str:
    text = _read_text(path)
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = []
    for idx, row in enumerate(csv.reader(text.splitlines(), dialect)):
        if idx >= 250:
            rows.append("...")
            break
        rows.append(" | ".join(cell.strip() for cell in row if cell is not None))
    return "\n".join(rows)


def _xlsx_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        data = zf.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(data)
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    strings = []
    for si in root.findall("a:si", ns):
        parts = [node.text or "" for node in si.findall(".//a:t", ns)]
        strings.append("".join(parts))
    return strings


def _read_xlsx(path: Path) -> str:
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    lines = []
    with zipfile.ZipFile(path) as zf:
        shared = _xlsx_shared_strings(zf)
        sheet_names = sorted(name for name in zf.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"))
        for sheet_idx, sheet_name in enumerate(sheet_names[:8], start=1):
            lines.append(f"# sheet {sheet_idx}")
            root = ET.fromstring(zf.read(sheet_name))
            for row_idx, row in enumerate(root.findall(".//a:sheetData/a:row", ns)):
                if row_idx >= 220:
                    lines.append("...")
                    break
                values = []
                for cell in row.findall("a:c", ns):
                    raw = cell.find("a:v", ns)
                    if raw is None or raw.text is None:
                        inline = cell.find("a:is", ns)
                        if inline is not None:
                            values.append("".join(t.text or "" for t in inline.findall(".//a:t", ns)).strip())
                        continue
                    value = raw.text
                    if cell.attrib.get("t") == "s":
                        try:
                            value = shared[int(value)]
                        except (ValueError, IndexError):
                            pass
                    values.append(str(value).strip())
                if any(values):
                    lines.append(" | ".join(values))
    return "\n".join(lines)


def _read_docx(path: Path) -> str:
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))
    paragraphs = []
    for paragraph in root.findall(".//w:p", ns):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", ns)).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def _read_pdf(path: Path) -> str:
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        return ""
    completed = subprocess.run(
        [pdftotext, "-layout", str(path), "-"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=20,
    )
    return completed.stdout if completed.returncode == 0 else ""


def extract(path_str: str) -> dict:
    path = Path(path_str)
    suffix = path.suffix.lower()
    if not path.exists() or not path.is_file():
        return {"ok": False, "error": "file_not_found", "text": ""}
    try:
        if suffix in {".txt", ".md", ".log"}:
            text = _read_text(path)
        elif suffix in {".csv", ".tsv"}:
            text = _read_csv(path)
        elif suffix == ".xlsx":
            text = _read_xlsx(path)
        elif suffix == ".docx":
            text = _read_docx(path)
        elif suffix == ".pdf":
            text = _read_pdf(path)
        else:
            text = _read_text(path) if path.stat().st_size < 2_000_000 else ""
        text = _clip(text)
        return {"ok": bool(text), "error": "" if text else "empty_or_unsupported", "text": text}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:300], "text": ""}


if __name__ == "__main__":
    print(json.dumps(extract(sys.argv[1]), ensure_ascii=False))
