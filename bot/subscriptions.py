from datetime import date
from decimal import Decimal

import psycopg


def create_subscription(
    conn: psycopg.Connection,
    user_id: int,
    origin_code: str,
    destination_code: str,
    depart_date: date,
    max_price: Decimal,
) -> int:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO flight_bot.subscriptions
                (user_id, origin_code, destination_code, depart_date, max_price)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (user_id, origin_code, destination_code, depart_date, max_price),
        )
        row = cursor.fetchone()
        conn.commit()
        return row[0]


def list_subscriptions(
    conn: psycopg.Connection,
    user_id: int,
) -> list[tuple]:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, origin_code, destination_code, depart_date,
                   max_price, last_price, last_checked_at
            FROM flight_bot.subscriptions
            WHERE user_id = %s AND is_active = TRUE
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        return cursor.fetchall()


def deactivate_subscription(
    conn: psycopg.Connection,
    user_id: int,
    subscription_id: int,
) -> bool:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE flight_bot.subscriptions
            SET is_active = FALSE
            WHERE id = %s AND user_id = %s AND is_active = TRUE
            RETURNING id
            """,
            (subscription_id, user_id),
        )
        row = cursor.fetchone()
        conn.commit()
        return row is not None


def update_check_result(
    conn: psycopg.Connection,
    subscription_id: int,
    price: Decimal | None,
) -> None:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE flight_bot.subscriptions
            SET last_price = %s, last_checked_at = NOW()
            WHERE id = %s
            """,
            (price, subscription_id),
        )
        conn.commit()