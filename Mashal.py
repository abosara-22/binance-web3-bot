import time
import requests
import logging
import threading
from datetime import datetime, timezone, timedelta

# ==================== Data & Credentials ====================
TELEGRAM_BOT_TOKEN = "8695941579:AAF3dMqXMB6kMzuVXFvg5yBMqFltUZ0vOz8"
TELEGRAM_CHAT_ID = "1777406294"

CHECK_INTERVAL = 20           # فحص التريند كل 20 ثانية
TWO_HOURS_INTERVAL = 7200     # تقرير كل ساعتين

# DEXScreener Endpoints
DEX_TRENDING_API = "https://api.dexscreener.com/token-boosts/top/v1"
DEX_PAIR_API = "https://api.dexscreener.com/latest/dex/tokens/"

known_trending_tokens = set()
today_logged_tokens = []  # العملات التي دخلت اليوم (لتسجيل تقرير الساعتين)
last_utc_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def send_telegram_message(text):
    """إرسال رسالة عبر التلجرام"""
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
        logging.error(f"Telegram send error: {e}")
        return False

def get_token_details(token_address):
    """جلب بيانات ومؤشرات العملة"""
    try:
        res = requests.get(f"{DEX_PAIR_API}{token_address}", timeout=10)
        if res.status_code == 200:
            data = res.json()
            pairs = data.get("pairs")
            if pairs:
                pairs.sort(key=lambda x: float(x.get("liquidity", {}).get("usd", 0) or 0), reverse=True)
                return pairs[0]
    except Exception as e:
        logging.error(f"Error fetching token pair details: {e}")
    return None

def evaluate_token_advisory(liquidity, mcap, vol_24h):
    """إعطاء رأي استشاري وتقييم المخاطر"""
    if liquidity < 10000:
        return "⚠️ **توخي الحذر الشديد** (السيولة متدنية جداً - High Risk)"
    elif liquidity < 40000:
        return "👀 **تحت الملاحظة** (سيولة متوسطة - لا يُنصح بضخ مبالغ كبيرة)"
    elif liquidity >= 40000 and vol_24h > 100000:
        ratio = (vol_24h / mcap) if mcap > 0 else 0
        if ratio > 0.6:
            return "🔥 **فرصة واعدة للتداول اليومي** (نشاط وتدفق سيولة قوي جداً)"
        return "✅ **جيدة ومستقرة** (سيولة وتداول متوازنان)"
    else:
        return "👀 **تحت الملاحظة والترقب**"

def format_instant_alert(pair_data, alert_num=1):
    """تنسيق التنبيه الفوري المكرر 3 مرات مع عقد قابل للنسخ السريع"""
    base = pair_data.get("baseToken", {})
    symbol = base.get("symbol", "N/A")
    name = base.get("name", "N/A")
    address = base.get("address", "N/A")
    chain = pair_data.get("chainId", "N/A").upper()
    
    price = pair_data.get("priceUsd", "0")
    liquidity = float(pair_data.get("liquidity", {}).get("usd", 0) or 0)
    mcap = float(pair_data.get("fdv", 0) or 0)
    vol_24h = float(pair_data.get("volume", {}).get("h24", 0) or 0)
    created_at = pair_data.get("pairCreatedAt", 0)
    
    utc_launch = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC') if created_at else "غير محدد"
    dex_url = pair_data.get("url", "#")
    
    bot_advisory = evaluate_token_advisory(liquidity, mcap, vol_24h)
    
    msg = (
        f"🚀 **تنبيه عملة جديدة في (رائجة / Trending)!** (إشعار {alert_num}/3)\n\n"
        f"🪙 **العملة:** {name} (`{symbol}`)\n"
        f"🌐 **الشبكة:** `{chain}`\n\n"
        f"📋 **العقد (اضغط للنسخ السريع):**\n`{address}`\n\n"
        f"💵 **السعر الحالي:** `${price}`\n"
        f"💧 **السيولة (Liquidity):** `${liquidity:,.2f}`\n"
        f"📊 **القيمة السوقية (Market Cap):** `${mcap:,.2f}`\n"
        f"📈 **حجم التداول 24س:** `${vol_24h:,.2f}`\n"
        f"⏰ **توقيت الإصدار:** `{utc_launch}`\n\n"
        f"🧠 **الرأي الاستشاري وتقييم المخاطر:**\n{bot_advisory}\n\n"
        f"🔗 [تداول واعرض الرسم البياني على DEX]({dex_url})\n"
        f"⏱️ *تنبيه مكرر (3 مرات كل 5 دقائق).* "
    )
    return msg

