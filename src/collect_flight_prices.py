import json
import os
from datetime import UTC, datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
API_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"

ROUTES = [
    {"origin": "MOW", "destination": "LED"},
    {"origin": "MOW", "destination": "KZN"},
    {"origin": "MOW", "destination": "AER"},
    {"origin": "LED", "destination": "KZN"},
    {"origin": "LED", "destination": "AER"},
]


def fetch_route_prices(
    origin: str,
    destination: str,
    token: str,
    departure_month: str,
) -> dict:
    """Request cached ticket-price observations for one route."""
    params = {
        "origin": origin,
        "destination": destination,
        "departure_at": departure_month,
        "one_way": "true",
        "direct": "false",
        "sorting": "price",
        "currency": "rub",
        "limit": 1000,
    }

    response = requests.get(
        API_URL,
        params=params,
        headers={"X-Access-Token": token},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    load_dotenv()

    token = os.getenv("TRAVELPAYOUTS_TOKEN")
    if not token:
        raise RuntimeError(
            "TRAVELPAYOUTS_TOKEN is missing. Add it to the local .env file."
        )

    departure_month = "2026-11"
    collected_at = datetime.now(UTC)
    collected_at_iso = collected_at.isoformat()

    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    for route in ROUTES:
        origin = route["origin"]
        destination = route["destination"]

        print(f"Requesting {origin} -> {destination}...")

        payload = fetch_route_prices(
            origin=origin,
            destination=destination,
            token=token,
            departure_month=departure_month,
        )

        output = {
            "metadata": {
                "collected_at_utc": collected_at_iso,
                "departure_month": departure_month,
                "origin": origin,
                "destination": destination,
                "source": "Aviasales Data API / Travelpayouts",
            },
            "response": payload,
        }

        filename = (
            f"prices_{origin}_{destination}_"
            f"{collected_at.strftime('%Y%m%dT%H%M%SZ')}.json"
        )
        output_path = RAW_DATA_DIR / filename

        with output_path.open("w", encoding="utf-8") as file:
            json.dump(output, file, ensure_ascii=False, indent=2)

        records_count = len(payload.get("data", []))
        print(f"Saved {records_count} records to {output_path.name}")

    print("Collection complete.")


if __name__ == "__main__":
    main()
    
