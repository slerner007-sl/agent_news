import { createHash } from "node:crypto";
import { basename } from "node:path";
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";

import {
  consumePendingComment,
  getFeedbackCounts,
  getNewsCommentContext,
  parseFeedbackCallback,
  rememberPendingComment,
  resolveCommentTtlMs,
  resolveDbPath,
  resolvePendingPath,
  saveFeedback,
  saveKnowledgeDocument,
} from "./feedback-store.js";

function cleanText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function cleanCommentText(value) {
  return cleanText(value).replace(/(^|\s)@agent_ler_bot\b[:,\s-]*/gi, "$1").trim();
}

const COMMENT_TITLE_MAX_LENGTH = 82;
const SENDER_PY_PATH = "/home/user1/gosb_bot/sender.py";
const SOURCES_TXT_PATH = "/home/user1/gosb_bot/config/sources.txt";
const HOLDINGS_TXT_PATH = "/home/user1/gosb_bot/config/holdings.txt";
const KNOWLEDGE_FILE_READER_PATH = "/home/user1/gosb_bot/knowledge_file_reader.py";
const OPENCLAW_INBOUND_MEDIA_DIR = "/home/user1/.openclaw/media/inbound";
const BOT_INFO_BUTTON_TEXT = "Что я умею?";
const DEFAULT_METRICS_THREAD_ID = "2";
const DEFAULT_METHODOLOGY_THREAD_ID = "130";

const ACTION_TOASTS = {
  useful: {
    inserted: "Оценка сохранена: полезно.",
    removed: "Оценку снял: полезно.",
    updated: "Оценку обновил: полезно.",
  },
  boring: {
    inserted: "Оценка сохранена: неинтересно.",
    removed: "Оценку снял: неинтересно.",
    updated: "Оценку обновил: неинтересно.",
  },
};

const BOT_INFO_FILTER_PROMPT = `Текущий промт отбора:
Ты — редактор банковского регионального дайджеста для конкретного ГОСБа.

Цель: отобрать новости, которые реально полезны региональному банку.
Учитываются регион/территория ГОСБа, локальные ключевые слова и закрепленные клиентские холдинги.

Считать релевантным:
- новости о закрепленных клиентских холдингах ГОСБа: сделки, стройки, инвестиции, производство, суды, банкротства, проверки, собственники, расширение/сокращение бизнеса;
- банковский сектор, Сбер, конкуренты, карты, платежи, вклады, кредиты, ипотека;
- мошенничество, киберриски, нелегальный трафик, схемы хищения денег;
- ЦБ РФ, ключевая ставка, регулирование, налоги, судебные и банкротные риски;
- крупный бизнес, промышленность, инвестиции, производство, застройщики, МСП, если есть связь с клиентами, кредитованием или рисками банка;
- повестка ЛПР и органов власти, если она влияет на экономику региона или клиентов банка.

Считать шумом:
- спорт, погода, развлечения, розыгрыши, поздравления, алкогольные ограничения, бытовая городская повестка;
- новости только с географией региона без банковского, экономического или риск-содержания.

LLM возвращает решение по каждой новости: relevant, category, impact, confidence, summary или reject_reason. Для холдингов используется категория client_holding.`;

function truncateText(value, maxLength) {
  const text = cleanText(value);
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength - 3).trimEnd() + "...";
}

function formatCommentPrompt(newsContext) {
  const title = truncateText(newsContext?.title, COMMENT_TITLE_MAX_LENGTH) || "выбранная новость";
  return ["Комментарий к новости:", title, "", "Ответь на это сообщение."].join("\n");
}

function formatSavedCommentText(newsContext) {
  const title = truncateText(newsContext?.title, COMMENT_TITLE_MAX_LENGTH);
  if (!title) return "Комментарий сохранен.";
  return ["Комментарий сохранен:", title].join("\n");
}

function normalizeButtonText(value) {
  return cleanText(value).toLowerCase().replace(/ё/g, "е").replace(/[?!.,:;]+$/g, "");
}

function isBotInfoRequest(value) {
  const text = normalizeButtonText(value);
  return [
    "что я умею",
    "меню",
    "/what_can_you_do",
    "/what_can_you_do@agent_ler_bot",
    "/help",
    "/help@agent_ler_bot",
  ].includes(text);
}

function isBlockedMenuRequest(value) {
  const text = normalizeButtonText(value);
  return text === "/menu" || text === "/menu@agent_ler_bot";
}

function isMetricsInfoRequest(value) {
  const text = normalizeButtonText(value);
  return [
    "/metrics",
    "/metrics@agent_ler_bot",
    "метрики",
    "какие метрики",
    "какие метрики?",
  ].includes(text);
}

function parseMetricsRows(contentText) {
  const rows = [];
  for (const rawLine of cleanText(contentText).split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#") || !line.includes("|")) continue;
    const parts = line.split("|").map((part) => part.trim());
    if (parts.length < 6) continue;
    const [block, role, direction, category, name, number] = parts;
    if (!name || !number || name === "Наименование метрики" || name === "metric_name") continue;
    rows.push({ block, role, direction, category, name, number });
  }
  return rows;
}

