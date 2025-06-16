import logging
import re
from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, CallbackQueryHandler, filters
)

# Config
TOKEN = '7523409542:AAGlQI94jLTKoAhTZwIoZhv99b-9L5nfCu4'  # Replace with your bot token
ADMIN_ID = 1908801848     # Replace with your Telegram ID

# In-memory data
whitelist = set()
user_boss_map = {}
awaiting_message = {}
awaiting_action = {}

# Logging
logging.basicConfig(level=logging.INFO)

# Suspicious message check
def is_suspicious(uid, username, name, text):
    patterns = [
        r"my name is", r"this is", r"i am", r"contact me", r"username",
        str(uid), str(uid)[:5], str(uid)[-5:]
    ]
    tokens = set(re.findall(r'\w+', text.lower()))
    if username:
        patterns.append(username.lower())
    if name:
        name_parts = name.lower().split()
        patterns.extend(name_parts)
        patterns.append(name.lower())
    for pat in patterns:
        if any(pat in token for token in tokens):
            return True
    return False

# Inline button keyboards
def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add User", callback_data="add_user"),
         InlineKeyboardButton("🗑 Remove User", callback_data="remove_user")],
        [InlineKeyboardButton("🧑‍💼 Assign Boss", callback_data="assign_boss"),
         InlineKeyboardButton("📋 List Users", callback_data="list_users")]
    ])

def employee_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Start Forwarding", callback_data="start_forwarding")],
        [InlineKeyboardButton("🛑 Stop Forwarding", callback_data="stop_forwarding")],
        [InlineKeyboardButton("ℹ️ Status", callback_data="status")]
    ])

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    name = user.first_name or "User"
    if uid == ADMIN_ID:
        await update.message.reply_text(
            f"👑 Welcome {name} (Admin)!\nUse the buttons below:",
            reply_markup=admin_keyboard()
        )
    elif uid in user_boss_map.values():
        await update.message.reply_text(
            f"👋 Welcome {name}!\n📥 You are a *Boss*. You will receive messages from your employees.",
            parse_mode="Markdown"
        )
    elif uid in whitelist:
        await update.message.reply_text(
            f"👋 Welcome {name}!\n✅ You are an *Employee*.\nUse the buttons below.",
            parse_mode="Markdown",
            reply_markup=employee_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ You are not authorized to use this bot. Contact the admin."
        )

# Inline button handler
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data

    if uid == ADMIN_ID:
        if data == "add_user":
            awaiting_action[uid] = "add_user"
            await query.edit_message_text("🔹 Send the User ID to add:")
        elif data == "remove_user":
            awaiting_action[uid] = "remove_user"
            await query.edit_message_text("🔹 Send the User ID to remove:")
        elif data == "assign_boss":
            awaiting_action[uid] = "assign_boss_employee"
            await query.edit_message_text("🔹 Send the *Employee ID* to assign a boss to:", parse_mode="Markdown")
        elif data == "list_users":
            if not whitelist:
                await query.edit_message_text("⚠️ Whitelist is empty.")
            else:
                msg = "\n".join(f"👤 {u} → 👨‍💼 {user_boss_map.get(u, 'None')}" for u in whitelist)
                await query.edit_message_text(msg, reply_markup=admin_keyboard())
    elif uid in whitelist:
        if data == "start_forwarding":
            awaiting_message[uid] = True
            await query.edit_message_text("✅ Forwarding ON.\nAll your future messages will be sent to your boss.", reply_markup=employee_keyboard())
        elif data == "stop_forwarding":
            awaiting_message.pop(uid, None)
            await query.edit_message_text("🛑 Forwarding OFF.", reply_markup=employee_keyboard())
        elif data == "status":
            boss_id = user_boss_map.get(uid)
            msg = f"👨‍💼 Your boss: {boss_id}" if boss_id else "❌ No boss assigned."
            await query.edit_message_text(msg, reply_markup=employee_keyboard())

# Handle replies from admin (user ID input etc.)
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    if uid != ADMIN_ID:
        return

    if awaiting_action.get(uid) == "add_user":
        try:
            target = int(text)
            whitelist.add(target)
            await update.message.reply_text(f"✅ User {target} added.", reply_markup=admin_keyboard())
        except:
            await update.message.reply_text("❌ Invalid user ID.", reply_markup=admin_keyboard())
        awaiting_action.pop(uid)

    elif awaiting_action.get(uid) == "remove_user":
        try:
            target = int(text)
            whitelist.discard(target)
            user_boss_map.pop(target, None)
            awaiting_message.pop(target, None)
            await update.message.reply_text(f"🗑 Removed user {target}.", reply_markup=admin_keyboard())
        except:
            await update.message.reply_text("❌ Invalid user ID.", reply_markup=admin_keyboard())
        awaiting_action.pop(uid)

    elif awaiting_action.get(uid) == "assign_boss_employee":
        try:
            context.user_data["pending_employee"] = int(text)
            awaiting_action[uid] = "assign_boss_boss"
            await update.message.reply_text("🔹 Now send the *Boss ID*:", parse_mode="Markdown")
        except:
            await update.message.reply_text("❌ Invalid Employee ID.")
    elif awaiting_action.get(uid) == "assign_boss_boss":
        try:
            employee_id = context.user_data.get("pending_employee")
            boss_id = int(text)
            user_boss_map[employee_id] = boss_id
            await update.message.reply_text(f"✅ Assigned boss {boss_id} to employee {employee_id}.", reply_markup=admin_keyboard())
        except:
            await update.message.reply_text("❌ Invalid Boss ID.", reply_markup=admin_keyboard())
        awaiting_action.pop(uid)
        context.user_data.pop("pending_employee", None)

# Handle messages from employee (text or media)
async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = update.effective_user
    name = user.full_name or ""
    username = user.username or ""
    boss_id = user_boss_map.get(uid)

    if uid not in whitelist or not awaiting_message.get(uid) or not boss_id:
        return

    # Check for suspicious message
    text = update.message.caption or update.message.text or ""
    if text and is_suspicious(uid, username, name, text):
        await update.message.reply_text("⚠️ Suspicious message blocked. Not forwarded.")
        await context.bot.send_message(ADMIN_ID, f"🚨 Suspicious message blocked from user {uid}:\n{text}")
        return

    try:
        if update.message.text:
            await context.bot.send_message(chat_id=boss_id, text=update.message.text)
        elif update.message.photo:
            await context.bot.send_photo(chat_id=boss_id, photo=update.message.photo[-1].file_id, caption=text or "")
        elif update.message.document:
            await context.bot.send_document(chat_id=boss_id, document=update.message.document.file_id, caption=text or "")
        elif update.message.audio:
            await context.bot.send_audio(chat_id=boss_id, audio=update.message.audio.file_id, caption=text or "")
        elif update.message.video:
            await context.bot.send_video(chat_id=boss_id, video=update.message.video.file_id, caption=text or "")
        else:
            await update.message.reply_text("✅ Sent to your boss.")
            return

        await update.message.reply_text("✅ Forwarded.", reply_markup=employee_keyboard())
    except Exception as e:
        logging.error(f"Forwarding failed: {e}")
        await update.message.reply_text("❌ Forwarding failed.")

# Main function
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(MessageHandler(filters.TEXT & filters.User(user_id=ADMIN_ID), handle_text))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_all_messages))

    app.run_polling()

if __name__ == "__main__":
    main()
