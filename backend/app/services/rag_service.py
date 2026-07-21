import asyncio
import math
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol
from uuid import UUID

import psycopg
from dotenv import load_dotenv
from openai import AsyncOpenAI

from app.services.database import require_postgres_url


DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 100
DEFAULT_TOP_K = 4
EMBEDDING_DIMENSIONS = 1536


class RAGConfigurationError(RuntimeError):
    pass


class RAGProviderError(RuntimeError):
    pass


class RAGStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class EmbeddedChunk:
    index: int
    text: str
    embedding: list[float]


class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


def chunk_text(
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("Chunk size and overlap are invalid.")

    normalized = " ".join(text.split())
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        hard_end = min(start + chunk_size, len(normalized))
        end = hard_end
        if hard_end < len(normalized):
            split_at = normalized.rfind(" ", start, hard_end)
            if split_at > start + chunk_size // 2:
                end = split_at
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(end - overlap, start + 1)
    return chunks


class OpenAIEmbeddingProvider:
    def __init__(self) -> None:
        load_dotenv()
        self._api_key = os.getenv("OPENAI_API_KEY")
        self._model = os.getenv(
            "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self._api_key:
            raise RAGConfigurationError(
                "OPENAI_API_KEY must be configured for report embeddings."
            )

        all_embeddings: list[list[float]] = []
        try:
            async with AsyncOpenAI(
                api_key=self._api_key,
                timeout=60.0,
                max_retries=2,
            ) as client:
                for start in range(0, len(texts), 100):
                    batch = texts[start : start + 100]
                    response = await client.embeddings.create(
                        model=self._model,
                        input=batch,
                        dimensions=EMBEDDING_DIMENSIONS,
                        encoding_format="float",
                    )
                    ordered = sorted(response.data, key=lambda item: item.index)
                    all_embeddings.extend(
                        [list(item.embedding) for item in ordered]
                    )
        except Exception as exc:
            raise RAGProviderError(
                "The embedding service is temporarily unavailable."
            ) from exc

        if len(all_embeddings) != len(texts) or any(
            len(vector) != EMBEDDING_DIMENSIONS for vector in all_embeddings
        ):
            raise RAGProviderError("The embedding service returned invalid vectors.")
        return all_embeddings


class RAGService:
    def __init__(
        self,
        provider: EmbeddingProvider | None = None,
        database_url: str | None = None,
    ) -> None:
        load_dotenv()
        self._provider = provider or OpenAIEmbeddingProvider()
        self._database_url = database_url or os.getenv("DATABASE_URL")

    async def embed_document(self, text: str) -> list[EmbeddedChunk]:
        chunks = chunk_text(text)
        embeddings = await self._provider.embed(chunks)
        if len(embeddings) != len(chunks):
            raise RAGProviderError(
                "The embedding service returned the wrong number of vectors."
            )
        for embedding in embeddings:
            _vector_literal(embedding)
        return [
            EmbeddedChunk(index=index, text=chunk, embedding=embedding)
            for index, (chunk, embedding) in enumerate(zip(chunks, embeddings))
        ]

    async def retrieve(
        self,
        patient_id: UUID,
        session_id: UUID,
        query: str,
        *,
        top_k: int = DEFAULT_TOP_K,
    ) -> list[str]:
        has_reports = await asyncio.to_thread(
            self._has_reports_sync, patient_id, session_id
        )
        if not has_reports:
            return []

        query_vectors = await self._provider.embed([query])
        if len(query_vectors) != 1:
            raise RAGProviderError("The embedding service returned no query vector.")
        return await asyncio.to_thread(
            self._retrieve_sync,
            patient_id,
            session_id,
            query_vectors[0],
            top_k,
        )

    def _connection(self) -> psycopg.Connection:
        try:
            database_url = require_postgres_url(self._database_url)
        except ValueError as exc:
            raise RAGConfigurationError(str(exc)) from exc
        return psycopg.connect(
            database_url,
            connect_timeout=10,
            application_name="patient-intake-rag",
        )

    def _has_reports_sync(self, patient_id: UUID, session_id: UUID) -> bool:
        try:
            with self._connection() as connection:
                row = connection.execute(
                    """
                    select 1
                    from public.reports
                    where patient_id = %s and session_id = %s
                    limit 1
                    """,
                    (patient_id, session_id),
                ).fetchone()
                return row is not None
        except psycopg.Error as exc:
            raise RAGStoreError("Could not check for session reports.") from exc

    def _retrieve_sync(
        self,
        patient_id: UUID,
        session_id: UUID,
        embedding: list[float],
        top_k: int,
    ) -> list[str]:
        vector = _vector_literal(embedding)
        try:
            with self._connection() as connection:
                rows = connection.execute(
                    """
                    select chunk.chunk_text
                    from public.report_chunks as chunk
                    join public.reports as report on report.id = chunk.report_id
                    where chunk.patient_id = %s
                      and report.patient_id = %s
                      and report.session_id = %s
                    order by chunk.embedding <=> %s::extensions.vector
                    limit %s
                    """,
                    (patient_id, patient_id, session_id, vector, top_k),
                ).fetchall()
                return [row[0] for row in rows]
        except psycopg.Error as exc:
            raise RAGStoreError("Could not retrieve report context.") from exc


def _vector_literal(embedding: list[float]) -> str:
    if len(embedding) != EMBEDDING_DIMENSIONS or not all(
        math.isfinite(value) for value in embedding
    ):
        raise RAGProviderError("Embedding vector has invalid dimensions or values.")
    return "[" + ",".join(format(value, ".9g") for value in embedding) + "]"


@lru_cache
def get_rag_service() -> RAGService:
    return RAGService()
