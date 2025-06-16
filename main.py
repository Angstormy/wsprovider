import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)
import re
from rapidfuzz import fuzz

# Bot token and admin ID
TOKEN = '7523409542:AAGlQI94jLTKoAhTZwIoZhv99b-9L5nfCu4'  # Replace with your bot token
ADMIN_ID = 1908801848     # Replace with your Telegram ID

# In-memory data
whitelist = set()
user_boss_map = {}
awaiting_message = {}

# Logging
logging.basicConfig(level=logging.INFO)

def get_buttons_for_user(uid):
    if uid == ADMIN_ID:
        return [[InlineKeyboardButton("📋 List Users", callback_data="list_users")]]
    elif uid in user_boss_map.values():
        return [[InlineKeyboardButton("🔁 View Forwarded Messages", callback_data="noop")]]
    elif uid in whitelist:
        return [
            [InlineKeyboardButton("📨 Start Forwarding", callback_data="start_forward")],
            [InlineKeyboardButton("🛑 Stop Forwarding", callback_data="stop_forward")],
            [InlineKeyboardButton("ℹ️ Status", callback_data="status")]
        ]
    else:
        return []

def suspicious_message(text: str, name: str, username: str, uid: int) -> bool:
    text = text.lower()
    keywords = ["my name is", "i am", "username", "id is", "my id", "handle"]
    for k in keywords:
        if k in text:
            return True
    fields = [name.lower(), username.lower() if username else "", str(uid)]
    for field in fields:
        if not field:
            continue
        for word in re.findall(r'\w+', text):
            if fuzz.partial_ratio(word, field) > 85:
                return True
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    name = user.first_name or "User"
    buttons = get_buttons_for_user(uid)

    if uid == ADMIN_ID:
        text = f"👑 Welcome {name}, you are the *Admin*."
    elif uid in user_boss_map.values():
        text = f"🧑‍💼 Welcome {name}, you are a *Boss*. Messages from employees will appear here."
    elif uid in whitelist:
        text = f"🧑‍🔧 Hello {name}, you are an *Employee*. Use the buttons below to start sending work updates to your boss."
    else:
        text = "🚫 You are not authorized to use this bot."

    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    buttons = get_buttons_for_user(uid)

    if query.data == "list_users" and uid == ADMIN_ID:
        lines = [f"👤 {u} → 👨‍💼 {user_boss_map.get(u, 'No boss')}" for u in whitelist]
        await query.edit_message_text("\n".join(lines) or "No users yet.", reply_markup=InlineKeyboardMarkup(buttons))
    elif query.data == "start_forward":
        if uid in whitelist:
            if uid not in user_boss_map:
                await query.edit_message_text("❌ No boss assigned.", reply_markup=InlineKeyboardMarkup(buttons))
            else:
                awaiting_message[uid] = True
                await query.edit_message_text("✅ Forwarding enabled.", reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await query.edit_message_text("🚫 You are not authorized.", reply_markup=InlineKeyboardMarkup(buttons))
    elif query.data == "stop_forward":
        awaiting_message.pop(uid, None)
        await query.edit_message_text("🛑 Forwarding stopped.", reply_markup=InlineKeyboardMarkup(buttons))
    elif query.data == "status":
        boss_id = user_boss_map.get(uid)
        if boss_id:
            masked = str(boss_id)[:2] + "****" + str(boss_id)[-2:]
            await query.edit_message_text(f"📊 Your boss is: {masked}", reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await query.edit_message_text("❌ No boss assigned.", reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await query.edit_message_text("ℹ️ Feature not implemented.", reply_markup=InlineKeyboardMarkup(buttons))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = update.effective_user.first_name or ""
    username = update.effective_user.username or ""
    text = update.message.text or update.message.caption or ""

    if awaiting_message.get(uid):
        if suspicious_message(text, name, username, uid):
            await context.bot.send_message(ADMIN_ID, f"⚠️ Suspicious message from {uid} blocked:
{text}")
            await update.message.reply_text("❌ Message blocked for revealing personal info.")
            return
        boss_id = user_boss_map.get(uid)
        if not boss_id:
            await update.message.reply_text("❌ No boss assigned.")
            return
        try:
            await context.bot.copy_message(
                chat_id=boss_id,
                from_chat_id=update.effective_chat.id,
                message_id=update.message.message_id
            )
            await update.message.reply_text("✅ Forwarded to your boss.")
        except Exception as e:
            logging.error(e)
            await update.message.reply_text("⚠️ Failed to forward.")

# Admin Commands
async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /adduser <user_id>")
        return
    uid = int(context.args[0])
    whitelist.add(uid)
    await update.message.reply_text(f"✅ Added user {uid}.")

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    uid = int(context.args[0])
    whitelist.discard(uid)
    user_boss_map.pop(uid, None)
    awaiting_message.pop(uid, None)
    await update.message.reply_text(f"🗑️ Removed user {uid}.")

async def set_boss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /setboss <user_id> <boss_id>")
        return
    uid, bid = int(context.args[0]), int(context.args[1])
    user_boss_map[uid] = bid
    await update.message.reply_text(f"✅ Boss {bid} assigned to user {uid}.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("adduser", add_user))
    app.add_handler(CommandHandler("removeuser", remove_user))
    app.add_handler(CommandHandler("setboss", set_boss))

    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == "__main__":
    main()
