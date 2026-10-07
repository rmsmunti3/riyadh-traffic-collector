import datetime
import os
import pandas as pd
import pytz
import requests

# Retrieve API key securely from GitHub Environment Secrets
API_KEY = os.environ.get("TOMTOM_API_KEY")

ROADS = [
    # --- North-South Main Arteries ---
    {
        "road_name": "King Fahd Road",
        "district": "Al Olaya",
        "lat": 24.7118,
        "lon": 46.6744,
    },
    {
        "road_name": "King Khalid Road",
        "district": "Umm Al Hamam / Hittin",
        "lat": 24.7292,
        "lon": 46.6115,
    },
    {
        "road_name": "Abu Bakr Al Siddiq Road",
        "district": "Al Wurud / Al Taawun",
        "lat": 24.7561,
        "lon": 46.6998,
    },
    {
        "road_name": "Al Takhassusi Street",
        "district": "Al Mohammadiyyah / Al Rahmaniyyah",
        "lat": 24.7176,
        "lon": 46.6628,
    },
    {
        "road_name": "Prince Turki Al Awwal Road",
        "district": "Hittin / Al Nakheel",
        "lat": 24.7389,
        "lon": 46.6272,
    },
    # --- East-West Main Corridors ---
    {
        "road_name": "Khurais Road",
        "district": "Al Murabba",
        "lat": 24.6908,
        "lon": 46.6853,
    },
    {
        "road_name": "Al Khaleej Bridge (Khurais)",
        "district": "Al Malaz / Al Murabba",
        "lat": 24.6852,
        "lon": 46.7214,
    },
    {
        "road_name": "King Abdullah Road",
        "district": "Al Wurud",
        "lat": 24.7335,
        "lon": 46.6631,
    },
    {
        "road_name": "Al Urubah Road",
        "district": "Al Olaya / Al Rahmaniyyah",
        "lat": 24.7103,
        "lon": 46.6789,
    },
    # --- Ring Roads & Bridges ---
    {
        "road_name": "Northern Ring Road",
        "district": "Al Nakheel",
        "lat": 24.7675,
        "lon": 46.6792,
    },
    {
        "road_name": "Eastern Ring Road",
        "district": "Al Quds",
        "lat": 24.7478,
        "lon": 46.7381,
    },
    {
        "road_name": "Western Ring Road",
        "district": "Dhahrat Laban / Al Suwaidi",
        "lat": 24.6189,
        "lon": 46.6025,
    },
    {
        "road_name": "Wadi Laban Cable Bridge (Suspension Bridge)",
        "district": "Dhahrat Laban",
        "lat": 24.6144,
        "lon": 46.5822,
    },
]

CSV_FILE = "riyadh_traffic_stream.csv"


def collect():
  riyadh_tz = pytz.timezone("Asia/Riyadh")
  now_riyadh = datetime.datetime.now(riyadh_tz)
  timestamp_str = now_riyadh.strftime("%Y-%m-%d %H:%M:%S")

  batch_records = []

  for road in ROADS:
    url = (
        "https://api.tomtom.com/traffic/services/4/flowSegmentData/"
        f"relative0/10/json?point={road['lat']},{road['lon']}&unit=KMPH&key={API_KEY}"
    )

    try:
      resp = requests.get(url, timeout=10)
      if resp.status_code == 200:
        flow = resp.json().get("flowSegmentData", {})
        curr_spd = flow.get("currentSpeed", 0)
        free_spd = flow.get("freeFlowSpeed", 0)
        curr_time = flow.get("currentTravelTime", 0)
        free_time = flow.get("freeFlowTravelTime", 0)

        congestion = (
            round((1 - (curr_spd / free_spd)) * 100, 2) if free_spd > 0 else 0.0
        )
        delay_sec = max(0, curr_time - free_time)
        delay_min = round(delay_sec / 60, 1)

        batch_records.append({
            "timestamp": timestamp_str,
            "road_name": road["road_name"],
            "district": road["district"],
            "latitude": road["lat"],
            "longitude": road["lon"],
            "current_speed_kmh": curr_spd,
            "free_flow_speed_kmh": free_spd,
            "delay_minutes": delay_min,
            "congestion_percentage": max(0.0, congestion),
        })
    except Exception as e:
      print(f"Error on {road['road_name']}: {e}")

  if batch_records:
    df_new = pd.DataFrame(batch_records)
    file_exists = os.path.exists(CSV_FILE)
    df_new.to_csv(
        CSV_FILE, mode="a", index=False, header=not file_exists, encoding="utf-8"
    )
    print(f"[{timestamp_str}] Ingested {len(batch_records)} records.")


if __name__ == "__main__":
  collect()
