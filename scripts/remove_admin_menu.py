"""
Убирает нижнюю reply-кнопку из темы Админ.
"""

from _bootstrap import bootstrap

bootstrap()

from agent_news.sender import send_message

CHAT_ID = "-1003932865226"
ADMIN_THREAD_ID = None


def main():
    ok = send_message(
        CHAT_ID,
        "Кнопку меню из Админ убрал.",
        thread_id=ADMIN_THREAD_ID,
        reply_markup={"remove_keyboard": True},
    )
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
