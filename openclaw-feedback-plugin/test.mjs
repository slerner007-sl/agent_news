import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { DatabaseSync } from "node:sqlite";
import {
  consumePendingComment,
  parseFeedbackCallback,
  rememberPendingComment,
  saveFeedback,
} from "./feedback-store.js";
import { handleFeedbackCallback, handlePendingComment } from "./plugin-core.js";

const tempDir = mkdtempSync(path.join(os.tmpdir(), "gosb-feedback-"));

try {
  assert.deepEqual(parseFeedbackCallback("useful:123"), { action: "useful", newsId: 123 });
  assert.deepEqual(parseFeedbackCallback("boring:456"), { action: "boring", newsId: 456 });
  assert.deepEqual(parseFeedbackCallback("comment:789"), { action: "comment", newsId: 789 });
  assert.equal(parseFeedbackCallback("bad:123"), null);
  assert.equal(parseFeedbackCallback("useful:abc"), null);

  const pendingPath = path.join(tempDir, "pending.json");
  assert.equal(
    rememberPendingComment({
      pendingPath,
      newsId: 42,
      accountId: "default",
      conversationId: "-1001:topic:6",
      senderId: "100",
      senderUsername: "stepan",
      now: 1_000,
      ttlMs: 60_000,
    }),
    true,
  );
  assert.equal(
    consumePendingComment({
      pendingPath,
      accountId: "default",
      conversationId: "-1001:topic:6",
      senderId: "101",
      now: 2_000,
    }),
    null,
  );
  assert.equal(
    consumePendingComment({
      pendingPath,
      accountId: "default",
      conversationId: "-1001:topic:6",
      senderId: "100",
      now: 2_000,
    }).newsId,
    42,
  );
  assert.equal(JSON.stringify(JSON.parse(readFileSync(pendingPath, "utf8"))), "{}");

  const dbPath = path.join(tempDir, "news_bot.db");
  const db = new DatabaseSync(dbPath);
  db.exec(`
    CREATE TABLE sent_news (
      id INTEGER PRIMARY KEY,
      gosb_id INTEGER NOT NULL,
      news_id INTEGER NOT NULL,
      summary TEXT,
      sent_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE feedback (
      id INTEGER PRIMARY KEY,
      gosb_id INTEGER,
      news_id INTEGER,
      user_id TEXT,
      username TEXT,
      action TEXT,
      comment TEXT,
      created_at TEXT DEFAULT (datetime('now'))
    );
    INSERT INTO sent_news (gosb_id, news_id, summary) VALUES (77, 42, 'summary');
  `);

  await saveFeedback({
    dbPath,
    newsId: 42,
    userId: "100",
    username: "stepan",
    action: "useful",
  });
  await saveFeedback({
    dbPath,
    newsId: 42,
    userId: "100",
    username: "stepan",
    action: "comment",
    comment: "good item",
  });

  const rows = db
    .prepare("SELECT gosb_id, news_id, user_id, username, action, comment FROM feedback ORDER BY id")
    .all()
    .map((row) => [row.gosb_id, row.news_id, row.user_id, row.username, row.action, row.comment]);
  assert.deepEqual(rows, [
    [77, 42, "100", "stepan", "useful", null],
    [77, 42, "100", "stepan", "comment", "good item"],
  ]);

  const replies = [];
  let clearedButtons = 0;
  const pluginConfig = {
    dbPath,
    pendingPath: path.join(tempDir, "plugin-pending.json"),
    commentTtlMs: 60_000,
  };
  const callbackCtx = {
    accountId: "default",
    conversationId: "-1001:topic:6",
    senderId: "100",
    senderUsername: "stepan",
    callback: { data: "comment:42" },
    respond: {
      clearButtons: async () => {
        clearedButtons += 1;
      },
      reply: async (message) => {
        replies.push(message.text);
      },
    },
  };

  assert.deepEqual(await handleFeedbackCallback(callbackCtx, pluginConfig), { handled: true });
  assert.equal(clearedButtons, 1);
  assert.equal(replies.length, 1);
  assert.equal(
    replies[0],
    "Ответь reply на это сообщение комментарием. Если не сохранится, напиши в чат: @agent_ler_bot твой комментарий.",
  );

  const beforeDispatchResult = await handlePendingComment(
    {
      channel: "telegram",
      content: "@agent_ler_bot надо меньше политики",
    },
    {
      accountId: "default",
      conversationId: "-1001:topic:6",
      senderId: "100",
    },
    pluginConfig,
  );
  assert.deepEqual(beforeDispatchResult, {
    handled: true,
    text: "Комментарий сохранен. Спасибо, это пойдет в обучение агента.",
  });

  const commentRow = db
    .prepare("SELECT action, comment FROM feedback ORDER BY id DESC LIMIT 1")
    .get();
  assert.deepEqual(
    { action: commentRow.action, comment: commentRow.comment },
    { action: "comment", comment: "надо меньше политики" },
  );
  db.close();

  console.log("ok");
} finally {
  rmSync(tempDir, { recursive: true, force: true });
}
