import asyncio
import re
from datetime import date, datetime

from favorites_ui import favorite_keyboard

import requests
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from cities import city_label, find_cities, load_directory
from search_service import fetch_logged_flights


ORIGIN, DESTINATION, DEPARTURE = range(3)
TEXT_INPUT = filters.TEXT & ~filters.COMMAND
RETRY_CITY = "↩️ Ввести другой город"


def build_search_handler(main_menu):
    async def begin(update, context):
        context.user_data["flight_search"] = {}

        await update.effective_message.reply_text(
            "Подготавливаю справочник городов…",
            reply_markup=ReplyKeyboardRemove(),
        )

        try:
            await asyncio.to_thread(load_directory)
        except Exception as error:
            print("Ошибка справочника:", type(error).__name__)

            await update.effective_message.reply_text(
                "Не удалось загрузить справочник городов.\n"
                "Проверь соединение и начни поиск ещё раз.",
                reply_markup=main_menu,
            )
            return ConversationHandler.END

        await update.effective_message.reply_text(
            "Откуда летим?\n\n"
            "Введи название города или его код.\n"
            "Например: Москва, London или MOW.\n\n"
            "При неточном названии предложу варианты.\n"
            "Отмена: /cancel"
        )
        return ORIGIN

    async def choose_city(update, context, field, state):
        message = update.effective_message
        text = message.text.strip()
        params = context.user_data["flight_search"]

        pending = params.get("pending_city")

        if pending and pending["field"] == field:
            if text == RETRY_CITY:
                params.pop("pending_city", None)
                await message.reply_text(
                    "Введи другое название города или его код.",
                    reply_markup=ReplyKeyboardRemove(),
                )
                return state

            selected = pending["choices"].get(text)

            if selected is not None:
                params.pop("pending_city", None)
                return await accept_city(
                    update, context, field, state, selected
                )

            # Разрешаем вместо кнопки написать новое название.
            params.pop("pending_city", None)

        try:
            matches, exact = await asyncio.to_thread(
                find_cities, text
            )
        except Exception as error:
            print("Ошибка поиска города:", type(error).__name__)
            await message.reply_text(
                "Не удалось проверить город. Попробуй ещё раз.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return state

        if not matches:
            await message.reply_text(
                "Не нашёл подходящий город.\n"
                "Напиши полное название на русском или английском "
                "либо известный код города.\n"
                "Отмена: /cancel",
                reply_markup=ReplyKeyboardRemove(),
            )
            return state

        if exact:
            return await accept_city(
                update, context, field, state, matches[0]
            )

        choices = {
            city_label(city): city
            for city in matches
        }
        params["pending_city"] = {
            "field": field,
            "choices": choices,
        }

        keyboard = [[label] for label in choices]
        keyboard.append([RETRY_CITY])

        await message.reply_text(
            "Уточни, какой город ты имеешь в виду.\n"
            "Выбери вариант кнопкой или напиши другое название.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard,
                resize_keyboard=True,
                one_time_keyboard=True,
            ),
        )
        return state

    async def accept_city(update, context, field, state, city):
        params = context.user_data["flight_search"]
        message = update.effective_message

        if field == "destination" and city["code"] == params["origin"]:
            await message.reply_text(
                "Город назначения совпадает с отправлением.\n"
                "Введи другой город.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return state

        params[field] = city["code"]
        params[f"{field}_name"] = city["name"]

        if field == "origin":
            await message.reply_text(
                f"Отправление: {city_label(city)}.\n\n"
                "Куда летим?\n"
                "Введи название города или его код.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return DESTINATION

        await message.reply_text(
            f"Маршрут: {params['origin_name']} "
            f"→ {params['destination_name']}.\n\n"
            "Когда вылетаем?\n"
            "Введи дату в формате ДД.ММ.ГГГГ.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return DEPARTURE

    async def receive_origin(update, context):
        return await choose_city(
            update, context, "origin", ORIGIN
        )

    async def receive_destination(update, context):
        return await choose_city(
            update, context, "destination", DESTINATION
        )

    async def receive_departure(update, context):
        message = update.effective_message
        text = message.text.strip()

        try:
            if not re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", text):
                raise ValueError

            departure = datetime.strptime(text, "%d.%m.%Y").date()
        except ValueError:
            await message.reply_text(
                "Введи существующую дату в формате ДД.ММ.ГГГГ."
            )
            return DEPARTURE

        if departure < date.today():
            await message.reply_text(
                "Эта дата уже прошла. Введи сегодняшнюю или будущую."
            )
            return DEPARTURE

        params = context.user_data["flight_search"]
        params["departure_date"] = departure.isoformat()

        await message.reply_text(
            "Проверяю предложения по выбранному маршруту…"
        )

        try:
            search_id, flights = await asyncio.to_thread(
                fetch_logged_flights,
                telegram_user_id=update.effective_user.id,
                origin=params["origin"],
                destination=params["destination"],
                departure_date=params["departure_date"],
            )
        except requests.HTTPError as error:
            status = (
                error.response.status_code
                if error.response is not None
                else None
            )
            print("Ошибка запроса цен. HTTP:", status)
            print(
                "Параметры:",
                params["origin"],
                params["destination"],
                params["departure_date"],
            )

            if status == 400:
                explanation = (
                    "API отклонил параметры запроса. "
                    "Попробуй другой маршрут или дату."
                )
            elif status == 429:
                explanation = (
                    "API временно ограничил количество запросов. "
                    "Попробуй позже."
                )
            else:
                explanation = (
                    "Сервис цен вернул ошибку. Попробуй позже."
                )

            await message.reply_text(
                explanation,
                reply_markup=main_menu,
            )
            return ConversationHandler.END
        except Exception as error:
            print("Ошибка запроса цен:", type(error).__name__)
            await message.reply_text(
                "Не удалось получить цены. "
                "Попробуй начать поиск позже.",
                reply_markup=main_menu,
            )
            return ConversationHandler.END

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
                actual_date == departure
                and flight.get("origin") == params["origin"]
                and flight.get("destination") == params["destination"]
            ):
                matching_flights.append(flight)

        if not matching_flights:
            await message.reply_text(
                "В ответе API нет предложений на выбранный "
                "маршрут и дату.\n\n"
                "Это не означает, что рейсов нет: "
                "в базе найденных цен может не быть данных.",
                reply_markup=main_menu,
            )
            return ConversationHandler.END

        await message.reply_text(
            f"Предложений в ответе: {len(matching_flights)}.\n"
            "Перелёт в одну сторону, цены в рублях.",
            reply_markup=main_menu,
        )

        for offer_index, flight in enumerate(matching_flights[:5]):
            departure_time = datetime.fromisoformat(
                flight["departure_at"]
            )

            price = flight.get("price")
            price_text = (
                f"{price:,.0f}".replace(",", " ") + " ₽"
                if isinstance(price, (int, float))
                else "не указана"
            )

            duration = flight.get("duration_to")
            duration_text = (
                f"{duration} мин."
                if duration is not None
                else "не указана"
            )

            transfers = flight.get("transfers")
            transfers_text = (
                str(transfers)
                if transfers is not None
                else "не указаны"
            )

            offset = departure_time.strftime("%z")
            timezone_text = (
                f"UTC{offset[:3]}:{offset[3:]}"
                if offset
                else "не указан"
            )

            origin_airport = (
                flight.get("origin_airport") or params["origin"]
            )
            destination_airport = (
                flight.get("destination_airport")
                or params["destination"]
            )
            airline = flight.get("airline") or "не указана"
            number = flight.get("flight_number") or ""

            await message.reply_text(
                f"✈️ {params['origin_name']} "
                f"→ {params['destination_name']}\n"
                f"Аэропорты: {origin_airport} → "
                f"{destination_airport}\n"
                f"Вылет: {departure_time.strftime('%d.%m.%Y %H:%M')}\n"
                f"Часовой пояс: {timezone_text}\n"
                f"Рейс: {airline} {number}\n"
                f"Цена: {price_text}\n"
                f"Пересадки: {transfers_text}\n"
                f"Длительность: {duration_text}\n\n"
                "Цена из базы найденных предложений. "
                "Перед покупкой её нужно проверить.",
                reply_markup=favorite_keyboard(
                    search_id,
                    offer_index,
                ),
            )

        return ConversationHandler.END

    async def cancel(update, context):
        context.user_data.pop("flight_search", None)

        await update.effective_message.reply_text(
            "Ввод отменён. Можно начать заново.",
            reply_markup=main_menu,
        )
        return ConversationHandler.END

    return ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex(r"^✈️ Поиск билетов$"),
                begin,
            )
        ],
        states={
            ORIGIN: [
                MessageHandler(TEXT_INPUT, receive_origin)
            ],
            DESTINATION: [
                MessageHandler(TEXT_INPUT, receive_destination)
            ],
            DEPARTURE: [
                MessageHandler(TEXT_INPUT, receive_departure)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", cancel),
        ],
        allow_reentry=True,
    )