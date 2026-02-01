import time, os, asyncio, aiohttp, json, random
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- [ SECURE CONFIG ] ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "421311524"))
REQUIRED_GROUP = "@The_Bot_Group" # Naya group
SAVE_FILE = "working_proxies.txt"
USER_DATA_FILE = "user_access.json"
COOLDOWN_TIME = 60 # Seconds

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

def get_progress_bar(ready):
    total_goal = 5000
    ratio = min(ready / total_goal, 1.0)
    bar = "█" * int(ratio * 10) + "░" * (10 - int(ratio * 10))
    return f"[{bar}] {int(ratio * 100)}%"

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

# --- [ LIVE DASHBOARD ] ---
async def update_dashboard(context: ContextTypes.DEFAULT_TYPE):
    ready_count = sum(1 for line in open(SAVE_FILE)) if os.path.exists(SAVE_FILE) else 0
    ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    curr_time = ist_now.strftime('%H:%M:%S')
    
    dash_text = (
        "🛰 **PROXY SCRAPER CORE v7.5**\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🟢 **System:** `Active` | ⚡ **Threads:** `40/s`\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📦 **Scraped:** `{stats['scraped']:,}`\n"
        f"🔎 **Checked:** `{stats['checked']:,}`\n"
        f"🔥 **Ready:** `{ready_count:,}`\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📊 **Efficiency:** `{get_progress_bar(ready_count)}`\n"
        f"🕒 **Last Sync:** `{curr_time} IST`\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "👤 **Developer:** @RoshanGP4A\n"
        "📢 **Group:** @The_Bot_Group"
    )

    try:
        if 'last_dash_id' in context.bot_data:
            await context.bot.edit_message_text(chat_id=ADMIN_ID, message_id=context.bot_data['last_dash_id'], text=dash_text, parse_mode='Markdown')
        else:
            msg = await context.bot.send_message(chat_id=ADMIN_ID, text=dash_text, parse_mode='Markdown')
            context.bot_data['last_dash_id'] = msg.message_id
    except: pass

# --- [ HANDLERS ] ---
async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    user_id = u.effective_user.id
    try:
        m = await c.bot.get_chat_member(chat_id=REQUIRED_GROUP, user_id=user_id)
        if m.status not in ['member', 'administrator', 'creator']: raise Exception()
    except:
        kb = [[InlineKeyboardButton("📢 Join Group", url=f"https://t.me/{REQUIRED_GROUP[1:]}")],
              [InlineKeyboardButton("✅ I have Joined", callback_data="check_join")]]
        await u.message.reply_text("👋 Hello! Join our group to use the Proxy Scraper.", reply_markup=InlineKeyboardMarkup(kb))
        return

    uid_str = str(user_id)
    rem = "Admin" if user_id == ADMIN_ID else None
    if uid_str in user_access:
        expiry = datetime.fromisoformat(user_access[uid_str])
        if datetime.utcnow() < expiry:
            diff = expiry - datetime.utcnow()
            rem = f"{diff.seconds // 60}m {diff.seconds % 60}s"
    
    if not rem:
        kb = [[InlineKeyboardButton("📩 Request Access", callback_data=f"req_{user_id}")]]
        await u.message.reply_text("⚠️ No active session. Request access:", reply_markup=InlineKeyboardMarkup(kb))
        return

    kb = [['📊 Status', '📥 Get Proxy']]
    await u.message.reply_text(f"✅ **Access Active** ({rem})\nChoose an option:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True), parse_mode='Markdown')

async def handle_buttons(u: Update, c: ContextTypes.DEFAULT_TYPE):
    user_id = u.effective_user.id
    text = u.message.text
    
    if text == '📊 Status':
        ready_count = sum(1 for line in open(SAVE_FILE)) if os.path.exists(SAVE_FILE) else 0
        await u.message.reply_text(f"🛰 **STATUS**\nReady: `{ready_count}`\nChecked: `{stats['checked']}`", parse_mode='Markdown')

    elif text == '📥 Get Proxy':
        now = time.time()
        if user_id in user_cooldowns and now - user_cooldowns[user_id] < COOLDOWN_TIME:
            await u.message.reply_text(f"⏳ **Cooldown Active**\nWait `{int(COOLDOWN_TIME - (now - user_cooldowns[user_id]))}s`.", parse_mode='Markdown')
            return

        if os.path.exists(SAVE_FILE) and os.path.getsize(SAVE_FILE) > 0:
            user_cooldowns[user_id] = now
            with open(SAVE_FILE, 'r') as f: all_p = f.readlines()
            sample = random.sample(all_p, min(len(all_p), 2))
            
            isp_name = await get_isp_info(sample[0].split("://")[-1].split(":")[0])

            # --- [ FINALIZED UI ] ---
            proxy_card = (
                "🛰 **PROXY SCRAPER: ASSIGNED**\n"
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
            await u.message.reply_text(proxy_card, parse_mode='Markdown')
        else:
            await u.message.reply_text("❌ No proxies ready yet.")

async def admin_callback(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    if q.data == "check_join": await start(q, c)
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
    app.add_handler(CallbackQueryHandler(admin_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))
    
    if app.job_queue:
        app.job_queue.run_repeating(scraper_task, interval=120, first=5)
        app.job_queue.run_repeating(update_dashboard, interval=15, first=10)
    
    app.run_polling()

if __name__ == "__main__": main()
                    
