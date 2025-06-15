import logging
import os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes
)
from functools import wraps

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory storage (non-persistent)
user_boss_map = {}          # user_id → boss_id
last_status = {}            # user_id → last sent status
whitelisted_users = set()   # user_ids allowed to use bot
ADMINS = {123456789}        # Replace with your own Telegram user ID

# --- Decorators ---
def check_whitelist(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id in ADMINS or user_id in whitelisted_users:
            return await func(update, context)
        await update.message.reply_text("❌ Access denied. You are not authorized to use this bot.")
    return wrapper

def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id in ADMINS:
            return await func(update, context)
        await update.message.reply_text("❌ Only bot admins can use this command.")
    return wrapper

# --- Commands ---
@check_whitelist
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Welcome to the Boss Bot!\n"
        "You can:\n"
        "📤 Use /sendtoboss by replying to a message\n"
        "ℹ️ Use /status to check your last sent message\n"
        "❓ Use /help to view all available commands"
    )

@check_whitelist
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 User Commands:\n"
        "/sendtoboss – Forward replied message to your boss\n"
        "/status – Show status of last sent message\n"
        "🔒 Admin Commands:\n"
        "/setboss <user_id> <boss_id> – Link or update a user's boss\n"
        "/resetboss <user_id> – Unlink a user's boss\n"
        "/allow <user_id> – Whitelist a user\n"
        "/remove <user_id> – Remove user from whitelist\n"
        "/listusers – List all whitelisted users"
    )

@check_whitelist
async def sendtoboss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not update.message.reply_to_message:
        await update.message.reply_text("❗ Please reply to a message and use /sendtoboss.")
        return

    if user_id not in user_boss_map:
        await update.message.reply_text("❌ No boss assigned to you. Contact the admin.")
        return

    boss_id = user_boss_map[user_id]
    try:
        forwarded = await context.bot.forward_message(
            chat_id=boss_id,
            from_chat_id=update.message.reply_to_message.chat_id,
            message_id=update.message.reply_to_message.message_id
        )
        await update.message.reply_text("✅ Message sent to your boss.")
        last_status[user_id] = f"Delivered (Message ID: {forwarded.message_id})"
    except Exception as e:
        logger.error(f"Forwarding failed: {e}")
        await update.message.reply_text("❌ Failed to forward message.")
        last_status[user_id] = "Failed"

@check_whitelist
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    status = last_status.get(user_id, "No messages sent yet.")
    await update.message.reply_text(f"📄 Last Status: {status}")

# --- Admin-only Commands ---
@admin_only
async def setboss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2 or not all(arg.isdigit() for arg in context.args):
        await update.message.reply_text("❗ Usage: /setboss <user_id> <boss_id>")
        return

    user_id = int(context.args[0])
    boss_id = int(context.args[1])
    user_boss_map[user_id] = boss_id
    await update.message.reply_text(f"✅ Boss for user {user_id} set to {boss_id}.")

@admin_only
async def resetboss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("❗ Usage: /resetboss <user_id>")
        return

    user_id = int(context.args[0])
    if user_id in user_boss_map:
        del user_boss_map[user_id]
        await update.message.reply_text(f"🗑️ Boss link for user {user_id} has been removed.")
    else:
        await update.message.reply_text("⚠️ This user has no boss linked.")

@admin_only
async def allow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("❗ Usage: /allow <user_id>")
        return

    user_id = int(context.args[0])
    whitelisted_users.add(user_id)
    await update.message.reply_text(f"✅ User {user_id} added to whitelist.")

@admin_only
async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("❗ Usage: /remove <user_id>")
        return

    user_id = int(context.args[0])
    if user_id in whitelisted_users:
        whitelisted_users.remove(user_id)
        await update.message.reply_text(f"🗑️ User {user_id} removed from whitelist.")
    else:
        await update.message.reply_text("⚠️ User was not in whitelist.")

@admin_only
async def listusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not whitelisted_users:
        await update.message.reply_text("⚠️ No users in whitelist.")
    else:
        users = '\n'.join(str(uid) for uid in sorted(whitelisted_users))
        await update.message.reply_text(f"✅ Whitelisted Users:\n{users}")

# --- Main Bot Launcher ---
if __name__ == "__main__":
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        raise RuntimeError("❌ BOT_TOKEN environment variable not set!")

    app = ApplicationBuilder().token(TOKEN).build()

    # User commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("sendtoboss", sendtoboss))
    app.add_handler(CommandHandler("status", status))

    # Admin commands
    app.add_handler(CommandHandler("setboss", setboss))
    app.add_handler(CommandHandler("resetboss", resetboss))
    app.add_handler(CommandHandler("allow", allow))
    app.add_handler(CommandHandler("remove", remove))
    app.add_handler(CommandHandler("listusers", listusers))

    print("🤖 Bot is running...")
    app.run_polling()
