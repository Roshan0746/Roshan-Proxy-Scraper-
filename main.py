import time, os, asyncio, aiohttp, json, random
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- [ SECURE CONFIG ] ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "421311524"))
REQUIRED_GROUP = "@The_Bot_Group" # Underscores fixed
SAVE_FILE = "working_proxies.txt"
USER_DATA_FILE = "user_access.json"
COOLDOWN_TIME = 60 # Cooldown only for Get Proxy
AUTO_DELETE_TIME = 600 # 10 Minutes

# Global Stats
stats = {"scraped": 0, "checked": 0, "start": time.time()}
user_cooldowns = {} 

# --- [ DATA PERSISTENCE ] ---
def load_users():
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_users(data):
    with open(USER_DATA_FILE, "w") as f: json.dump(data, f)

user_access = load_users()

# --- [ UI & INTEL HELPERS ] ---
async def get_isp_info(ip):
    try:
        url = f"http://ip-api.com/json/{ip}?fields=status,isp"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=3) as r:
                data = await r.json()
                return data.get('isp', 'Global Network') if data.get('status') == 'success' else "Global Network"
    except: return "Global Network"

def get_progress_bar(ready, checked):
    # Dynamic Success Rate Logic
    if checked == 0: return "[░░░░░░░░░░] 0%"
    ratio = min(ready / checked, 1.0)
    filled = int(ratio * 10)
    bar = "█" * filled + "░" * (10 - filled)
    return f"[{bar}] {int(ratio * 100)}%"

async def delete_message_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.delete_message(chat_id=context.job.chat_id, message_id=context.job.data)
    except: pass

# --- [ INSTANT UI GENERATORS ] ---

def get_status_dashboard():
    # Instant calculation from file
    ready_count = 0
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, 'r') as f:
            ready_count = len(f.readlines())
    
    ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    curr_time = ist_now.strftime('%H:%M:%S')
    efficiency = get_progress_bar(ready_count, stats['checked'])
    
    return (
        "🛰 **Proxy Scraper**\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🟢 **System:** `Active` | ⚡ **Threads:** `40/s`\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📦 **Scraped:** `{stats['scraped']:,}`\n"
        f"🔎 **Checked:** `{stats['checked']:,}`\n"
        f"🔥 **Ready:** `{ready_count:,}`\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📊 **Efficiency:** `{efficiency}`\n"
        f"🕒 **Last Sync:** `{curr_time} IST`\n\n"
        "👤 **By** @RoshanGP4A\n"
        "📢 **Join:** @The_Bot_Group" # Underscore intact
    )

async def get_proxy_card_ui():
    if os.path.exists(SAVE_FILE) and os.path.getsize(SAVE_FILE) > 0:
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
            "📢 **Join:** @The_Bot_Group" # Underscore intact
        )
    return "❌ No proxies ready. Scraper is running..."

# --- [ CORE ENGINE ] ---
async def check_proxy(proxy, p_type, context):
    url = "https://www.instagram.com/accounts/login/"
    proxy_url = f"http://{proxy}" if p_type == "http" else f"{p_type}://{proxy}"
    stats["checked"] += 1
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.get(url, proxy=proxy_url) as response:
                if response.status == 200:
                    with open(SAVE_FILE, "a") as f: f.write(f"{p_type}://{proxy}\n")
    except: pass

async def scraper_task(context: ContextTypes.DEFAULT_TYPE):
    sources = {"http": "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http",
               "socks4": "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks4",
               "socks5": "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5"}
    async with aiohttp.ClientSession() as session:
        for p_type, url in sources.items():
            try:
                async with session.get(url) as r:
                    proxies = (await r.text()).strip().split('\n')
                    stats["scraped"] += len(proxies)
                    tasks = [check_proxy(p.strip(), p_type, context) for p in proxies[:40] if ":" in p]
                    await asyncio.gather(*tasks)
            except: continue

