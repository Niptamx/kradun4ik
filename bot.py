import os
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)
from telethon import TelegramClient, events
from dotenv import load_dotenv
import asyncio

load_dotenv()

# Налаштування
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
SOURCE_CHANNEL = os.getenv("SOURCE_CHANNEL")  # без @
DEST_CHANNEL = os.getenv("DEST_CHANNEL")      # з @
CONFIRM_CHAT_ID = int(os.getenv("CONFIRM_CHAT_ID"))  # ID групи
AUTO_POST = {"enabled": False}
TEMP_MESSAGES = {}

# Telethon клієнт
client = TelegramClient("anon", API_ID, API_HASH)

# Telegram Bot
app = ApplicationBuilder().token(BOT_TOKEN).build()

def get_keyboard(post_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Опублікувати", callback_data=f"approve:{post_id}"),
            InlineKeyboardButton("📝 Редагувати", callback_data=f"edit:{post_id}"),
            InlineKeyboardButton("❌ Відхилити", callback_data=f"reject:{post_id}")
        ],
        [
            InlineKeyboardButton("🔁 Авто-публікація: " + ("Увімкнена ✅" if AUTO_POST["enabled"] else "Вимкнена ❌"),
                                 callback_data="toggle_auto")
        ]
    ])

@client.on(events.NewMessage(chats=SOURCE_CHANNEL))
async def handler(event):
    text = event.raw_text
    media = event.media

    # Якщо авто-постинг увімкнено
    if AUTO_POST["enabled"]:
        if media:
            await event.download_media("temp")
            await app.bot.send_document(chat_id=DEST_CHANNEL, document=open("temp", "rb"), caption=text or "")
            os.remove("temp")
        else:
            await app.bot.send_message(chat_id=DEST_CHANNEL, text=text)
        return

    # Зберігаємо тимчасово
    TEMP_MESSAGES[event.id] = {"text": text, "media": media}
    await app.bot.send_message(
        chat_id=CONFIRM_CHAT_ID,
        text=f"Новий пост із @{SOURCE_CHANNEL}:

{text}",
        reply_markup=get_keyboard(event.id)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "toggle_auto":
        AUTO_POST["enabled"] = not AUTO_POST["enabled"]
        await query.edit_message_reply_markup(reply_markup=get_keyboard("dummy"))
        return

    action, msg_id = data.split(":")
    msg_id = int(msg_id)
    message_data = TEMP_MESSAGES.get(msg_id)

    if not message_data:
        await query.edit_message_text("⛔ Пост не знайдено або вже оброблений.")
        return

    if action == "approve":
        if message_data["media"]:
            await client.download_media(await client.get_messages(SOURCE_CHANNEL, ids=msg_id), "temp")
            await context.bot.send_document(chat_id=DEST_CHANNEL, document=open("temp", "rb"), caption=message_data["text"] or "")
            os.remove("temp")
        else:
            await context.bot.send_message(chat_id=DEST_CHANNEL, text=message_data["text"])
        await query.edit_message_text("✅ Пост опубліковано.")
        TEMP_MESSAGES.pop(msg_id)

    elif action == "reject":
        await query.edit_message_text("❌ Пост відхилено.")
        TEMP_MESSAGES.pop(msg_id)

    elif action == "edit":
        await query.edit_message_text("✍️ Надішли новий текст поста.")
        context.user_data["editing"] = msg_id

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_id = context.user_data.get("editing")
    if msg_id is not None and msg_id in TEMP_MESSAGES:
        TEMP_MESSAGES[msg_id]["text"] = update.message.text
        await update.message.reply_text("✅ Текст оновлено. Натисни 'Опублікувати' ще раз.")
        context.user_data["editing"] = None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Бот працює. Очікую пости.")

# Обробники
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

# Запуск
async def main():
    await client.start()
    await app.initialize()
    await app.start()
    print("🤖 Бот запущено.")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())