function formatMetricsSummary(pluginConfig = {}) {
  const dbPath = resolveDbPath(pluginConfig);
  try {
    const db = new DatabaseSync(dbPath);
    try {
      db.exec("PRAGMA busy_timeout = 5000");
      const doc = db.prepare(`
        SELECT file_name, source_key, content_text, created_at
        FROM knowledge_documents
        WHERE kind = 'metrics'
          AND COALESCE(is_current, 1) = 1
          AND source_type = 'file'
          AND COALESCE(content_text, '') <> ''
        ORDER BY created_at DESC
        LIMIT 1
      `).get();
      if (!doc) {
        return "Файл со справочником метрик пока не загружен. Пришли .xlsx в тему метрик.";
      }

      const rows = parseMetricsRows(doc.content_text);
      const sourceName = cleanText(doc.source_key) || cleanText(doc.file_name) || "справочник метрик";
      if (!rows.length) {
        return `${sourceName}: файл загружен, но я не смог распознать строки метрик.`;
      }

      const blockCounts = new Map();
      const categoryCounts = new Map();
      for (const row of rows) {
        const block = row.block || "Без блока";
        const category = row.category || "Без категории";
        blockCounts.set(block, (blockCounts.get(block) || 0) + 1);
        categoryCounts.set(category, (categoryCounts.get(category) || 0) + 1);
      }
      const topBlocks = [...blockCounts.entries()]
        .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "ru"))
        .slice(0, 10)
        .map(([name, count]) => `• ${name}: ${count}`)
        .join("\n");
      const topCategories = [...categoryCounts.entries()]
        .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "ru"))
        .slice(0, 8)
        .map(([name, count]) => `• ${name}: ${count}`)
        .join("\n");
      const examples = rows
        .slice(0, 8)
        .map((row) => `• ${row.number} — ${row.name}`)
        .join("\n");

      return [
        `${sourceName}, ${rows.length} метрик.`,
        "",
        "Блоки:",
        topBlocks,
        "",
        "Категории:",
        topCategories,
        "",
        "Первые строки:",
        examples,
      ].join("\n");
    } finally {
      db.close();
    }
  } catch (error) {
    return "Не смог прочитать справочник метрик: " + (error instanceof Error ? error.message : String(error));
  }
}

export async function handleMetricsInfoRequest(event, ctx, pluginConfig = {}) {
  if (event.channel !== "telegram") return;
  const text = event.body ?? event.content;
  if (!isMetricsInfoRequest(text)) return;
  if (!isGroupConversation(event, ctx)) {
    return {
      handled: true,
      reply: { text: "Личные сообщения отключены. Используй /metrics@agent_ler_bot в рабочей группе." },
    };
  }
  const textResponse = formatMetricsSummary(pluginConfig);
  return {
    handled: true,
    text: textResponse,
    reply: { text: textResponse },
  };
}

export async function handleBlockedMenuCommand(event) {
  if (event.channel !== "telegram") return;
  const text = event.body ?? event.content;
  if (!isBlockedMenuRequest(text)) return;
  return {
    handled: true,
    reply: {
      text: "Команду /menu отключил. Используй /what_can_you_do.",
    },
  };
}

function isTopicIdRequest(value) {
  const text = normalizeButtonText(value);
  return [
    "/topic_id",
    "/topic_id@agent_ler_bot",
    "topic_id@agent_ler_bot",
    "@agent_ler_bot topic_id",
    "@agent_ler_bot /topic_id",
  ].includes(text);
}

function isSourcesMetaComment(value) {
  const text = normalizeButtonText(value);
  return (
    !text ||
    text.startsWith("источники") ||
    text.startsWith("форматы") ||
    text.startsWith("rss:") ||
    text.startsWith("telegram:") ||
    text.startsWith("tg:") ||
    text.startsWith("wpapi:") ||
    text.startsWith("wordpress:")
  );
}

