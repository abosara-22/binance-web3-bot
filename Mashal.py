import time
import requests
import logging
import threading
from datetime import datetime, timezone, timedelta

# ==================== Data & Credentials ====================
TELEGRAM_BOT_TOKEN = "8695941579:AAF3dMqXMB6kMzuVXFvg5yBMqFltUZ0vOz8"
TELEGRAM_CHAT_ID = "1777406294"

CHECK_INTERVAL = 20         # فحص التريند كل 20 ثانية
FOUR_HOURS_INTERVAL = 14400 # تقرير كل 4 ساعات (14400 ثانية)

# DEXScreener Endpoints
DEX_TRENDING_API = "https://api.dexscreener.com/token-boosts/top/v1"
DEX_PAIR_API = "https://api.dexscreener.com/latest/dex/tokens/"

known_trending_tokens = set()
today_logged_tokens = []  # العملات التي دخلت اليوم لتتبعها في التقرير
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
    """جلب بيانات ومؤشرات العملة الحالية من DEXScreener"""
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
    if liquidity < 1000:
        return "🚨 **تحذير عالي (Rug Pull / احتيال)** - تم سحب معظم السيولة!"
    elif liquidity < 10000:
        return "⚠️ **توخي الحذر الشديد** (السيولة متدنية جداً - High Risk)"
    elif liquidity < 40000:
        return "👀 **تحت الملاحظة** (سيولة متوسطة)"
    elif liquidity >= 40000 and vol_24h > 100000:
        ratio = (vol_24h / mcap) if mcap > 0 else 0
        if ratio > 0.6:
            return "🔥 **فرصة واعدة للتداول اليومي** (نشاط وتدفق سيولة قوي)"
        return "✅ **جيدة ومستقرة** (سيولة وتداول متوازنان)"
    else:
        return "👀 **تحت الملاحظة والترقب**"

def send_instant_alert(pair_data):
    """إرسال تنبيه فوري مرّة واحدة فقط فور رصد العملة الجديدة"""
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
        f"🚀 **تنبيه عملة جديدة في (رائجة / Trending)!**\n\n"
        f"🪙 **العملة:** {name} (`{symbol}`)\n"
        f"🌐 **الشبكة:** `{chain}`\n\n"
        f"📋 **العقد (اضغط للنسخ السريع):**\n`{address}`\n\n"
        f"💵 **السعر الحالي:** `${price}`\n"
        f"💧 **السيولة:** `${liquidity:,.2f}`\n"
        f"📊 **القيمة السوقية:** `${mcap:,.2f}`\n"
        f"📈 **حجم التداول 24س:** `${vol_24h:,.2f}`\n"
        f"⏰ **توقيت الإصدار:** `{utc_launch}`\n\n"
        f"🧠 **الرأي الاستشاري وتقييم المخاطر:**\n{bot_advisory}\n\n"
        f"🔗 [تداول واعرض الرسم البياني على DEX]({dex_url})"
    )
    send_telegram_message(msg)

