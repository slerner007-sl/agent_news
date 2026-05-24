"""
llm_filter.py - news filtering through the local OpenClaw gateway.
"""

import json
import os
import subprocess
from pathlib import Path
from db import get_active_gosbs, get_unsent_news, mark_as_sent

OPENCLAW_BIN = os.getenv("OPENCLAW_BIN", "/home/user1/.npm-global/bin/openclaw")
OPENCLAW_MODEL = os.getenv("OPENCLAW_MODEL", "openai/gpt-5.5")
OPENCLAW_TIMEOUT = int(os.getenv("OPENCLAW_TIMEOUT", "240"))
FALLBACK_LIMIT = int(os.getenv("NEWS_FALLBACK_LIMIT", "5"))
PROJECT_DIR = Path(__file__).resolve().parent


def _strip_code_fences(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _extract_json(text: str) -> dict:
    cleaned = _strip_code_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(cleaned[start:end + 1])


def _openclaw_json(prompt: str) -> dict:
    result = subprocess.run(
        [
            OPENCLAW_BIN,
            "agent",
            "--agent", "main",
            "--model", OPENCLAW_MODEL,
            "--message", prompt,
            "--timeout", str(OPENCLAW_TIMEOUT),
            "--json",
        ],
        cwd=PROJECT_DIR,
        text=True,
        capture_output=True,
        timeout=OPENCLAW_TIMEOUT + 30,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(detail[:1000] or f"openclaw exited with {result.returncode}")

    payload = json.loads(result.stdout)
    meta = payload.get("result", {}).get("meta", {})
    content = meta.get("finalAssistantVisibleText") or meta.get("finalAssistantRawText")
    if not content:
        payloads = payload.get("result", {}).get("payloads", [])
        if payloads:
            content = payloads[0].get("text")
    if not content:
        raise RuntimeError("openclaw returned no assistant text")
    return _extract_json(content)


def _fallback_relevant(candidates: list) -> list:
    """Keep the digest alive if the LLM is temporarily unavailable."""
    relevant = []
    for news in candidates[:FALLBACK_LIMIT]:
        body = (news.get("body") or "").strip()
        summary = body[:220].strip()
        if len(body) > 220:
            summary += "..."
        if not summary:
            summary = "Новость прошла тематический keyword-фильтр."
        relevant.append({"news": news, "summary": summary})
    return relevant


def filter_news_for_gosb(gosb: dict, news_items: list) -> list:
    """One LLM call for the whole news list for one GOSB."""
    if not news_items:
        return []

    keywords = json.loads(gosb["keywords"])
    candidates = [
        n for n in news_items
        if any(
            kw.lower() in (n["title"] + " " + (n["body"] or "")).lower()
            for kw in keywords
        )
    ]

    if not candidates:
        print("  ℹ️  После keyword-фильтра: 0 кандидатов")
        return []

    print(f"  📋 Keyword-фильтр: {len(news_items)} → {len(candidates)} кандидатов")

    news_list = "\n".join([
        (
            f"[{i}] {n['title']}\n"
            f"Источник: {n.get('source') or '-'}\n"
            f"Текст: {(n.get('body') or '')[:700]}"
        )
        for i, n in enumerate(candidates)
    ])

    prompt = f"""{gosb['system_prompt']}

Вот список новостей:
{news_list}

Верни только валидный JSON без markdown и пояснений.
Схема ответа строго такая:
{{"relevant": [{{"index": 0, "summary": "почему это важно для банка"}}]}}
Если релевантных новостей нет, верни {{"relevant": []}}."""

    try:
        result = _openclaw_json(prompt)

        relevant = []
        for item in result.get("relevant", []):
            idx = int(item["index"])
            if 0 <= idx < len(candidates):
                relevant.append({
                    "news": candidates[idx],
                    "summary": str(item.get("summary") or "").strip(),
                })

        print(f"  ✅ LLM отобрал: {len(relevant)} релевантных")
        return relevant

    except Exception as e:
        print(f"  ❌ Ошибка LLM/OpenClaw: {e}")
        fallback = _fallback_relevant(candidates)
        print(f"  ⚠️  Fallback: отправим {len(fallback)} новостей после keyword-фильтра")
        return fallback


def run_filter():
    """Run filtering for all active GOSBs."""
    gosbs = get_active_gosbs()
    print(f"🔍 Фильтруем новости для {len(gosbs)} ГОСБов...\n")

    for gosb in gosbs:
        print(f"📍 {gosb['name']}")
        news_items = get_unsent_news(gosb["id"], since_hours=24)
        news_items = [dict(n) for n in news_items]
        print(f"  📰 Новостей за 24ч: {len(news_items)}")

        relevant = filter_news_for_gosb(gosb, news_items)

        for item in relevant:
            mark_as_sent(gosb["id"], item["news"]["id"], item["summary"])

        print()

    print("✅ Фильтрация завершена")
    return True


if __name__ == "__main__":
    run_filter()