function loadSourceNames(pluginConfig = {}) {
  const sourcesPath = cleanText(pluginConfig.sourcesPath) || SOURCES_TXT_PATH;
  const defaultGroup = cleanText(pluginConfig.defaultSourcesGroup) || "Самарская область";
  try {
    const sources = [];
    let currentGroup = defaultGroup;
    for (const rawLine of readFileSync(sourcesPath, "utf8").split(/\r?\n/)) {
      const line = rawLine.trim();
      if (!line) continue;
      if (line.startsWith("#")) {
        const heading = cleanText(line.replace(/^#+\s*/, ""));
        if (!isSourcesMetaComment(heading)) currentGroup = heading;
        continue;
      }
      const separator = line.indexOf(":");
      if (separator <= 0) continue;
      const type = line.slice(0, separator).trim();
      const parts = line.slice(separator + 1).split("|").map((part) => part.trim()).filter(Boolean);
      if (!parts[0]) continue;
      sources.push({ type, name: parts[0], group: currentGroup });
    }
    return sources;
  } catch {
    return [];
  }
}

function escapeTelegramAutoLink(value) {
  return cleanText(value).replace(/([A-Za-zА-Яа-я0-9])\.([A-Za-zА-Яа-я0-9])/g, "$1．$2");
}

function loadHoldings(pluginConfig = {}) {
  const holdingsPath = cleanText(pluginConfig.holdingsPath) || HOLDINGS_TXT_PATH;
  try {
    return readFileSync(holdingsPath, "utf8")
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line && !line.startsWith("#"))
      .map((line) => {
        const parts = line.split("|").map((part) => part.trim());
        if (!parts[0] || !parts[1]) return null;
        return { gosb: parts[0], name: parts[1] };
      })
      .filter(Boolean);
  } catch {
    return [];
  }
}

function loadActiveGosbs(pluginConfig = {}) {
  const dbPath = resolveDbPath(pluginConfig);
  try {
    const db = new DatabaseSync(dbPath);
    try {
      db.exec("PRAGMA busy_timeout = 5000");
      return db
        .prepare(`
          SELECT name, region, thread_id
          FROM gosb_config
          WHERE active = 1
          ORDER BY id
        `)
        .all()
        .map((row) => ({
          name: cleanText(row.name),
          region: cleanText(row.region),
          threadId: cleanText(String(row.thread_id ?? "")),
        }))
        .filter((row) => row.name);
    } finally {
      db.close();
    }
  } catch {
    return [];
  }
}

function formatSourceLine(sources) {
  if (!sources.length) return "Источники: список пока не прочитан.";
  const rssCount = sources.filter((source) => ["rss", "smi"].includes(source.type)).length;
  const telegramCount = sources.filter((source) => ["telegram", "tg"].includes(source.type)).length;
  const wpapiCount = sources.filter((source) => ["wpapi", "wordpress"].includes(source.type)).length;
  const typeParts = [`${rssCount} RSS`, `${telegramCount} Telegram`];
  if (wpapiCount) typeParts.push(`${wpapiCount} WP API`);

  const byGroup = new Map();
  for (const source of sources) {
    const group = cleanText(source.group) || "Без группы";
    byGroup.set(group, (byGroup.get(group) || 0) + 1);
  }
  const groups = [...byGroup.entries()]
    .map(([group, count]) => `${escapeTelegramAutoLink(group)} — ${count}`)
    .join("; ");
  return `Источники по регионам: ${groups}. Всего по всем ГОСБам: ${sources.length} (${typeParts.join(", ")}).`;
}

function formatHoldingsLine(holdings) {
  if (!holdings.length) return "Холдинги: список пока не подключен.";
  const byGosb = new Map();
  for (const holding of holdings) {
    const gosb = cleanText(holding.gosb) || "Без ГОСБа";
    byGosb.set(gosb, (byGosb.get(gosb) || 0) + 1);
  }
  const groups = [...byGosb.entries()]
    .map(([gosb, count]) => `${escapeTelegramAutoLink(gosb)} — ${count}`)
    .join("; ");
  return `Клиентские холдинги: ${groups}. Всего: ${holdings.length}.`;
}

function formatGosbLine(gosbs) {
  if (!gosbs.length) return "ГОСБы: активные конфиги пока не прочитаны.";
  const names = gosbs.map((gosb) => gosb.name).join(", ");
  return `ГОСБы: ${gosbs.length} активных: ${names}.`;
}

function formatRegionsLine(gosbs) {
  const regions = gosbs.map((gosb) => gosb.region).filter(Boolean);
  if (!regions.length) return "Регионы: список пока не прочитан.";
  return `Регионы: ${regions.join("; ")}.`;
}

function formatBotIntro(gosbs) {
  if (!gosbs.length) return "Я новостной бот для региональных ГОСБов.";
  if (gosbs.length === 1) return `Я новостной бот для ${gosbs[0].name}.`;
  return `Я новостной бот для ${gosbs.length} региональных ГОСБов.`;
}

function formatBotInfoSummary(pluginConfig = {}) {
  const sources = loadSourceNames(pluginConfig);
  const holdings = loadHoldings(pluginConfig);
  const gosbs = loadActiveGosbs(pluginConfig);
  return [
    formatBotIntro(gosbs),
    "",
    "Что делаю:",
    "- собираю новости из RSS и Telegram-источников;",
    "- отбираю релевантное для каждого ГОСБа через LLM V2;",
    "- отправляю дайджесты в свои Telegram-топики;",
    "- собираю разметку: полезно, неинтересно и комментарии;",
    "- даю снять случайную реакцию повторным нажатием;",
    "- связываю новости с метриками из отдельной темы.",
    "",
    formatGosbLine(gosbs),
    formatRegionsLine(gosbs),
    "",
    formatSourceLine(sources),
    formatHoldingsLine(holdings),
    "",
    "Метрики: присылай определения и значения в тему метрик, методологию — в чат База знаний. Я сохраняю их отдельно и использую при связке новостей с показателями.",
  ].join("\n");
}

function resolveTelegramBotToken(pluginConfig = {}) {
  const direct = cleanText(pluginConfig.botToken);
  if (direct) return direct;

  const envName = cleanText(pluginConfig.botTokenEnv) || "GOSB_TELEGRAM_BOT_TOKEN";
  const fromEnv = cleanText(process.env[envName]) || cleanText(process.env.TELEGRAM_BOT_TOKEN);
  if (fromEnv) return fromEnv;

  return "";
}

function escapeHtml(value) {
  return cleanText(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function formatPromptBlockHtml() {
  const title = "<b>Текущий промт отбора</b>";
  const prompt = BOT_INFO_FILTER_PROMPT.replace(/^Текущий промт отбора:\n?/, "");
  return title + "\n\n<blockquote>" + escapeHtml(prompt) + "</blockquote>";
}

function threadIdFromConversation(value) {
  return cleanText(value).split(":topic:")[1] || "";
}

function telegramTargetFromSessionKey(value) {
  const text = cleanText(value);
  const match = text.match(/telegram:group:(-?\d+):topic:(\d+)/);
  if (!match) return { chatId: "", threadId: "" };
  return { chatId: match[1], threadId: match[2] };
}

async function sendTelegramTextMessage({ chatId, threadId, text, parseMode = "", replyMarkup = null, pluginConfig = {} }) {
  const token = resolveTelegramBotToken(pluginConfig);
  const targetChatId = cleanText(chatId);
  const messageText = cleanText(text);
  if (!token || !targetChatId || !messageText || typeof fetch !== "function") return false;

  const payload = {
    chat_id: targetChatId,
    text: messageText,
    disable_web_page_preview: true,
  };
  const cleanThreadId = cleanText(threadId);
  if (cleanThreadId && /^\d+$/.test(cleanThreadId)) payload.message_thread_id = Number(cleanThreadId);
  if (parseMode) payload.parse_mode = parseMode;
  if (replyMarkup) payload.reply_markup = replyMarkup;

  try {
    const response = await fetch("https://api.telegram.org/bot" + token + "/sendMessage", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) return false;
    const body = await response.json().catch(() => null);
    return body?.ok === true;
  } catch {
    return false;
  }
}

async function sendPromptBlockMessage({ chatId, threadId, pluginConfig = {} }) {
  if (pluginConfig.promptBlockEnabled === false) return false;
  return sendTelegramTextMessage({
    chatId,
    threadId,
    text: formatPromptBlockHtml(),
    parseMode: "HTML",
    pluginConfig,
  });
}

function sendPromptBlockMessageLater(args) {
  const rawDelay = Number(args?.pluginConfig?.promptBlockDelayMs ?? 900);
  const delayMs = Number.isFinite(rawDelay) ? Math.max(0, rawDelay) : 900;
  setTimeout(() => {
    sendPromptBlockMessage(args).catch(() => {});
  }, delayMs);
}

function botInfoTargetFromBeforeDispatch(event = {}, ctx = {}) {
  const conversationId = cleanText(ctx.conversationId) || cleanText(event.conversationId);
  const ctxSession = telegramTargetFromSessionKey(ctx.sessionKey);
  const eventSession = telegramTargetFromSessionKey(event.sessionKey);
  return {
    chatId: telegramChatIdFromConversation(conversationId) || ctxSession.chatId || eventSession.chatId,
    threadId:
      cleanText(ctx.threadId) ||
      cleanText(event.threadId) ||
      threadIdFromConversation(conversationId) ||
      ctxSession.threadId ||
      eventSession.threadId,
  };
}

async function answerCallbackToast(ctx, pluginConfig, text) {
  const callbackQueryId = cleanText(ctx.callbackId);
  const token = resolveTelegramBotToken(pluginConfig);
  if (!callbackQueryId || !token || typeof fetch !== "function") return false;

  try {
    const response = await fetch("https://api.telegram.org/bot" + token + "/answerCallbackQuery", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        callback_query_id: callbackQueryId,
        text,
        show_alert: false,
        cache_time: 0,
      }),
    });
    if (!response.ok) return false;
    const body = await response.json().catch(() => null);
    return body?.ok === true;
  } catch {
    return false;
  }
}

