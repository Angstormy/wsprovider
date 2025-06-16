import logging
import os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
)

# Load token from environment variable
TOKEN = '7523409542:AAGlQI94jLTKoAhTZwIoZhv99b-9L5nfCu4'

# Admin Telegram User ID (replace with your own)
ADMIN_ID = 1908801848 # 🔁 Replace this with your Telegram user ID

# In-memory storage
whitelist = set()
user_boss_map = {}

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot is running...")

# /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📋 Available Commands:\n"
        "/sendtoboss - Reply to a message to send it to your boss\n"
        "/status - Check your boss assignment\n"
        "🔐 Admin Commands:\n"
        "/adduser <user_id>\n"
        "/removeuser <user_id>\n"
        "/setboss <user_id> <boss_id>\n"
        "/listusers"
    )
    await update.message.reply_text(help_text)

# /status
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in user_boss_map:
        await update.message.reply_text(f"✅ Your boss is set to: {user_boss_map[uid]}")
    else:
        await update.message.reply_text("❌ You do not have a boss assigned yet.")

# /sendtoboss
async def send_to_boss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in whitelist:
        await update.message.reply_text("🚫 You are not authorized to use this bot.")
        return

    boss_id = user_boss_map.get(uid)
    if not boss_id:
        await update.message.reply_text("❌ No boss assigned to you.")
        return

    if update.message.reply_to_message:
        await context.bot.copy_message(
            chat_id=boss_id,
            from_chat_id=update.effective_chat.id,
            message_id=update.message.reply_to_message.message_id
        )
        await update.message.reply_text("✅ Message forwarded to your boss.")
    else:
        await update.message.reply_text("ℹ️ Please reply to a message you want to send.")

# Admin-only: /adduser
async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /adduser <user_id>")
        return
    try:
        user_id = int(context.args[0])
        whitelist.add(user_id)
        await update.message.reply_text(f"✅ User {user_id} added to whitelist.")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")

# Admin-only: /removeuser
async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /removeuser <user_id>")
        return
    try:
        user_id = int(context.args[0])
        whitelist.discard(user_id)
        user_boss_map.pop(user_id, None)
        await update.message.reply_text(f"🗑️ User {user_id} removed.")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")

# Admin-only: /setboss
async def set_boss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /setboss <user_id> <boss_id>")
        return
    try:
        user_id = int(context.args[0])
        boss_id = int(context.args[1])
        user_boss_map[user_id] = boss_id
        await update.message.reply_text(f"✅ Boss {boss_id} assigned to user {user_id}.")
    except ValueError:
        await update.message.reply_text("❌ Invalid IDs.")

# Admin-only: /listusers
async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not whitelist:
        await update.message.reply_text("Whitelist is empty.")
        return
    lines = [f"👤 {uid} → 👨‍💼 {user_boss_map.get(uid, 'Not assigned')}" for uid in whitelist]
    await update.message.reply_text("\n".join(lines))

# Main entrypoint
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("sendtoboss", send_to_boss))

    # Admin Commands
    app.add_handler(CommandHandler("adduser", add_user))
    app.add_handler(CommandHandler("removeuser", remove_user))
    app.add_handler(CommandHandler("setboss", set_boss))
    app.add_handler(CommandHandler("listusers", list_users))

    app.run_polling()

if __name__ == "__main__":
    main()
