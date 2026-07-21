"""Deeper RAG checks, complementing tests/test_rag_service.py.

Covers content integrity in chunking, provider failure paths, vector
validation, and that retrieval stays scoped to the requesting patient
and session.
"""

import unittest
from unittest.mock import patch
from uuid import uuid4

from app.services.rag_service import (
    EMBEDDING_DIMENSIONS,
    RAGProviderError,
    RAGService,
    chunk_text,
    _vector_literal,
)


def _vector(value: float = 0.1) -> list[float]:
    return [value] * EMBEDDING_DIMENSIONS


class QueuedEmbeddingProvider:
    """Returns pre-queued responses so failure modes can be simulated."""

    def __init__(self, queued: list[list[list[float]]] | None = None) -> None:
        self.calls: list[list[str]] = []
        self._queued = queued

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        if self._queued is not None:
            return self._queued.pop(0)
        return [_vector() for _ in texts]


class ChunkingIntegrityTests(unittest.TestCase):
    def test_empty_and_whitespace_produce_no_chunks(self) -> None:
        self.assertEqual(chunk_text(""), [])
        self.assertEqual(chunk_text("  \n\t "), [])

    def test_short_text_survives_as_single_chunk(self) -> None:
        self.assertEqual(chunk_text("HbA1c 7.9 %"), ["HbA1c 7.9 %"])

    def test_no_words_are_lost_across_chunk_boundaries(self) -> None:
        words = [f"word{i}" for i in range(600)]
        chunks = chunk_text(" ".join(words))
        joined = " ".join(chunks)
        missing = [word for word in words if word not in joined]
        self.assertEqual(missing, [], msg=f"lost at chunk boundaries: {missing[:5]}")

    def test_invalid_parameters_raise(self) -> None:
        for kwargs in (
            {"chunk_size": 0},
            {"overlap": -1},
            {"chunk_size": 100, "overlap": 100},
        ):
            with self.assertRaises(ValueError):
                chunk_text("text", **kwargs)


class VectorLiteralTests(unittest.TestCase):
    def test_valid_vector_formats_for_pgvector(self) -> None:
        literal = _vector_literal(_vector(0.5))
        self.assertTrue(literal.startswith("[") and literal.endswith("]"))
        self.assertEqual(len(literal.split(",")), EMBEDDING_DIMENSIONS)

    def test_wrong_dimension_is_rejected(self) -> None:
        with self.assertRaises(RAGProviderError):
            _vector_literal([0.1, 0.2, 0.3])

    def test_non_finite_values_are_rejected(self) -> None:
        for bad_value in (float("nan"), float("inf")):
            vector = _vector()
            vector[0] = bad_value
            with self.assertRaises(RAGProviderError):
                _vector_literal(vector)


class ProviderFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_mismatched_embedding_count_raises(self) -> None:
        provider = QueuedEmbeddingProvider(queued=[[_vector()]])
        service = RAGService(provider=provider, database_url="unused")

        with self.assertRaises(RAGProviderError):
            await service.embed_document("finding " * 300)

    async def test_missing_query_vector_raises(self) -> None:
        provider = QueuedEmbeddingProvider(queued=[[]])
        service = RAGService(provider=provider, database_url="unused")

        with patch.object(RAGService, "_has_reports_sync", return_value=True):
            with self.assertRaises(RAGProviderError):
                await service.retrieve(uuid4(), uuid4(), "question")


class RetrievalScopingTests(unittest.IsolatedAsyncioTestCase):
    async def test_retrieval_passes_the_requesting_patient_and_session(self) -> None:
        provider = QueuedEmbeddingProvider()
        service = RAGService(provider=provider, database_url="unused")
        patient_id, session_id = uuid4(), uuid4()

        with (
            patch.object(RAGService, "_has_reports_sync", return_value=True),
            patch.object(
                RAGService, "_retrieve_sync", return_value=["chunk"]
            ) as retrieve_sync,
        ):
            result = await service.retrieve(
                patient_id, session_id, "What was my hemoglobin?", top_k=4
            )

        self.assertEqual(result, ["chunk"])
        args = retrieve_sync.call_args.args
        self.assertEqual(args[0], patient_id, "must scope to the requesting patient")
        self.assertEqual(args[1], session_id, "must scope to the requesting session")
        self.assertEqual(args[3], 4)

    async def test_report_check_uses_the_requesting_identity(self) -> None:
        provider = QueuedEmbeddingProvider()
        service = RAGService(provider=provider, database_url="unused")
        patient_id, session_id = uuid4(), uuid4()

        with patch.object(
            RAGService, "_has_reports_sync", return_value=False
        ) as has_reports:
            await service.retrieve(patient_id, session_id, "question")

        self.assertEqual(has_reports.call_args.args, (patient_id, session_id))


if __name__ == "__main__":
    unittest.main()
