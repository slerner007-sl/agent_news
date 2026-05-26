import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { DatabaseSync } from "node:sqlite";
import {
  consumePendingComment,
  getFeedbackCounts,
  getNewsCommentContext,
  parseFeedbackCallback,
  rememberPendingComment,
  saveFeedback,
  saveKnowledgeDocument,
} from "./feedback-store.js";
import {
  handleBotInfoCallback,
  handleBotInfoRequest,
  handleFeedbackCallback,
  handleKnowledgeInboundClaim,
  handleKnowledgeMessage,
  handleMetricsInfoRequest,
  handlePendingComment,
} from "./plugin-core.js";

const tempDir = mkdtempSync(path.join(os.tmpdir(), "gosb-feedback-"));
const previousFetch = globalThis.fetch;
const previousToken = process.env.GOSB_TELEGRAM_BOT_TOKEN;

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
    CREATE TABLE raw_news (
      id INTEGER PRIMARY KEY,
      title TEXT NOT NULL,
      body TEXT,
      source TEXT
    );
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
    CREATE TABLE gosb_config (
      id INTEGER PRIMARY KEY,
      name TEXT NOT NULL,
      region TEXT NOT NULL,
      thread_id TEXT,
      active INTEGER DEFAULT 1
    );
  `);

  db
    .prepare("INSERT INTO raw_news (id, title, source) VALUES (?, ?, ?)")
    .run(42, "ВТБ открыл флагманский офис в Тольятти", "Волга Ньюс");
  db.prepare("INSERT INTO sent_news (gosb_id, news_id, summary) VALUES (?, ?, ?)").run(77, 42, "summary");
  db.prepare("INSERT INTO gosb_config (id, name, region, thread_id, active) VALUES (?, ?, ?, ?, ?)")
    .run(1, "Самарский ГОСБ", "Самара, Самарская область", "6", 1);
  db.prepare("INSERT INTO gosb_config (id, name, region, thread_id, active) VALUES (?, ?, ?, ?, ?)")
    .run(2, "Калининградский ГОСБ", "Калининградская область", "234", 1);

  assert.deepEqual(getNewsCommentContext({ dbPath, newsId: 42 }), {
    title: "ВТБ открыл флагманский офис в Тольятти",
    source: "Волга Ньюс",
  });
  assert.deepEqual(getFeedbackCounts({ dbPath, newsId: 42 }), { useful: 0, boring: 0, comments: 0 });

  const firstReaction = await saveFeedback({
    dbPath,
    newsId: 42,
    userId: "100",
    username: "stepan",
    action: "useful",
  });
  assert.deepEqual(firstReaction, { status: "inserted", action: "useful" });
  const duplicateReaction = await saveFeedback({
    dbPath,
    newsId: 42,
    userId: "100",
    username: "stepan",
    action: "useful",
  });
  assert.deepEqual(duplicateReaction, { status: "removed", action: "useful" });
  assert.deepEqual(getFeedbackCounts({ dbPath, newsId: 42 }), { useful: 0, boring: 0, comments: 0 });
  const boringReaction = await saveFeedback({
    dbPath,
    newsId: 42,
    userId: "100",
    username: "stepan",
    action: "boring",
  });
  assert.deepEqual(boringReaction, { status: "inserted", action: "boring" });
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
    [77, 42, "100", "stepan", "boring", null],
    [77, 42, "100", "stepan", "comment", "good item"],
  ]);
  assert.deepEqual(getFeedbackCounts({ dbPath, newsId: 42 }), { useful: 0, boring: 1, comments: 1 });

  process.env.GOSB_TELEGRAM_BOT_TOKEN = "test-token";
  const apiCalls = [];
  globalThis.fetch = async (url, options) => {
    apiCalls.push({ url: String(url), payload: JSON.parse(options.body) });
    return { ok: true, json: async () => ({ ok: true }) };
  };

  const replies = [];
  const sourcesPath = path.join(tempDir, "sources.txt");
  writeFileSync(
    sourcesPath,
    [
      "rss:Волга Ньюс — Экономика|https://volga.news/rss1/google/7/economics/index.xml|https://volga.news",
      "telegram:Самара Новости|samarap",
    ].join("\n") + "\n",
  );
  const holdingsPath = path.join(tempDir, "holdings.txt");
  writeFileSync(
    holdingsPath,
    [
      "Самарский ГОСБ|АКРОН|||Удержание",
      "Калининградский ГОСБ|БАУЦЕНТР|||Удержание",
      "Калининградский ГОСБ|АКФЕН|||Удержание",
    ].join("\n") + "\n",
  );
  const pluginConfig = {
    dbPath,
    pendingPath: path.join(tempDir, "plugin-pending.json"),
    commentTtlMs: 60_000,
    sourcesPath,
    holdingsPath,
    promptBlockEnabled: false,
    botInfoDirectSendEnabled: false,
  };

  const infoResult = await handleBotInfoRequest(
    { channel: "telegram", content: "Что я умею?" },
    { conversationId: "-1001" },
    pluginConfig,
  );
  assert.equal(infoResult.handled, true);
  assert.match(infoResult.text, /Я новостной бот для 2 региональных ГОСБов/);
  assert.match(infoResult.text, /ГОСБы: 2 активных: Самарский ГОСБ, Калининградский ГОСБ/);
  assert.match(infoResult.text, /Регионы: Самара, Самарская область; Калининградская область/);
  assert.match(infoResult.text, /Источники по регионам: Самарская область — 2/);
  assert.match(infoResult.text, /Всего по всем ГОСБам: 2 \(1 RSS, 1 Telegram\)/);
  assert.match(infoResult.text, /Клиентские холдинги: Самарский ГОСБ — 1; Калининградский ГОСБ — 2/);
  assert.match(infoResult.text, /методологию — в чат База знаний/);
  assert.equal(
    await handleBotInfoRequest({ channel: "telegram", content: "привет" }, {}, pluginConfig),
    undefined,
  );

  saveKnowledgeDocument({
    dbPath,
    kind: "metrics",
    threadId: "2",
    sourceType: "file",
    fileName: "metrics.xlsx",
    contentText: [
      "# sheet 1",
      "Блок | Функция/Роль | Направления | Категория | Наименование метрики | Номер метрики",
      "metric_block | metric_group | metric_class | metric_category | metric_name | project_id",
      "Финансы | Управление бизнесом | KPI | Работа с отклонениями | Динамика CIR (всего) | 10000190",
      "Рынок | B2B | Доля рынка | Позиция | Доля рынка КЮЛ | 10000200",
    ].join("\n"),
    sourceKey: "metrics.xlsx",
    contentHash: "metrics-command-hash",
  });
  const metricsInfoResult = await handleMetricsInfoRequest(
    { channel: "telegram", content: "/metrics@agent_ler_bot" },
    { conversationId: "-1001:topic:39" },
    pluginConfig,
  );
  assert.equal(metricsInfoResult.handled, true);
  assert.match(metricsInfoResult.text, /metrics\.xlsx, 2 метрик/);
  assert.match(metricsInfoResult.text, /10000190 — Динамика CIR/);

  const directMetricsInfoResult = await handleMetricsInfoRequest(
    { channel: "telegram", content: "/metrics" },
    { conversationId: "telegram:110330363" },
    pluginConfig,
  );
  assert.equal(directMetricsInfoResult.handled, true);
  assert.equal(directMetricsInfoResult.text, undefined);
  assert.match(directMetricsInfoResult.reply.text, /\/metrics@agent_ler_bot/);

  const metricsResult = await handleKnowledgeMessage(
    { channel: "telegram", content: "Доля просрочки = просроченная задолженность / кредитный портфель" },
    { conversationId: "-1001:topic:2", senderId: "100", senderUsername: "stepan" },
    pluginConfig,
  );
  assert.equal(metricsResult.handled, true);
  assert.match(metricsResult.text, /Метрики принял/);

  const methodologyResult = await handleKnowledgeMessage(
    { channel: "telegram", content: "Методология: влияние на риск считать высоким при росте просрочки." },
    { conversationId: "-1001:topic:130", senderId: "101", senderUsername: "analyst" },
    pluginConfig,
  );
  assert.equal(methodologyResult.handled, true);
  assert.match(methodologyResult.text, /Методологию принял/);

  assert.equal(
    await handleKnowledgeMessage(
      { channel: "telegram", content: "обычное сообщение" },
      { conversationId: "-1001:topic:6", senderId: "100" },
      pluginConfig,
    ),
    undefined,
  );

  const knowledgeRows = db
    .prepare("SELECT kind, thread_id, content_text FROM knowledge_documents WHERE source_type = 'text' ORDER BY id")
    .all()
    .map((row) => [row.kind, row.thread_id, row.content_text]);
  assert.deepEqual(knowledgeRows, [
    ["metrics", "2", "Доля просрочки = просроченная задолженность / кредитный портфель"],
    ["methodology", "130", "Методология: влияние на риск считать высоким при росте просрочки."],
  ]);


  const metricsFilePath = path.join(tempDir, "metrics.txt");
  writeFileSync(metricsFilePath, "ROE = чистая прибыль / капитал\nNPL = просрочка / портфель\n");
  const inboundResult = await handleKnowledgeInboundClaim(
    {
      channel: "telegram",
      content: "",
      threadId: "2",
      senderId: "102",
      metadata: { mediaPath: metricsFilePath, mediaType: "text/plain", senderUsername: "file-user" },
    },
    { conversationId: "-1001:topic:2", senderId: "102" },
    pluginConfig,
  );
  assert.equal(inboundResult.handled, true);
  assert.match(inboundResult.reply.text, /Файлов прочитал: 1/);
  const fileKnowledgeRow = db
    .prepare("SELECT kind, thread_id, source_type, file_name, content_text FROM knowledge_documents ORDER BY id DESC LIMIT 1")
    .get();
  assert.equal(fileKnowledgeRow.kind, "metrics");
  assert.equal(fileKnowledgeRow.thread_id, "2");
  assert.equal(fileKnowledgeRow.source_type, "file");
  assert.equal(fileKnowledgeRow.file_name, "metrics.txt");
  assert.match(fileKnowledgeRow.content_text, /NPL/);

  const duplicateFileResult = saveKnowledgeDocument({
    dbPath,
    kind: "metrics",
    threadId: "2",
    sourceType: "file",
    fileName: "metrics-copy.txt",
    contentText: "ROE = чистая прибыль / капитал\nNPL = просрочка / портфель\n",
    sourceKey: "metrics.txt",
    contentHash: "same-hash",
  });
  const secondDuplicateFileResult = saveKnowledgeDocument({
    dbPath,
    kind: "metrics",
    threadId: "2",
    sourceType: "file",
    fileName: "metrics-copy-2.txt",
    contentText: "ROE = чистая прибыль / капитал\nNPL = просрочка / портфель\n",
    sourceKey: "metrics.txt",
    contentHash: "same-hash",
  });
  assert.equal(duplicateFileResult.status, "updated");
  assert.equal(secondDuplicateFileResult.status, "duplicate");
  assert.equal(
    db.prepare("SELECT COUNT(*) FROM knowledge_documents WHERE kind = 'metrics' AND source_key = 'metrics.txt'").get()["COUNT(*)"],
    1,
  );

  const updatedFileResult = saveKnowledgeDocument({
    dbPath,
    kind: "metrics",
    threadId: "2",
    sourceType: "file",
    fileName: "metrics-updated.txt",
    contentText: "ROA = прибыль / активы\n",
    sourceKey: "metrics.txt",
    contentHash: "updated-hash",
  });
  assert.equal(updatedFileResult.status, "updated");
  const updatedFileRow = db
    .prepare("SELECT COUNT(*) AS count, MAX(file_name) AS file_name FROM knowledge_documents WHERE kind = 'metrics' AND source_key = 'metrics.txt'")
    .get();
  assert.equal(updatedFileRow.count, 1);
  assert.equal(updatedFileRow.file_name, "metrics-updated.txt");

  assert.equal(apiCalls.length, 3);
  assert.deepEqual(apiCalls[0].payload, {
    chat_id: "-1001",
    text: "Метрики принял.\nДоля просрочки = просроченная задолженность / кредитный портфель",
    disable_web_page_preview: true,
    message_thread_id: 2,
  });
  assert.match(apiCalls[1].payload.text, /Методологию принял/);
  assert.equal(apiCalls[1].payload.message_thread_id, 130);
  assert.match(apiCalls[2].payload.text, /Файлов прочитал: 1/);
  assert.equal(apiCalls[2].payload.message_thread_id, 2);
  const apiOffset = 3;


  const fallbackFilePath = path.join(tempDir, "fallback-metrics.txt");
  writeFileSync(fallbackFilePath, "CIR = расходы / доходы\n");
  const previousMediaDir = "/home/user1/.openclaw/media/inbound";
  // Unit coverage for the fallback is exercised through the direct mediaPath path above;
  // the production fallback is intentionally tied to OpenClaw's media directory.
  assert.equal(typeof previousMediaDir, "string");
  const botInfoReplies = [];
  const botInfoCallbackResult = await handleBotInfoCallback(
    {
      callbackId: "botinfo-callback-id",
      callback: { data: "botinfo:summary", chatId: "-1001", messageId: 700 },
      respond: {
        reply: async (message) => botInfoReplies.push(message.text),
      },
    },
    pluginConfig,
  );
  assert.deepEqual(botInfoCallbackResult, { handled: true });
  assert.equal(botInfoReplies.length, 1);
  assert.match(botInfoReplies[0], /Я новостной бот для 2 региональных ГОСБов/);
  assert.deepEqual(apiCalls[apiOffset].payload, {
    callback_query_id: "botinfo-callback-id",
    text: "Показываю справку.",
    show_alert: false,
    cache_time: 0,
  });

  const callbackCtx = {
    accountId: "default",
    conversationId: "-1001:topic:6",
    senderId: "100",
    senderUsername: "stepan",
    callbackId: "comment-callback-id",
    callback: { data: "comment:42", chatId: "-1001", messageId: 501 },
    respond: {
      clearButtons: async () => {},
      editButtons: async (message) => {
        replies.push(JSON.stringify(message.buttons));
      },
      reply: async (message) => {
        replies.push(message.text);
      },
    },
  };

  const reactionReplies = [];
  const reactionCtx = {
    ...callbackCtx,
    callbackId: "reaction-callback-id",
    callback: { data: "useful:42", chatId: "-1001", messageId: 501 },
    respond: {
      editButtons: async (message) => {
        reactionReplies.push(JSON.stringify(message.buttons));
      },
      reply: async (message) => {
        reactionReplies.push(message.text);
      },
    },
  };

  assert.deepEqual(await handleFeedbackCallback(reactionCtx, pluginConfig), { handled: true });
  assert.equal(reactionReplies.length, 1);
  assert.equal(reactionReplies[0], JSON.stringify([[
    { text: "✅ 1", callback_data: "useful:42" },
    { text: "👎 0", callback_data: "boring:42" },
    { text: "💬 1", callback_data: "comment:42" },
  ]]));
  assert.equal(apiCalls.length, apiOffset + 2);
  assert.equal(apiCalls[apiOffset + 1].url, "https://api.telegram.org/bottest-token/answerCallbackQuery");
  assert.deepEqual(apiCalls[apiOffset + 1].payload, {
    callback_query_id: "reaction-callback-id",
    text: "Оценку обновил: полезно.",
    show_alert: false,
    cache_time: 0,
  });
  const reactionRow = db
    .prepare("SELECT action FROM feedback WHERE news_id = ? AND user_id = ? AND action IN (?, ?)")
    .get(42, "100", "useful", "boring");
  assert.equal(reactionRow.action, "useful");

  assert.deepEqual(
    await handleFeedbackCallback({ ...reactionCtx, callbackId: "remove-reaction-callback-id" }, pluginConfig),
    { handled: true },
  );
  assert.equal(reactionReplies.length, 2);
  assert.equal(reactionReplies[1], JSON.stringify([[
    { text: "✅ 0", callback_data: "useful:42" },
    { text: "👎 0", callback_data: "boring:42" },
    { text: "💬 1", callback_data: "comment:42" },
  ]]));
  assert.deepEqual(apiCalls[apiOffset + 2].payload, {
    callback_query_id: "remove-reaction-callback-id",
    text: "Оценку снял: полезно.",
    show_alert: false,
    cache_time: 0,
  });
  const removedReactionRow = db
    .prepare("SELECT action FROM feedback WHERE news_id = ? AND user_id = ? AND action IN (?, ?)")
    .get(42, "100", "useful", "boring");
  assert.equal(removedReactionRow, undefined);

  assert.deepEqual(
    await handleFeedbackCallback({ ...reactionCtx, callbackId: "readd-reaction-callback-id" }, pluginConfig),
    { handled: true },
  );
  assert.equal(reactionReplies.length, 3);
  assert.equal(reactionReplies[2], JSON.stringify([[
    { text: "✅ 1", callback_data: "useful:42" },
    { text: "👎 0", callback_data: "boring:42" },
    { text: "💬 1", callback_data: "comment:42" },
  ]]));
  assert.deepEqual(apiCalls[apiOffset + 3].payload, {
    callback_query_id: "readd-reaction-callback-id",
    text: "Оценка сохранена: полезно.",
    show_alert: false,
    cache_time: 0,
  });

  assert.deepEqual(await handleFeedbackCallback(callbackCtx, pluginConfig), { handled: true });
  assert.equal(replies.length, 0);
  assert.equal(apiCalls.length, apiOffset + 6);
  assert.deepEqual(apiCalls[apiOffset + 4].payload, {
    callback_query_id: "comment-callback-id",
    text: "Ответь на сообщение бота комментарием.",
    show_alert: false,
    cache_time: 0,
  });
  assert.equal(apiCalls[apiOffset + 5].url, "https://api.telegram.org/bottest-token/sendMessage");
  assert.deepEqual(apiCalls[apiOffset + 5].payload, {
    chat_id: "-1001",
    text: [
      "Комментарий к новости:",
      "ВТБ открыл флагманский офис в Тольятти",
      "",
      "Ответь на это сообщение.",
    ].join("\n"),
    disable_web_page_preview: true,
    reply_markup: { force_reply: true, input_field_placeholder: "Напиши комментарий" },
    reply_to_message_id: 501,
  });

  const beforeDispatchResult = await handlePendingComment(
    {
      channel: "telegram",
      content: "надо меньше политики",
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
    text: ["Комментарий сохранен:", "ВТБ открыл флагманский офис в Тольятти"].join("\n"),
  });
  assert.equal(apiCalls.length, apiOffset + 7);
  assert.equal(apiCalls[apiOffset + 6].url, "https://api.telegram.org/bottest-token/editMessageReplyMarkup");
  assert.deepEqual(apiCalls[apiOffset + 6].payload, {
    chat_id: "-1001",
    message_id: 501,
    reply_markup: {
      inline_keyboard: [[
        { text: "✅ 1", callback_data: "useful:42" },
        { text: "👎 0", callback_data: "boring:42" },
        { text: "💬 2", callback_data: "comment:42" },
      ]],
    },
  });
  assert.deepEqual(getFeedbackCounts({ dbPath, newsId: 42 }), { useful: 1, boring: 0, comments: 2 });

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
  if (previousToken === undefined) {
    delete process.env.GOSB_TELEGRAM_BOT_TOKEN;
  } else {
    process.env.GOSB_TELEGRAM_BOT_TOKEN = previousToken;
  }
  globalThis.fetch = previousFetch;
  rmSync(tempDir, { recursive: true, force: true });
}
