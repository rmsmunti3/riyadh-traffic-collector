import os
import time
import base64
import threading
from datetime import datetime
import pytz
import requests
import pandas as pd
from flask import Flask

app = Flask(__name__)

# المتغيرات البيئية
TOMTOM_KEY = os.environ.get("TOMTOM_API_KEY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "rmsmunti3/riyadh-traffic-collector")
CSV_FILENAME = "traffic_data.csv"

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

def update_github_csv(new_records):
    """تحديث ملف CSV مباشرة في مستودع GitHub عبر API"""
    if not GITHUB_TOKEN:
        print("تحذير: لم يتم تعيين GITHUB_TOKEN، لن يتم الرفع إلى GitHub.")
        return

    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{CSV_FILENAME}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    # 1. جلب الملف الحالي من GitHub
    sha = None
    existing_content = ""
    res = requests.get(api_url, headers=headers)
    if res.status_code == 200:
        file_info = res.json()
        sha = file_info.get("sha")
        content_bytes = base64.b64decode(file_info.get("content", ""))
        existing_content = content_bytes.decode("utf-8")

    # 2. إنشاء السطور الجديدة
    df_new = pd.DataFrame(new_records)
    if existing_content.strip():
        # إذا كان الملف موجوداً، نضيف الأسطر بدون تكرار ترويسة الأعمدة (Header)
        new_csv_str = df_new.to_csv(index=False, header=False)
        updated_content = existing_content.rstrip() + "\n" + new_csv_str
    else:
        # إذا كان ملفاً جديداً
        updated_content = df_new.to_csv(index=False, header=True)

    # 3. إرسال التحديث إلى GitHub
    encoded_content = base64.b64encode(updated_content.encode("utf-8")).decode("utf-8")
    payload = {
        "message": f"Auto-update traffic data: {new_records[0]['timestamp']}",
        "content": encoded_content
    }
    if sha:
        payload["sha"] = sha

    put_res = requests.put(api_url, headers=headers, json=payload)
    if put_res.status_code in [200, 201]:
        print(f"تم بنجاح رفع وتحديث {len(new_records)} سطر في {CSV_FILENAME} على GitHub!")
    else:
        print(f"فشل الرفع إلى GitHub: كود {put_res.status_code} - {put_res.text}")

def fetch_traffic():
    riyadh_tz = pytz.timezone("Asia/Riyadh")
    now_str = datetime.now(riyadh_tz).strftime("%Y-%m-%d %H:%M:%S")
    records = []

    print(f"\n--- [ {now_str} ] بدء دورة سحب حركة المرور ---")

    for loc in LOCATIONS:
        url = (
            f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
            f"?point={loc['lat']},{loc['lon']}&unit=KMPH&key={TOMTOM_KEY}"
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
        update_github_csv(records)

def background_loop():
    time.sleep(5)
    while True:
        try:
            fetch_traffic()
        except Exception as err:
            print(f"خطأ في الدورة: {err}")
        print("بانتظار 15 دقيقة للدورة القادمة...")
        time.sleep(900)

@app.route("/")
def home():
    return "Riyadh Traffic Collector is actively updating GitHub 24/7!"

if __name__ == "__main__":
    t = threading.Thread(target=background_loop, daemon=True)
    t.start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
