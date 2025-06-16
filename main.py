import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)
from rapidfuzz import fuzz

TOKEN = '7523409542:AAGlQI94jLTKoAhTZwIoZhv99b-9L5nfCu4'  # Replace this!
ADMIN_ID = 1908801848     # Replace with your actual admin ID

# Data stores
whitelist = set()
user_boss_map = {}
awaiting_message = {}
admin_state = {}

# Logging
logging.basicConfig(level=logging.INFO)

# Utility: Get Role-based Keyboard
def get_main_keyboard(uid):
    if uid == ADMIN_ID:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add User", callback_data="add_user"),
             InlineKeyboardButton("🗑 Remove User", callback_data="remove_user")],
            [InlineKeyboardButton("👨‍💼 Set Boss", callback_data="set_boss"),
             InlineKeyboardButton("📋 List Users", callback_data="list_users")]
        ])
    elif uid in user_boss_map.values():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="refresh")]
        ])
    elif uid in whitelist:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Send to Boss", callback_data="send_to_boss"),
             InlineKeyboardButton("🛑 Stop Forwarding", callback_data="stop_forward")],
            [InlineKeyboardButton("🔄 Refresh", callback_data="refresh")]
        ])
    return None

# Start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    name = user.full_name

    if uid == ADMIN_ID:
        text = f"👑 Welcome {name} (Admin)!\nManage users and roles below."
    elif uid in user_boss_map.values():
        text = f"👋 Hello {name}, you are a *Boss*.\nYou'll receive messages from your employees here."
    elif uid in whitelist:
        text = f"👋 Welcome {name}!\nYou are an *Employee*. Use buttons below to interact."
    else:
        text = f"🚫 You are not authorized. Please contact the Admin."
        await update.message.reply_text(text)
        return

    await update.message.reply_text(text, parse_mode="Markdown",
                                    reply_markup=get_main_keyboard(uid))

# Button handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data

    if data == "add_user":
        admin_state[uid] = "awaiting_add_user"
        await query.edit_message_text("🆔 Send the user ID to add:")

    elif data == "remove_user":
        admin_state[uid] = "awaiting_remove_user"
        await query.edit_message_text("🗑 Send the user ID to remove:")

    elif data == "set_boss":
        admin_state[uid] = "awaiting_set_boss"
        await query.edit_message_text("👤 Enter the Employee ID to assign a boss:")

    elif data == "list_users":
        if not whitelist:
            text = "ℹ️ Whitelist is empty."
        else:
            text = "👥 Whitelisted Users:\n" + "\n".join([
                f"{uid} → Boss: {user_boss_map.get(uid, 'None')}" for uid in whitelist
            ])
        await query.edit_message_text(text, reply_markup=get_main_keyboard(uid))

    elif data == "send_to_boss":
        if uid not in whitelist:
            await query.edit_message_text("🚫 You are not whitelisted.")
        elif uid not in user_boss_map:
            await query.edit_message_text("❌ No boss assigned.")
        else:
            awaiting_message[uid] = True
            await query.edit_message_text("📤 Forwarding enabled.", reply_markup=get_main_keyboard(uid))

    elif data == "stop_forward":
        awaiting_message.pop(uid, None)
        await query.edit_message_text("🛑 Forwarding stopped.", reply_markup=get_main_keyboard(uid))

    elif data == "refresh":
        await query.edit_message_text("🔄 Refreshed.", reply_markup=get_main_keyboard(uid))

# Handle text
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    text = update.message.text
    state = admin_state.get(uid)

    # Suspicious content check (name, username, id, keywords)
    if awaiting_message.get(uid):
        user_data = [str(uid), user.username or "", user.first_name or "", user.last_name or ""]
        keywords = ["my name is", "username", "id is", "I am", "I'm", "nm is"]
        lower_text = text.lower()
        if any(kw in lower_text for kw in keywords) or any(
            fuzz.partial_ratio(part.lower(), lower_text) > 80 for part in user_data if part):
            awaiting_message.pop(uid, None)
            await context.bot.send_message(ADMIN_ID,
                f"⚠️ Suspicious message from {uid} blocked:\n{text}")
            await update.message.reply_text("🚫 Suspicious content detected. Admin notified.")
            return
        boss_id = user_boss_map.get(uid)
        if boss_id:
            await context.bot.copy_message(chat_id=boss_id,
                                           from_chat_id=update.effective_chat.id,
                                           message_id=update.message.message_id)
            await update.message.reply_text("✅ Message forwarded to your boss.")
        return

    # Admin states
    if state == "awaiting_add_user":
        try:
            new_id = int(text)
            whitelist.add(new_id)
            await update.message.reply_text(f"✅ Added user {new_id}.",
                                            reply_markup=get_main_keyboard(uid))
        except:
            await update.message.reply_text("❌ Invalid ID.")
        admin_state.pop(uid, None)

    elif state == "awaiting_remove_user":
        try:
            rid = int(text)
            whitelist.discard(rid)
            user_boss_map.pop(rid, None)
            awaiting_message.pop(rid, None)
            await update.message.reply_text(f"🗑 Removed user {rid}.",
                                            reply_markup=get_main_keyboard(uid))
        except:
            await update.message.reply_text("❌ Invalid ID.")
        admin_state.pop(uid, None)

    elif state == "awaiting_set_boss":
        try:
            emp_id = int(text)
            admin_state[uid] = {"step": "awaiting_boss_id", "employee_id": emp_id}
            await update.message.reply_text("👨‍💼 Now enter the Boss ID:")
        except:
            await update.message.reply_text("❌ Invalid Employee ID.")

    elif isinstance(state, dict) and state.get("step") == "awaiting_boss_id":
        try:
            boss_id = int(text)
            emp_id = state["employee_id"]
            user_boss_map[emp_id] = boss_id
            await update.message.reply_text(f"✅ Boss {boss_id} assigned to employee {emp_id}.",
                                            reply_markup=get_main_keyboard(uid))
        except:
            await update.message.reply_text("❌ Invalid Boss ID.")
        admin_state.pop(uid, None)

# Help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Use the buttons to interact with the bot.")

# Main
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling()

if __name__ == "__main__":
    main()
