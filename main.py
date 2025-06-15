import os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
)

from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# In-memory user-boss mapping and whitelist
user_boss_map = {}
whitelisted_users = set()

# ✅ Admin-only check
def is_admin(user_id):
    return user_id == ADMIN_ID

# ✅ Whitelisted check
def is_whitelisted(user_id):
    return user_id in whitelisted_users or is_admin(user_id)

# 🔐 /adduser <user_id>
async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if context.args:
        uid = int(context.args[0])
        whitelisted_users.add(uid)
        await update.message.reply_text(f"✅ User {uid} added to whitelist.")

# 🔐 /removeuser <user_id>
async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if context.args:
        uid = int(context.args[0])
        whitelisted_users.discard(uid)
        user_boss_map.pop(uid, None)
        await update.message.reply_text(f"🚫 User {uid} removed from whitelist.")

# 🔐 /setboss <user_id> <boss_id>
async def set_boss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) == 2:
        user_id = int(context.args[0])
        boss_id = int(context.args[1])
        user_boss_map[user_id] = boss_id
        await update.message.reply_text(f"✅ Boss set for user {user_id} → {boss_id}")

# 🔐 /listusers
async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    lines = ["📋 Whitelisted Users & Bosses:"]
    for user in whitelisted_users:
        boss = user_boss_map.get(user, "❌ Not set")
        lines.append(f"- User {user} → Boss {boss}")
    await update.message.reply_text("\n".join(lines))

# 📤 /sendtoboss (for whitelisted users)
async def send_to_boss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_whitelisted(user_id):
        await update.message.reply_text("❌ You are not authorized to use this bot.")
        return
    boss_id = user_boss_map.get(user_id)
    if not boss_id:
        await update.message.reply_text("⚠️ No boss assigned. Contact admin.")
        return
    if update.message.reply_to_message:
        msg = update.message.reply_to_message
        await context.bot.copy_message(chat_id=boss_id, from_chat_id=msg.chat_id, message_id=msg.message_id)
        await update.message.reply_text("✅ Message forwarded to your boss.")
    else:
        await update.message.reply_text("ℹ️ Please reply to a message with /sendtoboss.")

# ℹ️ /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ℹ️ Use /sendtoboss by replying to a message.\nAdmins can use /adduser, /removeuser, /setboss.")

# 🚀 Main entry
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("adduser", add_user))
    app.add_handler(CommandHandler("removeuser", remove_user))
    app.add_handler(CommandHandler("setboss", set_boss))
    app.add_handler(CommandHandler("listusers", list_users))
    app.add_handler(CommandHandler("sendtoboss", send_to_boss))
    app.add_handler(CommandHandler("help", help_command))

    print("🤖 Bot is running...")
    app.run_polling()
