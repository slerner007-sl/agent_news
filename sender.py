"""
sender.py — отправка отфильтрованных новостей в Telegram
"""

import requests
from datetime import datetime
from db import get_conn, get_active_gosbs

BOT_TOKEN = "8655293057:AAEeSNZLenovxgQq-XLGewz7wBNAcBAJhRo"
TG_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message(chat_id: str, text: str, thread_id: str = None) -> bool:
    try:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if thread_id:
            payload["message_thread_id"] = int(thread_id)
        response = requests.post(f"{TG_URL}/sendMessage", json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
        return False


def get_unsent_for_today(gosb_id: int) -> list:
    with get_conn() as conn:
        return conn.execute("""
            SELECT r.title, r.url, s.summary, s.sent_at
            FROM sent_news s
            JOIN raw_news r ON r.id = s.news_id
            WHERE s.gosb_id = ?
              AND date(s.sent_at) = date('now')
            ORDER BY s.sent_at DESC
        """, (gosb_id,)).fetchall()


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

        # Шапка отдельным сообщением
        send_message(
            gosb["chat_id"],
            f"📰 <b>Дайджест новостей — {gosb['name']}</b>\n<i>{date_str} | {len(news_items)} новостей</i>",
            gosb["thread_id"]
        )

        # Каждая новость отдельным сообщением
        for i, item in enumerate(news_items, 1):
            text = (
                f"<b>{i}. {item['title']}</b>\n"
                f"{item['summary']}\n"
                f"<a href='{item['url']}'>Читать →</a>"
            )
            send_message(gosb["chat_id"], text, gosb["thread_id"])

        print(f"  ✅ Отправлено {len(news_items)} новостей в топик {gosb['thread_id']}")

    print("\n✅ Готово")


if __name__ == "__main__":
    send_digest()
