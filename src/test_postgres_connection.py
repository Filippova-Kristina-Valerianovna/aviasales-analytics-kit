from pathlib import Path
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

db_url = (
    f"postgresql+psycopg://{os.getenv('POSTGRES_USER')}:"
    f"{os.getenv('POSTGRES_PASSWORD')}@"
    f"{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/"
    f"{os.getenv('POSTGRES_DB')}"
)

engine = create_engine(db_url)

with engine.connect() as connection:
    result = connection.execute(
        text(
            """
            SELECT
                current_database() AS database_name,
                current_user AS user_name,
                version() AS postgresql_version;
            """
        )
    )
    row = result.mappings().one()

print(f"Connected to database: {row['database_name']}")
print(f"Connected as user: {row['user_name']}")
print(f"PostgreSQL version: {row['postgresql_version']}")