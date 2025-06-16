import logging
import re
from rapidfuzz import fuzz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

TOKEN = '7523409542:AAGlQI94jLTKoAhTZwIoZhv99b-9L5nfCu4'
ADMIN_ID = 1908801848  # Replace with your admin ID

whitelist = set()
user_boss_map = {}
awaiting_message = {}
admin_state = {}  # Tracks admin input steps

# Setup logging
logging.basicConfig(level=logging.INFO)

def get_main_keyboard(user_id):
    if user_id == ADMIN_ID:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add User", callback_data="add_user")],
            [InlineKeyboardButton("👨‍💼 Set Boss", callback_data="set_boss")],
            [InlineKeyboardButton("🗑️ Remove User", callback_data="remove_user")],
            [InlineKeyboardButton("📋 List Users", callback_data="list_users")]
        ])
    elif user_id in user_boss_map.values():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("ℹ️ Boss Panel (View Only)", callback_data="noop")]
        ])
    elif user_id in whitelist:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📨 Send to Boss", callback_data="sendtoboss")],
            [InlineKeyboardButton("🛑 Stop Forward", callback_data="stopforward")],
            [InlineKeyboardButton("🔎 Check Status", callback_data="status")]
        ])
    else:
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = update.effective_user.first_name or "User"
    kb = get_main_keyboard(uid)

    if uid == ADMIN_ID:
        text = f"👑 Welcome {name} (Admin)!\nUse the buttons to manage the system."
    elif uid in user_boss_map.values():
        text = f"👋 Welcome {name}!\nYou're a *Boss*. Employees will forward messages to you."
    elif uid in whitelist:
        text = f"👋 Welcome {name}!\nYou're an *Employee*. Use this bot to message your boss securely."
    else:
        text = f"⛔ You are not authorized.\nContact admin to gain access."

    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ℹ️ Use the buttons below based on your role.",
                                    reply_markup=get_main_keyboard(update.effective_user.id))

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    boss_id = user_boss_map.get(uid)
    if boss_id:
        await update.message.reply_text(f"✅ Your boss is: {boss_id}")
    else:
        await update.message.reply_text("❌ You don't have a boss assigned yet.")
    await update.message.reply_text("📍 What do you want to do next?",
                                    reply_markup=get_main_keyboard(uid))

# Interactive button handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data

    if uid != ADMIN_ID and data in {"add_user", "remove_user", "set_boss", "list_users"}:
        await query.edit_message_text("⛔ Only the admin can use this.")
        return

    if data == "add_user":
        admin_state[uid] = "awaiting_add_user"
        await query.edit_message_text("📥 Enter the User ID to add:")
    elif data == "remove_user":
        admin_state[uid] = "awaiting_remove_user"
        await query.edit_message_text("🗑️ Enter the User ID to remove:")
    elif data == "set_boss":
        admin_state[uid] = "awaiting_set_boss"
        await query.edit_message_text("👨‍💼 Enter in format: <user_id> <boss_id>")
    elif data == "list_users":
        if not whitelist:
            await query.edit_message_text("⚠️ No users in the system yet.")
        else:
            lines = [f"👤 {u} → 👨‍💼 {user_boss_map.get(u, 'No Boss')}" for u in whitelist]
            await query.edit_message_text("\n".join(lines))
        await query.message.reply_text("⬇️ Choose your next action:",
                                       reply_markup=get_main_keyboard(uid))
    elif data == "sendtoboss":
        awaiting_message[uid] = True
        await query.edit_message_text("📨 Forwarding mode ON. All messages will be sent to your boss.")
        await query.message.reply_text("⬇️ What would you like to do next?",
                                       reply_markup=get_main_keyboard(uid))
    elif data == "stopforward":
        awaiting_message.pop(uid, None)
        await query.edit_message_text("🛑 Forwarding stopped.")
        await query.message.reply_text("⬇️ Choose next action:",
                                       reply_markup=get_main_keyboard(uid))
    elif data == "status":
        await status(update, context)

# Suspicious message checker
def is_suspicious(uid, username, name, message):
    message_lower = message.lower()
    bad_patterns = [
        r"\bmy name is\b", r"\bi am\b", r"\busername\b", r"\bid\b", r"\bnm\b", r"\bthis is\b"
    ]
    if any(p in message_lower for p in [str(uid), str(name).lower(), str(username).lower()]):
        return True
    if any(re.search(pattern, message_lower) for pattern in bad_patterns):
        return True
    if fuzz.partial_ratio(str(uid), message) > 80:
        return True
    return False

# Handle text messages
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    text = update.message.text.strip()

    if uid == ADMIN_ID and uid in admin_state:
        state = admin_state.pop(uid)
        if state == "awaiting_add_user":
            try:
                target = int(text)
                whitelist.add(target)
                await update.message.reply_text(f"✅ User {target} added.")
            except:
                await update.message.reply_text("❌ Invalid User ID.")
        elif state == "awaiting_remove_user":
            try:
                target = int(text)
                whitelist.discard(target)
                user_boss_map.pop(target, None)
                await update.message.reply_text(f"🗑️ User {target} removed.")
            except:
                await update.message.reply_text("❌ Invalid User ID.")
        elif state == "awaiting_set_boss":
            try:
                parts = text.split()
                uid2 = int(parts[0])
                boss_id = int(parts[1])
                user_boss_map[uid2] = boss_id
                await update.message.reply_text(f"✅ Boss {boss_id} assigned to user {uid2}.")
            except:
                await update.message.reply_text("❌ Format must be: <user_id> <boss_id>")

        await update.message.reply_text("📍 Choose next action:",
                                        reply_markup=get_main_keyboard(uid))
        return

    # If employee is in forwarding mode
    if awaiting_message.get(uid):
        boss_id = user_boss_map.get(uid)
        if not boss_id:
            await update.message.reply_text("⚠️ No boss assigned.")
            return
        if is_suspicious(uid, user.username or "", user.first_name or "", text):
            await context.bot.send_message(ADMIN_ID,
                f"⚠️ Suspicious message blocked from {uid}:\n{text}")
            await update.message.reply_text("🚫 Message blocked due to sensitive content.")
            return
        try:
            await context.bot.copy_message(
                chat_id=boss_id,
                from_chat_id=update.effective_chat.id,
                message_id=update.message.message_id
            )
            await update.message.reply_text("✅ Forwarded to boss.")
        except:
            await update.message.reply_text("⚠️ Failed to forward.")
    else:
        await update.message.reply_text("ℹ️ Message ignored.\nUse 'Send to Boss' to start forwarding.")

# Main function
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling()

if __name__ == "__main__":
    main()
