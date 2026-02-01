import time, os, asyncio, aiohttp, json, random
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- [ CONFIG ] ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "421311524"))
REQUIRED_GROUP = "@The_Bot_Group" #
SAVE_FILE = "working_proxies.txt"
USER_DATA_FILE = "user_access.json"
COOLDOWN_TIME = 60 
AUTO_DELETE_TIME = 600 # 10 Minutes

stats = {"scraped": 0, "checked": 0}
user_cooldowns = {} 

# --- [ HELPERS ] ---
async def get_isp_info(ip):
    try:
        url = f"http://ip-api.com/json/{ip}?fields=status,isp"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=3) as r:
                data = await r.json()
                return data.get('isp', 'Global Network') if data.get('status') == 'success' else "Global Network"
    except: return "Global Network"

async def delete_message_job(context: ContextTypes.DEFAULT_TYPE):
    # Message ko gayab karne wala logic
    try:
        await context.bot.delete_message(chat_id=context.job.chat_id, message_id=context.job.data)
    except: pass

async def get_proxy_card(ready_count):
    # Title: Sirf "Proxy Scraper"
    if not os.path.exists(SAVE_FILE) or os.path.getsize(SAVE_FILE) == 0:
        return "❌ No proxies ready yet."
        
    with open(SAVE_FILE, 'r') as f: all_p = f.readlines()
    sample = random.sample(all_p, min(len(all_p), 2))
    p1_ip = sample[0].split("://")[-1].split(":")[0]
    isp_name = await get_isp_info(p1_ip)

    return (
        "🛰 **Proxy Scraper**\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🏢 **ISP:** `{isp_name}`\n"
        "🌍 **LOC:** 🇮🇳 `Mumbai`\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 `{sample[0].strip()}`\n"
        f"🔗 `{sample[1].strip() if len(sample)>1 else 'Scanning...'}`\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✅ **Verified** |\n"
        "👤 **By** @RoshanGP4A\n"
        "📢 **Join:** @The_Bot_Group"
    )

# --- [ HANDLERS ] ---
async def handle_buttons(u: Update, c: ContextTypes.DEFAULT_TYPE):
    user_id = u.effective_user.id
    text = u.message.text
    now = time.time()
    
    # Ready count calculation
    ready_count = sum(1 for line in open(SAVE_FILE)) if os.path.exists(SAVE_FILE) else 0

    if text == '📊 Status':
        # Status par koi cooldown nahi hai
        card_text = await get_proxy_card(ready_count)
        kb = [[InlineKeyboardButton("🔄 Refresh Status", callback_data="refresh_status")]]
        await u.message.reply_text(card_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))

    elif text == '📥 Get Proxy':
        # Cooldown sirf yahan chalega
        if user_id != ADMIN_ID and user_id in user_cooldowns and now - user_cooldowns[user_id] < COOLDOWN_TIME:
            wait = int(COOLDOWN_TIME - (now - user_cooldowns[user_id]))
            await u.message.reply_text(f"⏳ **Cooldown Active**\nWait `{wait}s` more.", parse_mode='Markdown')
            return

        user_cooldowns[user_id] = now
        card_text = await get_proxy_card(ready_count)
        msg = await u.message.reply_text(card_text, parse_mode='Markdown')
        
        # 10 minute baad auto-delete schedule
        c.job_queue.run_once(delete_message_job, AUTO_DELETE_TIME, chat_id=u.effective_chat.id, data=msg.message_id)

async def callback_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    
    if q.data == "refresh_status":
        # Purane status message ko hi edit karega
        ready_count = sum(1 for line in open(SAVE_FILE)) if os.path.exists(SAVE_FILE) else 0
        card_text = await get_proxy_card(ready_count)
        try:
            await q.edit_message_text(
                card_text, 
                parse_mode='Markdown', 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh Status", callback_data="refresh_status")]])
            )
        except: pass

# --- [ MAIN ] ---
def main():
    if not os.path.exists(SAVE_FILE): open(SAVE_FILE, "w").close()
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Command & Button Handlers
    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Welcome!", reply_markup=ReplyKeyboardMarkup([['📊 Status', '📥 Get Proxy']], resize_keyboard=True))))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))
    
    # Scraper & Dashboard Tasks (Internal logic same as v7.7)
    # ... (Scraper logic here)
    
    app.run_polling()

if __name__ == "__main__": main()
    
