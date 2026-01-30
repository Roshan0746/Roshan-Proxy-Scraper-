import time, os, asyncio, aiohttp
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- [ SECURE CONFIG ] ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "421311524"))
SAVE_FILE = "working_proxies.txt"

stats = {"scraped": 0, "checked": 0, "ready": 0, "start": time.time(), "active": True}

# --- [ INTEL ENGINE ] ---

async def get_ip_intel(ip):
    try:
        url = f"http://ip-api.com/json/{ip}?fields=status,countryCode,city,isp,query"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as r:
                data = await r.json()
                return data if data.get('status') == 'success' else None
    except: return None

async def check_proxy(proxy, p_type, context):
    url = "https://www.instagram.com/accounts/login/"
    proxy_url = f"http://{proxy}" if p_type == "http" else f"{p_type}://{proxy}"
    stats["checked"] += 1
    
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.get(url, proxy=proxy_url) as response:
                if response.status == 200:
                    stats["ready"] += 1
                    intel = await get_ip_intel(proxy.split(":")[0])
                    
                    cc = intel.get('countryCode', 'UN') if intel else "UN"
                    flag = chr(ord(cc[0]) + 127397) + chr(ord(cc[1]) + 127397)
                    isp = intel.get('isp', 'Unknown ISP') if intel else "Unknown ISP"
                    is_res = "👤 Residential" if any(x in isp.lower() for x in ["telecom", "jio", "network", "mobile", "broadband"]) else "☁️ Datacenter"
                    
                    # --- IST TIMING LOGIC ---
                    # UTC se +5:30 hours add kar rahe hain
                    ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
                    curr_time = ist_now.strftime('%H:%M')

                    msg = (
                        "🔎 **FRESH IP FOUND**\n"
                        "───────────────────\n"
                        f"⚙️ **Type:** {p_type.upper()}\n"
                        f"🔗 **Addr:** `{proxy}`\n"
                        f"🚀 **Perf:** Active • {is_res}\n"
                        f"📶 **Net:** {flag} {isp}\n"
                        "───────────────────\n"
                        f"✅ **Verified & Active** • ⏱ {curr_time} IST"
                    )
                    await context.bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode='Markdown')
                    with open(SAVE_FILE, "a") as f: f.write(f"{p_type}://{proxy}\n")
    except Exception: pass

async def scraper_task(context: ContextTypes.DEFAULT_TYPE):
    if not stats["active"]: return
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

# --- [ HANDLERS ] ---

async def post_init(application: Application):
    try:
        await application.bot.send_message(chat_id=ADMIN_ID, text="🚀 **Engine Online on Railway!**\nTime Zone set to IST.")
    except: pass

async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    kb = [['📊 Status', '📥 Get Proxy']]
    await u.message.reply_text(
        "🚀 **Roshan Proxy Engine v4.4**\n"
        "───────────────────\n"
        "Developer: RoshanGP4A\n"
        "Status: Hunting for IG IPs...", 
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
        parse_mode='Markdown'
    )

async def handle_buttons(u: Update, c: ContextTypes.DEFAULT_TYPE):
    text = u.message.text
    if text == '📊 Status':
        uptime = round((time.time() - stats["start"]) / 60, 1)
        await u.message.reply_text(
            f"🛰 **REAL-TIME STATS**\n"
            "───────────────────\n"
            f"📦 **Total Scraped:** {stats['scraped']}\n"
            f"🔎 **Total Checked:** {stats['checked']}\n"
            f"🔥 **IG Ready Found:** {stats['ready']}\n"
            f"⏱ **System Uptime:** {uptime}m",
            parse_mode='Markdown'
        )
    elif text == '📥 Get Proxy':
        if os.path.exists(SAVE_FILE) and os.path.getsize(SAVE_FILE) > 0:
            with open(SAVE_FILE, 'r') as f: last = f.readlines()[-1].strip()
            await u.message.reply_text(f"✅ **Latest Working IP:**\n`{last}`", parse_mode='Markdown')
        else:
            await u.message.reply_text("❌ No verified proxies yet.")

def main():
    if not os.path.exists(SAVE_FILE): open(SAVE_FILE, "w").close()
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))
    
    if app.job_queue:
        app.job_queue.run_repeating(scraper_task, interval=120, first=5)
    
    app.run_polling()

if __name__ == "__main__": main()
