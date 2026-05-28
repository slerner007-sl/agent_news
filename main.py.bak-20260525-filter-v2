"""
main.py — точка входа, запускает полный цикл
parser → llm_filter → sender
"""

import sys
from datetime import datetime
from parser import collect_all_news
from llm_filter import run_filter
from sender import send_digest


def main():
    start = datetime.now()
    print(f"\n{'='*50}")
    print(f"🚀 Запуск дайджеста: {start.strftime('%d.%m.%Y %H:%M')}")
    print(f"{'='*50}\n")

    # 1. Собираем новости
    print("📡 ШАГ 1: Сбор новостей\n")
    saved = collect_all_news()

    if saved == 0:
        print("ℹ️  Новых новостей нет, продолжаем с тем что есть в БД\n")

    # 2. Фильтруем через LLM
    print("\n🤖 ШАГ 2: Фильтрация через LLM\n")
    run_filter()

    # 3. Отправляем в Telegram
    print("\n📤 ШАГ 3: Отправка в Telegram\n")
    send_digest()

    end = datetime.now()
    elapsed = (end - start).seconds
    print(f"\n{'='*50}")
    print(f"✅ Готово за {elapsed} сек.")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