function buildFeedbackButtons(newsId, counts) {
  return [[
    { text: "✅ " + counts.useful, callback_data: "useful:" + newsId },
    { text: "👎 " + counts.boring, callback_data: "boring:" + newsId },
    { text: "💬 " + counts.comments, callback_data: "comment:" + newsId },
  ]];
}

async function updateFeedbackButtons(ctx, dbPath, newsId) {
  if (typeof ctx.respond?.editButtons !== "function") return false;

  try {
    const counts = getFeedbackCounts({ dbPath, newsId });
    await ctx.respond.editButtons({ buttons: buildFeedbackButtons(newsId, counts) });
    return true;
  } catch {
    return false;
  }
}

async function sendForceReplyPrompt(ctx, pluginConfig, text) {
  const token = resolveTelegramBotToken(pluginConfig);
  const chatId = cleanText(ctx.callback?.chatId);
  if (!token || !chatId || typeof fetch !== "function") return false;

  const payload = {
    chat_id: chatId,
    text,
    disable_web_page_preview: true,
    reply_markup: {
      force_reply: true,
      input_field_placeholder: "Напиши комментарий",
    },
  };
  if (ctx.threadId) payload.message_thread_id = Number(ctx.threadId);
  if (ctx.callback?.messageId) payload.reply_to_message_id = Number(ctx.callback.messageId);

  try {
    const response = await fetch("https://api.telegram.org/bot" + token + "/sendMessage", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) return false;
    const body = await response.json().catch(() => null);
    return body?.ok === true;
  } catch {
    return false;
  }
}

