import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# === CONFIG ===
TOKEN = "7523409542:AAGlQI94jLTKoAhTZwIoZhv99b-9L5nfCu4"  # Replace with your bot token
ADMIN_ID = 1908801848       # Replace with your Telegram ID

# === DATA ===
whitelist = set()
user_boss_map = {}
awaiting_message = {}
conversation_state = {}
last_bot_message = {}

# === LOGGING ===
logging.basicConfig(level=logging.INFO)

# === UTILITIES ===

def role_keyboard(uid):
    if uid == ADMIN_ID:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add User", callback_data="add_user")],
            [InlineKeyboardButton("❌ Remove User", callback_data="remove_user")],
            [InlineKeyboardButton("👔 Assign Boss", callback_data="assign_boss")],
            [InlineKeyboardButton("📄 List Users", callback_data="list_users")]
        ])
    elif uid in user_boss_map.values():
        return InlineKeyboardMarkup([[InlineKeyboardButton("👑 You are a Boss", callback_data="noop")]])
    elif uid in whitelist:
        return employee_keyboard()
    else:
        return None

def employee_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Send to Boss", callback_data="start_forward")],
        [InlineKeyboardButton("🛑 Stop Forwarding", callback_data="stop_forward")],
        [InlineKeyboardButton("📊 My Status", callback_data="status")]
    ])

async def update_reply_markup(uid, context: ContextTypes.DEFAULT_TYPE):
    old_msg_id = last_bot_message.get(uid)
    if old_msg_id:
        try:
            await context.bot.edit_message_reply_markup(chat_id=uid, message_id=old_msg_id, reply_markup=None)
        except:
            pass

# === COMMAND HANDLERS ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    await update_reply_markup(uid, context)

    if uid == ADMIN_ID:
        msg = f"👑 Welcome Admin {user.first_name}!"
    elif uid in user_boss_map.values():
        msg = f"👋 Hello Boss {user.first_name}, your employees' messages will appear here."
    elif uid in whitelist:
        msg = f"👋 Welcome {user.first_name}! Use buttons below to manage messages to your boss."
    else:
        msg = "⛔ You are not authorized to use this bot."

    reply_markup = role_keyboard(uid)
    sent = await update.message.reply_text(msg, reply_markup=reply_markup)
    last_bot_message[uid] = sent.message_id

# === CALLBACK BUTTON HANDLER ===

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data
    await update_reply_markup(uid, context)

    if uid != ADMIN_ID and data.startswith(("add_", "remove_", "assign_")):
        return

    msg = "❌ Unknown action."
    if data == "add_user":
        conversation_state[uid] = "await_add_user"
        msg = "🔢 Send the Telegram ID to add."
    elif data == "remove_user":
        conversation_state[uid] = "await_remove_user"
        msg = "❌ Send the Telegram ID to remove."
    elif data == "assign_boss":
        conversation_state[uid] = "await_employee"
        msg = "👤 Send Employee's Telegram ID."
    elif data == "list_users":
        if whitelist:
            msg = "\n".join([f"👤 {u} → 👨‍💼 {user_boss_map.get(u, '❓')}" for u in whitelist])
        else:
            msg = "📂 No users found."
    elif data == "start_forward":
        awaiting_message[uid] = True
        msg = "📤 Now forwarding messages to your boss."
    elif data == "stop_forward":
        awaiting_message.pop(uid, None)
        msg = "🛑 Stopped forwarding."
    elif data == "status":
        boss_id = user_boss_map.get(uid)
        msg = f"👨‍💼 Your boss is {boss_id}" if boss_id else "❌ No boss assigned."

    sent = await query.message.reply_text(msg, reply_markup=role_keyboard(uid))
    last_bot_message[uid] = sent.message_id

# === ADMIN TEXT HANDLER ===

async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    state = conversation_state.get(uid)

    if uid != ADMIN_ID or not state:
        return

    if state == "await_add_user":
        try:
            new_id = int(text)
            whitelist.add(new_id)
            await update.message.reply_text(f"✅ Added user {new_id}")
        except:
            await update.message.reply_text("❌ Invalid user ID.")
        conversation_state.pop(uid)

    elif state == "await_remove_user":
        try:
            rem_id = int(text)
            whitelist.discard(rem_id)
            user_boss_map.pop(rem_id, None)
            await update.message.reply_text(f"✅ Removed user {rem_id}")
        except:
            await update.message.reply_text("❌ Invalid ID.")
        conversation_state.pop(uid)

    elif state == "await_employee":
        try:
            emp_id = int(text)
            conversation_state[uid] = ("await_boss", emp_id)
            await update.message.reply_text("👨‍💼 Send Boss ID.")
        except:
            await update.message.reply_text("❌ Invalid employee ID.")

    elif isinstance(state, tuple) and state[0] == "await_boss":
        emp_id = state[1]
        try:
            boss_id = int(text)
            user_boss_map[emp_id] = boss_id
            await update.message.reply_text(f"✅ Assigned Boss {boss_id} to Employee {emp_id}")
        except:
            await update.message.reply_text("❌ Invalid boss ID.")
        conversation_state.pop(uid)

# === SUSPICIOUS FILTER ===

def is_suspicious(text, user):
    terms = ["my name", "this is", "i am", "username", "contact"]
    return any(term in text.lower() for term in terms)

# === MESSAGE HANDLER ===

async def handle_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = update.effective_user

    if uid == ADMIN_ID and uid in conversation_state:
        await handle_admin_text(update, context)
        return

    if uid not in whitelist or not awaiting_message.get(uid):
        return

    boss_id = user_boss_map.get(uid)
    if not boss_id:
        await update.message.reply_text("❌ You don't have a boss assigned.")
        return

    suspicious = update.message.text and is_suspicious(update.message.text, user)
    if suspicious:
        await update.message.reply_text("⚠️ Suspicious message blocked.")
        await context.bot.send_message(ADMIN_ID, f"🚫 Suspicious message from {uid}: {update.message.text}")
        return

    try:
        await update_reply_markup(uid, context)

        if update.message.text:
            await context.bot.send_message(boss_id, f"📨 From {uid}: {update.message.text}")
        else:
            await context.bot.copy_message(chat_id=boss_id, from_chat_id=uid, message_id=update.message.message_id)

        sent = await update.message.reply_text("✅ Sent to boss.", reply_markup=employee_keyboard())
        last_bot_message[uid] = sent.message_id

    except Exception as e:
        await update.message.reply_text("❌ Failed to send.")
        logging.error(str(e))

# === MAIN ===

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ALL, handle_all))
    app.run_polling()

if __name__ == "__main__":
    main()
