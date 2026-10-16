import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

required = [
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
]

missing = [name for name in required if not os.getenv(name)]

if missing:
    raise SystemExit(
        "В .env не заполнены переменные: " + ", ".join(missing)
    )

try:
    with psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=10,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()

    if result == (1,):
        print("Подключение к PostgreSQL успешно!")
        print("Проверка SELECT 1 выполнена. Данные не изменялись.")

except psycopg.Error as error:
    print("Не удалось подключиться к PostgreSQL.")
    print("Тип ошибки:", type(error).__name__)
    print("SQLSTATE:", error.sqlstate or "не указан")