import os

import requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("TRAVELPAYOUTS_TOKEN")
if not token:
    raise RuntimeError(
        "TRAVELPAYOUTS_TOKEN is missing. Add it to the local .env file."
    )

url = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
params = {
    "origin": "MOW",
    "destination": "LED",
    "departure_at": "2026-11",
    "one_way": "true",
    "direct": "false",
    "sorting": "price",
    "currency": "rub",
    "limit": 30,
}

response = requests.get(
    url,
    params=params,
    headers={"X-Access-Token": token},
    timeout=30,
)

print("HTTP status:", response.status_code)

if response.status_code != 200:
    print("API response:", response.text[:500])
    response.raise_for_status()

payload = response.json()
records = payload.get("data", [])

print("Records received:", len(records))

if records:
    example = records[0]
    safe_fields = {
        key: example.get(key)
        for key in (
            "origin",
            "destination",
            "departure_at",
            "return_at",
            "price",
            "airline",
            "transfers",
            "duration",
        )
    }
    print("First record:", safe_fields)
else:
    print("No records returned for this route and period.")