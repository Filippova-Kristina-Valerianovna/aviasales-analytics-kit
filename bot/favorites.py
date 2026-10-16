from db import get_connection


def init_favorites():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS flight_bot.favorites (
                    favorite_id BIGINT GENERATED ALWAYS AS IDENTITY
                        PRIMARY KEY,
                    telegram_user_id BIGINT NOT NULL,
                    search_id BIGINT NOT NULL
                        REFERENCES flight_bot.search_requests(search_id)
                        ON DELETE RESTRICT,
                    offer_index INTEGER NOT NULL
                        CHECK (offer_index >= 0),
                    offer JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (
                        telegram_user_id,
                        search_id,
                        offer_index
                    )
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS
                    favorites_user_created_idx
                ON flight_bot.favorites (
                    telegram_user_id,
                    created_at DESC
                )
            """)


def save_favorite(
    telegram_user_id: int,
    search_id: int,
    offer_index: int,
) -> int | None:
    if offer_index < 0:
        raise ValueError("Номер предложения не может быть отрицательным")

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO flight_bot.favorites (
                    telegram_user_id,
                    search_id,
                    offer_index,
                    offer
                )
                SELECT
                    telegram_user_id,
                    search_id,
                    %s,
                    offers -> %s
                FROM flight_bot.search_requests
                WHERE search_id = %s
                  AND telegram_user_id = %s
                  AND status = 'success'
                  AND jsonb_typeof(offers) = 'array'
                  AND jsonb_array_length(offers) > %s
                ON CONFLICT (
                    telegram_user_id,
                    search_id,
                    offer_index
                )
                DO NOTHING
                RETURNING favorite_id
                """,
                (
                    offer_index,
                    offer_index,
                    search_id,
                    telegram_user_id,
                    offer_index,
                ),
            )

            row = cursor.fetchone()

            if row is not None:
                return row[0]

            cursor.execute(
                """
                SELECT favorite_id
                FROM flight_bot.favorites
                WHERE telegram_user_id = %s
                  AND search_id = %s
                  AND offer_index = %s
                """,
                (
                    telegram_user_id,
                    search_id,
                    offer_index,
                ),
            )

            row = cursor.fetchone()
            return row[0] if row is not None else None


def list_favorites(
    telegram_user_id: int,
    limit: int = 10,
) -> list[dict]:
    if not 1 <= limit <= 50:
        raise ValueError("Лимит должен быть от 1 до 50")

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    favorite_id,
                    search_id,
                    offer,
                    created_at
                FROM flight_bot.favorites
                WHERE telegram_user_id = %s
                ORDER BY created_at DESC, favorite_id DESC
                LIMIT %s
                """,
                (telegram_user_id, limit),
            )

            return [
                {
                    "favorite_id": row[0],
                    "search_id": row[1],
                    "offer": row[2],
                    "created_at": row[3],
                }
                for row in cursor.fetchall()
            ]


if __name__ == "__main__":
    init_favorites()
    print("Таблица flight_bot.favorites готова.")