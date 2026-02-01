import time, os, asyncio, aiohttp, json, random
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- [ CONFIG ] ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "421311524"))
REQUIRED_GROUP = "@roshantesting" 
SAVE_FILE = "working_proxies.txt"
USER_DATA_FILE = "user_access.json"
COOLDOWN_TIME = 60 # Seconds mein cooldown

# Global stats and state
stats = {"scraped": 0, "checked": 0, "ready": 0, "start": time.time()}
user_cooldowns = {} # {user_id: timestamp}

# --- [ DATA PERSISTENCE ] ---
def load_users():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, "r") as f: return json.load(f)
    return {}

def save_users(data):
    with open(USER_DATA_FILE, "w") as f: json.dump(data, f)

user_access = load_users()

# --- [ HELPERS ] ---
async def is_member(user_id, context):
    try:
        member = await context.bot.get_chat_member(chat_id=REQUIRED_GROUP, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except: return False

def get_remaining_time(user_id):
    if str(user_id) not in user_access: return None
    expiry = datetime.fromisoformat(user_access[str(user_id)])
    if datetime.utcnow() > expiry: return None
    diff = expiry - datetime.utcnow()
    return f"{diff.seconds // 60}m {diff.seconds % 60}s"

# --- [ SILENT SCRAPER ENGINE ] ---
async def check_proxy(proxy, p_type, context):
    url = "https://www.instagram.com/accounts/login/"
    proxy_url = f"http://{proxy}" if p_type == "http" else f"{p_type}://{proxy}"
    stats["checked"] += 1
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.get(url, proxy=proxy_url) as response:
                if response.status == 200:
                    stats["ready"] += 1
                    # Sirf file mein save hoga, chat mein noise nahi
                    with open(SAVE_FILE, "a") as f: f.write(f"{p_type}://{proxy}\n")
    except: pass

async def scraper_task(context: ContextTypes.DEFAULT_TYPE):
    sources = {
        "http": "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http",
        "socks4": "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks4",
        "socks5": "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5"
    }
    async with aiohttp.ClientSession() as session:
        for p_type, url in sources.items():
            try:
                async with session.get(url) as r:
                    proxies = (await r.text()).strip().split('\n')
                    stats["scraped"] += len(proxies)
                    tasks = [check_proxy(p.strip(), p_type, context) for p in proxies[:30] if ":" in p]
                    await asyncio.gather(*tasks)
            except: continue

# --- [ HANDLERS ] ---
async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    user_id = u.effective_user.id
    if not await is_member(user_id, c):
        kb = [[InlineKeyboardButton("📢 Join Group", url=f"https://t.me/{REQUIRED_GROUP[1:]}")],
              [InlineKeyboardButton("✅ I have Joined", callback_data="check_join")]]
        await u.message.reply_text("👋 Join the group to use this engine.", reply_markup=InlineKeyboardMarkup(kb))
        return

    rem_time = get_remaining_time(user_id)
    if not rem_time and user_id != ADMIN_ID:
        kb = [[InlineKeyboardButton("📩 Request Access", callback_data=f"req_{user_id}")]]
        await u.message.reply_text("⚠️ No active time window. Request access:", reply_markup=InlineKeyboardMarkup(kb))
        return

    kb = [['📊 Status', '📥 Get Proxy']]
    await u.message.reply_text(f"✅ **Access Active** ({rem_time or 'Admin'})\nChoose an option:", 
                               reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True), parse_mode='Markdown')

async def handle_buttons(u: Update, c: ContextTypes.DEFAULT_TYPE):
    user_id = u.effective_user.id
    text = u.message.text
    
    # 1. Access Check
    if user_id != ADMIN_ID and not get_remaining_time(user_id):
        await u.message.reply_text("❌ Session expired. Use /start.")
        return

    if text == '📊 Status':
        ready_count = 0
        if os.path.exists(SAVE_FILE):
            with open(SAVE_FILE, 'r') as f: ready_count = len(f.readlines())
        await u.message.reply_text(f"🛰 **STATS**\nReady IPs: `{ready_count}`\nChecked: `{stats['checked']}`", parse_mode='Markdown')

    elif text == '📥 Get Proxy':
        # 2. Cooldown Logic
        now = time.time()
        if user_id in user_cooldowns and now - user_cooldowns[user_id] < COOLDOWN_TIME:
            wait = int(COOLDOWN_TIME - (now - user_cooldowns[user_id]))
            await u.message.reply_text(f"⏳ Chill bro! Wait `{wait}s` before next request.", parse_mode='Markdown')
            return
        
        if os.path.exists(SAVE_FILE) and os.path.getsize(SAVE_FILE) > 0:
            user_cooldowns[user_id] = now # Set cooldown
            with open(SAVE_FILE, 'r') as f: all_p = f.readlines()
            # Random pick 2 proxies
            sample = random.sample(all_p, min(len(all_p), 2))
            proxies_text = "\n".join([f"✅ `{p.strip()}`" for p in sample])
            await u.message.reply_text(f"🎯 **Your Working IPs:**\n{proxies_text}\n\nNext in {COOLDOWN_TIME}s.", parse_mode='Markdown')
        else:
            await u.message.reply_text("❌ No proxies ready yet.")

async def admin_callback(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    if q.data.startswith("req_"):
        uid = q.data.split("_")[1]
        kb = [[InlineKeyboardButton("+10m", callback_data=f"add_{uid}_10"),
               InlineKeyboardButton("+60m", callback_data=f"add_{uid}_60")]]
        await c.bot.send_message(ADMIN_ID, f"🔔 Request from `{uid}`", reply_markup=InlineKeyboardMarkup(kb))
    elif q.data.startswith("add_"):
        _, uid, mins = q.data.split("_")
        user_access[str(uid)] = (datetime.utcnow() + timedelta(minutes=int(mins))).isoformat()
        save_users(user_access)
        await c.bot.send_message(int(uid), "✅ Access Granted! Try /start.")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(admin_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))
    
    if app.job_queue:
        app.job_queue.run_repeating(scraper_task, interval=180, first=10)
    
    app.run_polling()

if __name__ == "__main__": main()
        
