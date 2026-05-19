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


def insert_embeddings(filename: str, embeddings: list[list[float]]) -> None:
    conn = _get_connection()
    rows = [(filename, embedding) for embedding in embeddings]
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO document_chunks (filename, embedding) VALUES (%s, %s)",
            rows,
        )
    conn.commit()


def search_similar(query_embedding: list[float], top_k: int = 5) -> list[str]:
    conn = _get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT filename
            FROM (
                SELECT filename, MIN(embedding <=> %s::vector) AS min_dist
                FROM document_chunks
                GROUP BY filename
                ORDER BY min_dist
                LIMIT %s
            ) sub
            """,
            (query_embedding, top_k),
        )
        rows = cur.fetchall()
    return [row[0] for row in rows]
