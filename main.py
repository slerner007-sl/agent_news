"""
main.py — точка входа, запускает полный цикл
parser → llm_filter → sender
"""

import os
import sys
from datetime import datetime
from uuid import uuid4
from parser import collect_all_news
from llm_filter import run_filter
from sender import send_digest


def run_configured_filter(run_id: str | None = None) -> bool:
    """Run legacy or V2 filter. Returns True when Telegram sending is safe."""
    version = os.getenv("NEWS_FILTER_VERSION", "legacy").strip().lower()
    if version == "v2":
        from llm_filter_v2 import run_filter_v2

        mode = os.getenv("NEWS_FILTER_MODE", "shadow").strip().lower()
        run_filter_v2(mode=mode, run_id=run_id)
        return mode == "live"

    run_filter(run_id=run_id)
    return True


def main():
    start = datetime.now()
    run_id = f"digest-{start.strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}"
    print(f"\n{'='*50}")
    print(f"🚀 Запуск дайджеста: {start.strftime('%d.%m.%Y %H:%M')}")
    print(f"🧾 Run ID: {run_id}")
    print(f"{'='*50}\n")

    # 1. Собираем новости
    print("📡 ШАГ 1: Сбор новостей\n")
    saved = collect_all_news()

    if saved == 0:
        print("ℹ️  Новых новостей нет, продолжаем с тем что есть в БД\n")

    # 2. Фильтруем через LLM
    print("\n🤖 ШАГ 2: Фильтрация через LLM\n")
    should_send = run_configured_filter(run_id=run_id)

    # 3. Отправляем в Telegram
    if should_send:
        print("\n📤 ШАГ 3: Отправка в Telegram\n")
        send_digest(run_id=run_id)
    else:
        print("\n🧪 ШАГ 3: shadow/dry-run режим — отправка в Telegram пропущена\n")

    end = datetime.now()
    elapsed = (end - start).seconds
    print(f"\n{'='*50}")
    print(f"✅ Готово за {elapsed} сек.")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
