import os
import time
import threading
from datetime import datetime
import pytz
import requests
import pandas as pd
from flask import Flask

# إعداد تطبيق ويب بسيط لإرضاء سيرفر Render المجاني
app = Flask(__name__)

# مفتاح TomTom API من متغيرات البيئة
API_KEY = os.environ.get("TOMTOM_API_KEY", "")
CSV_FILE = "traffic_data.csv"

# الشرايين الـ 13 الرئيسية في الرياض
LOCATIONS = [
    {"name": "King Fahd Rd (Olaya / Downtown)", "lat": 24.7136, "lon": 46.6753},
    {"name": "Northern Ring Rd (Al Nakheel / KAFD)", "lat": 24.7743, "lon": 46.6385},
    {"name": "Eastern Ring Rd (Exit 10 / Al Quds)", "lat": 24.7562, "lon": 46.7487},
    {"name": "Southern Ring Rd (Shubra / Namar)", "lat": 24.5821, "lon": 46.6892},
    {"name": "Western Ring Rd (Dhahrat Laban)", "lat": 24.6437, "lon": 46.5921},
    {"name": "Makkah Al Mukarramah Rd (Al Mutamarat)", "lat": 24.6712, "lon": 46.6914},
    {"name": "Khurais Rd (Al Malaz / Al Rawdah)", "lat": 24.7088, "lon": 46.7326},
    {"name": "King Abdullah Rd (Al Wurud / Salah Ad Din)", "lat": 24.7431, "lon": 46.6834},
    {"name": "King Abdulaziz Rd (Al Yasmin / Sahafa)", "lat": 24.8115, "lon": 46.6453},
    {"name": "Prince Turki Ibn Abdulaziz Al Awwal (Hittin)", "lat": 24.7618, "lon": 46.6112},
    {"name": "King Khalid Rd (Hittin / Umm Al Hamam)", "lat": 24.7391, "lon": 46.5881},
    {"name": "Al Takhassusi (Al Mohammadiyyah)", "lat": 24.7295, "lon": 46.6573},
    {"name": "Olaya St (Al Olaya District)", "lat": 24.6975, "lon": 46.6852}
]

def fetch_traffic():
    """دالة لجلب بيانات حركة المرور لجميع الشرايين وحفظها في CSV"""
    riyadh_tz = pytz.timezone("Asia/Riyadh")
    now_str = datetime.now(riyadh_tz).strftime("%Y-%m-%d %H:%M:%S")
    records = []

    print(f"\n--- [ {now_str} ] بدء دورة سحب حركة المرور ---")

    for loc in LOCATIONS:
        url = (
            f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
            f"?point={loc['lat']},{loc['lon']}&unit=KMPH&key={API_KEY}"
        )
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                flow = resp.json().get("flowSegmentData", {})
                current_speed = flow.get("currentSpeed", 0)
                free_speed = flow.get("freeFlowSpeed", 0)
                current_time_sec = flow.get("currentTravelTime", 0)
                free_time_sec = flow.get("freeFlowTravelTime", 0)

                delay_sec = max(0, current_time_sec - free_time_sec)
                congestion_pct = (
                    round(((free_speed - current_speed) / free_speed) * 100, 2)
                    if free_speed > current_speed else 0.0
                )

                records.append({
                    "timestamp": now_str,
                    "location_name": loc["name"],
                    "latitude": loc["lat"],
                    "longitude": loc["lon"],
                    "current_speed_kmh": current_speed,
                    "free_flow_speed_kmh": free_speed,
                    "current_travel_time_sec": current_time_sec,
                    "free_flow_travel_time_sec": free_time_sec,
                    "delay_seconds": delay_sec,
                    "congestion_pct": congestion_pct
                })
            else:
                print(f"خطأ في جلب {loc['name']}: كود {resp.status_code}")
        except Exception as e:
            print(f"استثناء أثناء جلب {loc['name']}: {e}")

    if records:
        df_new = pd.DataFrame(records)
        if os.path.exists(CSV_FILE):
            df_new.to_csv(CSV_FILE, mode="a", header=False, index=False)
        else:
            df_new.to_csv(CSV_FILE, mode="w", header=True, index=False)
        print(f"تم بنجاح حفظ {len(records)} نقطة مرورية في {CSV_FILE}.")

def background_loop():
    """حلقة مستمرة تنفذ السحب كل 15 دقيقة في خيط معالجة منفصل"""
    # انتظار بضع ثوانٍ حتى يعمل خادم الويب أولاً
    time.sleep(5)
    while True:
        try:
            fetch_traffic()
        except Exception as err:
            print(f"خطأ غير متوقع في الدورة: {err}")
        print("بانتظار 15 دقيقة (900 ثانية) حتى الدورة القادمة...")
        time.sleep(900)

@app.route("/")
def home():
    return "Riyadh Traffic Collector is running 24/7!"

if __name__ == "__main__":
    # تشغيل مهمة السحب في الخلفية (Thread)
    collector_thread = threading.Thread(target=background_loop, daemon=True)
    collector_thread.start()

    # تشغيل خادم Flask على المنفذ المطلوب بواسطة Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
