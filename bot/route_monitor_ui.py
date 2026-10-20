from datetime import date
from decimal import Decimal, InvalidOperation

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from db import get_connection
from route_monitor import create_monitored_route, list_monitored_routes

ROUTE_ORIGIN, ROUTE_DESTINATION, ROUTE_MAX_PRICE = range(3)


async def route_monitor_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    await update.message.reply_text(
        "➕ Добавляем маршрут для мониторинга.\n"
        "Отправь код города или аэропорта вылета, например: MOW"
    )
    return ROUTE_ORIGIN


async def route_monitor_origin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    origin = update.message.text.strip().upper()

    if len(origin) != 3 or not origin.isalpha():
        await update.message.reply_text(
            "Пришли трёхбуквенный код, например: MOW"
        )
        return ROUTE_ORIGIN

    context.user_data["route_origin"] = origin
    await update.message.reply_text(
        "Теперь код города или аэропорта прилёта, например: LED"
    )
    return ROUTE_DESTINATION


async def route_monitor_destination(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    destination = update.message.text.strip().upper()

    if len(destination) != 3 or not destination.isalpha():
        await update.message.reply_text(
            "Пришли трёхбуквенный код, например: LED"
        )
        return ROUTE_DESTINATION

    if destination == context.user_data.get("route_origin"):
        await update.message.reply_text(
            "Город вылета и прилёта совпадают. Введи другой код прилёта:"
        )
        return ROUTE_DESTINATION

    context.user_data["route_destination"] = destination
    await update.message.reply_text(
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
        print(
            "Ошибка сохранения маршрута:",
            type(error).__name__,
            error,
        )
        await update.message.reply_text(
            "Не удалось сохранить маршрут. Возможно, он уже добавлен."
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "✅ Маршрут добавлен в мониторинг.\n"
        f"{origin} → {destination}\n"
        f"Порог цены: {max_price:.0f} ₽\n"
        "Период: любая дата в ближайшие 60 дней."
    )
    return ConversationHandler.END


async def route_monitor_cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    context.user_data.clear()
    await update.message.reply_text("Добавление маршрута отменено.")
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
        print(
            "Ошибка получения маршрутов:",
            type(error).__name__,
            error,
        )
        await update.message.reply_text(
            "Не удалось получить маршруты. Попробуй ещё раз чуть позже."
        )
        return

    if not rows:
        await update.message.reply_text(
            "У тебя пока нет маршрутов в мониторинге.\n"
            "Нажми «➕ Добавить маршрут»."
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
        "📋 Маршруты в мониторинге:\n\n" + "\n".join(lines)
    )