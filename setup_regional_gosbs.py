"""
Create/update regional GOSB configs for new territories.

New configs are inserted inactive until Telegram topic thread_id values are known.
"""

import json

from db import get_conn, init_db

CHAT_ID = "-1003932865226"

COMMON_PROMPT = """Ты — аналитик новостного дайджеста для {name}.
Отбирай новости, которые полезны региональному банку: банки, Сбер и конкуренты, ЦБ, ставки, кредиты, ипотека, вклады, платежи, мошенничество, банкротства, крупный бизнес, промышленность, инвестиции, строительство, МСП, решения губернатора и ведомств, влияющие на экономику региона или клиентов банка.
Не включай спорт, афишу, погоду, бытовые происшествия и федеральную политику без явной связи с регионом, бизнесом, банками или рисками."""

GOSBS = [
    {
        "name": "Ленинградский ГОСБ",
        "region": "Ленинградская область, Гатчина, Выборг, Сосновый Бор, Кириши, Тосно, Всеволожск, Тихвин, Кудрово, Мурино",
        "keywords": [
            "ленинградская область", "ленобласть", "гатчина", "выборг", "сосновый бор",
            "кириши", "тосно", "всеволожск", "тихвин", "кудрово", "мурино", "дрозденко", "47news", "online47", "lenobl", "lenobladminka",
        ],
    },
    {
        "name": "Калининградский ГОСБ",
        "region": "Калининградская область, Калининград, Балтийск, Советск, Черняховск, Гусев, Светлогорск, Зеленоградск",
        "keywords": [
            "калининградская область", "калининград", "балтийск", "советск",
            "черняховск", "гусев", "светлогорск", "зеленоградск", "беспрозванных", "rugrad", "клопс", "newkaliningrad", "gov39", "government_kgd", "kaliningradru",
        ],
    },
    {
        "name": "Ульяновский ГОСБ",
        "region": "Ульяновская область, Ульяновск, Димитровград, Новоульяновск, Инза, Барыш",
        "keywords": [
            "ульяновская область", "ульяновск", "димитровград", "новоульяновск",
            "инза", "барыш", "русских", "ulpressa", "ulpravda", "ulgovru",
        ],
    },
]


def main() -> None:
    init_db()
    with get_conn() as conn:
        for gosb in GOSBS:
            keywords = json.dumps(gosb["keywords"], ensure_ascii=False)
            prompt = COMMON_PROMPT.format(name=gosb["name"])
            existing = conn.execute(
                "SELECT id, active, thread_id FROM gosb_config WHERE name = ?",
                (gosb["name"],),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE gosb_config
                    SET chat_id = ?, region = ?, keywords = ?, system_prompt = ?
                    WHERE id = ?
                    """,
                    (CHAT_ID, gosb["region"], keywords, prompt, existing["id"]),
                )
                print(
                    f"обновлен: {gosb['name']} "
                    f"active={existing['active']} thread_id={existing['thread_id']}"
                )
            else:
                conn.execute(
                    """
                    INSERT INTO gosb_config (
                        name, chat_id, thread_id, region, keywords, system_prompt, active
                    ) VALUES (?, ?, ?, ?, ?, ?, 0)
                    """,
                    (gosb["name"], CHAT_ID, None, gosb["region"], keywords, prompt),
                )
                print(f"добавлен inactive: {gosb['name']}")


if __name__ == "__main__":
    main()
