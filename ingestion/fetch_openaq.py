"""
Fetch air quality measurements from OpenAQ API v3 and land raw JSON in the bronze layer.

Bronze layer principle: store the response AS-IS, no transformation, no filtering.
This gives us replayability -- if silver logic changes, we reprocess from bronze
instead of re-hitting the API.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

OPENAQ_BASE_URL = os.getenv("OPENAQ_BASE_URL")
BRONZE_DIR = Path(__file__).parent.parent / "data" / "bronze" / "openaq"

# Cities to track -- keep this small for a portfolio project (3-5 cities is plenty)
CITIES = {
    "Lahore": {"lat": 31.5497, "lon": 74.3436},
    "Delhi": {"lat": 28.7041, "lon": 77.1025},
    "Los Angeles": {"lat": 34.0522, "lon": -118.2437},
}

RADIUS_METERS = 25000  # 25km search radius around each city center


def fetch_locations(lat: float, lon: float, api_key: str) -> dict:
    """Find OpenAQ monitoring stations near a coordinate."""
    resp = requests.get(
        f"{OPENAQ_BASE_URL}/locations",
        params={"coordinates": f"{lat},{lon}", "radius": RADIUS_METERS, "limit": 10},
        headers={"X-API-Key": api_key},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_latest_measurements(location_id: int, api_key: str) -> dict:
    """Get latest sensor readings for a given station."""
    resp = requests.get(
        f"{OPENAQ_BASE_URL}/locations/{location_id}/latest",
        headers={"X-API-Key": api_key},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def run() -> Path:
    api_key = os.getenv("OPENAQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Set OPENAQ_API_KEY env var."
        )

    run_ts = datetime.now(timezone.utc)
    out_dir = BRONZE_DIR / run_ts.strftime("%Y-%m-%d")
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {"fetched_at": run_ts.isoformat(), "cities": {}}

    for city, coords in CITIES.items():
        locations = fetch_locations(coords["lat"], coords["lon"], api_key)
        city_readings = []
        for loc in locations.get("results", []):
            latest = fetch_latest_measurements(loc["id"], api_key)
            city_readings.append({"location": loc, "measurements": latest})
        payload["cities"][city] = city_readings

    out_file = out_dir / f"openaq_{run_ts.strftime('%Y%m%dT%H%M%S')}.json"
    out_file.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {out_file}")
    return out_file


if __name__ == "__main__":
    run()