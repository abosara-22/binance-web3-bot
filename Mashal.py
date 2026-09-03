import time
import requests
import logging
from datetime import datetime, timedelta

# ==================== Credentials & Settings ====================
TELEGRAM_BOT_TOKEN = "8695941579:AAF3dMqXMB6kMzuVXFvg5yBMqFltUZ0vOz8"
TELEGRAM_CHAT_ID = "1777406294"

CHECK_INTERVAL = 5             # فحص الإدراجات الجديدة (كل 5 ثوانٍ)
HEARTBEAT_INTERVAL = 1800      # رسالة التأكيد (كل 30 دقيقة)
REPORT_INTERVAL = 21600        # إرسال التقرير الشامل (كل 6 ساعات)

# 👈 غير هذا الرقم لتحديد مدة التقرير بالأيام (مثلاً: 7 لتقرير 7 أيام)
REPORT_DAYS_WINDOW = 4         

BINANCE_WEB3_API = "https://web3.binance.com/api/v1/dex/market/tokens"

# سجل للعملات المكتشفة
known_tokens_db = {}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def send_telegram_message(text):
    """إرسال رسالة نصية عبر التلجرام"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.status_code == 200
    except Exception as e:
        logging.error(f"Error sending message to Telegram: {e}")
        return False

def get_dex_details(contract_address):
    """جلب التفاصيل المتقدمة من DEXScreener"""
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{contract_address}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            pairs = data.get("pairs")
            if pairs and len(pairs) > 0:
                pair = pairs[0]
                
                liquidity = pair.get("liquidity", {}).get("usd", 0)
                price = pair.get("priceUsd", "N/A")
                fdv = pair.get("fdv", "N/A")
                price_change_24h = pair.get("priceChange", {}).get("h24", 0)
                
                info = pair.get("info", {})
                
                lp_locked = "غير محدد"
                if "liquidity" in pair and pair["liquidity"].get("base", 0) == 0:
                    lp_locked = "🔒 مغلقة / محروقة 100%"
                else:
                    lp_locked = "⚠️ غير مؤكدة / مفتوحة"

                websites = info.get("websites", [])
                socials = info.get("socials", [])
                
                site_url = websites[0].get("url") if websites else "غير متوفر"
                twitter_url = "غير متوفر"
                for s in socials:
                    if s.get("type") == "twitter":
                        twitter_url = s.get("url")
                        break
                        
                return {
                    "price": price,
                    "liquidity": liquidity,
                    "fdv": fdv,
                    "price_change_24h": price_change_24h,
                    "lp_locked": lp_locked,
                    "site": site_url,
                    "twitter": twitter_url,
                }
    except Exception as e:
        logging.error(f"Error fetching DEX details: {e}")
    return None

def evaluate_token_risk(liquidity, site, twitter, lp_locked):
    """تقييم مخاطر شامل ومفصل للعملة"""
    try:
        liq = float(liquidity)
    except:
        liq = 0

    if liq < 5000 or "مفتوحة" in lp_locked:
        return "🛑 خطر مرتفع (سيولة ضعيفة أو غير مغلقة - لا ينصح بالاستثمار)"
    elif liq >= 50000 and (site != "غير متوفر" or twitter != "غير متوفر"):
        return "🟢 آمنة نسبياً وواعدة (سيولة ممتازة وتوثيق قنوات)"
    else:
        return "🟡 غير واضحة / تحت المراقبة (تتطلب فحص يدوي دقيق)"

def send_telegram_alert(token_name, symbol, contract_address, chain, price, dex_info):
    """تنبيه فوري عند إدراج عملة جديدة"""
    liq = dex_info.get("liquidity", 0) if dex_info else 0
    site = dex_info.get("site", "غير متوفر") if dex_info else "غير متوفر"
    twitter = dex_info.get("twitter", "غير متوفر") if dex_info else "غير متوفر"
    current_price = dex_info.get("price", price) if dex_info else price
    fdv = dex_info.get("fdv", "غير معلن") if dex_info else "غير معلن"
    lp_locked = dex_info.get("lp_locked", "غير محدد") if dex_info else "غير محدد"
    
    rating = evaluate_token_risk(liq, site, twitter, lp_locked)
    dex_search_url = f"https://dexscreener.com/search?q={contract_address}"
    
    message = (
        f"🚨 **تنبيه: عملة جديدة في Binance Web3!** 🚨\n\n"
        f"🔹 **الاسم:** {token_name} ({symbol})\n"
        f"🌐 **الشبكة:** {chain}\n"
        f"💵 **السعر الأول:** ${price}\n"
        f"💧 **السيولة الحالية:** ${liq:,.2f} USD\n"
        f"🔐 **السيولة المغلقة:** {lp_locked}\n"
        f"🪙 **القيمة الكلية (FDV):** ${fdv}\n\n"
        f"🌐 **الموقع:** {site}\n"
        f"🐦 **تويتر:** {twitter}\n\n"
        f"📝 **عنوان العقد (انقر للنسخ):**\n"
        f"`{contract_address}`\n\n"
        f"💡 **التقييم الاسترشادي:**\n"
        f"👈 {rating}\n\n"
        f"🔗 [فتح العملة على DEXScreener]({dex_search_url})\n\n"
        f"⚠️ *مسؤولية القرار الاستثماري تعود لك بالكامل.*"
    )
    send_telegram_message(message)

def generate_and_send_report():
    """توليد وإرسال التقرير الشامل بناءً على المدة المحددة"""
    logging.info(f"Generating {REPORT_DAYS_WINDOW}-day comprehensive report...")
    
    now = datetime.now()
    days_ago = now - timedelta(days=REPORT_DAYS_WINDOW)
    
    recent_tokens = []
    for contract, info in known_tokens_db.items():
        detected_time = info.get("detected_at", now)
        if detected_time >= days_ago:
            recent_tokens.append(info)
            
    recent_tokens.sort(key=lambda x: x.get("detected_at", now), reverse=True)
    
    if not recent_tokens:
        send_telegram_message(f"📊 **تقرير الـ {REPORT_DAYS_WINDOW} أيام الماضية:**\n\nلم يتم إدراج عملات جديدة خلال هذه الفترة.")
        return

    header_msg = (
        f"📊 **التقرير التحليلي الشامل (آخر {REPORT_DAYS_WINDOW} أيام)** 📊\n"
        f"📅 **التاريخ:** {now.strftime('%Y-%m-%d %H:%M')}\n"
        f"🔢 **إجمالي العملات المكتشفة:** {len(recent_tokens)}\n"
        f"----------------------------------------\n"
        f"⚠️ *ملاحظة: هذا التقرير استرشادي، ومسؤولية القرار المالي تعود لك.*"
    )
    send_telegram_message(header_msg)

    for idx, token_data in enumerate(recent_tokens, 1):
        contract = token_data["contract"]
        dex_info = get_dex_details(contract) or {}
        
        launch_time = token_data["detected_at"].strftime("%Y-%m-%d %H:%M")
        launch_price = token_data.get("initial_price", "N/A")
        current_price = dex_info.get("price", launch_price)
        liq = dex_info.get("liquidity", 0)
        lp_locked = dex_info.get("lp_locked", "غير محدد")
        change_24h = dex_info.get("price_change_24h", 0)
        
        site = dex_info.get("site", "غير متوفر")
        twitter = dex_info.get("twitter", "غير متوفر")
        
        risk_status = evaluate_token_risk(liq, site, twitter, lp_locked)
        dex_url = f"https://dexscreener.com/search?q={contract}"

        item_msg = (
            f"📌 **#{idx} {token_data['name']} ({token_data['symbol']})**\n"
            f"🌐 **الشبكة:** {token_data['chain']}\n"
            f"⏰ **وقت الإدراج:** `{launch_time}`\n"
            f"💵 **سعر الإدراج:** ${launch_price}\n"
            f"📈 **السعر الحالي:** ${current_price} ({change_24h}% 24h)\n"
            f"💧 **السيولة:** ${liq:,.2f} USD\n"
            f"🔐 **حالة السيولة:** {lp_locked}\n\n"
            f"📝 **عقد العملة (انقر للنسخ):**\n"
            f"`{contract}`\n\n"
            f"🛡️ **رأي البوت للتحليل:**\n{risk_status}\n\n"
            f"🔗 [فحص التداول على DEXScreener]({dex_url})"
        )
        send_telegram_message(item_msg)
        time.sleep(1)

def fetch_web3_tokens():
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    params = {"page": 1, "size": 30, "sort": "listTime", "order": "desc"}
    try:
        res = requests.get(BINANCE_WEB3_API, headers=headers, params=params, timeout=5)
        if res.status_code == 200:
            return res.json().get("data", [])
    except Exception as e:
        logging.error(f"API Error: {e}")
    return []

def main():
    logging.info("Starting Binance Web3 Monitoring & Analytics Bot...")
    
    initial_tokens = fetch_web3_tokens()
    now = datetime.now()
    
    for token in initial_tokens:
        contract = token.get("contractAddress") or token.get("address")
        if contract:
            c_lower = contract.lower()
            known_tokens_db[c_lower] = {
                "name": token.get("name", "Unknown"),
                "symbol": token.get("symbol", "N/A"),
                "chain": token.get("chain", "N/A"),
                "contract": contract,
                "initial_price": token.get("price", "N/A"),
                "detected_at": now
            }

    logging.info(f"Loaded {len(known_tokens_db)} existing tokens. Bot active...")

    startup_msg = (
        "🤖 **تم تشغيل بوت التتبع والتحليل المتقدم!**\n\n"
        "✅ مراقبة فورية لـ **Binance Web3** كل 5 ثوانٍ.\n"
        "⏰ تأكيد حالة كل 30 دقيقة.\n"
        f"📊 **تقرير شامل وتحليلي كل 6 ساعات** لعملات الـ {REPORT_DAYS_WINDOW} أيام الماضية."
    )
    send_telegram_message(startup_msg)

    # إرسال التقرير الشامل فوراً عند التشغيل
    generate_and_send_report()

    last_heartbeat_time = time.time()
    last_report_time = time.time()

    while True:
        try:
            tokens = fetch_web3_tokens()
            for token in tokens:
                contract = token.get("contractAddress") or token.get("address")
                if not contract:
                    continue
                    
                c_lower = contract.lower()
                if c_lower not in known_tokens_db:
                    name = token.get("name", "Unknown")
                    symbol = token.get("symbol", "N/A")
                    chain = token.get("chain", "N/A")
                    price = token.get("price", "N/A")
                    detect_time = datetime.now()
                    
                    logging.info(f"New token detected: {symbol} ({contract})")
                    
                    token_data = {
                        "name": name,
                        "symbol": symbol,
                        "chain": chain,
                        "contract": contract,
                        "initial_price": price,
                        "detected_at": detect_time
                    }
                    known_tokens_db[c_lower] = token_data
                    
                    dex_info = get_dex_details(contract)
                    send_telegram_alert(name, symbol, contract, chain, price, dex_info)

            current_time = time.time()
            
            if current_time - last_heartbeat_time >= HEARTBEAT_INTERVAL:
                heartbeat_msg = (
                    "🟢 **تأكيد حالة البوت (كل 30 دقيقة):**\n\n"
                    "• البوت يعمل بنشاط وبدون مشاكل.\n"
                    f"• إجمالي العملات المحفوظة بالسجلات: `{len(known_tokens_db)}`"
                )
                send_telegram_message(heartbeat_msg)
                last_heartbeat_time = current_time

            if current_time - last_report_time >= REPORT_INTERVAL:
                generate_and_send_report()
                last_report_time = current_time

        except Exception as e:
            logging.error(f"Main loop error: {e}")
            
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()