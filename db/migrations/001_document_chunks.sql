CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS document_chunks (
    id        SERIAL PRIMARY KEY,
    filename  TEXT NOT NULL,
    embedding vector({{EMBEDDING_DIMENSIONS}})
);

CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx
    ON document_chunks
    USING ivfflat (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS document_chunks_filename_idx
    ON document_chunks (filename);
