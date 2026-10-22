import asyncio
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from cities import city_label, find_cities
from db import get_connection
from subscriptions import create_subscription, list_subscriptions


ORIGIN, DESTINATION, DEPART_DATE, MAX_PRICE = range(4)

SUBSCRIPTION_KEYS = (
    "subscription_origin",
    "subscription_destination",
    "subscription_depart_date",
    "subscription_origin_candidates",
    "subscription_destination_candidates",
)


def clear_subscription_data(context):
    for key in SUBSCRIPTION_KEYS:
        context.user_data.pop(key, None)


async def resolve_subscription_city(update, context, field):
    """Возвращает выбранный город или None, если нужен новый ввод."""
    message = update.effective_message
    text = message.text.strip()
    candidates_key = f"subscription_{field}_candidates"
    candidates = context.user_data.get(candidates_key, [])

    if text.isdecimal() and candidates:
        choice = int(text)

        if not 1 <= choice <= len(candidates):
            await message.reply_text(
                f"Выбери номер от 1 до {len(candidates)} "
                "или введи другое название города."
            )
            return None

        city = candidates[choice - 1]
        context.user_data.pop(candidates_key, None)
        return city

    try:
        cities, exact_match = await asyncio.to_thread(find_cities, text)
    except Exception as error:
        print("Ошибка поиска города:", type(error).__name__)
        await message.reply_text(
            "Не удалось загрузить справочник городов. "
            "Попробуй ещё раз чуть позже."
        )
        return None

    if not cities:
        context.user_data.pop(candidates_key, None)
        await message.reply_text(
            "Не нашла город. Введи другое название или код.\n"
            "Например: Москва, Мск или MOW.\n"
            "Отмена: /cancel"
        )
        return None

    if exact_match and len(cities) == 1:
        context.user_data.pop(candidates_key, None)
        return cities[0]

    context.user_data[candidates_key] = cities

    options = "\n".join(
        f"{number}. {city_label(city)}"
        for number, city in enumerate(cities, start=1)
    )

    await message.reply_text(
        "Уточни город — пришли номер из списка "
        "или другое название:\n\n" + options
    )
    return None


async def subscription_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    clear_subscription_data(context)

    await update.effective_message.reply_text(
        "🔔 Создаём подписку на конкретную дату.\n"
        "Отправь город вылета: название, сокращение или код.\n"
        "Например: Москва, Мск или MOW.\n\n"
        "Отменить создание: /cancel"
    )
    return ORIGIN


async def subscription_origin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    city = await resolve_subscription_city(update, context, "origin")

    if city is None:
        return ORIGIN

    context.user_data["subscription_origin"] = city["code"]

    await update.effective_message.reply_text(
        f"Откуда: {city_label(city)}.\n"
        "Теперь отправь город прилёта."
    )
    return DESTINATION


