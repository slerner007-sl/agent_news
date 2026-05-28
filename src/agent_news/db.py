"""
db.py — инициализация БД и все операции с данными
"""

import sqlite3
import json
from pathlib import Path

DB_PATH = Path("data/news_bot.db")


def get_conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS gosb_config (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            chat_id         TEXT NOT NULL,
            thread_id       TEXT,
            region          TEXT NOT NULL,
            keywords        TEXT NOT NULL,
            system_prompt   TEXT NOT NULL,
            active          INTEGER DEFAULT 1,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS raw_news (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            url             TEXT UNIQUE NOT NULL,
            title           TEXT NOT NULL,
            body            TEXT,
            source          TEXT,
            published_at    TEXT,
            collected_at    TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS sent_news (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            gosb_id         INTEGER NOT NULL REFERENCES gosb_config(id),
            news_id         INTEGER NOT NULL REFERENCES raw_news(id),
            summary         TEXT,
            run_id          TEXT,
            sent_at         TEXT DEFAULT (datetime('now')),
            UNIQUE(gosb_id, news_id)
        );


        CREATE TABLE IF NOT EXISTS feedback (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            gosb_id         INTEGER REFERENCES gosb_config(id),
            news_id         INTEGER NOT NULL REFERENCES raw_news(id),
            user_id         TEXT,
            username        TEXT,
            action          TEXT NOT NULL,
            comment         TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_feedback_news  ON feedback(news_id);
        CREATE INDEX IF NOT EXISTS idx_feedback_user  ON feedback(user_id);
        CREATE INDEX IF NOT EXISTS idx_feedback_action ON feedback(action);

        CREATE TABLE IF NOT EXISTS news_classification (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            gosb_id         INTEGER NOT NULL REFERENCES gosb_config(id),
            news_id         INTEGER NOT NULL REFERENCES raw_news(id),
            mode            TEXT NOT NULL,
            model           TEXT,
            relevant        INTEGER NOT NULL DEFAULT 0,
            category        TEXT,
            impact          TEXT,
            confidence      REAL,
            summary         TEXT,
            reject_reason   TEXT,
            rule_score      INTEGER DEFAULT 0,
            rule_hits       TEXT,
            llm_raw_json    TEXT,
            created_at      TEXT DEFAULT (datetime('now')),
            UNIQUE(gosb_id, news_id, mode)
        );

        CREATE INDEX IF NOT EXISTS idx_news_classification_news
            ON news_classification(news_id);
        CREATE INDEX IF NOT EXISTS idx_news_classification_gosb_mode
            ON news_classification(gosb_id, mode);
        CREATE INDEX IF NOT EXISTS idx_news_classification_relevant
            ON news_classification(relevant);

        CREATE INDEX IF NOT EXISTS idx_raw_news_collected ON raw_news(collected_at);
        CREATE INDEX IF NOT EXISTS idx_sent_news_gosb    ON sent_news(gosb_id);

        CREATE TABLE IF NOT EXISTS knowledge_documents (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            kind            TEXT NOT NULL,
            thread_id       TEXT,
            conversation_id TEXT,
            sender_id       TEXT,
            username        TEXT,
            source_type     TEXT NOT NULL DEFAULT 'text',
            file_name       TEXT,
            mime_type       TEXT,
            content_text    TEXT,
            raw_json        TEXT,
            source_key      TEXT,
            content_hash    TEXT,
            revision        INTEGER NOT NULL DEFAULT 1,
            is_current      INTEGER NOT NULL DEFAULT 1,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_knowledge_documents_kind
            ON knowledge_documents(kind);
        CREATE INDEX IF NOT EXISTS idx_knowledge_documents_created
            ON knowledge_documents(created_at);

        CREATE TABLE IF NOT EXISTS news_metric_links (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            gosb_id         INTEGER NOT NULL REFERENCES gosb_config(id),
            news_id         INTEGER NOT NULL REFERENCES raw_news(id),
            mode            TEXT NOT NULL,
            metric_key      TEXT NOT NULL,
            metric_name     TEXT,
            impact          TEXT,
            confidence      REAL,
            reason          TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_news_metric_links_news
            ON news_metric_links(news_id);
        CREATE INDEX IF NOT EXISTS idx_news_metric_links_gosb
            ON news_metric_links(gosb_id, mode);

        CREATE TABLE IF NOT EXISTS insights (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            gosb_id         INTEGER NOT NULL REFERENCES gosb_config(id),
            run_id          TEXT,
            title           TEXT NOT NULL,
            insight_type    TEXT NOT NULL,
            priority        TEXT NOT NULL,
            confidence      REAL NOT NULL DEFAULT 0,
            why_it_matters  TEXT,
            suggested_action TEXT,
            owner_hint      TEXT,
            evidence        TEXT,
            source_json     TEXT,
            llm_raw_json    TEXT,
            status          TEXT NOT NULL DEFAULT 'proposed',
            created_at      TEXT DEFAULT (datetime('now')),
            UNIQUE(gosb_id, run_id, title, suggested_action)
        );

        CREATE TABLE IF NOT EXISTS insight_news_links (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            insight_id      INTEGER NOT NULL REFERENCES insights(id),
            news_id         INTEGER NOT NULL REFERENCES raw_news(id),
            created_at      TEXT DEFAULT (datetime('now')),
            UNIQUE(insight_id, news_id)
        );

        CREATE TABLE IF NOT EXISTS insight_metric_links (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            insight_id      INTEGER NOT NULL REFERENCES insights(id),
            metric_key      TEXT NOT NULL,
            metric_name     TEXT,
            impact          TEXT,
            confidence      REAL,
            reason          TEXT,
            created_at      TEXT DEFAULT (datetime('now')),
            UNIQUE(insight_id, metric_key)
        );

        CREATE INDEX IF NOT EXISTS idx_insights_run
            ON insights(run_id);
        CREATE INDEX IF NOT EXISTS idx_insights_gosb_status
            ON insights(gosb_id, status);
        CREATE INDEX IF NOT EXISTS idx_insight_news_links_news
            ON insight_news_links(news_id);

        CREATE TABLE IF NOT EXISTS insight_feedback (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            gosb_id         INTEGER REFERENCES gosb_config(id),
            insight_id      INTEGER NOT NULL REFERENCES insights(id),
            user_id         TEXT,
            username        TEXT,
            action          TEXT NOT NULL,
            comment         TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_insight_feedback_insight
            ON insight_feedback(insight_id);
        CREATE INDEX IF NOT EXISTS idx_insight_feedback_user
            ON insight_feedback(user_id);
        CREATE INDEX IF NOT EXISTS idx_insight_feedback_action
            ON insight_feedback(action);
        """)

        columns = {row["name"] for row in conn.execute("PRAGMA table_info(gosb_config)")}
        if "thread_id" not in columns:
            conn.execute("ALTER TABLE gosb_config ADD COLUMN thread_id TEXT")

        sent_columns = {row["name"] for row in conn.execute("PRAGMA table_info(sent_news)")}
        if "run_id" not in sent_columns:
            conn.execute("ALTER TABLE sent_news ADD COLUMN run_id TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sent_news_run ON sent_news(run_id)")

        feedback_columns = {row["name"] for row in conn.execute("PRAGMA table_info(feedback)")}
        feedback_migrations = {
            "gosb_id": "ALTER TABLE feedback ADD COLUMN gosb_id INTEGER",
            "news_id": "ALTER TABLE feedback ADD COLUMN news_id INTEGER",
            "user_id": "ALTER TABLE feedback ADD COLUMN user_id TEXT",
            "username": "ALTER TABLE feedback ADD COLUMN username TEXT",
            "action": "ALTER TABLE feedback ADD COLUMN action TEXT",
            "comment": "ALTER TABLE feedback ADD COLUMN comment TEXT",
            "created_at": "ALTER TABLE feedback ADD COLUMN created_at TEXT",
        }
        for column, sql in feedback_migrations.items():
            if column not in feedback_columns:
                conn.execute(sql)


        knowledge_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(knowledge_documents)")
        }
        knowledge_migrations = {
            "source_key": "ALTER TABLE knowledge_documents ADD COLUMN source_key TEXT",
            "content_hash": "ALTER TABLE knowledge_documents ADD COLUMN content_hash TEXT",
            "revision": "ALTER TABLE knowledge_documents ADD COLUMN revision INTEGER NOT NULL DEFAULT 1",
            "is_current": "ALTER TABLE knowledge_documents ADD COLUMN is_current INTEGER NOT NULL DEFAULT 1",
        }
        for column, sql in knowledge_migrations.items():
            if column not in knowledge_columns:
                conn.execute(sql)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_documents_source
                ON knowledge_documents(kind, source_key, is_current)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_documents_hash
                ON knowledge_documents(kind, source_key, content_hash)
        """)

        classification_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(news_classification)")
        }
        classification_migrations = {
            "gosb_id": "ALTER TABLE news_classification ADD COLUMN gosb_id INTEGER",
            "news_id": "ALTER TABLE news_classification ADD COLUMN news_id INTEGER",
            "mode": "ALTER TABLE news_classification ADD COLUMN mode TEXT",
            "model": "ALTER TABLE news_classification ADD COLUMN model TEXT",
            "relevant": "ALTER TABLE news_classification ADD COLUMN relevant INTEGER DEFAULT 0",
            "category": "ALTER TABLE news_classification ADD COLUMN category TEXT",
            "impact": "ALTER TABLE news_classification ADD COLUMN impact TEXT",
            "confidence": "ALTER TABLE news_classification ADD COLUMN confidence REAL",
            "summary": "ALTER TABLE news_classification ADD COLUMN summary TEXT",
            "reject_reason": "ALTER TABLE news_classification ADD COLUMN reject_reason TEXT",
            "rule_score": "ALTER TABLE news_classification ADD COLUMN rule_score INTEGER DEFAULT 0",
            "rule_hits": "ALTER TABLE news_classification ADD COLUMN rule_hits TEXT",
            "llm_raw_json": "ALTER TABLE news_classification ADD COLUMN llm_raw_json TEXT",
            "created_at": "ALTER TABLE news_classification ADD COLUMN created_at TEXT",
        }
        for column, sql in classification_migrations.items():
            if column not in classification_columns:
                conn.execute(sql)
    print("✅ БД инициализирована")


def get_active_gosbs():
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM gosb_config WHERE active = 1"
        ).fetchall()


def get_unsent_news(gosb_id: int, since_hours: int = 24):
    with get_conn() as conn:
        return conn.execute("""
            SELECT r.*
            FROM raw_news r
            WHERE r.collected_at >= datetime('now', ? || ' hours')
              AND r.id NOT IN (
                  SELECT news_id FROM sent_news WHERE gosb_id = ?
              )
            ORDER BY r.published_at DESC
        """, (f"-{since_hours}", gosb_id)).fetchall()


def save_raw_news(items: list) -> int:
    saved = 0
    with get_conn() as conn:
        for item in items:
            try:
                conn.execute("""
                    INSERT INTO raw_news (url, title, body, source, published_at)
                    VALUES (:url, :title, :body, :source, :published_at)
                """, item)
                saved += 1
            except sqlite3.IntegrityError:
                pass
    return saved


def mark_as_sent(gosb_id: int, news_id: int, summary: str, run_id: str | None = None):
    with get_conn() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO sent_news (gosb_id, news_id, summary, run_id)
            VALUES (?, ?, ?, ?)
        """, (gosb_id, news_id, summary, run_id))


def save_news_classification(
    gosb_id: int,
    news_id: int,
    mode: str,
    model: str,
    relevant: bool,
    category: str,
    impact: str,
    confidence: float,
    summary: str,
    reject_reason: str,
    rule_score: int = 0,
    rule_hits: list | None = None,
    llm_raw_json: dict | list | str | None = None,
):
    if isinstance(llm_raw_json, (dict, list)):
        llm_raw_json = json.dumps(llm_raw_json, ensure_ascii=False)
    if isinstance(rule_hits, list):
        rule_hits = json.dumps(rule_hits, ensure_ascii=False)

    with get_conn() as conn:
        conn.execute("""
            INSERT INTO news_classification (
                gosb_id, news_id, mode, model, relevant, category, impact,
                confidence, summary, reject_reason, rule_score, rule_hits, llm_raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(gosb_id, news_id, mode) DO UPDATE SET
                model = excluded.model,
                relevant = excluded.relevant,
                category = excluded.category,
                impact = excluded.impact,
                confidence = excluded.confidence,
                summary = excluded.summary,
                reject_reason = excluded.reject_reason,
                rule_score = excluded.rule_score,
                rule_hits = excluded.rule_hits,
                llm_raw_json = excluded.llm_raw_json,
                created_at = datetime('now')
        """, (
            gosb_id,
            news_id,
            mode,
            model,
            int(bool(relevant)),
            category,
            impact,
            confidence,
            summary,
            reject_reason,
            rule_score,
            rule_hits,
            llm_raw_json,
        ))


def get_knowledge_context(kind: str | None = None, limit: int = 8, max_chars: int = 3500) -> str:
    query = """
        SELECT kind, content_text, file_name, created_at
        FROM knowledge_documents
        WHERE COALESCE(content_text, '') <> ''
          AND COALESCE(is_current, 1) = 1
    """
    params: list = []
    if kind:
        query += " AND kind = ?"
        params.append(kind)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()

    lines = []
    total = 0
    for row in rows:
        content = " ".join((row["content_text"] or "").split())
        if not content:
            continue
        name = row["file_name"] or row["kind"]
        line = f"- [{row['kind']}] {name}: {content[:700]}"
        if total + len(line) > max_chars:
            break
        lines.append(line)
        total += len(line)
    return "\n".join(lines) if lines else "Пока нет загруженного контекста."


def save_news_metric_links(
    gosb_id: int,
    news_id: int,
    mode: str,
    metric_links: list | None,
):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM news_metric_links WHERE gosb_id = ? AND news_id = ? AND mode = ?",
            (gosb_id, news_id, mode),
        )
        for link in metric_links or []:
            metric_key = str(link.get("metric_key") or link.get("metric_name") or "").strip()
            if not metric_key:
                continue
            conn.execute("""
                INSERT INTO news_metric_links (
                    gosb_id, news_id, mode, metric_key, metric_name,
                    impact, confidence, reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                gosb_id,
                news_id,
                mode,
                metric_key[:160],
                str(link.get("metric_name") or "").strip()[:220] or None,
                str(link.get("impact") or "context").strip()[:40],
                float(link.get("confidence") or 0),
                str(link.get("reason") or "").strip()[:500],
            ))


def save_insight(
    gosb_id: int,
    run_id: str | None,
    title: str,
    insight_type: str,
    priority: str,
    confidence: float,
    why_it_matters: str,
    suggested_action: str,
    owner_hint: str = "",
    evidence: str = "",
    news_ids: list[int] | None = None,
    metric_links: list | None = None,
    source: dict | list | str | None = None,
    llm_raw_json: dict | list | str | None = None,
) -> int | None:
    if isinstance(source, (dict, list)):
        source = json.dumps(source, ensure_ascii=False)
    if isinstance(llm_raw_json, (dict, list)):
        llm_raw_json = json.dumps(llm_raw_json, ensure_ascii=False)

    title = str(title or "").strip()
    insight_type = str(insight_type or "").strip()
    priority = str(priority or "").strip()
    why_it_matters = str(why_it_matters or "").strip()
    suggested_action = str(suggested_action or "").strip()
    owner_hint = str(owner_hint or "").strip()
    evidence = str(evidence or "").strip()

    with get_conn() as conn:
        cur = conn.execute("""
            INSERT OR IGNORE INTO insights (
                gosb_id, run_id, title, insight_type, priority, confidence,
                why_it_matters, suggested_action, owner_hint, evidence,
                source_json, llm_raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            gosb_id,
            run_id,
            title[:220],
            insight_type[:60],
            priority[:20],
            float(confidence or 0),
            why_it_matters[:900],
            suggested_action[:900],
            owner_hint[:160],
            evidence[:700],
            source,
            llm_raw_json,
        ))
        insight_id = cur.lastrowid
        if not insight_id:
            row = conn.execute("""
                SELECT id FROM insights
                WHERE gosb_id = ? AND COALESCE(run_id, '') = COALESCE(?, '')
                  AND title = ? AND suggested_action = ?
            """, (gosb_id, run_id, title[:220], suggested_action[:900])).fetchone()
            insight_id = row["id"] if row else None
        if not insight_id:
            return None

        for news_id in news_ids or []:
            conn.execute(
                "INSERT OR IGNORE INTO insight_news_links (insight_id, news_id) VALUES (?, ?)",
                (insight_id, int(news_id)),
            )

        for link in metric_links or []:
            metric_key = str(link.get("metric_key") or link.get("metric_name") or "").strip()
            if not metric_key:
                continue
            conn.execute("""
                INSERT OR IGNORE INTO insight_metric_links (
                    insight_id, metric_key, metric_name, impact, confidence, reason
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                insight_id,
                metric_key[:160],
                str(link.get("metric_name") or "").strip()[:220] or None,
                str(link.get("impact") or "context").strip()[:40],
                float(link.get("confidence") or 0),
                str(link.get("reason") or "").strip()[:500],
            ))
        return insight_id


def add_gosb(name, chat_id, region, keywords, system_prompt, thread_id=None):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO gosb_config (name, chat_id, thread_id, region, keywords, system_prompt)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, chat_id, thread_id, region, json.dumps(keywords, ensure_ascii=False), system_prompt))
    print(f"✅ ГОСБ '{name}' добавлен")


SAMARA_PROMPT = """Ты — аналитик новостей для Самарского отделения Сбербанка.
Тебе дан список новостей. Отбери только те, которые РЕЛЕВАНТНЫ для регионального банка:
- события банковского сектора в Самарской области
- изменения ЦБ РФ (ставки, регулирование)
- крупный бизнес, застройщики, промышленность Самары
- мошенничество, киберугрозы, финансовые преступления в регионе

НЕ включай: спорт, развлечения, погоду, федеральную политику без банковской связи.

Ответь ТОЛЬКО JSON (без markdown):
{"relevant": [{"index": 0, "summary": "Контекст и значимость для банка, не повторяй заголовок"}]}"""

SAMARA_KEYWORDS = [
    "сбербанк", "банк", "кредит", "ипотека", "вклад",
    "самара", "самарская", "тольятти", "цб рф", "ключевая ставка",
    "мошенник", "финанс", "застройщик"
]


if __name__ == "__main__":
    init_db()

    with get_conn() as conn:
        exists = conn.execute(
            "SELECT id FROM gosb_config WHERE name = 'Самарский ГОСБ'"
        ).fetchone()

    if not exists:
        add_gosb(
            name="Самарский ГОСБ",
            chat_id="-1003932865226",
            region="Самара, Самарская область, Тольятти",
            keywords=SAMARA_KEYWORDS,
            system_prompt=SAMARA_PROMPT,
        )
    else:
        print("ℹ️  Самарский ГОСБ уже есть в БД")
