import time
import requests
import logging
from datetime import datetime, timedelta

# ==================== Credentials & Settings ====================
TELEGRAM_BOT_TOKEN = "8695941579:AAF3dMqXMB6kMzuVXFvg5yBMqFltUZ0vOz8"
TELEGRAM_CHAT_ID = "1777406294"

CHECK_INTERVAL = 5             # فحص الإعلانات الجديدة
HEARTBEAT_INTERVAL = 1800      # رسالة التأكيد (كل 30 دقيقة)
REPORT_INTERVAL = 21600        # إرسال التقرير الشامل (كل 6 ساعات)

REPORT_DAYS_WINDOW = 10        # مدة التقرير بالأيام

# رابط إعلانات بينانس المباشر والرسمي
BINANCE_ANNOUNCEMENTS_API = "https://www.binance.com/bapi/composite/v1/public/cms/article/catalog/list/query?catalogId=48&pageNo=1&pageSize=15"

# سجل المقالات والإعلانات المكتشفة
known_articles_db = {}

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

def fetch_binance_announcements():
    """جلب قائمة إعلانات بينانس الرسمية"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    try:
        res = requests.get(BINANCE_ANNOUNCEMENTS_API, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data.get("success") and "data" in data and "articles" in data["data"]:
                return data["data"]["articles"]
    except Exception as e:
        logging.error(f"API Error fetching announcements: {e}")
    return []

def send_announcement_alert(article):
    """تنبيه فوري عند صدور إعلان إدراج أو مشروع جديد"""
    title = article.get("title", "بدون عنوان")
    code = article.get("code", "")
    article_id = article.get("id", "")
    article_url = f"https://www.binance.com/en/support/announcement/{code}" if code else "https://www.binance.com/en/support/announcement"
    
    message = (
        f"🚨 **تنبيه إعلان جديد من بينانس!** 🚨\n\n"
        f"📌 **العنوان:** {title}\n"
        f"🆔 **معرف الإعلان:** `{article_id}`\n\n"
        f"🔗 [عرض الإعلان المباشر على بينانس]({article_url})\n\n"
        f"⚡ *تابع المنصة والتداول فوراً لمواكبة التحديث.*"
    )
    send_telegram_message(message)

def generate_and_send_report():
    """توليد وإرسال التقرير الشامل للإعلانات المكتشفة"""
    logging.info(f"Generating {REPORT_DAYS_WINDOW}-day comprehensive report...")
    
    now = datetime.now()
    days_ago = now - timedelta(days=REPORT_DAYS_WINDOW)
    
    recent_articles = []
    for art_id, info in known_articles_db.items():
        detected_time = info.get("detected_at", now)
        if detected_time >= days_ago:
            recent_articles.append(info)
            
    recent_articles.sort(key=lambda x: x.get("detected_at", now), reverse=True)
    
    if not recent_articles:
        send_telegram_message(f"📊 **تقرير الـ {REPORT_DAYS_WINDOW} أيام الماضية:**\n\nلم يتم رصد إعلانات جديدة خلال هذه الفترة.")
        return

    header_msg = (
        f"📊 **التقرير التحليلي للإعلانات (آخر {REPORT_DAYS_WINDOW} أيام)** 📊\n"
        f"📅 **التاريخ:** {now.strftime('%Y-%m-%d %H:%M')}\n"
        f"🔢 **إجمالي الإعلانات المكتشفة:** {len(recent_articles)}\n"
        f"----------------------------------------"
    )
    send_telegram_message(header_msg)

    for idx, art_data in enumerate(recent_articles, 1):
        det_time = art_data["detected_at"].strftime("%Y-%m-%d %H:%M")
        code = art_data.get("code", "")
        article_url = f"https://www.binance.com/en/support/announcement/{code}" if code else "https://www.binance.com/en/support/announcement"

        item_msg = (
            f"📌 **#{idx} {art_data['title']}**\n"
            f"⏰ **وقت الرصد:** `{det_time}`\n"
            f"🔗 [رابط المقال]({article_url})"
        )
        send_telegram_message(item_msg)
        time.sleep(1)

def main():
    logging.info("Starting Binance Announcements Monitoring Bot...")
    
    initial_articles = fetch_binance_announcements()
    now = datetime.now()
    
    for art in initial_articles:
        art_id = art.get("id")
        if art_id:
            known_articles_db[art_id] = {
                "id": art_id,
                "title": art.get("title", "Unknown"),
                "code": art.get("code", ""),
                "detected_at": now
            }

    logging.info(f"Loaded {len(known_articles_db)} existing announcements. Bot active...")

    startup_msg = (
        "🤖 **تم تشغيل بوت التتبع والتحليل المتقدم!**\n\n"
        "✅ مراقبة فورية لإعلانات **Binance Official Announcements**.\n"
        "⏰ تأكيد حالة كل 30 دقيقة.\n"
        f"📊 **تقرير شامل وتحليلي كل 6 ساعات** لإعلانات الـ {REPORT_DAYS_WINDOW} أيام الماضية."
    )
    send_telegram_message(startup_msg)

    # إرسال التقرير الشامل فوراً عند التشغيل
    generate_and_send_report()

    last_heartbeat_time = time.time()
    last_report_time = time.time()

    while True:
        try:
            articles = fetch_binance_announcements()
            for art in articles:
                art_id = art.get("id")
                if not art_id:
                    continue
                    
                if art_id not in known_articles_db:
                    title = art.get("title", "Unknown")
                    code = art.get("code", "")
                    detect_time = datetime.now()
                    
                    logging.info(f"New announcement detected: {title}")
                    
                    art_data = {
                        "id": art_id,
                        "title": title,
                        "code": code,
                        "detected_at": detect_time
                    }
                    known_articles_db[art_id] = art_data
                    
                    send_announcement_alert(art)

            current_time = time.time()
            
            if current_time - last_heartbeat_time >= HEARTBEAT_INTERVAL:
                heartbeat_msg = (
                    "🟢 **تأكيد حالة البوت (كل 30 دقيقة):**\n\n"
                    "• البوت يعمل بنشاط وبدون مشاكل.\n"
                    f"• إجمالي الإعلانات المحفوظة بالسجلات: `{len(known_articles_db)}`"
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
