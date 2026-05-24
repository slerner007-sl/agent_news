import {
  consumePendingComment,
  parseFeedbackCallback,
  rememberPendingComment,
  resolveCommentTtlMs,
  resolveDbPath,
  resolvePendingPath,
  saveFeedback,
} from "./feedback-store.js";

const ACTION_LABELS = {
  useful: "Полезно",
  boring: "Неинтересно",
};

function cleanText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function cleanCommentText(value) {
  return cleanText(value).replace(/(^|\s)@agent_ler_bot\b[:,\s-]*/gi, "$1").trim();
}

async function clearButtonsQuietly(ctx) {
  try {
    await ctx.respond.clearButtons();
  } catch {
    // Telegram can reject button edits for older or already edited messages.
  }
}

export async function handleFeedbackCallback(ctx, pluginConfig = {}) {
  const parsed = parseFeedbackCallback(ctx.callback?.data);
  if (!parsed) return { handled: false };

  const dbPath = resolveDbPath(pluginConfig);
  const pendingPath = resolvePendingPath(pluginConfig);
  const senderId = cleanText(ctx.senderId);
  const senderUsername = cleanText(ctx.senderUsername);

  if (!senderId) {
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
    });

    if (!ok) {
      await ctx.respond.reply({ text: "Не смог запомнить новость для комментария." });
      return { handled: true };
    }

    await clearButtonsQuietly(ctx);
    await ctx.respond.reply({
      text: "Ответь reply на это сообщение комментарием. Если не сохранится, напиши в чат: @agent_ler_bot твой комментарий.",
    });
    return { handled: true };
  }

  try {
    await saveFeedback({
      dbPath,
      newsId: parsed.newsId,
      userId: senderId,
      username: senderUsername,
      action: parsed.action,
    });
    await clearButtonsQuietly(ctx);
    await ctx.respond.reply({ text: `${ACTION_LABELS[parsed.action]} — спасибо за оценку.` });
  } catch (error) {
    await ctx.respond.reply({
      text: `Не смог сохранить оценку: ${error instanceof Error ? error.message : String(error)}`,
    });
  }

  return { handled: true };
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
    await saveFeedback({
      dbPath: resolveDbPath(pluginConfig),
      newsId: pending.newsId,
      userId: ctx.senderId,
      username: pending.senderUsername,
      action: "comment",
      comment,
    });
    return {
      handled: true,
      text: "Комментарий сохранен. Спасибо, это пойдет в обучение агента.",
    };
  } catch (error) {
    return {
      handled: true,
      text: `Не смог сохранить комментарий: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}
