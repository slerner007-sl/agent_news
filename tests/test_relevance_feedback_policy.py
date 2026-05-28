from pathlib import Path
import os
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault("GOSB_TELEGRAM_BOT_TOKEN", "test-token")

from agent_news import db

fd, path = tempfile.mkstemp(prefix="relevance-feedback-", suffix=".db")
os.close(fd)
Path(path).unlink(missing_ok=True)
db.DB_PATH = Path(path)

db.init_db()
with db.get_conn() as conn:
    conn.execute("""
        INSERT INTO gosb_config (id, name, chat_id, thread_id, region, keywords, system_prompt)
        VALUES
            (1, 'Самарский ГОСБ', '-1001', '6', 'Самара, Самарская область', '["самара"]', 'test'),
            (2, 'Ульяновский ГОСБ', '-1002', '7', 'Ульяновск, Ульяновская область', '["ульяновск"]', 'test')
    """)
    for idx in range(1, 4):
        conn.execute(
            """
            INSERT INTO raw_news (id, url, title, body, source, published_at, collected_at)
            VALUES (?, ?, ?, ?, 'test', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                idx,
                f"https://example.com/boring-{idx}",
                f"ИТ-компания объявила о партнёрстве по ИИ {idx}",
                "общий бизнес пресс-релиз без клиента, риска, метрики или суммы",
            ),
        )
        conn.execute(
            """
            INSERT INTO news_classification (gosb_id, news_id, mode, model, relevant, category, impact, confidence, summary)
            VALUES (1, ?, 'live', 'test', 1, 'business', 'low', 0.7, 'summary')
            """,
            (idx,),
        )
        conn.execute(
            "INSERT INTO feedback (gosb_id, news_id, user_id, action) VALUES (1, ?, 'u', 'boring')",
            (idx,),
        )

from agent_news import llm_filter_v2

gosb = {
    "id": 2,
    "name": "Ульяновский ГОСБ",
    "region": "Ульяновск, Ульяновская область",
    "keywords": '["ульяновск"]',
}
policy = llm_filter_v2._load_feedback_policy()

generic_news = {
    "id": 101,
    "title": "Ульяновская компания объявила о партнёрстве в сфере ИИ",
    "body": "Общий бизнес пресс-релиз о развитии направления и партнёрстве.",
    "source": "rss:ulpressa",
    "collected_at": "2026-05-28 10:00:00",
}
concrete_news = {
    "id": 102,
    "title": "Ульяновский завод инвестирует 2 млрд рублей в производство",
    "body": "Проект создаёт спрос на оборудование и расчётное сопровождение.",
    "source": "rss:ulpressa",
    "collected_at": "2026-05-28 10:01:00",
}

candidates, skipped = llm_filter_v2.prepare_candidates(
    [generic_news, concrete_news],
    gosb,
    max_items=0,
    feedback_policy=policy,
)

assert len(candidates) == 1
assert candidates[0]["id"] == 102
assert candidates[0]["_feedback_policy"] == "global_boring"
assert candidates[0]["_feedback_score_delta"] < 0
assert candidates[0]["_feedback_concrete"] is True

assert len(skipped) == 1
assert skipped[0]["id"] == 101
assert skipped[0]["_skip_reason"] == "feedback_policy:global_boring:business"
assert skipped[0]["_feedback_concrete"] is False

prompt = llm_filter_v2._build_prompt(gosb, candidates)
assert "Глобальная политика по всем ГОСБ" in prompt
assert "Feedback prior: global_boring" in prompt
assert "общие региональные/пиар/назначенческие новости отклоняй" in prompt

Path(path).unlink(missing_ok=True)
print("relevance feedback policy ok")
