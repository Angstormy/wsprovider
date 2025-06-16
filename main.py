import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)

# --- Configuration ---
TOKEN = '7523409542:AAGlQI94jLTKoAhTZwIoZhv99b-9L5nfCu4'  # Replace this
ADMIN_ID = 1908801848      # Replace this

# --- In-memory stores ---
whitelist = set()
user_boss_map = {}
awaiting_message = {}
pending_action = {}

# --- Logging ---
logging.basicConfig(level=logging.INFO)

# --- Suspicious check helpers ---
def is_suspicious(message: str, username: str, name: str, user_id: int) -> bool:
    message = message.lower()
    parts = [username.lower(), name.lower(), str(user_id)]
    patterns = ["my name", "i am", "call me", "this is"]
    for p in parts:
        if p and p in message:
            return True
    if any(p in message for p in patterns):
        return True
    return False

# --- Button Keyboards ---
def get_admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add User", callback_data="add_user")],
        [InlineKeyboardButton("❌ Remove User", callback_data="remove_user")],
        [InlineKeyboardButton("👨‍💼 Assign Boss", callback_data="set_boss")],
        [InlineKeyboardButton("📋 List Users", callback_data="list_users")]
    ])

def get_employee_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📨 Send to Boss", callback_data="sendtoboss"),
            InlineKeyboardButton("🛑 Stop", callback_data="stopforward")
        ]
    ])

# --- Start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = update.effective_user.first_name or "User"

    if uid == ADMIN_ID:
        await update.message.reply_text(f"👑 Welcome Admin {name}", reply_markup=get_admin_keyboard())
    elif uid in user_boss_map.values():
        await update.message.reply_text(f"👨‍💼 Hello Boss {name}! You will receive employee messages here.")
    elif uid in whitelist:
        await update.message.reply_text(f"👋 Hello Employee {name}!", reply_markup=get_employee_keyboard())
    else:
        await update.message.reply_text("❌ You are not authorized. Contact admin.")

# --- Command Callback for Buttons ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    if uid != ADMIN_ID:
        if uid in whitelist:
            if query.data == "sendtoboss":
                awaiting_message[uid] = True
                await query.message.reply_text("✅ Forwarding ON", reply_markup=get_employee_keyboard())
            elif query.data == "stopforward":
                awaiting_message.pop(uid, None)
                await query.message.reply_text("🛑 Forwarding OFF", reply_markup=get_employee_keyboard())
        return

    if query.data == "add_user":
        pending_action[uid] = {"action": "add_user"}
        await query.message.reply_text("🔢 Send user ID to whitelist")
    elif query.data == "remove_user":
        pending_action[uid] = {"action": "remove_user"}
        await query.message.reply_text("🔢 Send user ID to remove")
    elif query.data == "set_boss":
        pending_action[uid] = {"action": "set_boss", "step": 1}
        await query.message.reply_text("👤 Send Employee ID")
    elif query.data == "list_users":
        if whitelist:
            lines = [f"👤 {u} → 👨‍💼 {user_boss_map.get(u, 'No boss')}" for u in whitelist]
            await query.message.reply_text("\n".join(lines), reply_markup=get_admin_keyboard())
        else:
            await query.message.reply_text("No users.", reply_markup=get_admin_keyboard())

# --- Handle Messages ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text
    name = update.effective_user.first_name or ""
    uname = update.effective_user.username or ""

    if uid == ADMIN_ID and uid in pending_action:
        action = pending_action[uid]

        if action["action"] == "add_user":
            try:
                tid = int(text)
                whitelist.add(tid)
                await update.message.reply_text(f"✅ User {tid} added.", reply_markup=get_admin_keyboard())
            except:
                await update.message.reply_text("❌ Invalid ID", reply_markup=get_admin_keyboard())
            pending_action.pop(uid)

        elif action["action"] == "remove_user":
            try:
                tid = int(text)
                whitelist.discard(tid)
                user_boss_map.pop(tid, None)
                awaiting_message.pop(tid, None)
                await update.message.reply_text(f"🗑️ Removed {tid}.", reply_markup=get_admin_keyboard())
            except:
                await update.message.reply_text("❌ Invalid ID", reply_markup=get_admin_keyboard())
            pending_action.pop(uid)

        elif action["action"] == "set_boss":
            step = action.get("step")
            try:
                tid = int(text)
                if step == 1:
                    action["emp"] = tid
                    action["step"] = 2
                    await update.message.reply_text("👨‍💼 Now send Boss ID")
                elif step == 2:
                    user_boss_map[action["emp"]] = tid
                    await update.message.reply_text(f"✅ Assigned Boss {tid} to Employee {action['emp']}", reply_markup=get_admin_keyboard())
                    pending_action.pop(uid)
            except:
                await update.message.reply_text("❌ Invalid ID", reply_markup=get_admin_keyboard())

        return

    if uid in whitelist and awaiting_message.get(uid):
        if is_suspicious(text, uname, name, uid):
            await update.message.reply_text("🚫 Suspicious content! Message not sent.")
            await context.bot.send_message(
                ADMIN_ID,
                f"⚠️ Suspicious message from {uid} blocked:\n{text}"
            )
            return  # Don't show employee keyboard if message blocked

        boss_id = user_boss_map.get(uid)
        if not boss_id:
            await update.message.reply_text("❌ No boss assigned.")
            return
        try:
            await context.bot.copy_message(
                chat_id=boss_id,
                from_chat_id=uid,
                message_id=update.message.message_id
            )
            await update.message.reply_text("✅ Sent to boss.", reply_markup=get_employee_keyboard())
        except Exception as e:
            logging.error(f"Error forwarding: {e}")
            await update.message.reply_text("❌ Failed to send.", reply_markup=get_employee_keyboard())

# --- App Runner ---
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == '__main__':
    main()
