from datetime import date
from decimal import Decimal, InvalidOperation

from cities import city_label, find_cities
from db import get_connection
from route_monitor import create_monitored_route, list_monitored_routes
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

ROUTE_ORIGIN, ROUTE_ORIGIN_SELECT, ROUTE_DESTINATION, ROUTE_DESTINATION_SELECT, ROUTE_MAX_PRICE = range(5)

MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["✈️ Поиск билетов"],
        ["🔔 Мои подписки", "⭐ Избранное"],
        ["➕ Добавить маршрут", "📋 Маршруты"],
        ["🔎 Проверить маршруты"],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выбери действие",
)


async def route_monitor_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    await update.message.reply_text(
        "➕ Добавляем маршрут для мониторинга.\n"
        "Отправь город вылета: название, код или сокращение.\n"
        "Например: Москва, Мск или MOW"
    )
    return ROUTE_ORIGIN


async def route_monitor_origin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    cities, exact_match = find_cities(update.message.text)

    if not cities:
        await update.message.reply_text(
            "Не нашла такой город. Попробуй ещё раз:\n"
            "например, Москва, Мск или MOW."
        )
        return ROUTE_ORIGIN

    if exact_match:
        context.user_data["route_origin"] = cities[0]["code"]
        await update.message.reply_text(
            f"Откуда: {city_label(cities[0])}.\n"
            "Теперь отправь город прилёта."
        )
        return ROUTE_DESTINATION

    context.user_data["route_origin_candidates"] = cities
    options = "\n".join(
        f"{index + 1}. {city_label(city)}"
        for index, city in enumerate(cities)
    )
    await update.message.reply_text(
        "Нашла несколько городов. Выбери номер:\n\n" + options
    )
    return ROUTE_ORIGIN_SELECT


