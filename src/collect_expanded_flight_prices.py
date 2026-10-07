from __future__ import annotations

import json
import os
import time
from datetime import date, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data" / "raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Берём настройки из .env в корне проекта:
# aviasales-analytics-kit/.env
load_dotenv(PROJECT_DIR / ".env")

API_URL = "https://api.travelpayouts.com/v1/prices/cheap"
TOKEN = os.getenv("TRAVELPAYOUTS_TOKEN")

ORIGINS = [
    "MOW",  # Москва
    "LED",  # Санкт-Петербург
    "KZN",  # Казань
    "SVX",  # Екатеринбург
    "OVB",  # Новосибирск
]

DESTINATIONS = [
    "AER",  # Сочи
    "LED",  # Санкт-Петербург
    "KZN",  # Казань
    "SVX",  # Екатеринбург
    "OVB",  # Новосибирск
    "TJM",  # Тюмень
    "UFA",  # Уфа
    "ROV",  # Ростов-на-Дону
    "KRR",  # Краснодар
    "MRV",  # Минеральные Воды
]

DEPARTURE_DAYS_AHEAD = [7, 14, 21, 30, 45, 60, 90, 120]
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

    collected_at = date.today().isoformat()
    output_file = DATA_DIR / f"expanded_flight_prices_{collected_at}.jsonl"

    requests_total = 0
    records_total = 0

    with output_file.open("w", encoding="utf-8") as file:
        for origin in ORIGINS:
            for destination in DESTINATIONS:
                if origin == destination:
                    continue

                for days_ahead in DEPARTURE_DAYS_AHEAD:
                    departure_at = date.today() + timedelta(days=days_ahead)

                    try:
                        payload = fetch_prices(origin, destination, departure_at)
                        requests_total += 1

                        row = {
                            "collected_at": collected_at,
                            "origin": origin,
                            "destination": destination,
                            "departure_at": departure_at.isoformat(),
                            "days_ahead": days_ahead,
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

    print("\nСбор завершён.")
    print(f"Запросов отправлено: {requests_total}")
    print(f"Строк записано: {records_total}")
    print(f"Файл: {output_file}")


if __name__ == "__main__":
    main()