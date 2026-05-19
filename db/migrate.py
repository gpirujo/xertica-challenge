import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv()

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def main() -> None:
    dims = os.environ.get("EMBEDDING_DIMENSIONS")
    if not dims:
        raise ValueError("EMBEDDING_DIMENSIONS is not set in the environment")

    sql_path = _MIGRATIONS_DIR / "001_document_chunks.sql"
    sql = sql_path.read_text(encoding="utf-8").replace("{{EMBEDDING_DIMENSIONS}}", dims)

    conn = psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ.get("POSTGRES_PORT", 5432)),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql)
    finally:
        conn.close()

    print("Migration applied successfully.")


if __name__ == "__main__":
    main()
