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

# === COMMAND ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await send_role_message(uid, context)

# === BUTTON HANDLER ===

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
        msg = "👤 Send Employee ID to assign boss."
    elif data == "list_users":
        if whitelist:
            msg = "\n".join([f"👤 {u} → 👨‍💼 {user_boss_map.get(u, '❓')}" for u in whitelist])
        else:
            msg = "📂 No users found."
    elif data == "start_forward":
        awaiting_message[uid] = True
        msg = "📤 Forwarding enabled."
    elif data == "stop_forward":
        awaiting_message.pop(uid, None)
        msg = "🛑 Forwarding stopped."
    elif data == "status":
        boss = user_boss_map.get(uid)
        msg = f"👨‍💼 Boss: {boss}" if boss else "❌ No boss assigned."

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
            awaiting_message.pop(rem_id, None)
            await update.message.reply_text(f"✅ Removed user {rem_id}")
        except:
            await update.message.reply_text("❌ Invalid ID.")
        conversation_state.pop(uid)

    elif state == "await_employee":
        try:
            emp_id = int(text)
            conversation_state[uid] = ("await_boss", emp_id)
            await update.message.reply_text("👨‍💼 Now send the Boss ID.")
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

# === HELPER TO SEND ROLE MESSAGE ===

async def send_role_message(uid, context):
    await update_reply_markup(uid, context)
    keyboard = role_keyboard(uid)

    if uid == ADMIN_ID:
        text = "👑 You are Admin."
    elif uid in user_boss_map.values():
        text = "👔 You are a Boss."
    elif uid in whitelist:
        text = "👋 Welcome! Use buttons below."
    else:
        text = "⛔ You're not authorized."
        keyboard = None

    sent = await context.bot.send_message(uid, text, reply_markup=keyboard)
    last_bot_message[uid] = sent.message_id

# === SUSPICIOUS CHECK ===

def is_suspicious(text, user):
    terms = ["my name", "this is", "username", str(user.id), user.username or ""]
    return any(term.lower() in text.lower() for term in terms if term)

# === MESSAGE HANDLER ===

async def handle_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = update.effective_user

    if uid == ADMIN_ID and uid in conversation_state:
        await handle_admin_text(update, context)
        return

    # Auto show buttons for whitelisted user who never used /start
    if uid in whitelist and uid not in last_bot_message:
        await send_role_message(uid, context)
        return

    # Skip unapproved users
    if uid not in whitelist:
        return

    if not awaiting_message.get(uid):
        return

    boss_id = user_boss_map.get(uid)
    if not boss_id:
        await update.message.reply_text("❌ No boss assigned.")
        return

    if update.message.text and is_suspicious(update.message.text, user):
        await update.message.reply_text("⚠️ Suspicious message blocked.")
        await context.bot.send_message(ADMIN_ID, f"🚨 Suspicious from {uid}:\n{update.message.text}")
        return

    try:
        await update_reply_markup(uid, context)

        if update.message.text:
            await context.bot.send_message(boss_id, f"📨 From {uid}: {update.message.text}")
        else:
            await context.bot.copy_message(chat_id=boss_id, from_chat_id=uid, message_id=update.message.message_id)

        sent = await update.message.reply_text("✅ Message sent.", reply_markup=employee_keyboard())
        last_bot_message[uid] = sent.message_id

    except Exception as e:
        await update.message.reply_text("❌ Failed to forward.")
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
