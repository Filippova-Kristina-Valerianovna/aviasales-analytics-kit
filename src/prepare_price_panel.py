from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_DIR / "data" / "raw"
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = PROCESSED_DIR / "price_panel.csv"


def extract_offers(row: dict) -> list[dict]:
    """Преобразует одну строку JSONL в плоские строки с предложениями."""
    records = []

    payload = row.get("payload", {})
    data = payload.get("data", {})

    if not data:
        return records

    for returned_destination, transfers_groups in data.items():
        for transfers, offer in transfers_groups.items():
            records.append(
                {
                    "collected_at": row["collected_at"],
                    "origin": row["origin"],
                    "destination_requested": row["destination"],
                    "destination_returned": returned_destination,
                    "requested_departure_at": row["departure_at"],
                    "departure_at": offer.get("departure_at"),
                    "return_at": offer.get("return_at"),
                    "expires_at": offer.get("expires_at"),
                    "price": offer.get("price"),
                    "currency": payload.get("currency"),
                    "airline": offer.get("airline"),
                    "flight_number": offer.get("flight_number"),
                    "transfers": int(transfers),
                    "duration": offer.get("duration"),
                    "duration_to": offer.get("duration_to"),
                    "duration_back": offer.get("duration_back"),
                    "source_file": row.get("source_file"),
                }
            )

    return records


def main() -> None:
    raw_files = sorted(RAW_DIR.glob("price_panel_*.jsonl"))

    if not raw_files:
        raise FileNotFoundError(
            "Не найдены файлы price_panel_*.jsonl в data/raw. "
            "Сначала запусти collect_price_panel.py."
        )

    records = []

    for raw_file in raw_files:
        with raw_file.open(encoding="utf-8") as file:
            for line in file:
                row = json.loads(line)
                row["source_file"] = raw_file.name
                records.extend(extract_offers(row))

    if not records:
        raise ValueError(
            "В файлах панели не найдено ни одного ценового предложения. "
            "Проверь содержимое поля payload['data']."
        )

    panel = pd.DataFrame(records)

    datetime_columns = [
        "collected_at",
        "requested_departure_at",
        "departure_at",
        "return_at",
        "expires_at",
    ]

    for column in datetime_columns:
        panel[column] = pd.to_datetime(panel[column], errors="coerce", utc=True)

    numeric_columns = [
        "price",
        "flight_number",
        "transfers",
        "duration",
        "duration_to",
        "duration_back",
    ]

    for column in numeric_columns:
        panel[column] = pd.to_numeric(panel[column], errors="coerce")

    panel["days_before_departure"] = (
        panel["requested_departure_at"].dt.normalize()
        - panel["collected_at"].dt.normalize()
    ).dt.days

    panel["is_direct"] = panel["transfers"].eq(0)

    panel = panel.sort_values(
        ["collected_at", "origin", "destination_requested", "requested_departure_at"]
    ).reset_index(drop=True)

    panel.to_csv(OUTPUT_FILE, index=False)

    print("Подготовка панели завершена.")
    print(f"Raw-файлов обработано: {len(raw_files)}")
    print(f"Ценовых предложений: {len(panel)}")
    print("Пустые ответы API не включены в итоговую таблицу.")
    print(f"Период сбора: {panel['collected_at'].min()} — {panel['collected_at'].max()}")
    print(f"Файл: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()