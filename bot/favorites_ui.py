import asyncio

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, filters

from favorites import list_favorites, save_favorite


def favorite_keyboard(search_id, offer_index):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⭐ Сохранить",
                callback_data=f"fav:{search_id}:{offer_index}",
            )
        ]
    ])


async def save_favorite_callback(update, context):
    query = update.callback_query
    await query.answer()

    _, search_id, offer_index = query.data.split(":")

    try:
        favorite_id = await asyncio.to_thread(
            save_favorite,
            telegram_user_id=query.from_user.id,
            search_id=int(search_id),
            offer_index=int(offer_index),
        )
    except Exception as error:
        print("Ошибка сохранения избранного:", type(error).__name__)
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=(
                "Не удалось сохранить предложение. "
                "Попробуй нажать кнопку ещё раз."
            ),
        )
        return

    if favorite_id is None:
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=(
                "Предложение не найдено или относится "
                "к поиску другого пользователя."
            ),
        )
        return

    await query.edit_message_reply_markup(
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "⭐ Сохранено",
                    callback_data=f"fav:{search_id}:{offer_index}",
                )
            ]
        ])
    )


def format_favorite(item):
    offer = item["offer"]
    price = offer.get("price")

    price_text = (
        f"{price:,.0f}".replace(",", " ") + " ₽"
        if isinstance(price, (int, float))
        else "не указана"
    )

    return (
        f"⭐ Избранное #{item['favorite_id']}\n"
        f"Маршрут: {offer.get('origin', '—')} → "
        f"{offer.get('destination', '—')}\n"
        f"Вылет: {offer.get('departure_at', 'не указан')}\n"
        f"Рейс: {offer.get('airline', '—')} "
        f"{offer.get('flight_number', '')}\n"
        f"Сохранённая цена: {price_text}\n"
        f"Пересадки: {offer.get('transfers', 'не указаны')}\n\n"
        "Это данные на момент поиска, "
        "а не обновлённая цена."
    )


def build_favorites_handlers(main_menu):
    async def show_favorites(update, context):
        try:
            items = await asyncio.to_thread(
                list_favorites,
                telegram_user_id=update.effective_user.id,
                limit=10,
            )
        except Exception as error:
            print("Ошибка чтения избранного:", type(error).__name__)
            await update.effective_message.reply_text(
                "Не удалось загрузить избранное. Попробуй позже.",
                reply_markup=main_menu,
            )
            return

        if not items:
            await update.effective_message.reply_text(
                "В избранном пока ничего нет.\n"
                "Выполни поиск и нажми «⭐ Сохранить» "
                "под подходящим предложением.",
                reply_markup=main_menu,
            )
            return

        await update.effective_message.reply_text(
            f"Последние сохранённые предложения: {len(items)}.",
            reply_markup=main_menu,
        )

        for item in items:
            await update.effective_message.reply_text(
                format_favorite(item)
            )

    return [
        CallbackQueryHandler(
            save_favorite_callback,
            pattern=r"^fav:\d+:\d+$",
        ),
        MessageHandler(
            filters.Regex(r"^⭐ Избранное$"),
            show_favorites,
        ),
    ]