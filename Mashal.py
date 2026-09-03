import time
import requests
import logging
import threading
from datetime import datetime, timedelta

# ==================== Credentials & Settings ====================
TELEGRAM_BOT_TOKEN = "8695941579:AAF3dMqXMB6kMzuVXFvg5yBMqFltUZ0vOz8"
TELEGRAM_CHAT_ID = "1777406294"

CHECK_INTERVAL = 5             # فحص الإعلانات كل 5 ثوانٍ
HEARTBEAT_INTERVAL = 1800      # تقرير الحالة والعملات اليومية (كل 30 دقيقة)

BINANCE_ANNOUNCEMENTS_API = "https://www.binance.com/bapi/composite/v1/public/cms/article/catalog/list/query?catalogId=48&pageNo=1&pageSize=20"

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

def repeat_alert_task(article):
    """تكرار التنبيه 5 مرات متتالية بين كل تنبيه 5 دقائق"""
    title = article.get("title", "بدون عنوان")
    code = article.get("code", "")
    article_id = article.get("id", "")
    article_url = f"https://www.binance.com/en/support/announcement/{code}" if code else "https://www.binance.com/en/support/announcement"

    for i in range(1, 6):
        message = (
            f"🚨 **تنبيه هام: إعلان جديد في بينانس! (إشعار {i}/5)** 🚨\n\n"
            f"📌 **العنوان:** {title}\n"
            f"🆔 **معرف الإعلان:** `{article_id}`\n\n"
            f"🔗 [عرض الإعلان المباشر على بينانس]({article_url})\n\n"
            f"⚡ *تنبيه مكرر لضمان الانتباه والتحرك السريع.*"
        )
        send_telegram_message(message)
        if i < 5:
            time.sleep(300)  # الانتظار 5 دقائق (300 ثانية) قبل التكرار التالي

def trigger_repeated_alert(article):
    """تشغيل تكرار التنبيهات في مسار خلفي لعدم تعطيل الفحص الرئيسي"""
    threading.Thread(target=repeat_alert_task, args=(article,), daemon=True).start()

def send_daily_status_report():
    """تقرير كل 30 دقيقة يحتوي على كافة الإعلانات والعملات المدرجة اليوم مرتبة تصاعدياً"""
    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day)
    
    today_articles = []
    for art_id, info in known_articles_db.items():
        if info.get("detected_at", now) >= today_start:
            today_articles.append(info)
            
    # ترتيب تصاعدي من الأقدم إلى الأحدث اليوم
    today_articles.sort(key=lambda x: x.get("detected_at", now))
    
    report_msg = (
        f"🟢 **تأكيد حالة البوت وقائمة اليوم (كل 30 دقيقة):**\n"
        f"📅 **التاريخ:** {now.strftime('%Y-%m-%d %H:%M')}\n"
        f"• البوت يعمل بنشاط وبدون مشاكل.\n"
        f"• إجمالي العملات والإعلانات المرصودة اليوم: `{len(today_articles)}`\n"
        f"----------------------------------------\n"
    )
    
    if not today_articles:
        report_msg += "لا توجد إعلانات أو عملات مرصودة حتى الآن لهذا اليوم."
        send_telegram_message(report_msg)
    else:
        send_telegram_message(report_msg)
        for idx, art in enumerate(today_articles, 1):
            t_str = art["detected_at"].strftime("%H:%M:%S")
            code = art.get("code", "")
            article_url = f"https://www.binance.com/en/support/announcement/{code}" if code else "https://www.binance.com/en/support/announcement"
            
            item_msg = (
                f"🔹 **#{idx}** `{t_str}` - {art['title']}\n"
                f"🔗 [رابط الإعلان]({article_url})"
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
        "🤖 **تم تشغيل بوت التتبع المحدث!**\n\n"
        "✅ مراقبة فورية لإعلانات **Binance Official Announcements** كل 5 ثوانٍ.\n"
        "⏰ إرسال قائمة عملات وإعلانات اليوم مرتبة تصاعدياً كل 30 دقيقة.\n"
        "🔔 تكرار التنبيه الفوري عند صدور أي عملة جديدة 5 مرات (بين كل تنبيه 5 دقائق)."
    )
    send_telegram_message(startup_msg)

    last_heartbeat_time = time.time()

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
                    
                    # إطلاق التنبيه الفوري المكرر 5 مرات
                    trigger_repeated_alert(art)

            current_time = time.time()
            
            # تقرير الـ 30 دقيقة مع إظهار العملات مرتبة تصاعدياً
            if current_time - last_heartbeat_time >= HEARTBEAT_INTERVAL:
                send_daily_status_report()
                last_heartbeat_time = current_time

        except Exception as e:
            logging.error(f"Main loop error: {e}")
            
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
