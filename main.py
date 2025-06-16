import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# === CONFIG ===
TOKEN = "7523409542:AAGlQI94jLTKoAhTZwIoZhv99b-9L5nfCu4"  # Replace this
ADMIN_ID = 1908801848     # Replace with your Telegram ID

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
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("👑 You are a Boss", callback_data="noop")]
        ])
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

# === HANDLERS ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    name = user.first_name or "User"
    await update_reply_markup(uid, context)

    if uid == ADMIN_ID:
        msg = f"👑 Welcome {name} (Admin)!\nUse buttons below to manage."
    elif uid in user_boss_map.values():
        msg = f"📥 Welcome {name}, Boss!\nYou will receive your employee messages here."
    elif uid in whitelist:
        msg = f"👋 Welcome {name}!\nUse this bot to forward work messages to your boss."
    else:
        msg = f"⛔ Hello {name}, you're not authorized to use this bot."

    reply_markup = role_keyboard(uid)
    sent = await update.message.reply_text(msg, reply_markup=reply_markup)
    last_bot_message[uid] = sent.message_id


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data
    await update_reply_markup(uid, context)

    if uid != ADMIN_ID and data.startswith("add_") or data.startswith("remove_") or data.startswith("assign_"):
        return

    if data == "add_user":
        conversation_state[uid] = "await_add_user"
        msg = "🔢 Send the Telegram ID of the user to add."
    elif data == "remove_user":
        conversation_state[uid] = "await_remove_user"
        msg = "❌ Send the Telegram ID of the user to remove."
    elif data == "assign_boss":
        conversation_state[uid] = "await_employee_for_boss"
        msg = "👤 Send Employee's Telegram ID."
    elif data == "list_users":
        if not whitelist:
            msg = "📂 Whitelist is empty."
        else:
            msg = "\n".join([f"👤 {u} → 👨‍💼 {user_boss_map.get(u, 'No boss')}" for u in whitelist])
    elif data == "start_forward":
        awaiting_message[uid] = True
        msg = "📨 Forwarding enabled. All your messages will be sent to your boss."
    elif data == "stop_forward":
        awaiting_message.pop(uid, None)
        msg = "🛑 Forwarding stopped."
    elif data == "status":
        boss_id = user_boss_map.get(uid)
        msg = f"📊 Boss: {boss_id}" if boss_id else "❌ No boss assigned."
    else:
        msg = "⏳ Coming soon..."

    reply_markup = role_keyboard(uid) if uid != ADMIN_ID else role_keyboard(uid)
    sent = await query.message.reply_text(msg, reply_markup=reply_markup)
    last_bot_message[uid] = sent.message_id


async def handle_admin_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()

    if uid != ADMIN_ID:
        return

    state = conversation_state.get(uid)
    if not state:
        return

    if state == "await_add_user":
        try:
            new_uid = int(text)
            whitelist.add(new_uid)
            await update.message.reply_text(f"✅ Added {new_uid}")
        except:
            await update.message.reply_text("❌ Invalid ID.")
        conversation_state.pop(uid)

    elif state == "await_remove_user":
        try:
            del_uid = int(text)
            whitelist.discard(del_uid)
            user_boss_map.pop(del_uid, None)
            awaiting_message.pop(del_uid, None)
            await update.message.reply_text(f"✅ Removed {del_uid}")
        except:
            await update.message.reply_text("❌ Invalid ID.")
        conversation_state.pop(uid)

    elif state == "await_employee_for_boss":
        try:
            emp_id = int(text)
            conversation_state[uid] = ("await_boss_for_employee", emp_id)
            await update.message.reply_text("👨‍💼 Send Boss's Telegram ID.")
        except:
            await update.message.reply_text("❌ Invalid ID.")

    elif isinstance(state, tuple) and state[0] == "await_boss_for_employee":
        emp_id = state[1]
        try:
            boss_id = int(text)
            user_boss_map[emp_id] = boss_id
            await update.message.reply_text(f"✅ Assigned Boss {boss_id} to Employee {emp_id}")
        except:
            await update.message.reply_text("❌ Invalid ID.")
        conversation_state.pop(uid)


def is_suspicious(text, user):
    terms = [
        "my name", "i am", "this is", "username", "contact", "reach me",
        str(user.id), user.username or "", user.first_name or ""
    ]
    return any(term.lower() in text.lower() for term in terms if term)


async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = update.effective_user

    # Admin command flow
    if uid == ADMIN_ID and uid in conversation_state:
        await handle_admin_conversation(update, context)
        return

    # Skip others
    if uid not in whitelist:
        return

    if not awaiting_message.get(uid):
        return

    boss_id = user_boss_map.get(uid)
    if not boss_id:
        await update.message.reply_text("❌ No boss assigned.")
        return

    if update.message.text and is_suspicious(update.message.text, user):
        await update.message.reply_text("⚠️ Suspicious message blocked. Not forwarded.")
        await context.bot.send_message(ADMIN_ID, f"⚠️ Suspicious message from {uid} blocked:\n{update.message.text}")
        return

    try:
        if update.message.text:
            await context.bot.send_message(boss_id, f"📨 Message from {uid}:\n{update.message.text}")
        elif update.message.document:
            await context.bot.copy_message(chat_id=boss_id, from_chat_id=uid, message_id=update.message.message_id)
        elif update.message.photo:
            await context.bot.copy_message(chat_id=boss_id, from_chat_id=uid, message_id=update.message.message_id)
        elif update.message.video:
            await context.bot.copy_message(chat_id=boss_id, from_chat_id=uid, message_id=update.message.message_id)
        elif update.message.audio:
            await context.bot.copy_message(chat_id=boss_id, from_chat_id=uid, message_id=update.message.message_id)
        else:
            await update.message.reply_text("⚠️ Unsupported message type.")
            return

        await update_reply_markup(uid, context)
        sent = await update.message.reply_text("✅ Forwarded.", reply_markup=employee_keyboard())
        last_bot_message[uid] = sent.message_id

    except Exception as e:
        logging.error(f"Forwarding error: {e}")
        await update.message.reply_text("❌ Failed to forward.")


# === MAIN ===
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ALL, handle_all_messages))
    app.run_polling()

if __name__ == "__main__":
    main()
