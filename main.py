import logging
import re
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
)
from rapidfuzz import fuzz

# Bot token and admin ID
TOKEN = '7523409542:AAGlQI94jLTKoAhTZwIoZhv99b-9L5nfCu4'  # Replace this with your actual token
ADMIN_ID = 1908801848     # Replace with your Telegram user ID

# In-memory data
whitelist = set()
user_boss_map = {}
awaiting_message = {}

# Logging
logging.basicConfig(level=logging.INFO)

# Suspicious patterns
SUSPICIOUS_PATTERNS = [
    r"\\bmy name is\\b",
    r"\\bi am\\b",
    r"\\bthis is\\b",
    r"\\bmy username\\b",
    r"\\buser id\\b",
    r"\\bid is\\b",
    r"\\bcontact me\\b",
    r"\\bmessage me\\b"
]

# Function to detect suspicious content
def is_suspicious(message: str, name: str, username: str, uid: int) -> (bool, str):
    message_lower = message.lower()

    for pattern in SUSPICIOUS_PATTERNS:
        if re.search(pattern, message_lower):
            return True, "Suspicious phrase detected"

    name_parts = name.lower().split()
    for part in name_parts:
        if fuzz.partial_ratio(part, message_lower) > 80:
            return True, f"Fuzzy name match: '{part}'"

    if username and fuzz.partial_ratio(username.lower(), message_lower) > 80:
        return True, "Fuzzy username match"

    if str(uid) in message_lower:
        return True, "User ID detected"

    return False, ""

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    name = user.first_name or "User"

    if uid == ADMIN_ID:
        await update.message.reply_text(f"\U0001F451 Welcome {name} (Admin)!\n\U0001F527 You can manage users, assign bosses, and monitor the bot.")
    elif uid in user_boss_map.values():
        await update.message.reply_text(f"\U0001F44B Welcome {name}!\n\U0001F4E5 You are a *Boss*. You will receive messages from your assigned employees here.", parse_mode="Markdown")
    elif uid in whitelist:
        await update.message.reply_text(f"\U0001F44B Welcome {name}!\n\u2705 You are an *Employee*. Use /help to get started.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"\U0001F44B Hello {name}, you are not authorized to use this bot.\n\u274C Please contact the Admin.")

# /help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "\U0001F4CB Available Commands:\n"
        "/sendtoboss - Start forwarding messages to your boss\n"
        "/stopforward - Stop forwarding\n"
        "/status - Check boss assignment\n"
        "\U0001F510 Admin Commands:\n"
        "/adduser <user_id>\n"
        "/removeuser <user_id>\n"
        "/setboss <user_id> <boss_id>\n"
        "/listusers"
    )

# /status command
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    boss_id = user_boss_map.get(uid)
    if boss_id:
        masked = str(boss_id)[:2] + "****" + str(boss_id)[-2:]
        await update.message.reply_text(f"\u2705 Your boss is set to: {masked}")
    else:
        await update.message.reply_text("\u274C No boss assigned.")

# /sendtoboss command
async def send_to_boss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in whitelist:
        await update.message.reply_text("\U0001F6AB You are not authorized.")
        return
    if uid not in user_boss_map:
        await update.message.reply_text("\u274C No boss assigned.")
        return
    awaiting_message[uid] = True
    await update.message.reply_text("\U0001F4E8 Forwarding mode is ON. Type /stopforward to stop.")

# /stopforward command
async def stop_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if awaiting_message.get(uid):
        awaiting_message.pop(uid)
        await update.message.reply_text("\U0001F6D1 Forwarding stopped.")
    else:
        await update.message.reply_text("\u2139 You are not in forwarding mode.")

# Message handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = update.effective_user.first_name or ""
    username = update.effective_user.username or ""
    message_text = update.message.text or ""

    if awaiting_message.get(uid):
        boss_id = user_boss_map.get(uid)
        if not boss_id:
            await update.message.reply_text("\u274C No boss assigned.")
            return

        suspicious, reason = is_suspicious(message_text, name, username, uid)
        if suspicious:
            await update.message.reply_text("\U0001F6AB Message blocked (sensitive info detected). Not forwarded.")
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"\U0001F6A8 *Blocked Message Alert!*\n"
                    f"\U0001F464 From: {name} (ID: {uid}, @{username})\n"
                    f"\u274C Reason: {reason}\n"
                    f"\U0001F4DD Message:\n{message_text}"
                ),
                parse_mode="Markdown"
            )
            return

        try:
            await context.bot.copy_message(
                chat_id=boss_id,
                from_chat_id=update.effective_chat.id,
                message_id=update.message.message_id
            )
            await update.message.reply_text("\u2705 Forwarded to your boss.")
        except Exception as e:
            logging.error(f"Forwarding failed: {e}")
            await update.message.reply_text("\u26A0 Failed to forward.")

# Admin commands
async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /adduser <user_id>")
        return
    try:
        uid = int(context.args[0])
        whitelist.add(uid)
        await update.message.reply_text(f"\u2705 Added user {uid} to whitelist.")
    except:
        await update.message.reply_text("\u274C Invalid user ID.")

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
        await update.message.reply_text(f"\U0001F5D1 Removed user {uid}.")
    except:
        await update.message.reply_text("\u274C Invalid user ID.")

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
        await update.message.reply_text(f"\u2705 Assigned boss {bid} to user {uid}.")
    except:
        await update.message.reply_text("\u274C Invalid IDs.")

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not whitelist:
        await update.message.reply_text("Whitelist is empty.")
        return
    lines = [f"\U0001F464 {uid} → \U0001F468‍\U0001F4BC {user_boss_map.get(uid, 'No boss')}" for uid in whitelist]
    await update.message.reply_text("\n".join(lines))

# Main app
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
