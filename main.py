import time, os, asyncio, aiohttp, json, random
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- [ CONFIG ] ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "421311524"))
REQUIRED_GROUP = "@roshantesting" #
SAVE_FILE = "working_proxies.txt"
USER_DATA_FILE = "user_access.json"
COOLDOWN_TIME = 60 # Seconds

# Stats tracking
stats = {"scraped": 0, "checked": 0, "start": time.time()}
user_cooldowns = {} 

# --- [ PERSISTENCE & UI HELPERS ] ---
def load_users():
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_users(data):
    with open(USER_DATA_FILE, "w") as f: json.dump(data, f)

user_access = load_users()

def get_progress_bar(ready):
    # Attractive progress bar logic
    total_goal = 5000
    ratio = min(ready / total_goal, 1.0)
    filled = int(ratio * 10)
    bar = "█" * filled + "░" * (10 - filled)
    return f"[{bar}] {int(ratio * 100)}%"

# --- [ CORE SCRAPER ENGINE ] ---
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
                    tasks = [check_proxy(p.strip(), p_type, context) for p in proxies[:40] if ":" in p]
                    await asyncio.gather(*tasks)
            except: continue

# --- [ LIVE DASHBOARD TASK ] ---
async def update_dashboard(context: ContextTypes.DEFAULT_TYPE):
    # Admin ke liye live updating UI
    ready_count = 0
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, 'r') as f: ready_count = len(f.readlines())
    
    ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    curr_time = ist_now.strftime('%H:%M:%S')
    
    dash_text = (
        "🛰 **PROXY SCRAPER v6.0**\n"
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
        "🤖 **Bot:** [Click Here](https://t.me/YourBotUsername)" # Replace with your bot link
    )

    try:
        # Purane message ko edit karega bina spam kiye
        if 'last_dash_id' in context.bot_data:
            await context.bot.edit_message_text(
                chat_id=ADMIN_ID,
                message_id=context.bot_data['last_dash_id'],
                text=dash_text,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
        else:
            msg = await context.bot.send_message(chat_id=ADMIN_ID, text=dash_text, parse_mode='Markdown', disable_web_page_preview=True)
            context.bot_data['last_dash_id'] = msg.message_id
    except: pass

# --- [ USER HANDLERS ] ---
async def is_member(user_id, context):
    try:
        member = await context.bot.get_chat_member(chat_id=REQUIRED_GROUP, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except: return False

def get_remaining_time(user_id):
    if user_id == ADMIN_ID: return "Unlimited (Admin)"
    uid_str = str(user_id)
    if uid_str not in user_access: return None
    expiry = datetime.fromisoformat(user_access[uid_str])
    if datetime.utcnow() > expiry: return None
    diff = expiry - datetime.utcnow()
    return f"{diff.seconds // 60}m {diff.seconds % 60}s"

async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    user_id = u.effective_user.id
    if not await is_member(user_id, c):
        kb = [[InlineKeyboardButton("📢 Join Group", url=f"https://t.me/{REQUIRED_GROUP[1:]}")],
              [InlineKeyboardButton("✅ I have Joined", callback_data="check_join")]]
        await u.message.reply_text("👋 Hello! Access is limited to group members.", reply_markup=InlineKeyboardMarkup(kb))
        return

    rem = get_remaining_time(user_id)
    if not rem:
        kb = [[InlineKeyboardButton("📩 Request Access", callback_data=f"req_{user_id}")]]
        await u.message.reply_text("⚠️ No active session found. Request access:", reply_markup=InlineKeyboardMarkup(kb))
        return

    kb = [['📊 Status', '📥 Get Proxy']]
    await u.message.reply_text(f"✅ **Access Active**\nRemaining: `{rem}`", 
                               reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True), parse_mode='Markdown')

async def handle_buttons(u: Update, c: ContextTypes.DEFAULT_TYPE):
    user_id = u.effective_user.id
    text = u.message.text
    
    if user_id != ADMIN_ID and not get_remaining_time(user_id):
        await u.message.reply_text("❌ Session expired. Use /start.")
        return

    if text == '📊 Status':
        ready_count = 0
        if os.path.exists(SAVE_FILE):
            with open(SAVE_FILE, 'r') as f: ready_count = len(f.readlines())
        await u.message.reply_text(f"🛰 **STATUS**\nReady IPs: `{ready_count}`\nChecked: `{stats['checked']}`", parse_mode='Markdown')

    elif text == '📥 Get Proxy':
        now = time.time()
        if user_id in user_cooldowns and now - user_cooldowns[user_id] < COOLDOWN_TIME: #
            wait = int(COOLDOWN_TIME - (now - user_cooldowns[user_id]))
            await u.message.reply_text(f"⏳ Cooldown: Wait `{wait}s`.", parse_mode='Markdown')
            return

        if os.path.exists(SAVE_FILE) and os.path.getsize(SAVE_FILE) > 0:
            user_cooldowns[user_id] = now
            with open(SAVE_FILE, 'r') as f: all_p = f.readlines()
            # Send limited random proxies
            sample = random.sample(all_p, min(len(all_p), 2))
            proxies_text = "\n".join([f"✅ `{p.strip()}`" for p in sample])
            await u.message.reply_text(f"🎯 **Your Working IPs:**\n{proxies_text}\n\n👤 Dev: @RoshanGP4A", parse_mode='Markdown') #
        else:
            await u.message.reply_text("❌ No proxies ready. Scraper is running...")

async def callback_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
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

# --- [ MAIN ] ---
def main():
    if not os.path.exists(SAVE_FILE): open(SAVE_FILE, "w").close()
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))
    
    if app.job_queue:
        # Scraper har 2 min mein chalega
        app.job_queue.run_repeating(scraper_task, interval=120, first=5)
        # Dashboard har 15 seconds mein edit hoga
        app.job_queue.run_repeating(update_dashboard, interval=15, first=10)
    
    app.run_polling()

if __name__ == "__main__": main()
        