def send_four_hours_report():
    """تقرير شامل كل 4 ساعات مع فحص حقيقي لحالة العملات ورصد سحب السيولة"""
    now_utc = datetime.now(timezone.utc)
    report_msg = (
        f"📊 **التقرير الدائري المحدث (كل 4 ساعات):**\n"
        f"🌐 **التوقيت:** `{now_utc.strftime('%Y-%m-%d %H:%M UTC')}`\n"
        f"• إجمالي العملات المرصودة اليوم: `{len(today_logged_tokens)}`\n"
        f"----------------------------------------\n"
    )
    send_telegram_message(report_msg)
    
    if not today_logged_tokens:
        send_telegram_message("لم تُضَف أي عملات جديدة حتى الآن هذا اليوم.")
        return

    for idx, item in enumerate(today_logged_tokens, 1):
        # جلب البيانات الحية المحدثة للعملة الآن
        current_pair = get_token_details(item['address'])
        
        if current_pair:
            curr_price = current_pair.get("priceUsd", "0")
            curr_liq = float(current_pair.get("liquidity", {}).get("usd", 0) or 0)
            curr_vol = float(current_pair.get("volume", {}).get("h24", 0) or 0)
            
            # كشف سحب السيولة (Rug Pull)
            if curr_liq < 500:
                status_str = "🚨 **[Rug Pull / احتيال - تم سحب السيولة]**"
            else:
                initial_liq = item['initial_liquidity']
                liq_change = ((curr_liq - initial_liq) / initial_liq * 100) if initial_liq > 0 else 0
                status_str = f"🟢 **نشطة** (تغير السيولة: `{liq_change:+.1f}%`)"

            t_msg = (
                f"🔹 **#{idx}** `{item['time_utc']} UTC` - **{item['symbol']}** ({item['chain']})\n"
                f"📋 العقد: `{item['address']}` 👈 *(اضغط للنسخ)*\n"
                f"📌 **الحالة الحالية:** {status_str}\n"
                f"💵 السعر: `${curr_price}` | 💧 السيولة الحالية: `${curr_liq:,.0f}` | 📈 التداول: `${curr_vol:,.0f}`"
            )
        else:
            # في حال تم حذف زوج التداول تماماً من المنصة
            t_msg = (
                f"🔹 **#{idx}** `{item['time_utc']} UTC` - **{item['symbol']}** ({item['chain']})\n"
                f"📋 العقد: `{item['address']}` 👈 *(اضغط للنسخ)*\n"
                f"📌 **الحالة الحالية:** 🚨 **[تم حذف الزوج / احتمال احتيال مؤكد]**"
            )
            
        send_telegram_message(t_msg)
        time.sleep(1)

def send_end_of_day_best_5_report():
    """تقرير نهاية اليوم (UTC): أفضل 5 عملات متصدرة القائمة للتداول اليومي"""
    now_utc = datetime.now(timezone.utc)
    trending_raw = fetch_trending_tokens()
    all_pairs = []
    
    for item in trending_raw[:25]:
        addr = item.get("tokenAddress")
        if addr:
            pair = get_token_details(addr)
            if pair:
                all_pairs.append(pair)
                
    if not all_pairs:
        msg = f"🌙 **تقرير نهاية اليوم (UTC) - {now_utc.strftime('%Y-%m-%d')}**\n\nلم يتم العثور على بيانات كافية في التريند حالياً."
        send_telegram_message(msg)
        return

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
    logging.info("Starting Web3 Trending Monitor with Live Status & 4H Reports...")
    
    initial_tokens = fetch_trending_tokens()
    for item in initial_tokens:
        addr = item.get("tokenAddress")
        if addr:
            known_trending_tokens.add(addr)

    startup_msg = (
        "🤖 **تم تشغيل البوت المحدث بنجاح!**\n\n"
        "⚡ **التنبيه الفوري:** تنبيه واحد فقط لكل عملة جديدة بدقة عالية.\n"
        "📊 **تقرير كل 4 ساعات:** تقرير شامل ببيانات حية ومباشرة لكشف عملات سحب السيولة (Rug Pull).\n"
        "🏆 **تقرير نهاية اليوم (UTC):** أفضل 5 عملات مناسبة للتداول اليومي."
    )
    send_telegram_message(startup_msg)

    last_four_hours_time = time.time()

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
                            "initial_liquidity": float(pair_data.get("liquidity", {}).get("usd", 0) or 0)
                        }
                        today_logged_tokens.append(token_info)
                        
                        # إرسال تنبيه واحد فقط بدون تكرار
                        send_instant_alert(pair_data)

            # إرسال التقرير الشامل كل 4 ساعات
            if time.time() - last_four_hours_time >= FOUR_HOURS_INTERVAL:
                send_four_hours_report()
                last_four_hours_time = time.time()

        except Exception as e:
            logging.error(f"Main loop error: {e}")
            
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
