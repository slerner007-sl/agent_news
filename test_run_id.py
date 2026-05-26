from pathlib import Path
import os
import tempfile

import db

fd, path = tempfile.mkstemp(prefix="run-id-test-", suffix=".db")
Path(path).unlink()
db.DB_PATH = Path(path)

db.init_db()
with db.get_conn() as conn:
    conn.execute("""
        INSERT INTO gosb_config (id, name, chat_id, thread_id, region, keywords, system_prompt)
        VALUES (1, 'Test GOSB', 'chat', NULL, 'Самара', '["банк"]', 'Отбери банковские новости')
    """)
    conn.execute("""
        INSERT INTO raw_news (id, url, title, body, source, published_at)
        VALUES
            (1, 'https://example.com/bank', 'Банк выдал кредит бизнесу в Самаре', 'банк кредит бизнес мошенничество Самара', 'test', datetime('now')),
            (2, 'https://example.com/old', 'Старая банковская новость', 'банк кредит', 'test', datetime('now')),
            (3, 'https://example.com/noise', 'Спартак выиграл матч', 'спорт футбол матч', 'test', datetime('now'))
    """)
    conn.execute("""
        INSERT INTO sent_news (gosb_id, news_id, summary, run_id)
        VALUES (1, 2, 'old summary', 'old-run')
    """)

from llm_filter_v2 import run_filter_v2

run_filter_v2(
    mode="live",
    since_hours=24,
    limit=10,
    batch_size=5,
    min_confidence=0.5,
    disable_llm=True,
    run_id="current-run",
)

os.environ.setdefault("GOSB_TELEGRAM_BOT_TOKEN", "test-token")
import sender

sent = []

def fake_send_message(chat_id, text, thread_id=None, reply_markup=None):
    sent.append((chat_id, text, thread_id, reply_markup))
    return True

sender.send_message = fake_send_message
sender.send_digest(run_id="current-run")

with db.get_conn() as conn:
    rows = conn.execute("""
        SELECT r.title, s.run_id
        FROM sent_news s
        JOIN raw_news r ON r.id = s.news_id
        ORDER BY s.run_id, r.id
    """).fetchall()

print("rows", [(row["title"], row["run_id"]) for row in rows])
print("sent_messages", len(sent))
print("sent_titles", [msg[1].splitlines()[0] for msg in sent])

assert len(sent) == 2, "expected header + one current-run news"
assert "Банк выдал кредит" in sent[1][1]
assert "Старая банковская" not in "\n".join(msg[1] for msg in sent)

Path(path).unlink(missing_ok=True)