# --- [ ACCESS HELPERS ] ---
def get_remaining_time(user_id):
    if user_id == ADMIN_ID: return "Admin"
    uid_str = str(user_id)
    if uid_str not in user_access: return None
    expiry = datetime.fromisoformat(user_access[uid_str])
    if datetime.utcnow() > expiry: return None
    diff = expiry - datetime.utcnow()
    return f"{diff.seconds // 60}m {diff.seconds % 60}s"

# --- [ MAIN HANDLERS ] ---
async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    user_id = u.effective_user.id
    try:
        m = await c.bot.get_chat_member(chat_id=REQUIRED_GROUP, user_id=user_id)
        if m.status not in ['member', 'administrator', 'creator']: raise Exception()
    except:
        # Link fixed with underscores
        kb = [[InlineKeyboardButton("📢 Join Group", url=f"https://t.me/The_Bot_Group")],
              [InlineKeyboardButton("✅ I have Joined", callback_data="check_join")]]
        await u.message.reply_text("👋 Join our group to use the Proxy Scraper.", reply_markup=InlineKeyboardMarkup(kb))
        return

    rem = get_remaining_time(user_id)
    if not rem:
        kb = [[InlineKeyboardButton("📩 Request Access", callback_data=f"req_{user_id}")]]
        await u.message.reply_text("⚠️ No active session.", reply_markup=InlineKeyboardMarkup(kb))
        return

    kb = [['📊 Status', '📥 Get Proxy']]
    await u.message.reply_text(f"✅ **Access Active** ({rem})", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True), parse_mode='Markdown')

async def handle_buttons(u: Update, c: ContextTypes.DEFAULT_TYPE):
    user_id = u.effective_user.id
    text = u.message.text
    now = time.time()
    
    rem_time = get_remaining_time(user_id)
    if user_id != ADMIN_ID and not rem_time:
        await u.message.reply_text("❌ Session expired. Use /start.")
        return

    if text == '📊 Status':
        kb = [[InlineKeyboardButton("🔄 Refresh Status", callback_data="refresh_status")]]
        await u.message.reply_text(get_status_dashboard(), parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))

    elif text == '📥 Get Proxy':
        # Admin Bypass restored: You can test instantly, users wait 60s
        if user_id != ADMIN_ID and user_id in user_cooldowns:
            time_diff = now - user_cooldowns[user_id]
            if time_diff < COOLDOWN_TIME:
                wait = int(COOLDOWN_TIME - time_diff)
                await u.message.reply_text(f"⏳ **Cooldown Active**\nWait `{wait}s` more.", parse_mode='Markdown')
                return

        proxy_text = await get_proxy_card_ui()
        if "❌" not in proxy_text:
            user_cooldowns[user_id] = now 
            msg = await u.message.reply_text(proxy_text, parse_mode='Markdown')
            c.job_queue.run_once(delete_message_job, AUTO_DELETE_TIME, chat_id=u.effective_chat.id, data=msg.message_id)
        else:
            await u.message.reply_text(proxy_text)

async def callback_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    
    if q.data == "check_join": 
        await start(q, c)
    elif q.data == "refresh_status":
        try:
            await q.edit_message_text(
                get_status_dashboard(),
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh Status", callback_data="refresh_status")]])
            )
        except Exception: pass 
    elif q.data.startswith("req_"):
        uid = q.data.split("_")[1]
        kb = [[InlineKeyboardButton("+10m", callback_data=f"add_{uid}_10"), InlineKeyboardButton("+60m", callback_data=f"add_{uid}_60")]]
        await c.bot.send_message(ADMIN_ID, f"🔔 Request from `{uid}`", reply_markup=InlineKeyboardMarkup(kb))
    elif q.data.startswith("add_"):
        _, uid, mins = q.data.split("_")
        user_access[str(uid)] = (datetime.utcnow() + timedelta(minutes=int(mins))).isoformat()
        save_users(user_access)
        await c.bot.send_message(int(uid), f"✨ Access Granted for {mins}m!")

def main():
    if not os.path.exists(SAVE_FILE): open(SAVE_FILE, "w").close()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))
    
    if app.job_queue:
        app.job_queue.run_repeating(scraper_task, interval=120, first=5)
    
    app.run_polling()

if __name__ == "__main__": main()
        
