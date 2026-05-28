from pathlib import Path
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault("GOSB_TELEGRAM_BOT_TOKEN", "test-token")

from agent_news import db

fd, path = tempfile.mkstemp(prefix="reflection-cycles-", suffix=".db")
Path(path).unlink(missing_ok=True)
db.DB_PATH = Path(path)

db.init_db()
with db.get_conn() as conn:
    conn.execute("""
        INSERT INTO gosb_config (id, name, chat_id, thread_id, region, keywords, system_prompt)
        VALUES (1, 'Самарский ГОСБ', '-1001', '6', 'Самара', '["банк"]', 'test')
    """)
    for idx in range(1, 7):
        conn.execute(
            """
            INSERT INTO raw_news (id, url, title, body, source, published_at, collected_at)
            VALUES (?, ?, ?, ?, 'test', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                idx,
                f"https://example.com/{idx}",
                f"Регуляторный риск для клиента {idx}",
                "банк регуляторный риск клиент",
            ),
        )
        conn.execute(
            "INSERT INTO sent_news (gosb_id, news_id, summary, run_id, sent_at) VALUES (1, ?, 'summary', 'run-week', CURRENT_TIMESTAMP)",
            (idx,),
        )
        conn.execute(
            """
            INSERT INTO news_classification (gosb_id, news_id, mode, model, relevant, category, impact, confidence, summary)
            VALUES (1, ?, 'live', 'test', 1, 'risk_signal', 'high', 0.9, 'summary')
            """,
            (idx,),
        )
    conn.execute("""
        INSERT INTO insights (id, gosb_id, run_id, title, insight_type, priority, confidence, why_it_matters, suggested_action, created_at)
        VALUES
            (1, 1, 'run-week', 'Риск клиента 1', 'risk_signal', 'high', 0.91, 'why', 'act', CURRENT_TIMESTAMP),
            (2, 1, 'run-week', 'Риск клиента 2', 'risk_signal', 'high', 0.89, 'why', 'act', CURRENT_TIMESTAMP),
            (3, 1, 'run-week', 'Конкурентный шум', 'competitor_signal', 'medium', 0.82, 'why', 'act', CURRENT_TIMESTAMP)
    """)
    conn.execute("""
        INSERT INTO insight_metric_links (insight_id, metric_key, metric_name, impact, confidence, reason)
        VALUES
            (1, '100', 'Доля рынка КЮЛ', 'risk', 0.7, 'test'),
            (2, '100', 'Доля рынка КЮЛ', 'risk', 0.7, 'test')
    """)
    conn.execute("INSERT INTO feedback (gosb_id, news_id, user_id, action, comment) VALUES (1, 1, 'u', 'boring', '')")
    conn.execute("INSERT INTO feedback (gosb_id, news_id, user_id, action, comment) VALUES (1, 2, 'u', 'boring', '')")
    conn.execute("INSERT INTO feedback (gosb_id, news_id, user_id, action, comment) VALUES (1, 3, 'u', 'boring', '')")
    conn.execute("INSERT INTO insight_feedback (gosb_id, insight_id, user_id, action, comment) VALUES (1, 3, 'u', 'boring', '')")
    conn.execute("INSERT INTO insight_feedback (gosb_id, insight_id, user_id, action, comment) VALUES (1, 3, 'u', 'boring', '')")

from agent_news import reflection_cycles

base = Path(path).with_suffix("")
reflection_cycles.REPORTS_DIR = base / "reports"
reflection_cycles.RUNTIME_MEMORY_PATH = base / "memory" / "runtime_memory.md"

weekly = reflection_cycles.write_cycle_report("weekly", days=7, update_memory=False)
weekly_json = Path(weekly["json_path"])
weekly_data = json.loads(weekly_json.read_text())
assert weekly_data["cycle"] == "weekly"
assert weekly_data["scope"]["sent_news"] == 6
assert weekly_data["meta_insights"]
assert weekly_data["feedback_adjustments"]
assert Path(weekly["summary_path"]).exists()
assert Path(weekly["journal_path"]).exists()

strategic = reflection_cycles.write_cycle_report("strategic", days=30, update_memory=True)
strategic_data = json.loads(Path(strategic["json_path"]).read_text())
assert strategic_data["strategic_patterns"]
assert reflection_cycles.RUNTIME_MEMORY_PATH.exists()

Path(path).unlink(missing_ok=True)
shutil.rmtree(base, ignore_errors=True)
print("reflection cycles ok")
