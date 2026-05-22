"""
bot_handler.py — обработчик кнопок обратной связи
Запускается отдельно: python3 bot_handler.py
"""

import logging
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8655293057:AAEeSNZLenovxgQq-XLGewz7wBNAcBAJhRo"
DB_PATH = "/home/user1/gosb_bot/data/news_bot.db"

logging.basicConfig(level=logging.INFO)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def save_feedback(news_id: int, user_id: str, username: str, action: str, comment: str = None):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO feedback (news_id, user_id, username, action, comment)
            VALUES (?, ?, ?, ?, ?)
        """, (news_id, user_id, username, action, comment))


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data  # формат: "useful:123", "boring:123", "comment:123"
    action, news_id = data.split(":")
    news_id = int(news_id)
    user_id = str(query.from_user.id)
    username = query.from_user.username or query.from_user.first_name

    if action == "comment":
        # Просим написать комментарий
        context.user_data["awaiting_comment"] = news_id
        await query.message.reply_text(
            "✍️ Напиши свой комментарий к этой новости — он поможет улучшить агента:"
        )
        return

    save_feedback(news_id, user_id, username, action)

    labels = {"useful": "✅ Полезно", "boring": "👎 Неинтересно"}
    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text(f"{labels.get(action, action)} — спасибо за оценку!")


async def handle_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    news_id = context.user_data.get("awaiting_comment")
    if not news_id:
        return

    user_id = str(update.message.from_user.id)
    username = update.message.from_user.username or update.message.from_user.first_name
    comment = update.message.text

    save_feedback(news_id, user_id, username, "comment", comment)
    context.user_data.pop("awaiting_comment", None)

    await update.message.reply_text("💾 Комментарий сохранён — спасибо!")


def build_keyboard(news_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Полезно", callback_data=f"useful:{news_id}"),
        InlineKeyboardButton("👎 Неинтересно", callback_data=f"boring:{news_id}"),
        InlineKeyboardButton("💬 Комментарий", callback_data=f"comment:{news_id}"),
    ]])


if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_comment))
    print("🤖 Обработчик кнопок запущен...")
    app.run_polling()