async def subscription_destination(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    city = await resolve_subscription_city(update, context, "destination")

    if city is None:
        return DESTINATION

    if city["code"] == context.user_data.get("subscription_origin"):
        await update.effective_message.reply_text(
            "Города вылета и прилёта совпадают. "
            "Введи другой город прилёта."
        )
        return DESTINATION

    context.user_data["subscription_destination"] = city["code"]

    await update.effective_message.reply_text(
        f"Куда: {city_label(city)}.\n"
        "Введи дату вылета в формате ДД-ММ-ГГГГ.\n"
        "Например: 15-12-2026.\n"
        "Через точки тоже можно: 15.12.2026."
    )
    return DEPART_DATE


async def subscription_depart_date(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    text = update.effective_message.text.strip()

    try:
        if not re.fullmatch(r"\d{2}([.-])\d{2}\1\d{4}", text):
            raise ValueError

        depart_date = datetime.strptime(
            text.replace(".", "-"),
            "%d-%m-%Y",
        ).date()
    except ValueError:
        await update.effective_message.reply_text(
            "Введи существующую дату в формате ДД-ММ-ГГГГ.\n"
            "Например: 15-12-2026 или 15.12.2026."
        )
        return DEPART_DATE

    if depart_date < date.today():
        await update.effective_message.reply_text(
            "Эта дата уже прошла. Введи сегодняшнюю или будущую дату."
        )
        return DEPART_DATE

    context.user_data["subscription_depart_date"] = depart_date

    await update.effective_message.reply_text(
        "При какой цене билет будет тебе интересен?\n"
        "Введи сумму в рублях, например: 15000."
    )
    return MAX_PRICE


def save_subscription_to_db(user_id, origin, destination, depart_date, max_price):
    with get_connection() as conn:
        return create_subscription(
            conn,
            user_id,
            origin,
            destination,
            depart_date,
            max_price,
        )


def load_subscriptions_from_db(user_id):
    with get_connection() as conn:
        return list_subscriptions(conn, user_id)


async def subscription_max_price(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    message = update.effective_message
    text = (
        message.text.strip()
        .replace(" ", "")
        .replace("\u00a0", "")
        .replace("\u202f", "")
        .replace(",", ".")
    )

    try:
        max_price = Decimal(text)

        if not max_price.is_finite():
            raise ValueError

        if not Decimal("0") < max_price <= Decimal("99999999.99"):
            raise ValueError

        if max_price != max_price.quantize(Decimal("0.01")):
            raise ValueError
    except (InvalidOperation, ValueError):
        await message.reply_text(
            "Введи положительную цену до 99 999 999,99 ₽ "
            "с максимум двумя знаками после запятой.\n"
            "Например: 15000 или 15000,50."
        )
        return MAX_PRICE

    origin = context.user_data.get("subscription_origin")
    destination = context.user_data.get("subscription_destination")
    depart_date = context.user_data.get("subscription_depart_date")

    if not origin or not destination or depart_date is None:
        clear_subscription_data(context)
        await message.reply_text(
            "Данные подписки потерялись. "
            "Нажми «🔔 Создать подписку» и начни заново."
        )
        return ConversationHandler.END

    try:
        await asyncio.to_thread(
            save_subscription_to_db,
            update.effective_user.id,
            origin,
            destination,
            depart_date,
            max_price,
        )
    except Exception as error:
        print("Ошибка сохранения подписки:", type(error).__name__)
        await message.reply_text(
            "Не удалось сохранить подписку.\n"
            "Если ещё не делала этого, отправь /cancel, затем /start.\n"
            "Иначе повтори ввод цены позже или отмени через /cancel."
        )
        return MAX_PRICE

    clear_subscription_data(context)

    await message.reply_text(
        "✅ Подписка сохранена.\n"
        f"{origin} → {destination}\n"
        f"Дата: {depart_date.strftime('%d-%m-%Y')}\n"
        f"Порог цены: {max_price:.2f} ₽."
    )
    return ConversationHandler.END


async def subscription_cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    clear_subscription_data(context)
    await update.effective_message.reply_text(
        "Создание подписки отменено."
    )
    return ConversationHandler.END


async def show_subscriptions(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.effective_message

    try:
        rows = await asyncio.to_thread(
            load_subscriptions_from_db,
            update.effective_user.id,
        )
    except Exception as error:
        print("Ошибка получения подписок:", type(error).__name__)
        await message.reply_text(
            "Не удалось получить подписки. Попробуй позже."
        )
        return

    if not rows:
        await message.reply_text(
            "У тебя пока нет активных подписок."
        )
        return

    await message.reply_text("🔔 Твои подписки:")

    for row in rows:
        (
            subscription_id,
            origin,
            destination,
            depart_date,
            max_price,
            last_price,
            _,
        ) = row

        price_text = (
            f"Последняя цена: {last_price:.2f} ₽"
            if last_price is not None
            else "Цена ещё не проверялась"
        )

        await message.reply_text(
            f"#{subscription_id}: {origin} → {destination}\n"
            f"Дата: {depart_date.strftime('%d-%m-%Y')}\n"
            f"Порог: {max_price:.2f} ₽\n"
            f"{price_text}"
        )