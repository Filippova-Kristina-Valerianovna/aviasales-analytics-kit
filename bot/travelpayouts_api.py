import json
import os
from datetime import date, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv


PROJECT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_DIR / ".env")

API_URL = (
    "https://api.travelpayouts.com"
    "/aviasales/v3/prices_for_dates"
)


def fetch_flights(
    origin: str,
    destination: str,
    departure_date: str,
) -> list[dict]:
    token = os.getenv("TRAVELPAYOUTS_TOKEN")

    if not token:
        raise RuntimeError("Не заполнен TRAVELPAYOUTS_TOKEN в .env")

    params = {
        "origin": origin,
        "destination": destination,
        "departure_at": departure_date,
        "currency": "rub",
        "one_way": "true",
        "direct": "false",
        "sorting": "price",
        "unique": "false",
        "limit": 5,
        "page": 1,
    }

    response = requests.get(
        API_URL,
        params=params,
        headers={"X-Access-Token": token},
        timeout=30,
    )
    response.raise_for_status()

    payload = response.json()

    if payload.get("success") is not True:
        raise RuntimeError("API не подтвердил успешный запрос")

    flights = payload.get("data")

    if not isinstance(flights, list):
        raise RuntimeError("API вернул неожиданный формат data")

    return flights


def main() -> None:
    departure_date = (
        date.today() + timedelta(days=14)
    ).isoformat()

    print(f"Проверяем MOW → LED, вылет {departure_date}")

    try:
        flights = fetch_flights(
            origin="MOW",
            destination="LED",
            departure_date=departure_date,
        )
    except requests.Timeout:
        print("Ошибка: API не ответил за отведённое время.")
        return
    except requests.ConnectionError:
        print("Ошибка соединения с API. Проверь интернет и VPN.")
        return
    except requests.HTTPError as error:
        print(
            "Ошибка HTTP:",
            error.response.status_code,
        )
        return
    except (ValueError, RuntimeError) as error:
        print("Ошибка обработки ответа:", str(error))
        return

    print(f"Получено предложений: {len(flights)}")

    if not flights:
        print("Для этого запроса в ответе API нет предложений.")
        return

    print(json.dumps(flights[0], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()