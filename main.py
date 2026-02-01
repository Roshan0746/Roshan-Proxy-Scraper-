import time, os, asyncio, aiohttp, json, random
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- [ SECURE CONFIG ] ---
BOT_TOKEN = os.getenv("BOT_TOKEN") # Yahan apna Token daalein agar env me nahi hai
ADMIN_ID = int(os.getenv("ADMIN_ID", "421311524"))
REQUIRED_GROUP = "@ThisIsBotGroup" 
SAVE_FILE = "working_proxies.txt"
COOLDOWN_TIME = 60 # Button spam rokne ke liye wait time
AUTO_DELETE_TIME = 600 # 10 Minutes

# Global Stats
stats = {"scraped": 0, "checked": 0, "start": time.time()}
user_cooldowns = {} 

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
        "📢 **Join: @ThisIsBotGroup**"
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
            "📢 **Join: @ThisIsBotGroup**"
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

# --- [ MAIN HANDLERS ] ---
async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    user_id = u.effective_user.id
    
    # --- MEMBER CHECK LOGIC ---
    try:
        if user_id != ADMIN_ID: # Admin bypass check
            m = await c.bot.get_chat_member(chat_id=REQUIRED_GROUP, user_id=user_id)
            if m.status not in ['member', 'administrator', 'creator']: raise Exception()
    except:
        # User not in group
        kb = [[InlineKeyboardButton("📢 Join Group", url="https://t.me/ThisIsBotGroup")],
              [InlineKeyboardButton("✅ I have Joined", callback_data="check_join")]]
        await u.message.reply_text("👋 **Access Denied!**\n\nYou must join our group to use this bot.", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        return

    # --- ACCESS GRANTED (NO TIMER) ---
    kb = [['📊 Status', '📥 Get Proxy']]
    await u.message.reply_text(f"✅ **Access Granted!**\nWelcome to Proxy Scraper.", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True), parse_mode='Markdown')

async def handle_buttons(u: Update, c: ContextTypes.DEFAULT_TYPE):
    user_id = u.effective_user.id
    text = u.message.text
    now = time.time()
    
    # Re-check membership on every click (Security)
    try:
        if user_id != ADMIN_ID:
            m = await c.bot.get_chat_member(chat_id=REQUIRED_GROUP, user_id=user_id)
            if m.status not in ['member', 'administrator', 'creator']:
                await u.message.reply_text("❌ You left the group. Join back to use.")
                return
    except: return

    if text == '📊 Status':
        kb = [[InlineKeyboardButton("🔄 Refresh Status", callback_data="refresh_status")]]
        await u.message.reply_text(get_status_dashboard(), parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))

    elif text == '📥 Get Proxy':
        # Simple Flood Control
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
    
