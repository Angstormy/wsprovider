import logging
import re
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
)

# Bot token and admin ID
TOKEN = 'YOUR_BOT_TOKEN'  # 🔁 Replace this!
ADMIN_ID = 1908801848     # 🔁 Replace with your Telegram ID

# In-memory data
whitelist = set()
user_boss_map = {}
awaiting_message = {}

# Logging
logging.basicConfig(level=logging.INFO)

# Utility: generate fuzzy keyword variants
def get_fuzzy_keywords(name, username, uid):
    parts = name.lower().split()
    name_variants = set()
    for part in parts:
        name_variants.add(part)
        if len(part) > 3:
            name_variants.add(part[:3])
    if username:
        name_variants.add(username.lower())
    name_variants.add(str(uid))
    return name_variants

# Utility: suspicious phrases
SUSPICIOUS_PATTERNS = [
    r"\bmy name is\b",
    r"\bi am\b",
    r"\bthis is\b",
    r"\bmy username\b",
    r"\buser id\b",
    r"\bid is\b",
    r"\bcontact me\b",
    r"\bmessage me\b"
]

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    name = user.first_name or "User"

    if uid == ADMIN_ID:
        await update.message.reply_text(
            f"👑 Welcome {name} (Admin)!\n"
            f"🔧 You can manage users, assign bosses, and monitor the bot."
        )
    elif uid in user_boss_map.values():
        await update.message.reply_text(
            f"👋 Welcome {name}!\n"
            f"📥 You are a *Boss*. You will receive messages from your assigned employees here.",
            parse_mode="Markdown"
        )
    elif uid in whitelist:
        await update.message.reply_text(
            f"👋 Welcome {name}!\n"
            f"✅ You are an *Employee*. Use this bot only for work-related message forwarding.\n"
            f"Use /help to get started.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"👋 Hello {name}, you are not authorized to use this bot.\n"
            f"❌ Please contact the Admin to get access."
        )

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
        masked = str(boss_id)[:2] + "****" + str(boss_id)[-2:]
        await update.message.reply_text(f"✅ Your boss is set to: {masked}")
    else:
        await update.message.reply_text("❌ No boss assigned.")

# /sendtoboss
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

# /stopforward
async def stop_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if awaiting_message.get(uid):
        awaiting_message.pop(uid)
        await update.message.reply_text("🛑 Forwarding stopped.")
    else:
        await update.message.reply_text("ℹ️ You are not in forwarding mode.")

# 🚨 handle_message: with full validation
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = (update.effective_user.first_name or "").lower()
    username = (update.effective_user.username or "").lower()
    message_text = (update.message.text or "").lower()

    if awaiting_message.get(uid):
        boss_id = user_boss_map.get(uid)
        if not boss_id:
            await update.message.reply_text("❌ No boss assigned.")
            return

        # 🚨 Check for identity or suspicious phrases
        keywords = get_fuzzy_keywords(name, username, uid)
        matched_keywords = [kw for kw in keywords if kw in message_text]

        suspicious_match = any(re.search(p, message_text) for p in SUSPICIOUS_PATTERNS)

        if matched_keywords or suspicious_match:
            await update.message.reply_text("🚫 Message contains personal identity info. It was NOT forwarded.")
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"🚨 *Blocked Message Attempt!*\n"
                    f"👤 From: {name} (ID: {uid}, @{username})\n"
                    f"🛑 Reason: {'Suspicious phrase' if suspicious_match else 'Keyword match'}\n"
                    f"📝 Message:\n{update.message.text}"
                ),
                parse_mode="Markdown"
            )
            return

        # ✅ Forward valid message
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

# Entry point
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
