"""
Отправляет в General нижнюю reply-кнопку "Что я умею?".
"""

import requests

from sender import TG_URL, send_message

GENERAL_CHAT_ID = "-1003932865226"
GENERAL_THREAD_ID = 39
BUTTON_TEXT = "Что я умею?"


def build_info_keyboard():
    return {
        "keyboard": [[{"text": BUTTON_TEXT}]],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Выберите действие",
    }


def install_command_menu():
    commands = [
        {"command": "what_can_you_do", "description": "Что я умею?"},
        {"command": "menu", "description": "Вернуть кнопку меню"},
    ]
    payloads = [
        {"commands": commands},
        {"scope": {"type": "all_group_chats"}, "commands": commands},
        {"scope": {"type": "chat", "chat_id": GENERAL_CHAT_ID}, "commands": commands},
    ]
    ok = True
    for payload in payloads:
        response = requests.post(f"{TG_URL}/setMyCommands", json=payload, timeout=15)
        if not response.ok:
            print(f"Не смог обновить Telegram menu commands: {response.text}")
            ok = False
    response = requests.post(
        f"{TG_URL}/setChatMenuButton",
        json={"menu_button": {"type": "commands"}},
        timeout=15,
    )
    if not response.ok:
        print(f"Не смог обновить Telegram menu button: {response.text}")
        ok = False
    return ok


def main():
    commands_ok = install_command_menu()
    message_ok = send_message(
        GENERAL_CHAT_ID,
        "Меню бота обновлено.",
        thread_id=GENERAL_THREAD_ID,
        reply_markup=build_info_keyboard(),
    )
    raise SystemExit(0 if commands_ok and message_ok else 1)


if __name__ == "__main__":
    main()