def repeat_alert_3_times(pair_data):
    """تكرار التنبيه الفوري 3 مرات يفصل بينها 5 دقائق"""
    for i in range(1, 4):
        msg = format_instant_alert(pair_data, alert_num=i)
        send_telegram_message(msg)
        if i < 3:
            time.sleep(300)

def send_two_hours_report():
    """تقرير كل ساعتين بالعملات المضافة اليوم بتوقيت UTC"""
    now_utc = datetime.now(timezone.utc)
    report_msg = (
        f"📊 **تقرير العملات الرائجة المضافة اليوم (كل ساعتين):**\n"
        f"🌐 **التوقيت:** `{now_utc.strftime('%Y-%m-%d %H:%M UTC')}`\n"
        f"• عدد العملات المرصودة حتى الآن اليوم: `{len(today_logged_tokens)}`\n"
        f"----------------------------------------\n"
    )
    send_telegram_message(report_msg)
    
    if today_logged_tokens:
        for idx, item in enumerate(today_logged_tokens, 1):
            t_msg = (
                f"🔹 **#{idx}** `{item['time_utc']} UTC` - **{item['symbol']}** ({item['chain']})\n"
                f"📋 العقد: `{item['address']}` 👈 *(اضغط للنسخ)*\n"
                f"💵 السعر: `${item['price']}` | 💧 السيولة: `${item['liquidity']:,.0f}` | 📈 التداول: `${item['volume']:,.0f}`"
            )
            send_telegram_message(t_msg)
            time.sleep(1)
    else:
        send_telegram_message("لم تُضَف أي عملات جديدة حتى الآن هذا اليوم.")

def send_end_of_day_best_5_report():
    """تقرير نهاية اليوم (UTC): جلب أفضل 5 عملات متصدرة القائمة عموماً ومناسبة للتداول اليومي"""
    now_utc = datetime.now(timezone.utc)
    
    # جلب القائمة الكاملة الحالية من قائمة رائجة
    trending_raw = fetch_trending_tokens()
    all_pairs = []
    
    for item in trending_raw[:25]:  # أخذ أفضل 25 عملة في التريند للتحليل
        addr = item.get("tokenAddress")
        if addr:
            pair = get_token_details(addr)
            if pair:
                all_pairs.append(pair)
                
    if not all_pairs:
        msg = f"🌙 **تقرير نهاية اليوم (UTC) - {now_utc.strftime('%Y-%m-%d')}**\n\nلم يتم العثور على بيانات كافية في التريند حالياً."
        send_telegram_message(msg)
        return

    # ترتيب العملات المتاحة بالقائمة حالياً حسب السيولة وحجم التداول (أفضل عملات التداول اليومي)
    all_pairs.sort(
        key=lambda x: (
            float(x.get("liquidity", {}).get("usd", 0) or 0) + 
            (float(x.get("volume", {}).get("h24", 0) or 0) * 0.5)
        ),
        reverse=True
    )
    
    top_5 = all_pairs[:5]
    
    report_msg = (
        f"🏆 **التقرير النهائي لليوم لأفضل 5 عملات بقائمة (رائجة) للتداول اليومي**\n"
        f"📅 **التاريخ:** `{now_utc.strftime('%Y-%m-%d UTC')}`\n"
        f"🎯 **المعيار:** متصدرة القائمة عموماً بحجم سيولة ممتازة وتدفق تداول مرتفع.\n"
        f"----------------------------------------\n\n"
    )
    
    for idx, pair in enumerate(top_5, 1):
        base = pair.get("baseToken", {})
        symbol = base.get("symbol", "N/A")
        name = base.get("name", "N/A")
        address = base.get("address", "N/A")
        chain = pair.get("chainId", "N/A").upper()
        
        price = pair.get("priceUsd", "0")
        liquidity = float(pair.get("liquidity", {}).get("usd", 0) or 0)
        vol_24h = float(pair.get("volume", {}).get("h24", 0) or 0)
        dex_url = pair.get("url", "#")
        
        report_msg += (
            f"🏅 **المركز #{idx}: {name} (`{symbol}`)** - [{chain}]\n"
            f"📋 **العقد:** `{address}` 👈 *(اضغط للنسخ)*\n"
            f"💵 **السعر:** `${price}`\n"
            f"💧 **السيولة:** `${liquidity:,.2f}` | 📈 **حجم التداول 24س:** `${vol_24h:,.2f}`\n"
            f"💡 **تقييم التداول:** سيولة قوية وحركة نشطة مناسبة للمضاربة اليومية.\n"
            f"🔗 [فتح الرسم البياني والتداول]({dex_url})\n\n"
        )
        
    report_msg += "⚠️ *تنبيه: التداول اليومي يحمل مخاطر عالية، يرجى التداول بإدارة رأس مال حكيمة.*"
    send_telegram_message(report_msg)

