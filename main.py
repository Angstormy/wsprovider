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
awaiting_message = {}  # Tracks users who ran /sendtoboss

# Logging
logging.basicConfig(level=logging.INFO)

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot is running...")

# /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📋 Available Commands:\n"
        "/sendtoboss - Send next message to boss (text, image, file, etc)\n"
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

# /sendtoboss (enters awaiting state)
async def send_to_boss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in whitelist:
        await update.message.reply_text("🚫 You are not authorized.")
        return

    if uid not in user_boss_map:
        await update.message.reply_text("❌ No boss assigned.")
        return

    awaiting_message[uid] = True
    await update.message.reply_text("📨 Now send the message or file you want to forward to your boss.")

# Handles all incoming messages to check if user is awaiting
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if awaiting_message.get(uid):
        boss_id = user_boss_map.get(uid)
        if not boss_id:
            await update.message.reply_text("❌ No boss assigned.")
            return

        # Forward/copy the full message (regardless of type)
        try:
            await context.bot.copy_message(
                chat_id=boss_id,
                from_chat_id=update.effective_chat.id,
                message_id=update.message.message_id
            )
            await update.message.reply_text("✅ Message forwarded to your boss.")
        except Exception as e:
            logging.error(f"Failed to forward: {e}")
            await update.message.reply_text("⚠️ Failed to forward the message.")
        finally:
            awaiting_message.pop(uid, None)
    else:
        return  # ignore if not awaiting

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

# Main
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("sendtoboss", send_to_boss))
    app.add_handler(CommandHandler("adduser", add_user))
    app.add_handler(CommandHandler("removeuser", remove_user))
    app.add_handler(CommandHandler("setboss", set_boss))
    app.add_handler(CommandHandler("listusers", list_users))

    # Message handler for forwarding (text + all media)
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == "__main__":
    main()