async function updateFeedbackButtonsByMessage(pluginConfig, dbPath, pending) {
  const token = resolveTelegramBotToken(pluginConfig);
  const chatId = cleanText(pending?.callbackChatId);
  const messageId = Number(pending?.callbackMessageId);
  if (!token || !chatId || !Number.isInteger(messageId) || messageId <= 0 || typeof fetch !== "function") {
    return false;
  }

  try {
    const counts = getFeedbackCounts({ dbPath, newsId: pending.newsId });
    const response = await fetch("https://api.telegram.org/bot" + token + "/editMessageReplyMarkup", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        chat_id: chatId,
        message_id: messageId,
        reply_markup: { inline_keyboard: buildFeedbackButtons(pending.newsId, counts) },
      }),
    });
    if (!response.ok) return false;
    const body = await response.json().catch(() => null);
    return body?.ok === true;
  } catch {
    return false;
  }
}

function telegramChatIdFromConversation(value) {
  const conversation = cleanText(value);
  if (!conversation) return "";
  return conversation.split(":topic:")[0];
}

async function sendKnowledgeAckMessage(event, ctx, pluginConfig, text) {
  const token = resolveTelegramBotToken(pluginConfig);
  const chatId = telegramChatIdFromConversation(eventConversationId(event, ctx));
  const threadId = eventThreadId(event, ctx);
  if (!token || !chatId || !text || typeof fetch !== "function") return false;

  const payload = {
    chat_id: chatId,
    text,
    disable_web_page_preview: true,
  };
  if (threadId && /^\d+$/.test(threadId)) payload.message_thread_id = Number(threadId);

  try {
    const response = await fetch("https://api.telegram.org/bot" + token + "/sendMessage", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) return false;
    const body = await response.json().catch(() => null);
    return body?.ok === true;
  } catch {
    return false;
  }
}

export async function handleBotInfoCallback(ctx, pluginConfig = {}) {
  const data = cleanText(ctx.callback?.data);
  if (data !== "botinfo:summary") return { handled: false };

  await answerCallbackToast(ctx, pluginConfig, "Показываю справку.");
  const target = {
    chatId: ctx.callback?.chatId,
    threadId: ctx.threadId,
    pluginConfig,
  };
  const directSendEnabled = pluginConfig.botInfoDirectSendEnabled !== false;
  const summarySent = directSendEnabled
    ? await sendTelegramTextMessage({
        ...target,
        text: formatBotInfoSummary(pluginConfig),
      })
    : false;
  if (summarySent) {
    await sendPromptBlockMessage(target);
  } else {
    await ctx.respond.reply({ text: formatBotInfoSummary(pluginConfig) });
    sendPromptBlockMessageLater(target);
  }
  return { handled: true };
}