async def route_monitor_origin_select(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    cities = context.user_data.get("route_origin_candidates", [])

    try:
        choice = int(update.message.text.strip()) - 1
        city = cities[choice]
    except (ValueError, IndexError):
        await update.message.reply_text(
            "Пришли номер города из списка."
        )
        return ROUTE_ORIGIN_SELECT

    context.user_data["route_origin"] = city["code"]
    context.user_data.pop("route_origin_candidates", None)

    await update.message.reply_text(
        f"Откуда: {city_label(city)}.\n"
        "Теперь отправь город прилёта."
    )
    return ROUTE_DESTINATION


async def route_monitor_destination(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    cities, exact_match = find_cities(update.message.text)

    if not cities:
        await update.message.reply_text(
            "Не нашла такой город. Попробуй ещё раз:\n"
            "например, Санкт-Петербург, Питер или LED."
        )
        return ROUTE_DESTINATION

    if exact_match and cities[0]["code"] == context.user_data.get("route_origin"):
        await update.message.reply_text(
            "Город вылета и прилёта совпадают. Введи другой город прилёта."
        )
        return ROUTE_DESTINATION

    if exact_match:
        context.user_data["route_destination"] = cities[0]["code"]
        await update.message.reply_text(
            f"Куда: {city_label(cities[0])}.\n"
            "Какая цена будет выгодной? Пришли только число, например: 15000"
        )
        return ROUTE_MAX_PRICE

    context.user_data["route_destination_candidates"] = cities
    options = "\n".join(
        f"{index + 1}. {city_label(city)}"
        for index, city in enumerate(cities)
    )
    await update.message.reply_text(
        "Нашла несколько городов. Выбери номер:\n\n" + options
    )
    return ROUTE_DESTINATION_SELECT


async def route_monitor_destination_select(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    cities = context.user_data.get("route_destination_candidates", [])

    try:
        choice = int(update.message.text.strip()) - 1
        city = cities[choice]
    except (ValueError, IndexError):
        await update.message.reply_text(
            "Пришли номер города из списка."
        )
        return ROUTE_DESTINATION_SELECT

    if city["code"] == context.user_data.get("route_origin"):
        await update.message.reply_text(
            "Город вылета и прилёта совпадают. Выбери другой город."
        )
        return ROUTE_DESTINATION_SELECT

    context.user_data["route_destination"] = city["code"]
    context.user_data.pop("route_destination_candidates", None)

    await update.message.reply_text(
        f"Куда: {city_label(city)}.\n"
        "Какая цена будет выгодной? Пришли только число, например: 15000"
    )
    return ROUTE_MAX_PRICE


async def route_monitor_max_price(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    try:
        max_price = Decimal(update.message.text.strip().replace(",", "."))
    except InvalidOperation:
        await update.message.reply_text("Пришли цену числом, например: 15000")
        return ROUTE_MAX_PRICE

    if max_price <= 0:
        await update.message.reply_text("Цена должна быть больше нуля:")
        return ROUTE_MAX_PRICE

    user_id = update.effective_user.id
    origin = context.user_data.pop("route_origin")
    destination = context.user_data.pop("route_destination")

    try:
        with get_connection() as conn:
            create_monitored_route(
                conn,
                user_id,
                origin,
                destination,
                max_price,
                days_ahead=60,
            )
    except Exception as error:
        print("Ошибка сохранения маршрута:", type(error).__name__, error)
        await update.message.reply_text(
            "Не удалось сохранить маршрут. Возможно, он уже добавлен."
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "✅ Маршрут добавлен в мониторинг.\n"
        f"{origin} → {destination}\n"
        f"Порог цены: {max_price:.0f} ₽\n"
        "Период: любая дата в ближайшие 60 дней.",
        reply_markup=MAIN_MENU,
    )
    return ConversationHandler.END


async def route_monitor_cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "Добавление маршрута отменено.",
        reply_markup=MAIN_MENU,
    )
    return ConversationHandler.END


async def show_monitored_routes(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    user_id = update.effective_user.id

    try:
        with get_connection() as conn:
            rows = list_monitored_routes(conn, user_id)
    except Exception as error:
        print("Ошибка получения маршрутов:", type(error).__name__, error)
        await update.message.reply_text(
            "Не удалось получить маршруты. Попробуй ещё раз чуть позже."
        )
        return

    if not rows:
        await update.message.reply_text(
            "У тебя пока нет маршрутов в мониторинге.\n"
            "Нажми «➕ Добавить маршрут».",
            reply_markup=MAIN_MENU,
        )
        return

    lines = []
    for row in rows:
        route_id, origin, destination, max_price, days_ahead, _, last_price, _ = row

        if last_price is not None:
            price = f"последняя найденная цена {last_price:.0f} ₽"
        else:
            price = "цена ещё не проверялась"

        lines.append(
            f"#{route_id}: {origin} → {destination}, "
            f"до {max_price:.0f} ₽, {days_ahead} дней — {price}"
        )

    await update.message.reply_text(
        "📋 Маршруты в мониторинге:\n\n" + "\n".join(lines),
        reply_markup=MAIN_MENU,
    )

import asyncio
from datetime import timedelta

from search_service import fetch_logged_flights
from route_monitor import update_monitoring_result


async def check_monitored_routes(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.effective_message
    user_id = update.effective_user.id

    await message.reply_text(
        "🔎 Проверяю маршруты. Это может занять пару минут…"
    )

    try:
        with get_connection() as conn:
            routes = list_monitored_routes(conn, user_id)
    except Exception as error:
        print("Ошибка получения маршрутов:", type(error).__name__, error)
        await message.reply_text("Не удалось получить маршруты.")
        return

    if not routes:
        await message.reply_text(
            "У тебя нет активных маршрутов.\n"
            "Нажми «➕ Добавить маршрут».",
            reply_markup=MAIN_MENU,
        )
        return

    today = date.today()
    notifications = []

    for route in routes:
        route_id, origin, destination, max_price, days_ahead, *_ = route

        best_price = None
        best_date = None

        for day_offset in range(1, days_ahead + 1, 3):
            check_date = today + timedelta(days=day_offset)

            try:
                _, flights = await asyncio.to_thread(
                    fetch_logged_flights,
                    telegram_user_id=user_id,
                    origin=origin,
                    destination=destination,
                    departure_date=check_date.isoformat(),
                )
            except Exception as error:
                print(
                    f"Ошибка проверки {origin} → {destination} "
                    f"на {check_date.isoformat()}:",
                    type(error).__name__,
                    error,
                )
                continue

            for flight in flights:
                if not isinstance(flight, dict):
                    continue

                price = flight.get("price")
                if not isinstance(price, (int, float)):
                    continue

                if best_price is None or price < best_price:
                    best_price = price
                    best_date = check_date

        if best_price is None:
            continue

        if best_price <= float(max_price):
            notifications.append(
                f"🎉 {origin} → {destination}\n"
                f"Дата: {best_date.isoformat()}\n"
                f"Цена: {best_price:.0f} ₽\n"
                f"Порог: {max_price:.0f} ₽"
            )

            with get_connection() as conn:
                update_monitoring_result(
                    conn,
                    route_id,
                    Decimal(str(best_price)),
                    best_date,
                )

    if notifications:
        await message.reply_text(
            "🔎 Нашла подходящие цены:\n\n" + "\n\n".join(notifications),
            reply_markup=MAIN_MENU,
        )
    else:
        await message.reply_text(
            "Пока не нашла цен ниже твоих порогов.\n"
            "Попробуй проверить позже.",
            reply_markup=MAIN_MENU,
        )