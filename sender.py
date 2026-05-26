"""
sender.py — отправка с кнопками обратной связи
"""

import os
import time

import requests
from html import escape
from datetime import datetime
from db import get_conn, get_active_gosbs

BOT_TOKEN = os.getenv("GOSB_TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Telegram bot token is not set. Set GOSB_TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN.")
TG_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
SEND_DELAY_SECONDS = float(os.getenv("TG_SEND_DELAY_SECONDS", "1.2"))
SEND_MAX_RETRIES = int(os.getenv("TG_SEND_MAX_RETRIES", "3"))


def _retry_after(response) -> int:
    try:
        payload = response.json()
    except ValueError:
        return 3
    return int(payload.get("parameters", {}).get("retry_after") or 3)


def send_message(chat_id, text, thread_id=None, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if thread_id:
        payload["message_thread_id"] = int(thread_id)
    if reply_markup:
        payload["reply_markup"] = reply_markup

    for attempt in range(1, SEND_MAX_RETRIES + 1):
        try:
            response = requests.post(f"{TG_URL}/sendMessage", json=payload, timeout=15)
            if response.status_code == 429:
                wait_seconds = _retry_after(response) + 1
                print(f"  ⏳ Telegram rate limit: жду {wait_seconds} сек. (попытка {attempt})")
                time.sleep(wait_seconds)
                continue
            response.raise_for_status()
            time.sleep(SEND_DELAY_SECONDS)
            return True
        except Exception as e:
            if attempt >= SEND_MAX_RETRIES:
                print(f"❌ Ошибка отправки: {e}")
                return False
            time.sleep(2 * attempt)

    return False


def get_sent_for_today(gosb_id):
    with get_conn() as conn:
        return conn.execute("""
            SELECT r.id, r.title, r.url, s.summary
            FROM sent_news s
            JOIN raw_news r ON r.id = s.news_id
            WHERE s.gosb_id = ?
              AND date(s.sent_at) = date('now')
            ORDER BY s.sent_at DESC
        """, (gosb_id,)).fetchall()


def get_sent_for_run(gosb_id, run_id):
    with get_conn() as conn:
        return conn.execute("""
            SELECT r.id, r.title, r.url, s.summary
            FROM sent_news s
            JOIN raw_news r ON r.id = s.news_id
            WHERE s.gosb_id = ?
              AND s.run_id = ?
            ORDER BY s.sent_at DESC
        """, (gosb_id, run_id)).fetchall()


def build_keyboard(news_id):
    return {
        "inline_keyboard": [[
            {"text": "✅ 0", "callback_data": f"useful:{news_id}"},
            {"text": "👎 0", "callback_data": f"boring:{news_id}"},
            {"text": "💬 0", "callback_data": f"comment:{news_id}"},
        ]]
    }


def truncate_text(value, max_length):
    text = str(value or "")
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def send_digest(run_id=None):
    gosbs = get_active_gosbs()
    print(f"📤 Отправляем дайджест для {len(gosbs)} ГОСБов...\n")

    for gosb in gosbs:
        print(f"📍 {gosb['name']}")
        if run_id:
            news_items = get_sent_for_run(gosb["id"], run_id)
        else:
            news_items = get_sent_for_today(gosb["id"])
        news_items = [dict(n) for n in news_items]

        if not news_items:
            print(f"  ℹ️  Нет новостей для отправки")
            continue

        date_str = datetime.now().strftime("%d.%m.%Y")
        gosb_name = escape(str(gosb["name"]))
        thread_id = dict(gosb).get("thread_id")
        sent_count = 0
        failed_count = 0
        if not send_message(
            gosb["chat_id"],
            f"📰 <b>Дайджест — {gosb_name}</b>\n<i>{date_str} | {len(news_items)} новостей</i>",
            thread_id
        ):
            failed_count += 1

        for i, item in enumerate(news_items, 1):
            title = escape(truncate_text(item["title"], 500))
            summary = escape(truncate_text(item["summary"] or "", 2600))
            url = escape(str(item["url"]), quote=True)
            text = (
                f"<b>{i}. {title}</b>\n"
                f"{summary}\n"
                f"<a href='{url}'>Читать →</a>"
            )
            if send_message(
                gosb["chat_id"],
                text,
                thread_id,
                reply_markup=build_keyboard(item["id"])
            ):
                sent_count += 1
            else:
                failed_count += 1

        print(f"  ✅ Успешно отправлено {sent_count}/{len(news_items)} новостей")
        if failed_count:
            print(f"  ⚠️  Ошибок отправки: {failed_count}")

    print("\n✅ Готово")


if __name__ == "__main__":
    send_digest()
