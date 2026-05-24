"""
sender.py — отправка с кнопками обратной связи
"""

import requests
from html import escape
from datetime import datetime
from db import get_conn, get_active_gosbs

BOT_TOKEN = "8655293057:AAEeSNZLenovxgQq-XLGewz7wBNAcBAJhRo"
TG_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message(chat_id, text, thread_id=None, reply_markup=None):
    try:
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
        response = requests.post(f"{TG_URL}/sendMessage", json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
        return False


def get_unsent_for_today(gosb_id):
    with get_conn() as conn:
        return conn.execute("""
            SELECT r.id, r.title, r.url, s.summary
            FROM sent_news s
            JOIN raw_news r ON r.id = s.news_id
            WHERE s.gosb_id = ?
              AND date(s.sent_at) = date('now')
            ORDER BY s.sent_at DESC
        """, (gosb_id,)).fetchall()


def build_keyboard(news_id):
    return {
        "inline_keyboard": [[
            {"text": "✅ Полезно",      "callback_data": f"useful:{news_id}"},
            {"text": "👎 Неинтересно", "callback_data": f"boring:{news_id}"},
            {"text": "💬 Комментарий", "callback_data": f"comment:{news_id}"},
        ]]
    }


def send_digest():
    gosbs = get_active_gosbs()
    print(f"📤 Отправляем дайджест для {len(gosbs)} ГОСБов...\n")

    for gosb in gosbs:
        print(f"📍 {gosb['name']}")
        news_items = get_unsent_for_today(gosb["id"])
        news_items = [dict(n) for n in news_items]

        if not news_items:
            print(f"  ℹ️  Нет новостей для отправки")
            continue

        date_str = datetime.now().strftime("%d.%m.%Y")
        gosb_name = escape(str(gosb["name"]))
        send_message(
            gosb["chat_id"],
            f"📰 <b>Дайджест — {gosb_name}</b>\n<i>{date_str} | {len(news_items)} новостей</i>",
            gosb["thread_id"]
        )

        for i, item in enumerate(news_items, 1):
            title = escape(str(item["title"]))
            summary = escape(str(item["summary"] or ""))
            url = escape(str(item["url"]), quote=True)
            text = (
                f"<b>{i}. {title}</b>\n"
                f"{summary}\n"
                f"<a href='{url}'>Читать →</a>"
            )
            send_message(
                gosb["chat_id"],
                text,
                gosb["thread_id"],
                reply_markup=build_keyboard(item["id"])
            )

        print(f"  ✅ Отправлено {len(news_items)} новостей")

    print("\n✅ Готово")


if __name__ == "__main__":
    send_digest()