export async function handleFeedbackCallback(ctx, pluginConfig = {}) {
  const parsed = parseFeedbackCallback(ctx.callback?.data);
  if (!parsed) return { handled: false };

  const dbPath = resolveDbPath(pluginConfig);
  const pendingPath = resolvePendingPath(pluginConfig);
  const senderId = cleanText(ctx.senderId);
  const senderUsername = cleanText(ctx.senderUsername);

  if (!senderId) {
    await answerCallbackToast(ctx, pluginConfig, "Не смог определить пользователя.");
    await ctx.respond.reply({ text: "Не смог определить пользователя для сохранения оценки." });
    return { handled: true };
  }

  if (parsed.action === "comment") {
    const ok = rememberPendingComment({
      pendingPath,
      ttlMs: resolveCommentTtlMs(pluginConfig),
      newsId: parsed.newsId,
      accountId: ctx.accountId,
      conversationId: ctx.conversationId,
      senderId,
      senderUsername,
      callbackChatId: ctx.callback?.chatId,
      callbackMessageId: ctx.callback?.messageId,
      callbackThreadId: ctx.threadId,
    });

    if (!ok) {
      await answerCallbackToast(ctx, pluginConfig, "Не смог запомнить новость.");
      await ctx.respond.reply({ text: "Не смог запомнить новость для комментария." });
      return { handled: true };
    }

    let newsContext = null;
    try {
      newsContext = getNewsCommentContext({ dbPath, newsId: parsed.newsId });
    } catch {
      newsContext = null;
    }

    await answerCallbackToast(ctx, pluginConfig, "Ответь на сообщение бота комментарием.");
    const promptText = formatCommentPrompt(newsContext);
    const promptSent = await sendForceReplyPrompt(ctx, pluginConfig, promptText);
    if (!promptSent) await ctx.respond.reply({ text: promptText });
    return { handled: true };
  }

  try {
    const result = await saveFeedback({
      dbPath,
      newsId: parsed.newsId,
      userId: senderId,
      username: senderUsername,
      action: parsed.action,
    });
    const toastText = ACTION_TOASTS[parsed.action]?.[result.status] || "Оценка сохранена.";
    await updateFeedbackButtons(ctx, dbPath, parsed.newsId);
    await answerCallbackToast(ctx, pluginConfig, toastText);
  } catch (error) {
    const message = "Не смог сохранить оценку: " + (error instanceof Error ? error.message : String(error));
    await answerCallbackToast(ctx, pluginConfig, "Не смог сохранить оценку.");
    await ctx.respond.reply({ text: message });
  }

  return { handled: true };
}


function extractThreadId(ctx = {}) {
  return cleanText(ctx.threadId) || cleanText(ctx.conversationId).split(":topic:")[1] || "";
}

function getKnowledgeKindForThread(ctx = {}, pluginConfig = {}) {
  const threadId = extractThreadId(ctx);
  const metricsThreadId = cleanText(pluginConfig.metricsThreadId) || DEFAULT_METRICS_THREAD_ID;
  const methodologyThreadId = cleanText(pluginConfig.methodologyThreadId) || DEFAULT_METHODOLOGY_THREAD_ID;
  if (threadId && threadId === metricsThreadId) return "metrics";
  if (threadId && threadId === methodologyThreadId) return "methodology";
  return null;
}

function eventText(event = {}) {
  return cleanText(event.body ?? event.bodyForAgent ?? event.content ?? event.caption ?? event.text);
}

function eventSenderUsername(event = {}, ctx = {}) {
  return cleanText(event.senderUsername ?? event.metadata?.senderUsername ?? ctx.senderUsername);
}

function eventThreadId(event = {}, ctx = {}) {
  return cleanText(event.threadId) || extractThreadId(ctx) || cleanText(event.metadata?.threadId);
}

function eventConversationId(event = {}, ctx = {}) {
  return cleanText(event.conversationId) || cleanText(ctx.conversationId) || cleanText(event.to) || cleanText(event.metadata?.to);
}

function isGroupConversation(event = {}, ctx = {}) {
  const conversationId = eventConversationId(event, ctx);
  return conversationId.includes(":group:") || conversationId.includes(":topic:") || conversationId.startsWith("-100");
}

function eventMediaEntries(event = {}) {
  const metadata = event.metadata && typeof event.metadata === "object" ? event.metadata : {};
  const paths = [];
  const urls = [];
  const types = [];
  for (const value of [metadata.mediaPath, event.mediaPath]) if (cleanText(value)) paths.push(cleanText(value));
  for (const list of [metadata.mediaPaths, event.mediaPaths]) {
    if (Array.isArray(list)) for (const value of list) if (cleanText(value)) paths.push(cleanText(value));
  }
  for (const value of [metadata.mediaUrl, event.mediaUrl]) if (cleanText(value)) urls.push(cleanText(value));
  for (const list of [metadata.mediaUrls, event.mediaUrls]) {
    if (Array.isArray(list)) for (const value of list) if (cleanText(value)) urls.push(cleanText(value));
  }
  for (const value of [metadata.mediaType, event.mediaType]) if (cleanText(value)) types.push(cleanText(value));
  for (const list of [metadata.mediaTypes, event.mediaTypes]) {
    if (Array.isArray(list)) for (const value of list) if (cleanText(value)) types.push(cleanText(value));
  }

  const count = Math.max(paths.length, urls.length, types.length);
  const entries = [];
  for (let idx = 0; idx < count; idx += 1) {
    entries.push({
      path: paths[idx] || "",
      url: urls[idx] || "",
      mimeType: types[idx] || types[0] || "",
    });
  }
  return entries;
}


function isMediaPlaceholder(value) {
  return /^<media:[^>]+>$/.test(cleanText(value));
}

