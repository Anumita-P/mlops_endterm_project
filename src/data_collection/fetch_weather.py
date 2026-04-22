"""
NASA POWER Tamil Nadu Weather Fetcher (STABLE VERSION)
"""

import requests
import pandas as pd
from datetime import datetime
from pathlib import Path
import time
import random

# -----------------------------
# CONFIG
# -----------------------------
BASE_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

PARAMETERS = [
    "T2M",
    "T2M_MAX",
    "T2M_MIN",
    "PRECTOTCORR",
    "RH2M",
    "WS10M"
]

USER = "user123"   # IMPORTANT: not 'anonymous'

MAX_RETRIES = 5

# -----------------------------
# DISTRICTS
# -----------------------------
TN_DISTRICTS = {
    "Chengalpattu": (12.6753, 79.9496),
    "Cuddalore": (11.7507, 79.7789),
    "Dharmapuri": (12.1387, 78.5556),
    "Dindigul": (10.3624, 77.9754),
    "Erode": (11.3409, 77.7149),
    "Kanchipuram": (12.8343, 79.7029),
    "Kanniyakumari": (8.0883, 77.5385),
    "Karur": (10.9357, 78.0760),
    "Krishnagiri": (12.2022, 78.2111),
    "Madurai": (9.9252, 78.1198),
    "Nagapattinam": (10.7667, 79.8500),
    "Namakkal": (11.2261, 78.1667),
    "Nilgiris": (11.4429, 76.7236),
    "Perambalur": (11.2975, 78.8748),
    "Pudukkottai": (10.3833, 78.8167),
    "Ranipet": (12.9211, 79.3287),
    "Salem": (11.6643, 78.1460),
    "Sivagangai": (9.8489, 78.4734),
    "Tenkasi": (8.9604, 77.3159),
    "Thanjavur": (10.7870, 79.1378),
    "Theni": (10.0111, 77.4696),
    "Thirupathur": (12.2293, 79.3305),
    "Thiruvannamalai": (12.2343, 79.0733),
    "Tiruchirapalli": (10.7905, 78.7047),
    "Tirunelveli": (8.7139, 77.2566),
    "Tiruppur": (11.1085, 77.3411),
    "Tiruvallur": (13.1288, 79.9064),
    "Tiruvanantapuram": (8.7426, 76.9856),
    "Toothukudi": (8.7642, 78.1348),
    "Villupuram": (12.9698, 79.4969),
    "Virudhunagar": (9.5933, 77.9567),
    "Vellore": (12.9689, 79.1288),
}
# -----------------------------
# FETCH YEAR (ROBUST)
# -----------------------------
def fetch_year(lat, lon, year):
    params = {
        "start": f"{year}0101",
        "end": f"{year}1231",
        "latitude": lat,
        "longitude": lon,
        "parameters": ",".join(PARAMETERS),
        "format": "JSON",
        "community": "AG",
        "user": USER
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(BASE_URL, params=params, timeout=30)

            print(f"   🔍 {year} → {r.status_code}")

            if r.status_code == 200:
                return r.json()

            print("   ❌", r.text[:150])

        except requests.exceptions.RequestException as e:
            print(f"   ⚠️ Retry {attempt}/{MAX_RETRIES} failed:", e)

        # exponential backoff + jitter
        sleep_time = (2 ** attempt) + random.uniform(0, 1)
        time.sleep(sleep_time)

    raise Exception("Failed after retries")


# -----------------------------
# PARSE
# -----------------------------
def parse_nasa_response(data, district, lat, lon):
    rows = []

    if "properties" not in data:
        return rows

    daily = data["properties"]["parameter"]

    # get date keys safely
    dates = list(next(iter(daily.values())).keys())

    for d in dates:
        date_obj = datetime.strptime(d, "%Y%m%d").date()

        row = {
            "district": district,
            "latitude": lat,
            "longitude": lon,
            "date": date_obj,
            "year": date_obj.year,
            "month": date_obj.month,
        }

        for param in PARAMETERS:
            row[param] = daily.get(param, {}).get(d)

        rows.append(row)

    return rows


# -----------------------------
# MAIN
# -----------------------------
def main():
    print("🚀 Starting NASA POWER fetch...\n")

    all_rows = []

    for i, (district, (lat, lon)) in enumerate(TN_DISTRICTS.items(), 1):
        print(f"\n[{i}/{len(TN_DISTRICTS)}] {district}")

        for year in range(2000, 2022):
            try:
                data = fetch_year(lat, lon, year)
                rows = parse_nasa_response(data, district, lat, lon)
                all_rows.extend(rows)

            except Exception as e:
                print(f"   ✗ {year} FAILED:", e)

            # rate limiting safety
            time.sleep(0.5)

    df = pd.DataFrame(all_rows)

    if df.empty:
        print("\n❌ No data collected")
        return

    df = df.sort_values(["district", "date"])

    Path("data/raw/weather").mkdir(parents=True, exist_ok=True)
    df.to_csv("data/raw/weather/nasa_power_tn.csv", index=False)

    print("\n✅ DONE")
    print("Rows:", len(df))
    print("Districts:", df["district"].nunique())


if __name__ == "__main__":
    main()