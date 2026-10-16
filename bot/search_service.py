from datetime import date, datetime

from db import finish_search, start_search
from travelpayouts_api import fetch_flights


def fetch_logged_flights(
    telegram_user_id: int,
    origin: str,
    destination: str,
    departure_date: str,
) -> tuple[int, list[dict]]:
    search_id = start_search(
        telegram_user_id=telegram_user_id,
        origin=origin,
        destination=destination,
        departure_date=departure_date,
    )

    print(f"Поиск #{search_id}: запись создана.")

    try:
        flights = fetch_flights(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
        )

        requested_date = date.fromisoformat(departure_date)
        matching_flights = []

        for flight in flights:
            if not isinstance(flight, dict):
                continue

            try:
                actual_date = datetime.fromisoformat(
                    flight["departure_at"]
                ).date()
            except (KeyError, TypeError, ValueError):
                continue

            if (
                actual_date == requested_date
                and flight.get("origin") == origin
                and flight.get("destination") == destination
            ):
                matching_flights.append(flight)

    except Exception as error:
        response = getattr(error, "response", None)
        http_status = (
            response.status_code
            if response is not None
            else None
        )

        try:
            finish_search(
                search_id=search_id,
                status="error",
                error_type=type(error).__name__,
                http_status=http_status,
            )
            print(f"Поиск #{search_id}: ошибка сохранена.")
        except Exception as db_error:
            print(
                f"Поиск #{search_id}: "
                "не удалось сохранить ошибку:",
                type(db_error).__name__,
            )

        raise

    status = "success" if matching_flights else "empty"

    try:
        finish_search(
            search_id=search_id,
            status=status,
            offers=matching_flights,
        )
        print(
            f"Поиск #{search_id}: {status}, "
            f"предложений — {len(matching_flights)}."
        )
    except Exception as db_error:
        print(
            f"Поиск #{search_id}: "
            "результат получен, но не сохранён:",
            type(db_error).__name__,
        )

    return search_id, matching_flights