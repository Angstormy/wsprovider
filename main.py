import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from rapidfuzz import fuzz

TOKEN = '7523409542:AAGlQI94jLTKoAhTZwIoZhv99b-9L5nfCu4'  # Replace with your bot token
ADMIN_ID = 1908801848     # Replace with your own Telegram ID

# In-memory data
whitelist = set()
user_boss_map = {}
awaiting_message = {}

# Logging
logging.basicConfig(level=logging.INFO)

# Keywords to detect identity leaks
SUSPICIOUS_KEYWORDS = [
    "my name", "this is", "i am", "myself", "contact me", "reach me",
    "username", "user id", "uid", "my id", "nm is", "name is"
]

def is_suspicious(message: str, user) -> bool:
    message = message.lower()
    name_parts = (user.first_name or "").lower().split()
    if user.last_name:
        name_parts += user.last_name.lower().split()
    username = (user.username or '').lower()
    uid_str = str(user.id)

    # Check for direct UID or username
    if uid_str in message or username in message:
        return True

    # Check fuzzy name match
    for part in name_parts:
        if part and fuzz.partial_ratio(part, message) > 85:
            return True

    # Check for suspicious keywords
    for keyword in SUSPICIOUS_KEYWORDS:
        if keyword in message:
            return True

    return False

def get_main_buttons(uid):
    buttons = []
    if uid == ADMIN_ID:
        buttons = [
            [InlineKeyboardButton("➕ Add User", callback_data="admin_add")],
            [InlineKeyboardButton("❌ Remove User", callback_data="admin_remove")],
            [InlineKeyboardButton("👨‍💼 Set Boss", callback_data="admin_setboss")],
            [InlineKeyboardButton("📋 List Users", callback_data="admin_list")]
        ]
    elif uid in user_boss_map.values():
        buttons = [[InlineKeyboardButton("ℹ️ You are a Boss. No actions available.", callback_data="noop")]]
    elif uid in whitelist:
        buttons = [
            [InlineKeyboardButton("📤 Start Forwarding", callback_data="start_forward")],
            [InlineKeyboardButton("🛑 Stop Forwarding", callback_data="stop_forward")],
            [InlineKeyboardButton("📊 Check Status", callback_data="check_status")]
        ]
    return InlineKeyboardMarkup(buttons)

async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text("🔘 Choose an action:", reply_markup=get_main_buttons(uid))

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    name = user.first_name or "User"

    if uid == ADMIN_ID:
        text = f"👑 Welcome {name} (Admin)! You can manage users and bosses."
    elif uid in user_boss_map.values():
        text = f"🤵 Hello {name}! You are a *Boss*. Messages from your employees will arrive here."
    elif uid in whitelist:
        text = f"👋 Welcome {name}! You are an *Employee*. Use the buttons below to forward messages to your boss."
    else:
        text = f"🚫 Hello {name}, you are not authorized. Please contact the admin."
        await update.message.reply_text(text)
        return

    await update.message.reply_text(text, parse_mode="Markdown")
    await send_main_menu(update, context)

# Callback handler for inline buttons
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()

    if query.data == "admin_add":
        await query.edit_message_text("✏️ Use /adduser <user_id> to add a user.")
    elif query.data == "admin_remove":
        await query.edit_message_text("🗑️ Use /removeuser <user_id> to remove a user.")
    elif query.data == "admin_setboss":
        await query.edit_message_text("🧩 Use /setboss <user_id> <boss_id> to assign a boss.")
    elif query.data == "admin_list":
        users = [f"👤 {u} ➔ 👨‍💼 {user_boss_map.get(u, 'None')}" for u in whitelist]
        await query.edit_message_text("\n".join(users) or "No users in whitelist.")

    elif query.data == "start_forward":
        if uid not in whitelist:
            await query.edit_message_text("❌ You are not allowed to forward messages.")
        elif uid not in user_boss_map:
            await query.edit_message_text("⚠️ You have no boss assigned.")
        else:
            awaiting_message[uid] = True
            await query.edit_message_text("✅ Forwarding started. All your messages will go to your boss.")
    elif query.data == "stop_forward":
        awaiting_message.pop(uid, None)
        await query.edit_message_text("🛑 Forwarding stopped.")
    elif query.data == "check_status":
        bid = user_boss_map.get(uid)
        if bid:
            masked = str(bid)[:2] + "****" + str(bid)[-2:]
            await query.edit_message_text(f"👨‍💼 Your boss ID is: {masked}")
        else:
            await query.edit_message_text("❌ No boss assigned.")
    else:
        await query.edit_message_text("ℹ️ No action.")

    # After response, show menu again
    await context.bot.send_message(chat_id=uid, text="🔘 Main Menu:", reply_markup=get_main_buttons(uid))

# Message handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    message_text = update.message.text or ""

    if awaiting_message.get(uid):
        if is_suspicious(message_text, user):
            await update.message.reply_text("🚨 Message blocked due to sensitive content.")
            await context.bot.send_message(
                ADMIN_ID,
                f"⚠️ Suspicious message from {uid} blocked:\n\n{message_text}"
            )
            return

        boss_id = user_boss_map.get(uid)
        if boss_id:
            try:
                await context.bot.copy_message(
                    chat_id=boss_id,
                    from_chat_id=update.effective_chat.id,
                    message_id=update.message.message_id
                )
                await update.message.reply_text("📨 Message forwarded to your boss.")
            except Exception as e:
                logging.error(f"Failed to forward message: {e}")
                await update.message.reply_text("⚠️ Failed to forward message.")
        else:
            await update.message.reply_text("⚠️ No boss assigned.")

# Admin commands
async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        uid = int(context.args[0])
        whitelist.add(uid)
        await update.message.reply_text(f"✅ User {uid} added to whitelist.")
    except:
        await update.message.reply_text("❌ Usage: /adduser <user_id>")

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        uid = int(context.args[0])
        whitelist.discard(uid)
        awaiting_message.pop(uid, None)
        user_boss_map.pop(uid, None)
        await update.message.reply_text(f"🗑️ User {uid} removed.")
    except:
        await update.message.reply_text("❌ Usage: /removeuser <user_id>")

async def set_boss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        uid = int(context.args[0])
        bid = int(context.args[1])
        user_boss_map[uid] = bid
        await update.message.reply_text(f"👨‍💼 Boss {bid} assigned to user {uid}.")
    except:
        await update.message.reply_text("❌ Usage: /setboss <user_id> <boss_id>")

# App entry
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("adduser", add_user))
    app.add_handler(CommandHandler("removeuser", remove_user))
    app.add_handler(CommandHandler("setboss", set_boss))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == "__main__":
    main()