function findRecentInboundMedia(event = {}, maxAgeMs = 10 * 60 * 1000) {
  if (!existsSync(OPENCLAW_INBOUND_MEDIA_DIR)) return null;
  const timestamp = Number(event.timestamp || Date.now());
  const reference = Number.isFinite(timestamp) && timestamp > 0 ? timestamp : Date.now();
  try {
    const candidates = readdirSync(OPENCLAW_INBOUND_MEDIA_DIR)
      .map((name) => {
        const path = `${OPENCLAW_INBOUND_MEDIA_DIR}/${name}`;
        try {
          const stat = statSync(path);
          if (!stat.isFile()) return null;
          const age = Math.abs(stat.mtimeMs - reference);
          if (age > maxAgeMs) return null;
          return { path, mtimeMs: stat.mtimeMs, age };
        } catch {
          return null;
        }
      })
      .filter(Boolean)
      .sort((a, b) => a.age - b.age || b.mtimeMs - a.mtimeMs);
    return candidates[0] || null;
  } catch {
    return null;
  }
}

function extractFileText(filePath) {
  const path = cleanText(filePath);
  if (!path || !existsSync(path)) return { text: "", error: "file_not_found" };
  try {
    const raw = execFileSync("python3", [KNOWLEDGE_FILE_READER_PATH, path], {
      encoding: "utf8",
      timeout: 30_000,
      maxBuffer: 2 * 1024 * 1024,
    });
    const parsed = JSON.parse(raw);
    return { text: cleanText(parsed.text), error: cleanText(parsed.error) };
  } catch (error) {
    return { text: "", error: error instanceof Error ? error.message : String(error) };
  }
}


function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function fileSha256(filePath) {
  const path = cleanText(filePath);
  if (!path || !existsSync(path)) return "";
  try {
    return createHash("sha256").update(readFileSync(path)).digest("hex");
  } catch {
    return "";
  }
}

function normalizeSourceKey(fileName, sourceType = "text", kind = "knowledge") {
  const name = cleanText(fileName);
  if (name) {
    return name.replace(/---[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?=\.[^.]+$|$)/i, "");
  }
  return `${kind}:${sourceType}`;
}

function knowledgeSourceType(event = {}, text = "") {
  if (eventMediaEntries(event).length) return "file";
  const maybeFile = event.file || event.document || event.attachment || event.attachments;
  if (maybeFile) return "file";
  if (text) return "text";
  return "unknown";
}

function formatKnowledgeAck(kind, text, savedFiles = 0, fileErrors = [], duplicateFiles = 0, updatedFiles = 0) {
  const prefix = kind === "metrics" ? "Метрики принял." : "Методологию принял.";
  const shortText = truncateText(text, 96);
  const parts = [prefix];
  if (savedFiles > 0) parts.push(`Файлов прочитал: ${savedFiles}.`);
  if (duplicateFiles > 0) parts.push(`Дублей пропустил: ${duplicateFiles}.`);
  if (updatedFiles > 0) parts.push(`Новых версий: ${updatedFiles}.`);
  if (shortText) parts.push(shortText);
  if (fileErrors.length) parts.push(`Не прочитал файлов: ${fileErrors.length}.`);
  if (parts.length === 1) parts.push("Сообщение сохранил, но текста/файла в событии почти нет.");
  return parts.join("\n");
}

function saveKnowledgePayload({ event, ctx, pluginConfig, kind }) {
  const rawText = eventText(event);
  const baseText = isMediaPlaceholder(rawText) ? "" : rawText;
  const mediaEntries = eventMediaEntries(event);
  if (!mediaEntries.length && isMediaPlaceholder(rawText)) {
    const fallback = findRecentInboundMedia(event);
    if (fallback?.path) mediaEntries.push({ path: fallback.path, url: "", mimeType: rawText.slice(7, -1) });
  }
  const threadId = eventThreadId(event, ctx);
  const conversationId = eventConversationId(event, ctx);
  const senderId = cleanText(event.senderId) || cleanText(ctx.senderId);
  const username = eventSenderUsername(event, ctx);
  const fileErrors = [];
  let savedFiles = 0;
  let duplicateFiles = 0;
  let updatedFiles = 0;
  let combinedText = baseText;

  if (baseText || !mediaEntries.length) {
    saveKnowledgeDocument({
      dbPath: resolveDbPath(pluginConfig),
      kind,
      threadId,
      conversationId,
      senderId,
      username,
      sourceType: knowledgeSourceType(event, baseText),
      contentText: baseText,
      raw: { event, ctx },
      sourceKey: normalizeSourceKey("", "text", kind),
      contentHash: sha256(baseText),
    });
  }

  for (const media of mediaEntries) {
    const extracted = extractFileText(media.path);
    const fileName = media.path ? basename(media.path) : "telegram-file";
    const saveResult = saveKnowledgeDocument({
      dbPath: resolveDbPath(pluginConfig),
      kind,
      threadId,
      conversationId,
      senderId,
      username,
      sourceType: "file",
      fileName,
      mimeType: media.mimeType,
      contentText: extracted.text,
      raw: { media, error: extracted.error, event, ctx },
      sourceKey: normalizeSourceKey(fileName, "file", kind),
      contentHash: fileSha256(media.path) || sha256(extracted.text || fileName),
    });
    if (saveResult?.status === "duplicate") duplicateFiles += 1;
    if (saveResult?.status === "updated") updatedFiles += 1;
    if (extracted.text) {
      savedFiles += 1;
      combinedText = [combinedText, extracted.text].filter(Boolean).join("\n");
    } else {
      fileErrors.push(extracted.error || fileName);
    }
  }

  return { text: combinedText, savedFiles, duplicateFiles, updatedFiles, fileErrors };
}

