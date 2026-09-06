"""
Fetch weather data from Open-Meteo (no API key required, free forever).
Same bronze principle: raw dump, no transformation.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
import os

import requests
from dotenv import load_dotenv

load_dotenv()

OPEN_METEO_URL = os.getenv("OPEN_METEO_URL")
BRONZE_DIR = Path(__file__).parent.parent / "data" / "bronze" / "weather"

# Keep in sync with CITIES in fetch_openaq.py
CITIES = {
    "Lahore": {"lat": 31.5497, "lon": 74.3436},
    "Delhi": {"lat": 28.7041, "lon": 77.1025},
    "Los Angeles": {"lat": 34.0522, "lon": -118.2437},
}

HOURLY_VARS = ["temperature_2m", "relative_humidity_2m", "wind_speed_10m", "precipitation"]


def fetch_weather(lat: float, lon: float) -> dict:
    resp = requests.get(
        OPEN_METEO_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": ",".join(HOURLY_VARS),
            "past_days": 1,
            "forecast_days": 1,
            "timezone": "UTC",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def run() -> Path:
    run_ts = datetime.now(timezone.utc)
    out_dir = BRONZE_DIR / run_ts.strftime("%Y-%m-%d")
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {"fetched_at": run_ts.isoformat(), "cities": {}}
    for city, coords in CITIES.items():
        payload["cities"][city] = fetch_weather(coords["lat"], coords["lon"])

    out_file = out_dir / f"weather_{run_ts.strftime('%Y%m%dT%H%M%S')}.json"
    out_file.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {out_file}")
    return out_file


if __name__ == "__main__":
    run()