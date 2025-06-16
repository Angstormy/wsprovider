import logging
import re
from rapidfuzz import fuzz
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# Setup
TOKEN = '7523409542:AAGlQI94jLTKoAhTZwIoZhv99b-9L5nfCu4'  # Replace with actual token
ADMIN_ID = 1908801848

# In-memory data
whitelist = set()
user_boss_map = {}
awaiting_message = {}

logging.basicConfig(level=logging.INFO)


# 🔒 Check if message reveals identity
def is_suspicious(message: str, user: Update.effective_user) -> bool:
    msg = message.lower()

    keywords = [
        "my name is", "this is", "i am", "me is", "i'm",
        "username", "uid", "nm", "name:"
    ]

    for word in keywords:
        if word in msg:
            return True

    user_info = [user.first_name or "", user.username or "", str(user.id)]
    for info in user_info:
        if info:
            for word in info.lower().split():
                if fuzz.partial_ratio(word, msg) > 80:
                    return True

    return False


# 🔰 /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    name = user.first_name or "User"

    if uid == ADMIN_ID:
        text = f"👑 Welcome {name}, you are the *Admin*.\nYou can manage users and their assignments."
        buttons = [[InlineKeyboardButton("📋 List Users", callback_data="list_users")]]
    elif uid in user_boss_map.values():
        text = f"🧑‍💼 Welcome {name}, you are a *Boss*.\nEmployees assigned to you will send messages here."
        buttons = []
    elif uid in whitelist:
        text = f"🧑‍🔧 Hello {name}, you are an *Employee*.\nUse the bot only for work communication.\nPress below to start."
        buttons = [[
            InlineKeyboardButton("📨 Start Forwarding", callback_data="start_forward"),
            InlineKeyboardButton("🛑 Stop Forwarding", callback_data="stop_forward")
        ]]
    else:
        text = "🚫 You are not authorized to use this bot.\nPlease contact the Admin."
        buttons = []

    markup = InlineKeyboardMarkup(buttons) if buttons else None
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)


# 📥 Forward message or flag
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id

    if awaiting_message.get(uid):
        boss_id = user_boss_map.get(uid)
        if not boss_id:
            await update.message.reply_text("❌ No boss assigned.")
            return

        message_text = update.message.text or ""

        if is_suspicious(message_text, user):
            await update.message.reply_text("⚠️ Message blocked due to policy violation.")
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🚨 Suspicious message blocked from {uid}:\n\n{message_text}"
            )
            return

        try:
            await context.bot.copy_message(
                chat_id=boss_id,
                from_chat_id=update.effective_chat.id,
                message_id=update.message.message_id
            )
            await update.message.reply_text("✅ Sent to boss.")
        except Exception as e:
            logging.error(f"Forwarding error: {e}")
            await update.message.reply_text("⚠️ Could not forward message.")
    else:
        await update.message.reply_text("ℹ️ You're not in forwarding mode.")


# /status
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    boss_id = user_boss_map.get(uid)
    if boss_id:
        masked = str(boss_id)[:2] + "****" + str(boss_id)[-2:]
        await update.message.reply_text(f"✅ Boss assigned: {masked}")
    else:
        await update.message.reply_text("❌ No boss assigned.")


# ⚙️ Admin-only command
def is_admin(uid: int):
    return uid == ADMIN_ID


# 🔘 Handle Inline Button Clicks
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()

    if query.data == "start_forward":
        if uid in whitelist:
            if uid not in user_boss_map:
                await query.edit_message_text("❌ No boss assigned.")
                return
            awaiting_message[uid] = True
            await query.edit_message_text("📨 Forwarding mode is ON.")
        else:
            await query.edit_message_text("🚫 You are not authorized.")
    elif query.data == "stop_forward":
        if awaiting_message.pop(uid, None):
            await query.edit_message_text("🛑 Forwarding stopped.")
        else:
            await query.edit_message_text("ℹ️ Forwarding is not active.")
    elif query.data == "list_users":
        if not is_admin(uid):
            return
        text = "\n".join(
            [f"👤 {uid} → 👨‍💼 {user_boss_map.get(uid, 'No boss')}" for uid in whitelist]
        ) or "📭 No whitelisted users."
        await query.edit_message_text(text)


# 🔐 Admin commands
async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /adduser <user_id>")
        return
    try:
        uid = int(context.args[0])
        whitelist.add(uid)
        await update.message.reply_text(f"✅ Added {uid} to whitelist.")
    except:
        await update.message.reply_text("❌ Invalid ID.")


async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /removeuser <user_id>")
        return
    try:
        uid = int(context.args[0])
        whitelist.discard(uid)
        user_boss_map.pop(uid, None)
        awaiting_message.pop(uid, None)
        await update.message.reply_text(f"🗑 Removed user {uid}.")
    except:
        await update.message.reply_text("❌ Invalid ID.")


async def set_boss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /setboss <user_id> <boss_id>")
        return
    try:
        uid, bid = int(context.args[0]), int(context.args[1])
        user_boss_map[uid] = bid
        await update.message.reply_text(f"✅ Set boss {bid} for user {uid}.")
    except:
        await update.message.reply_text("❌ Invalid IDs.")


# /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📋 Commands:\n"
        "/start - Role-based welcome\n"
        "/status - Show boss\n"
        "/sendtoboss - Start forwarding\n"
        "/stopforward - Stop forwarding\n\n"
        "🔐 Admin Commands:\n"
        "/adduser <id>\n/removeuser <id>\n/setboss <uid> <bid>"
    )
    await update.message.reply_text(text)


# Main
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("adduser", add_user))
    app.add_handler(CommandHandler("removeuser", remove_user))
    app.add_handler(CommandHandler("setboss", set_boss))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()


if __name__ == "__main__":
    main()
