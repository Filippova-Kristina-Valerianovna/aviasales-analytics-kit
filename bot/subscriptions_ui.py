from datetime import date
from decimal import Decimal, InvalidOperation

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from db import get_connection
from subscriptions import create_subscription, list_subscriptions

ORIGIN, DESTINATION, DEPART_DATE, MAX_PRICE = range(4)


async def subscription_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    await update.message.reply_text(
        "🔔 Создаём подписку.\n"
        "Отправь город или код вылета:"
    )
    return ORIGIN


async def subscription_origin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    context.user_data["subscription_origin"] = update.message.text.strip()
    await update.message.reply_text("Теперь город или код прилёта:")
    return DESTINATION


async def subscription_destination(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    context.user_data["subscription_destination"] = update.message.text.strip()
    await update.message.reply_text("Дата вылета в формате ГГГГ-ММ-ДД:")
    return DEPART_DATE


async def subscription_depart_date(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    try:
        depart_date = date.fromisoformat(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Не понял дату. Пример: 2026-12-01")
        return DEPART_DATE

    if depart_date < date.today():
        await update.message.reply_text("Дата уже прошла. Введи будущую дату:")
        return DEPART_DATE

    context.user_data["subscription_depart_date"] = depart_date
    await update.message.reply_text(
        "Какая цена тебя устроит? Пришли только число, например: 15000"
    )
    return MAX_PRICE


async def subscription_max_price(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    try:
        max_price = Decimal(update.message.text.strip().replace(",", "."))
    except InvalidOperation:
        await update.message.reply_text("Пришли цену числом, например: 15000")
        return MAX_PRICE

    if max_price <= 0:
        await update.message.reply_text("Цена должна быть больше нуля:")
        return MAX_PRICE

    user_id = update.effective_user.id
    origin = context.user_data.pop("subscription_origin")
    destination = context.user_data.pop("subscription_destination")
    depart_date = context.user_data.pop("subscription_depart_date")

    try:
        with get_connection() as conn:
            create_subscription(
                conn,
                user_id,
                origin,
                destination,
                depart_date,
                max_price,
            )
    except Exception as error:
        print(
            "Ошибка сохранения подписки:",
            type(error).__name__,
            error,
        )
        await update.message.reply_text(
            "Не удалось сохранить подписку. Попробуй ещё раз чуть позже."
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "✅ Подписка сохранена.\n"
        f"{origin} → {destination}, {depart_date.isoformat()}, "
        f"до {max_price:.0f} ₽."
    )
    return ConversationHandler.END


async def subscription_cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    context.user_data.clear()
    await update.message.reply_text("Создание подписки отменено.")
    return ConversationHandler.END


async def show_subscriptions(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    user_id = update.effective_user.id

    try:
        with get_connection() as conn:
            rows = list_subscriptions(conn, user_id)
    except Exception as error:
        print(
            "Ошибка получения подписок:",
            type(error).__name__,
            error,
        )
        await update.message.reply_text(
            "Не удалось получить подписки. Попробуй ещё раз чуть позже."
        )
        return

    if not rows:
        await update.message.reply_text("У тебя пока нет активных подписок.")
        return

    lines = []
    for row in rows:
        subscription_id, origin, destination, depart_date, max_price, last_price, _ = row

        if last_price is not None:
            price = f"{last_price:.0f} ₽"
        else:
            price = "цена ещё не проверялась"

        lines.append(
            f"#{subscription_id}: {origin} → {destination}, "
            f"{depart_date.isoformat()}, до {max_price:.0f} ₽ — {price}"
        )

    await update.message.reply_text(
        "📋 Твои подписки:\n\n" + "\n".join(lines)
    )