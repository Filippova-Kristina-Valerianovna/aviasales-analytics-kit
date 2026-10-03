import json
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

REQUIRED_COLUMNS = [
    "origin",
    "destination",
    "departure_at",
    "return_at",
    "price",
    "airline",
    "transfers",
    "duration",
    "found_at",
]


def load_raw_records() -> pd.DataFrame:
    """Load records from all locally stored API JSON responses."""
    records: list[dict] = []

    for json_path in sorted(RAW_DATA_DIR.glob("prices_*.json")):
        with json_path.open(encoding="utf-8") as file:
            raw_payload = json.load(file)

        metadata = raw_payload.get("metadata", {})
        response_data = raw_payload.get("response", {}).get("data", [])

        for record in response_data:
            row = {
                column: record.get(column)
                for column in REQUIRED_COLUMNS
            }
            row["collected_at_utc"] = metadata.get("collected_at_utc")
            row["requested_departure_month"] = metadata.get("departure_month")
            row["source_file"] = json_path.name
            records.append(row)

    if not records:
        raise RuntimeError(
            "No raw JSON files found in data/raw. Run collect_flight_prices.py first."
        )

    return pd.DataFrame(records)


def clean_flight_prices(data: pd.DataFrame) -> pd.DataFrame:
    """Convert types and create analysis-ready features."""
    cleaned = data.copy()

    datetime_columns = [
        "departure_at",
        "return_at",
        "found_at",
        "collected_at_utc",
    ]
    for column in datetime_columns:
        cleaned[column] = pd.to_datetime(cleaned[column], errors="coerce", utc=True)

    numeric_columns = ["price", "transfers", "duration"]
    for column in numeric_columns:
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")

    cleaned = cleaned.dropna(
        subset=["origin", "destination", "departure_at", "price"]
    ).copy()

    cleaned["route"] = cleaned["origin"] + " → " + cleaned["destination"]
    cleaned["departure_date"] = cleaned["departure_at"].dt.date
    cleaned["departure_weekday"] = cleaned["departure_at"].dt.day_name()
    cleaned["departure_hour"] = cleaned["departure_at"].dt.hour
    cleaned["is_direct"] = cleaned["transfers"].eq(0)
    cleaned["duration_hours"] = (cleaned["duration"] / 60).round(2)
    cleaned["days_before_departure"] = (
        cleaned["departure_at"].dt.normalize()
        - cleaned["collected_at_utc"].dt.normalize()
    ).dt.days

    column_order = [
        "route",
        "origin",
        "destination",
        "departure_at",
        "departure_date",
        "departure_weekday",
        "departure_hour",
        "return_at",
        "price",
        "airline",
        "transfers",
        "is_direct",
        "duration",
        "duration_hours",
        "found_at",
        "collected_at_utc",
        "days_before_departure",
        "requested_departure_month",
        "source_file",
    ]

    return cleaned[column_order].sort_values(
        ["route", "departure_at", "price"]
    ).reset_index(drop=True)


def print_quality_summary(data: pd.DataFrame) -> None:
    """Print compact data-quality checks."""
    print(f"Rows: {len(data)}")
    print(f"Routes: {data['route'].nunique()}")
    print(f"Date range: {data['departure_date'].min()} to {data['departure_date'].max()}")
    print(f"Price range: {data['price'].min():.0f} to {data['price'].max():.0f} RUB")
    print(f"Missing prices: {data['price'].isna().sum()}")
    print(f"Duplicate rows: {data.duplicated().sum()}")
    print("\nRows by route:")
    print(data.groupby("route").size().sort_values(ascending=False))


def main() -> None:
    raw_data = load_raw_records()
    prepared_data = clean_flight_prices(raw_data)

    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = PROCESSED_DATA_DIR / "flight_prices_2026-11.csv"

    prepared_data.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"Saved processed data to: {output_path.name}")
    print_quality_summary(prepared_data)


if __name__ == "__main__":
    main()