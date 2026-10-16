import os
from datetime import date
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Jsonb


ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)


def get_connection():
    return psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=10,
    )


def init_db():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE SCHEMA IF NOT EXISTS flight_bot"
            )

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS flight_bot.users (
                    telegram_user_id BIGINT PRIMARY KEY,
                    chat_id BIGINT NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS flight_bot.search_requests (
                    search_id BIGINT GENERATED ALWAYS AS IDENTITY
                        PRIMARY KEY,
                    telegram_user_id BIGINT NOT NULL,
                    origin TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    departure_date DATE NOT NULL,
                    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    finished_at TIMESTAMPTZ,
                    status TEXT NOT NULL DEFAULT 'started'
                        CHECK (
                            status IN (
                                'started',
                                'success',
                                'empty',
                                'error'
                            )
                        ),
                    offers_count INTEGER NOT NULL DEFAULT 0
                        CHECK (offers_count >= 0),
                    offers JSONB NOT NULL DEFAULT '[]'::jsonb,
                    error_type TEXT,
                    http_status INTEGER
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS
                    search_requests_user_started_idx
                ON flight_bot.search_requests (
                    telegram_user_id,
                    started_at DESC
                )
            """)


def save_user(
    telegram_user_id: int,
    chat_id: int,
    username: str | None,
    first_name: str | None,
):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO flight_bot.users (
                    telegram_user_id,
                    chat_id,
                    username,
                    first_name
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (telegram_user_id)
                DO UPDATE SET
                    chat_id = EXCLUDED.chat_id,
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    updated_at = NOW()
                """,
                (
                    telegram_user_id,
                    chat_id,
                    username,
                    first_name,
                ),
            )


def start_search(
    telegram_user_id: int,
    origin: str,
    destination: str,
    departure_date: str,
) -> int:
    parsed_date = date.fromisoformat(departure_date)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO flight_bot.search_requests (
                    telegram_user_id,
                    origin,
                    destination,
                    departure_date
                )
                VALUES (%s, %s, %s, %s)
                RETURNING search_id
                """,
                (
                    telegram_user_id,
                    origin,
                    destination,
                    parsed_date,
                ),
            )
            search_id = cursor.fetchone()[0]

    return search_id


def finish_search(
    search_id: int,
    status: str,
    offers: list[dict] | None = None,
    error_type: str | None = None,
    http_status: int | None = None,
):
    if status not in {"success", "empty", "error"}:
        raise ValueError("Недопустимый статус завершения поиска")

    saved_offers = offers if offers is not None else []

    if status == "success" and not saved_offers:
        raise ValueError("Для success нужен непустой список предложений")

    if status in {"empty", "error"} and saved_offers:
        raise ValueError("Для empty и error список должен быть пустым")

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE flight_bot.search_requests
                SET
                    finished_at = NOW(),
                    status = %s,
                    offers_count = %s,
                    offers = %s,
                    error_type = %s,
                    http_status = %s
                WHERE search_id = %s
                  AND status = 'started'
                RETURNING search_id
                """,
                (
                    status,
                    len(saved_offers),
                    Jsonb(saved_offers),
                    error_type,
                    http_status,
                    search_id,
                ),
            )

            if cursor.fetchone() is None:
                raise ValueError(
                    "Поиск не найден или уже завершён"
                )


if __name__ == "__main__":
    init_db()
    print("Таблицы готовы:")
    print("- flight_bot.users")
    print("- flight_bot.search_requests")