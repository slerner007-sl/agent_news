"""
Удаляет нижнюю reply-клавиатуру и оставляет slash-команду /what_can_you_do.
"""

import requests

from _bootstrap import bootstrap

bootstrap()

from agent_news.sender import TG_URL, send_message

GENERAL_CHAT_ID = "-1003932865226"
GENERAL_THREAD_ID = 39


def install_command_menu():
    commands = [{"command": "what_can_you_do", "description": "Что я умею?"}]
    payloads = [
        {"commands": commands},
        {"scope": {"type": "all_group_chats"}, "commands": commands},
        {"scope": {"type": "chat", "chat_id": GENERAL_CHAT_ID}, "commands": commands},
    ]
    ok = True
    for payload in payloads:
        response = requests.post(f"{TG_URL}/setMyCommands", json=payload, timeout=15)
        if not response.ok:
            print(f"Не смог обновить Telegram commands: {response.text}")
            ok = False
    return ok


def remove_reply_keyboard():
    return send_message(
        GENERAL_CHAT_ID,
        "Нижнюю кнопку убрал. Используй /what_can_you_do.",
        thread_id=GENERAL_THREAD_ID,
        reply_markup={"remove_keyboard": True},
    )


def main():
    commands_ok = install_command_menu()
    message_ok = remove_reply_keyboard()
    raise SystemExit(0 if commands_ok and message_ok else 1)


if __name__ == "__main__":
    main()
