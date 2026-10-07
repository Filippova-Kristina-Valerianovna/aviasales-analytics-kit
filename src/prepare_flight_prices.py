import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

INPUT_FILE = RAW_DATA_DIR / "expanded_flight_prices_2026-10-03.jsonl"
OUTPUT_FILE = PROCESSED_DATA_DIR / "flight_prices_2026-10-03.csv"


def load_raw_records() -> tuple[pd.DataFrame, int, int]:
    """Read JSONL responses and flatten offers grouped by number of stops."""
    records: list[dict] = []
    api_responses = 0
    empty_responses = 0

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Raw file not found: {INPUT_FILE.name}. "
            "Run collect_expanded_flight_prices.py first."
        )

    with INPUT_FILE.open(encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue

            api_responses += 1
            request = json.loads(line)
            payload = request.get("payload", {})
            destinations = payload.get("data", {})

            if not payload.get("success") or not destinations:
                empty_responses += 1
                continue

            for returned_destination, offers_by_stops in destinations.items():
                for stops_text, offer in offers_by_stops.items():
                    if not offer:
                        continue

                    records.append(
                        {
                            "collected_at": request.get("collected_at"),
                            "origin": request.get("origin"),
                            "destination_requested": request.get("destination"),
                            "destination_returned": returned_destination,
                            "requested_departure_at": request.get("departure_at"),
                            "days_ahead": request.get("days_ahead"),
                            "currency": payload.get("currency"),
                            "transfers": pd.to_numeric(
                                stops_text,
                                errors="coerce",
                            ),
                            "airline": offer.get("airline"),
                            "price": offer.get("price"),
                            "flight_number": offer.get("flight_number"),
                            "departure_at": offer.get("departure_at"),
                            "return_at": offer.get("return_at"),
                            "expires_at": offer.get("expires_at"),
                            "duration": offer.get("duration"),
                            "duration_to": offer.get("duration_to"),
                            "duration_back": offer.get("duration_back"),
                            "source_file": INPUT_FILE.name,
                        }
                    )

    if not records:
        raise RuntimeError(
            "The raw file was read, but no flight offers were found."
        )

    return pd.DataFrame(records), api_responses, empty_responses


def clean_flight_prices(data: pd.DataFrame) -> pd.DataFrame:
    """Convert fields and create analysis-ready columns."""
    cleaned = data.copy()

    datetime_columns = [
        "collected_at",
        "requested_departure_at",
        "departure_at",
        "return_at",
        "expires_at",
    ]
    for column in datetime_columns:
        cleaned[column] = pd.to_datetime(
            cleaned[column],
            errors="coerce",
            utc=True,
        )

    numeric_columns = [
        "days_ahead",
        "transfers",
        "price",
        "flight_number",
        "duration",
        "duration_to",
        "duration_back",
    ]
    for column in numeric_columns:
        cleaned[column] = pd.to_numeric(
            cleaned[column],
            errors="coerce",
        )

    cleaned = cleaned.dropna(
        subset=[
            "origin",
            "destination_requested",
            "departure_at",
            "price",
        ]
    ).copy()

    cleaned = cleaned.loc[cleaned["price"] > 0].copy()

    cleaned["route"] = (
        cleaned["origin"]
        + " -> "
        + cleaned["destination_requested"]
    )
    cleaned["departure_date"] = cleaned["departure_at"].dt.date
    cleaned["return_date"] = cleaned["return_at"].dt.date
    cleaned["departure_weekday"] = cleaned["departure_at"].dt.day_name()
    cleaned["departure_hour"] = cleaned["departure_at"].dt.hour
    cleaned["is_direct"] = cleaned["transfers"].eq(0)

    cleaned["duration_hours"] = (
        cleaned["duration"] / 60
    ).round(2)
    cleaned["duration_to_hours"] = (
        cleaned["duration_to"] / 60
    ).round(2)
    cleaned["duration_back_hours"] = (
        cleaned["duration_back"] / 60
    ).round(2)

    cleaned["days_before_departure"] = (
        cleaned["departure_at"].dt.normalize()
        - cleaned["collected_at"].dt.normalize()
    ).dt.days

    column_order = [
        "route",
        "origin",
        "destination_requested",
        "destination_returned",
        "collected_at",
        "requested_departure_at",
        "departure_at",
        "departure_date",
        "departure_weekday",
        "departure_hour",
        "return_at",
        "return_date",
        "days_ahead",
        "days_before_departure",
        "price",
        "currency",
        "airline",
        "flight_number",
        "transfers",
        "is_direct",
        "duration",
        "duration_hours",
        "duration_to",
        "duration_to_hours",
        "duration_back",
        "duration_back_hours",
        "expires_at",
        "source_file",
    ]

    return (
        cleaned[column_order]
        .sort_values(
            ["route", "departure_at", "transfers", "price"]
        )
        .reset_index(drop=True)
    )


def print_quality_summary(
    data: pd.DataFrame,
    api_responses: int,
    empty_responses: int,
) -> None:
    """Print compact and useful quality checks."""
    print(f"API responses read: {api_responses}")
    print(f"Empty or unsuccessful responses: {empty_responses}")
    print(f"Flight offers after cleaning: {len(data)}")
    print(f"Routes: {data['route'].nunique()}")
    print(
        "Departure date range: "
        f"{data['departure_date'].min()} to "
        f"{data['departure_date'].max()}"
    )
    print(
        "Price range: "
        f"{data['price'].min():.0f} to "
        f"{data['price'].max():.0f} "
        f"{data['currency'].mode().iat[0].upper()}"
    )
    print(f"Missing prices: {data['price'].isna().sum()}")
    print(f"Duplicate rows: {data.duplicated().sum()}")

    print("\nOffers by number of transfers:")
    print(data["transfers"].value_counts().sort_index())

    print("\nOffers by route:")
    print(data.groupby("route").size().sort_values(ascending=False))


def main() -> None:
    raw_data, api_responses, empty_responses = load_raw_records()
    prepared_data = clean_flight_prices(raw_data)

    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    prepared_data.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print(f"Saved processed data to: {OUTPUT_FILE.name}")
    print_quality_summary(
        prepared_data,
        api_responses,
        empty_responses,
    )


if __name__ == "__main__":
    main()