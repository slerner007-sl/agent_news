import {
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import { DatabaseSync } from "node:sqlite";

const DEFAULT_DB_PATH = "/home/user1/gosb_bot/data/news_bot.db";
const DEFAULT_PENDING_PATH = "/home/user1/gosb_bot/data/openclaw_feedback_pending.json";
const DEFAULT_COMMENT_TTL_MS = 10 * 60 * 1000;

function nonEmptyString(value) {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

export function resolveDbPath(pluginConfig = {}) {
  return nonEmptyString(pluginConfig.dbPath) ?? process.env.GOSB_NEWS_DB ?? DEFAULT_DB_PATH;
}

export function resolvePendingPath(pluginConfig = {}) {
  return (
    nonEmptyString(pluginConfig.pendingPath) ??
    process.env.GOSB_FEEDBACK_PENDING ??
    DEFAULT_PENDING_PATH
  );
}

export function resolveCommentTtlMs(pluginConfig = {}) {
  const value = Number(pluginConfig.commentTtlMs);
  return Number.isFinite(value) && value >= 10_000 ? Math.trunc(value) : DEFAULT_COMMENT_TTL_MS;
}

export function parseFeedbackCallback(data) {
  const text = nonEmptyString(data);
  if (!text) return null;

  const separator = text.indexOf(":");
  if (separator <= 0 || separator === text.length - 1) return null;

  const action = text.slice(0, separator).trim();
  const rawNewsId = text.slice(separator + 1).trim();
  if (!["useful", "boring", "comment"].includes(action)) return null;
  if (!/^[0-9]+$/.test(rawNewsId)) return null;

  return {
    action,
    newsId: Number(rawNewsId),
  };
}

export async function saveFeedback({ dbPath, newsId, userId, username, action, comment }) {
  if (!Number.isInteger(newsId) || newsId <= 0) {
    throw new Error("Invalid news id");
  }
  if (!["useful", "boring", "comment"].includes(action)) {
    throw new Error("Invalid feedback action");
  }

  const db = new DatabaseSync(dbPath);
  try {
    db.exec("PRAGMA busy_timeout = 5000");
    const row = db
      .prepare("SELECT gosb_id FROM sent_news WHERE news_id = ? ORDER BY sent_at DESC LIMIT 1")
      .get(newsId);
    const gosbId = row && typeof row === "object" ? row.gosb_id : null;
    const normalizedUserId = String(userId ?? "");

    if (action === "useful" || action === "boring") {
      const existing = db
        .prepare(
          `
          SELECT id, action
          FROM feedback
          WHERE news_id = ?
            AND user_id = ?
            AND action IN ('useful', 'boring')
          ORDER BY id DESC
          LIMIT 1
          `,
        )
        .get(newsId, normalizedUserId);

      if (existing && typeof existing === "object") {
        if (existing.action === action) {
          return { status: "duplicate", action };
        }

        db.prepare(
          `
          UPDATE feedback
          SET gosb_id = ?,
              username = ?,
              action = ?,
              comment = NULL,
              created_at = datetime('now')
          WHERE id = ?
          `,
        ).run(gosbId ?? null, String(username ?? ""), action, existing.id);
        return { status: "updated", previousAction: existing.action, action };
      }
    }

    db.prepare(
      `
      INSERT INTO feedback (gosb_id, news_id, user_id, username, action, comment)
      VALUES (?, ?, ?, ?, ?, ?)
      `,
    ).run(
      gosbId ?? null,
      newsId,
      normalizedUserId,
      String(username ?? ""),
      action,
      comment ? String(comment) : null,
    );
  } finally {
    db.close();
  }

  return { status: "inserted", action };
}

function pendingKey({ accountId, conversationId, senderId }) {
  const account = nonEmptyString(accountId) ?? "default";
  const conversation = nonEmptyString(conversationId);
  const sender = nonEmptyString(senderId);
  if (!conversation || !sender) return null;
  return `${account}\u0000${conversation}\u0000${sender}`;
}

function conversationBase(value) {
  const text = nonEmptyString(value);
  if (!text) return "";
  return text.split(":topic:")[0];
}

function findPendingKey(state, params) {
  const exact = pendingKey(params);
  if (exact && state[exact]) return exact;

  const account = nonEmptyString(params.accountId) ?? "default";
  const conversation = nonEmptyString(params.conversationId);
  const sender = nonEmptyString(params.senderId);
  if (!sender) return null;

  const base = conversationBase(conversation);
  let best = null;
  for (const [key, entry] of Object.entries(state)) {
    if (!entry || typeof entry !== "object") continue;
    if ((nonEmptyString(entry.accountId) ?? "default") !== account) continue;
    if (nonEmptyString(entry.senderId) !== sender) continue;

    const entryConversation = nonEmptyString(entry.conversationId);
    const entryBase = conversationBase(entryConversation);
    const sameConversation = conversation && entryConversation === conversation;
    const sameBaseConversation = base && entryBase === base;
    if (!sameConversation && !sameBaseConversation) continue;

    if (!best || Number(entry.createdAt ?? 0) > Number(best.entry.createdAt ?? 0)) {
      best = { key, entry };
    }
  }
  return best?.key ?? null;
}

function readPendingFile(filePath) {
  try {
    if (!existsSync(filePath)) return {};
    const parsed = JSON.parse(readFileSync(filePath, "utf8"));
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

function writePendingFile(filePath, state) {
  mkdirSync(path.dirname(filePath), { recursive: true });
  const tmpPath = `${filePath}.${process.pid}.tmp`;
  writeFileSync(tmpPath, `${JSON.stringify(state, null, 2)}\n`, { mode: 0o600 });
  renameSync(tmpPath, filePath);
}

export function rememberPendingComment(params) {
  const key = pendingKey(params);
  if (!key) return false;

  const pendingPath = params.pendingPath ?? DEFAULT_PENDING_PATH;
  const state = readPendingFile(pendingPath);
  const now = params.now ?? Date.now();
  state[key] = {
    newsId: params.newsId,
    accountId: nonEmptyString(params.accountId) ?? "default",
    conversationId: params.conversationId,
    senderId: params.senderId,
    senderUsername: params.senderUsername ?? "",
    createdAt: now,
    expiresAt: now + (params.ttlMs ?? DEFAULT_COMMENT_TTL_MS),
  };
  writePendingFile(pendingPath, state);
  return true;
}

export function consumePendingComment(params) {
  const pendingPath = params.pendingPath ?? DEFAULT_PENDING_PATH;
  const state = readPendingFile(pendingPath);
  const key = findPendingKey(state, params);
  if (!key) return null;

  const entry = state[key];
  if (!entry || typeof entry !== "object") return null;

  delete state[key];
  writePendingFile(pendingPath, state);

  const now = params.now ?? Date.now();
  if (typeof entry.expiresAt === "number" && entry.expiresAt < now) return null;
  if (!Number.isInteger(entry.newsId) || entry.newsId <= 0) return null;
  return entry;
}
