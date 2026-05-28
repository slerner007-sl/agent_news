from pathlib import Path
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault("GOSB_TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("INSIGHT_MIN_CONFIDENCE", "0.75")

from agent_news import db

fd, path = tempfile.mkstemp(prefix="insights-test-", suffix=".db")
Path(path).unlink(missing_ok=True)
db.DB_PATH = Path(path)

db.init_db()
with db.get_conn() as conn:
    conn.execute("""
        INSERT INTO gosb_config (id, name, chat_id, thread_id, region, keywords, system_prompt)
        VALUES (1, 'Самарский ГОСБ', '-1001', '6', 'Самара, Самарская область', '["банк", "кредит", "самара"]', 'test')
    """)
    conn.execute("""
        INSERT INTO raw_news (id, url, title, body, source, published_at, collected_at)
        VALUES
            (1, 'https://example.com/1', 'Завод в Самаре запускает новую линию', 'банк кредит промышленность инвестиции Самара', 'test', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
            (2, 'https://example.com/2', 'Городская афиша на выходные', 'концерт спорт погода', 'test', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """)
    conn.execute("""
        INSERT INTO sent_news (gosb_id, news_id, summary, run_id)
        VALUES
            (1, 1, 'Инвестпроект может потребовать банковского сопровождения.', 'run-1'),
            (1, 2, 'Фоновая новость.', 'run-1')
    """)
    conn.execute("""
        INSERT INTO news_classification (
            gosb_id, news_id, mode, model, relevant, category, impact, confidence, summary, reject_reason
        )
        VALUES
            (1, 1, 'live', 'test', 1, 'business', 'high', 0.91, 'summary', ''),
            (1, 2, 'live', 'test', 1, 'other', 'low', 0.7, 'summary', '')
    """)
    conn.execute("""
        INSERT INTO knowledge_documents (kind, thread_id, source_type, file_name, content_text, source_key, content_hash, is_current)
        VALUES ('metrics', '2', 'file', 'metrics.xlsx', 'Наименование метрики | Номер метрики\nДоля рынка КЮЛ | 10000200', 'metrics.xlsx', 'h1', 1)
    """)

from agent_news import insights

report_dir = Path(path).with_suffix("") / "reports"
insights.REPORTS_DIR = report_dir

calls = []


def fake_openclaw_json(prompt):
    calls.append(prompt)
    return {
        "insights": [
            {
                "news_indexes": [0],
                "title": "Проверить потенциал финансирования инвестпроекта",
                "type": "client_signal",
                "priority": "high",
                "confidence": 0.88,
                "why_it_matters": "Инвестпроект промышленного предприятия может создать спрос на финансирование и расчетное обслуживание.",
                "suggested_action": "Проверить, является ли предприятие клиентом ГОСБа, и при наличии закрепления передать РМ сигнал для контакта.",
                "owner_hint": "РМ",
                "evidence": "Новость о запуске новой линии в Самаре.",
                "metric_links": [
                    {
                        "metric_key": "10000200",
                        "metric_name": "Доля рынка КЮЛ",
                        "impact": "context",
                        "confidence": 0.7,
                        "reason": "Может влиять на клиентскую базу юрлиц.",
                    }
                ],
            },
            {
                "news_indexes": [1],
                "title": "Слабый сигнал",
                "type": "no_action",
                "priority": "low",
                "confidence": 0.2,
                "why_it_matters": "нет",
                "suggested_action": "нет",
            },
        ]
    }


insights._openclaw_json = fake_openclaw_json
saved = insights.generate_insights("run-1", batch_size=10)
assert saved == 1
assert len(calls) == 1

with db.get_conn() as conn:
    insight_rows = conn.execute("SELECT title, priority, confidence FROM insights").fetchall()
    news_links = conn.execute("SELECT COUNT(*) AS c FROM insight_news_links").fetchone()["c"]
    metric_links = conn.execute("SELECT COUNT(*) AS c FROM insight_metric_links").fetchone()["c"]

assert len(insight_rows) == 1
assert insight_rows[0]["priority"] == "high"
assert news_links == 1
assert metric_links == 1

report_json = report_dir / "run-1" / "insights.json"
report_summary = report_dir / "run-1" / "summary.md"
report_journal = report_dir / "run-1" / "journal.md"
assert report_json.exists()
assert report_summary.exists()
assert report_journal.exists()
report_data = json.loads(report_json.read_text())
assert report_data["run_id"] == "run-1"
assert len(report_data["insights"]) == 1
assert report_data["scope"]["sent_news_total"] == 2
assert report_data["not_promoted_to_insight"][0]["title"] == "Городская афиша на выходные"

messages = []


def fake_send_message(chat_id, text, thread_id=None, reply_markup=None):
    messages.append((chat_id, text, thread_id, reply_markup))
    return True


insights._send_message = fake_send_message
assert insights.send_insights("run-1") == 0
assert messages == []

insights.INSIGHTS_THREAD_ID = "99"
assert insights.send_insights("run-1") == 1
assert len(messages) == 2
assert messages[0][2] == "99"
assert "Инсайты к действиям" in messages[0][1]
assert "Проверить потенциал" in messages[1][1]
assert "Связанные метрики" in messages[1][1]
assert "Доля рынка КЮЛ" in messages[1][1]
assert messages[1][3]["inline_keyboard"][0][0]["callback_data"] == "iuseful:1"

messages.clear()
insights.INSIGHTS_THREAD_ID = ""
insights.INSIGHTS_THREAD_IDS = "Самарский ГОСБ=136"
assert insights.send_insights("run-1") == 1
assert len(messages) == 2
assert messages[0][2] == "136"
assert "Самарский ГОСБ" in messages[0][1]
assert messages[1][3]["inline_keyboard"][0][2]["callback_data"] == "icomment:1"

Path(path).unlink(missing_ok=True)
shutil.rmtree(report_dir.parent, ignore_errors=True)
print("insights ok")
