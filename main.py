import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
)

# Bot token and admin ID
TOKEN = '7523409542:AAGlQI94jLTKoAhTZwIoZhv99b-9L5nfCu4'  # 🔁 Replace this!
ADMIN_ID = 1908801848

# In-memory data
whitelist = set()
user_boss_map = {}
awaiting_message = {}  # Tracks users in continuous forwarding mode

# Logging
logging.basicConfig(level=logging.INFO)

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot is running...")

# /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📋 Available Commands:\n"
        "/sendtoboss - Start forwarding all your messages to your boss\n"
        "/stopforward - Stop forwarding\n"
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
    boss_id = user_boss_map.get(uid)
    if boss_id:
        await update.message.reply_text(f"✅ Your boss is set to: {boss_id}")
    else:
        await update.message.reply_text("❌ No boss assigned.")

# /sendtoboss - activate continuous forwarding
async def send_to_boss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in whitelist:
        await update.message.reply_text("🚫 You are not authorized.")
        return

    if uid not in user_boss_map:
        await update.message.reply_text("❌ No boss assigned.")
        return

    awaiting_message[uid] = True
    await update.message.reply_text("📨 Forwarding mode is ON. All your messages will be sent to your boss.\nType /stopforward to stop.")

# /stopforward - stop forwarding mode
async def stop_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if awaiting_message.get(uid):
        awaiting_message.pop(uid)
        await update.message.reply_text("🛑 Forwarding stopped.")
    else:
        await update.message.reply_text("ℹ️ You are not in forwarding mode.")

# Handles all messages: forward if user is in forwarding mode
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if awaiting_message.get(uid):
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
            logging.error(f"Forwarding failed: {e}")
            await update.message.reply_text("⚠️ Failed to forward.")
    else:
        return  # Not in forwarding mode

# Admin: /adduser
async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /adduser <user_id>")
        return
    try:
        uid = int(context.args[0])
        whitelist.add(uid)
        await update.message.reply_text(f"✅ Added user {uid} to whitelist.")
    except:
        await update.message.reply_text("❌ Invalid user ID.")

# Admin: /removeuser
async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /removeuser <user_id>")
        return
    try:
        uid = int(context.args[0])
        whitelist.discard(uid)
        user_boss_map.pop(uid, None)
        awaiting_message.pop(uid, None)
        await update.message.reply_text(f"🗑️ Removed user {uid}.")
    except:
        await update.message.reply_text("❌ Invalid user ID.")

# Admin: /setboss
async def set_boss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /setboss <user_id> <boss_id>")
        return
    try:
        uid = int(context.args[0])
        bid = int(context.args[1])
        user_boss_map[uid] = bid
        await update.message.reply_text(f"✅ Assigned boss {bid} to user {uid}.")
    except:
        await update.message.reply_text("❌ Invalid IDs.")

# Admin: /listusers
async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not whitelist:
        await update.message.reply_text("Whitelist is empty.")
        return
    lines = [f"👤 {uid} → 👨‍💼 {user_boss_map.get(uid, 'No boss')}" for uid in whitelist]
    await update.message.reply_text("\n".join(lines))

# Main entry
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("sendtoboss", send_to_boss))
    app.add_handler(CommandHandler("stopforward", stop_forward))
    app.add_handler(CommandHandler("adduser", add_user))
    app.add_handler(CommandHandler("removeuser", remove_user))
    app.add_handler(CommandHandler("setboss", set_boss))
    app.add_handler(CommandHandler("listusers", list_users))

    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == "__main__":
    main()
