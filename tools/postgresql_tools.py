import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

_connection = None


def _get_connection():
    global _connection
    if _connection is None or _connection.closed:
        _connection = psycopg2.connect(
            host=os.environ["POSTGRES_HOST"],
            port=int(os.environ.get("POSTGRES_PORT", 5432)),
            dbname=os.environ["POSTGRES_DB"],
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
        )
    return _connection


def ensure_table() -> None:
    dims = os.environ.get("EMBEDDING_DIMENSIONS")
    if not dims:
        raise ValueError("EMBEDDING_DIMENSIONS is not set in the environment")

    conn = _get_connection()
    conn.rollback()
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS document_chunks (
                id           SERIAL PRIMARY KEY,
                filename     TEXT NOT NULL,
                country_code TEXT NOT NULL,
                embedding    vector({int(dims)})
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx
                ON document_chunks
                USING ivfflat (embedding vector_cosine_ops)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS document_chunks_country_filename_idx
                ON document_chunks (country_code, filename)
        """)
    conn.commit()


def insert_embeddings(filename: str, embeddings: list[list[float]], country_code: str) -> None:
    conn = _get_connection()
    rows = [(filename, country_code, embedding) for embedding in embeddings]
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO document_chunks (filename, country_code, embedding) VALUES (%s, %s, %s)",
            rows,
        )
    conn.commit()


def clear_table() -> None:
    """Delete all rows from document_chunks."""
    conn = _get_connection()
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE document_chunks")
    conn.commit()


def search_similar(query_embedding: list[float], top_k: int = 5, country_code: str = "") -> list[str]:
    conn = _get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT filename
            FROM (
                SELECT filename, MIN(embedding <=> %s::vector) AS min_dist
                FROM document_chunks
                WHERE country_code = %s
                GROUP BY filename
                ORDER BY min_dist
                LIMIT %s
            ) sub
            """,
            (query_embedding, country_code, top_k),
        )
        rows = cur.fetchall()
    return [row[0] for row in rows]
