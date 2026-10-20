import os
import asyncio

from favorites_ui import build_favorites_handlers
from subscriptions_ui import (
    ORIGIN,
    DESTINATION,
    DEPART_DATE,
    MAX_PRICE,
    subscription_start,
    subscription_origin,
    subscription_destination,
    subscription_depart_date,
    subscription_max_price,
    subscription_cancel,
    show_subscriptions,
)

from db import save_user
from flight_search import build_search_handler

from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)


load_dotenv()


BOT_TOKEN = os.getenv("BOT_TOKEN")


MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["✈️ Поиск билетов"],
        ["🔔 Мои подписки", "⭐ Избранное"],
        ["🔔 Создать подписку"],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выбери действие",
)


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message

    if user is None or chat is None or message is None:
        return

    try:
        await asyncio.to_thread(
            save_user,
            telegram_user_id=user.id,
            chat_id=chat.id,
            username=user.username,
            first_name=user.first_name,
        )
    except Exception as error:
        print(
            "Ошибка сохранения пользователя:",
            type(error).__name__,
        )
        await message.reply_text(
            "Не удалось сохранить данные в базе. "
            "Попробуй отправить /start чуть позже."
        )
        return

    print("Пользователь сохранён в PostgreSQL.")

    await message.reply_text(
        "Привет! Это бот для поиска выгодных авиабилетов.\n\n"
        "Выбери действие в меню ниже 👇",
        reply_markup=MAIN_MENU,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Доступные команды:\n"
        "/start — начать работу\n"
        "/help — показать справку\n"
        "/cancel — отменить создание подписки"
    )


async def handle_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.effective_message

    if message is None or message.text is None:
        return

    if message.text == "🔔 Мои подписки":
        await show_subscriptions(update, context)
        return

    responses = {
        "✈️ Поиск билетов": (
            "✈️ Здесь будет поиск билетов по маршруту и датам.\n\n"
            "Этот раздел пока в разработке."
        ),
        "⭐ Избранное": (
            "⭐ Здесь будут сохранённые варианты билетов.\n\n"
            "Сохранение и просмотр избранного пока не подключены."
        ),
    }

    response = responses.get(
        message.text,
        "Выбери кнопку в меню или отправь /start.",
    )

    await message.reply_text(
        response,
        reply_markup=MAIN_MENU,
    )


def build_subscription_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("^🔔 Создать подписку$"),
                subscription_start,
            )
        ],
        states={
            ORIGIN: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    subscription_origin,
                )
            ],
            DESTINATION: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    subscription_destination,
                )
            ],
            DEPART_DATE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    subscription_depart_date,
                )
            ],
            MAX_PRICE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    subscription_max_price,
                )
            ],
        },
        fallbacks=[
            CommandHandler("cancel", subscription_cancel),
        ],
    )


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не найден. Проверь файл .env")

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .concurrent_updates(False)
        .connect_timeout(30)
        .get_updates_connect_timeout(30)
        .build()
    )

    application.add_handler(build_search_handler(MAIN_MENU))

    for handler in build_favorites_handlers(MAIN_MENU):
        application.add_handler(handler)

    application.add_handler(build_subscription_conversation())

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_menu,
        )
    )

    print("Запускаем бота. Для остановки нажми Ctrl + C.")
    application.run_polling()


if __name__ == "__main__":
    main()