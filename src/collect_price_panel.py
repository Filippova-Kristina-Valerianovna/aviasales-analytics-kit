from __future__ import annotations

import json
import os
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data" / "raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(PROJECT_DIR / ".env")

API_URL = "https://api.travelpayouts.com/v1/prices/cheap"
TOKEN = os.getenv("TRAVELPAYOUTS_TOKEN")

TRACKED_ROUTES = [
    ("MOW", "LED"),
    ("MOW", "AER"),
    ("LED", "KZN"),
    ("KZN", "AER"),
    ("SVX", "OVB"),
]

TRACKED_DEPARTURES = [
    date(2026, 11, 15),
    date(2026, 12, 15),
    date(2027, 1, 15),
]

REQUEST_PAUSE_SECONDS = 0.4

def fetch_prices(origin: str, destination: str, departure_at: date) -> dict:
    params = {
        "token": TOKEN,
        "origin": origin,
        "destination": destination,
        "departure_at": departure_at.isoformat(),
        "currency": "rub",
    }

    response = requests.get(API_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()

def main() -> None: 
    if not TOKEN: 
        raise ValueError(
            "Не найден TRAVELPAYOUTS_TOKEN. "
            "Проверь файл .env в корне проекта."
        )

    collected_at = datetime.now(timezone.utc).isoformat()
    file_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    output_file = DATA_DIR / f"price_panel_{file_timestamp}.jsonl"

    requests_total = 0
    records_total = 0

    with output_file.open("w", encoding="utf-8") as file:
        for origin, destination in TRACKED_ROUTES:
            for departure_at in TRACKED_DEPARTURES:
                try:
                    payload = fetch_prices(origin, destination, departure_at)
                    requests_total += 1

                    row = {
                        "collected_at": collected_at,
                        "origin": origin,
                        "destination": destination,
                        "departure_at": departure_at.isoformat(),
                        "payload": payload,
                    }

                    file.write(json.dumps(row, ensure_ascii=False) + "\n")
                    records_total += 1

                    print(
                        f"[{requests_total}] "
                        f"{origin} → {destination}, "
                        f"{departure_at}: OK"
                    )

                except requests.RequestException as error:
                    print(
                        f"[{requests_total}] "
                        f"{origin} → {destination}, "
                        f"{departure_at}: ERROR — {error}"
                    )

                time.sleep(REQUEST_PAUSE_SECONDS)

    print("\nСбор панели завершён.")
    print(f"Запросов отправлено: {requests_total}")
    print(f"Строк записано: {records_total}")
    print(f"Файл: {output_file}")


if __name__ == "__main__":
    main()