def check_day_reset():
    """تغير اليوم بتوقيت UTC لتصفير السجل اليومي وإرسال تقرير أفضل 5"""
    global today_logged_tokens, last_utc_date
    current_utc_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    if current_utc_date != last_utc_date:
        send_end_of_day_best_5_report()
        today_logged_tokens = []
        last_utc_date = current_utc_date
        logging.info("UTC Day reset complete.")

def fetch_trending_tokens():
    """جلب قائمة التريند المباشرة"""
    try:
        res = requests.get(DEX_TRENDING_API, timeout=10)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        logging.error(f"Fetch error: {e}")
    return []

def main():
    logging.info("Starting Web3 Trending Monitor with Copyable Contracts...")
    
    initial_tokens = fetch_trending_tokens()
    for item in initial_tokens:
        addr = item.get("tokenAddress")
        if addr:
            known_trending_tokens.add(addr)

    startup_msg = (
        "🤖 **تم تشغيل البوت المحدث بنجاح!**\n\n"
        "📋 **العقود:** جميع عناوين العقود أصبحت سهلة للنسخ السريع بنقرة واحدة.\n"
        "⚡ **التنبيه الفوري:** 3 مرات كل 5 دقائق مع التفاصيل والرأي الاستشاري.\n"
        "📊 **تقرير كل ساعتين:** بالعملات المضافة اليوم.\n"
        "🏆 **تقرير نهاية اليوم (UTC):** أفضل 5 عملات متصدرة القائمة عموماً للتداول اليومي."
    )
    send_telegram_message(startup_msg)

    last_two_hours_time = time.time()

    while True:
        try:
            check_day_reset()

            trending_list = fetch_trending_tokens()
            for item in trending_list:
                token_addr = item.get("tokenAddress")
                if not token_addr:
                    continue
                    
                if token_addr not in known_trending_tokens:
                    known_trending_tokens.add(token_addr)
                    
                    pair_data = get_token_details(token_addr)
                    if pair_data:
                        now_utc_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
                        base = pair_data.get("baseToken", {})
                        
                        token_info = {
                            "time_utc": now_utc_str,
                            "symbol": base.get("symbol", "N/A"),
                            "chain": pair_data.get("chainId", "N/A").upper(),
                            "address": base.get("address", "N/A"),
                            "price": pair_data.get("priceUsd", "0"),
                            "liquidity": float(pair_data.get("liquidity", {}).get("usd", 0) or 0),
                            "volume": float(pair_data.get("volume", {}).get("h24", 0) or 0),
                            "url": pair_data.get("url", "#")
                        }
                        today_logged_tokens.append(token_info)
                        
                        threading.Thread(target=repeat_alert_3_times, args=(pair_data,), daemon=True).start()

            if time.time() - last_two_hours_time >= TWO_HOURS_INTERVAL:
                send_two_hours_report()
                last_two_hours_time = time.time()

        except Exception as e:
            logging.error(f"Main loop error: {e}")
            
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
