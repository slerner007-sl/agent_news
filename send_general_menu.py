"""
Отправляет в General нижнюю reply-кнопку "Что я умею?".
"""

from sender import send_message

GENERAL_CHAT_ID = "-1003932865226"
GENERAL_THREAD_ID = 39
BUTTON_TEXT = "Что я умею?"


def build_info_keyboard():
    return {
        "keyboard": [[{"text": BUTTON_TEXT}]],
        "resize_keyboard": True,
        "is_persistent": True,
        "input_field_placeholder": "Выберите действие",
    }


def main():
    ok = send_message(
        GENERAL_CHAT_ID,
        "Меню бота обновлено.",
        thread_id=GENERAL_THREAD_ID,
        reply_markup=build_info_keyboard(),
    )
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
