from datetime import date
from decimal import Decimal

import psycopg


def create_monitored_route(
    conn: psycopg.Connection,
    user_id: int,
    origin_code: str,
    destination_code: str,
    max_price: Decimal,
    days_ahead: int = 60,
) -> int:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO flight_bot.monitored_routes
                (user_id, origin_code, destination_code, max_price, days_ahead)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                user_id,
                origin_code,
                destination_code,
                max_price,
                days_ahead,
            ),
        )
        row = cursor.fetchone()
        conn.commit()
        return row[0]


def list_monitored_routes(
    conn: psycopg.Connection,
    user_id: int,
) -> list[tuple]:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, origin_code, destination_code, max_price,
                   days_ahead, last_checked_at, last_notified_price,
                   last_notified_date
            FROM flight_bot.monitored_routes
            WHERE user_id = %s AND is_active = TRUE
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        return cursor.fetchall()


def deactivate_monitored_route(
    conn: psycopg.Connection,
    user_id: int,
    route_id: int,
) -> bool:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE flight_bot.monitored_routes
            SET is_active = FALSE
            WHERE id = %s AND user_id = %s AND is_active = TRUE
            RETURNING id
            """,
            (route_id, user_id),
        )
        row = cursor.fetchone()
        conn.commit()
        return row is not None


def update_monitoring_result(
    conn: psycopg.Connection,
    route_id: int,
    price: Decimal | None,
    depart_date: date | None,
) -> None:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE flight_bot.monitored_routes
            SET last_checked_at = NOW(),
                last_notified_price = %s,
                last_notified_date = %s
            WHERE id = %s
            """,
            (price, depart_date, route_id),
        )
        conn.commit()