export async function handleKnowledgeMessage(event, ctx, pluginConfig = {}) {
  if (event.channel !== "telegram") return;

  const text = eventText(event);
  if (isTopicIdRequest(text) || isBotInfoRequest(text) || isMetricsInfoRequest(text)) return;

  const kind = getKnowledgeKindForThread(ctx, pluginConfig);
  if (!kind) return;

  try {
    const saved = saveKnowledgePayload({ event, ctx, pluginConfig, kind });
    const ackText = formatKnowledgeAck(kind, saved.text, saved.savedFiles, saved.fileErrors, saved.duplicateFiles, saved.updatedFiles);
    await sendKnowledgeAckMessage(event, ctx, pluginConfig, ackText);
    return {
      handled: true,
      text: ackText,
    };
  } catch (error) {
    return {
      handled: true,
      text: "Не смог сохранить знание: " + (error instanceof Error ? error.message : String(error)),
    };
  }
}

export async function handleKnowledgeInboundClaim(event, ctx, pluginConfig = {}) {
  if (event.channel !== "telegram") return;

  const text = eventText(event);
  if (isTopicIdRequest(text) || isBotInfoRequest(text) || isMetricsInfoRequest(text)) return;

  const threadId = eventThreadId(event, ctx);
  const metricsThreadId = cleanText(pluginConfig.metricsThreadId) || DEFAULT_METRICS_THREAD_ID;
  const methodologyThreadId = cleanText(pluginConfig.methodologyThreadId) || DEFAULT_METHODOLOGY_THREAD_ID;
  const kind = threadId === metricsThreadId ? "metrics" : threadId === methodologyThreadId ? "methodology" : null;
  if (!kind) return;

  try {
    const saved = saveKnowledgePayload({ event, ctx, pluginConfig, kind });
    const ackText = formatKnowledgeAck(kind, saved.text, saved.savedFiles, saved.fileErrors, saved.duplicateFiles, saved.updatedFiles);
    await sendKnowledgeAckMessage(event, ctx, pluginConfig, ackText);
    return {
      handled: true,
      reply: { text: ackText },
    };
  } catch (error) {
    return {
      handled: true,
      reply: { text: "Не смог сохранить знание: " + (error instanceof Error ? error.message : String(error)) },
    };
  }
}

export async function handleBotInfoRequest(event, ctx, pluginConfig = {}) {
  if (event.channel !== "telegram") return;
  const text = event.body ?? event.content;

  if (isTopicIdRequest(text)) {
    const threadId = cleanText(ctx.threadId) || cleanText(ctx.conversationId).split(":topic:")[1] || "нет thread_id";
    return {
      handled: true,
      text: "thread_id этой темы: " + threadId,
    };
  }

  if (!isBotInfoRequest(text)) return;

  const target = botInfoTargetFromBeforeDispatch(event, ctx);
  const summary = formatBotInfoSummary(pluginConfig);
  const directSendEnabled = pluginConfig.botInfoDirectSendEnabled !== false;
  const summarySent = directSendEnabled
    ? await sendTelegramTextMessage({ ...target, text: summary, pluginConfig })
    : false;
  if (summarySent) {
    await sendPromptBlockMessage({ ...target, pluginConfig });
    return { handled: true };
  }

  sendPromptBlockMessageLater({ ...target, pluginConfig });
  return {
    handled: true,
    text: summary,
  };
}

export async function handlePendingComment(event, ctx, pluginConfig = {}) {
  if (event.channel !== "telegram") return;

  const pending = consumePendingComment({
    pendingPath: resolvePendingPath(pluginConfig),
    accountId: ctx.accountId,
    conversationId: ctx.conversationId,
    senderId: ctx.senderId,
  });
  if (!pending) return;

  const comment = cleanCommentText(event.body ?? event.content);
  if (!comment) {
    return {
      handled: true,
      text: "Комментарий пустой, поэтому я его не сохранил.",
    };
  }

  try {
    const dbPath = resolveDbPath(pluginConfig);
    await saveFeedback({
      dbPath,
      newsId: pending.newsId,
      userId: ctx.senderId,
      username: pending.senderUsername,
      action: "comment",
      comment,
    });

    let newsContext = null;
    try {
      newsContext = getNewsCommentContext({ dbPath, newsId: pending.newsId });
    } catch {
      newsContext = null;
    }
    await updateFeedbackButtonsByMessage(pluginConfig, dbPath, pending);

    return {
      handled: true,
      text: formatSavedCommentText(newsContext),
    };
  } catch (error) {
    return {
      handled: true,
      text: "Не смог сохранить комментарий: " + (error instanceof Error ? error.message : String(error)),
    };
  }
}
