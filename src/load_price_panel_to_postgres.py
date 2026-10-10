from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_DIR / "data" / "raw"

load_dotenv(PROJECT_DIR / ".env")

db_url = (
    f"postgresql+psycopg://{os.getenv('POSTGRES_USER')}:"
    f"{os.getenv('POSTGRES_PASSWORD')}@"
    f"{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/"
    f"{os.getenv('POSTGRES_DB')}"
)

engine = create_engine(db_url)


CREATE_RAW_HASH_COLUMN = text(
    """
    ALTER TABLE raw.travelpayouts_responses
    ADD COLUMN IF NOT EXISTS source_hash TEXT;

    CREATE UNIQUE INDEX IF NOT EXISTS uq_travelpayouts_responses_source_hash
    ON raw.travelpayouts_responses (source_hash);
    """
)

INSERT_RAW_RESPONSE = text(
    """
    INSERT INTO raw.travelpayouts_responses (
        source_system,
        endpoint,
        request_params,
        response_payload,
        collected_ts,
        http_status,
        records_received,
        load_status,
        source_hash
    )
    VALUES (
        'travelpayouts',
        :endpoint,
        CAST(:request_params AS JSONB),
        CAST(:response_payload AS JSONB),
        CAST(:collected_ts AS TIMESTAMPTZ),
        :http_status,
        :records_received,
        'success',
        :source_hash
    )
    ON CONFLICT (source_hash) DO NOTHING
    RETURNING response_id;
    """
)

GET_RAW_RESPONSE_ID = text(
    """
    SELECT response_id
    FROM raw.travelpayouts_responses
    WHERE source_hash = :source_hash;
    """
)

INSERT_OBSERVATION = text(
    """
    INSERT INTO staging.flight_price_observations (
        response_id,
        origin_iata,
        destination_iata,
        route_key,
        departure_date,
        return_date,
        price,
        currency_code,
        airline_code,
        flight_number,
        transfers,
        duration_minutes,
        collected_ts,
        source_system
    )
    VALUES (
        :response_id,
        :origin_iata,
        :destination_iata,
        :route_key,
        CAST(:departure_date AS DATE),
        CAST(:return_date AS DATE),
        :price,
        :currency_code,
        :airline_code,
        :flight_number,
        :transfers,
        :duration_minutes,
        CAST(:collected_ts AS TIMESTAMPTZ),
        'travelpayouts'
    );
    """
)


def parse_timestamp(value: str) -> str:
    return value.replace("Z", "+00:00")


def get_source_hash(row: dict) -> str:
    canonical_json = json.dumps(
        row,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def extract_observations(row: dict, response_id: int) -> list[dict]:
    payload = row.get("payload", {})
    data = payload.get("data", {})

    observations = []

    for destination_returned, transfers_groups in data.items():
        for transfers, offer in transfers_groups.items():
            departure_at = offer.get("departure_at")
            if not departure_at or offer.get("price") is None:
                continue

            observations.append(
                {
                    "response_id": response_id,
                    "origin_iata": row["origin"],
                    "destination_iata": destination_returned,
                    "route_key": f"{row['origin']}-{destination_returned}",
                    "departure_date": departure_at[:10],
                    "return_date": (
                        offer["return_at"][:10]
                        if offer.get("return_at")
                        else None
                    ),
                    "price": offer["price"],
                    "currency_code": (
                        payload.get("currency") or "rub"
                    ).upper(),
                    "airline_code": offer.get("airline"),
                    "flight_number": (
                        str(offer["flight_number"])
                        if offer.get("flight_number") is not None
                        else None
                    ),
                    "transfers": int(transfers),
                    "duration_minutes": offer.get("duration"),
                    "collected_ts": parse_timestamp(row["collected_at"]),
                }
            )

    return observations


def main() -> None:
    raw_files = sorted(RAW_DIR.glob("price_panel_*.jsonl"))

    if not raw_files:
        raise FileNotFoundError(
            "No files price_panel_*.jsonl found in data/raw."
        )

    requests_loaded = 0
    requests_skipped = 0
    observations_loaded = 0

    with engine.begin() as connection:
        connection.execute(CREATE_RAW_HASH_COLUMN)

        for raw_file in raw_files:
            with raw_file.open(encoding="utf-8") as file:
                for line in file:
                    row = json.loads(line)
                    source_hash = get_source_hash(row)

                    payload = row.get("payload", {})
                    records_received = len(payload.get("data", {}))

                    request_params = {
                        "origin": row["origin"],
                        "destination": row["destination"],
                        "departure_at": row["departure_at"],
                        "currency": payload.get("currency"),
                        "source_file": raw_file.name,
                    }

                    result = connection.execute(
                        INSERT_RAW_RESPONSE,
                        {
                            "endpoint": "v1/prices/cheap",
                            "request_params": json.dumps(
                                request_params,
                                ensure_ascii=False,
                            ),
                            "response_payload": json.dumps(
                                payload,
                                ensure_ascii=False,
                            ),
                            "collected_ts": parse_timestamp(
                                row["collected_at"]
                            ),
                            "http_status": 200,
                            "records_received": records_received,
                            "source_hash": source_hash,
                        },
                    )

                    response_id = result.scalar_one_or_none()

                    if response_id is None:
                        requests_skipped += 1
                        continue

                    requests_loaded += 1

                    for observation in extract_observations(row, response_id):
                        connection.execute(
                            INSERT_OBSERVATION,
                            observation,
                        )
                        observations_loaded += 1

    print("PostgreSQL load completed.")
    print(f"JSONL requests loaded: {requests_loaded}")
    print(f"JSONL requests skipped as duplicates: {requests_skipped}")
    print(f"Flight-price observations loaded: {observations_loaded}")


if __name__ == "__main__":
    main()