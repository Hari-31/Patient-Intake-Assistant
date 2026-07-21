import unittest
from uuid import uuid4

from app.services.rag_service import (
    EMBEDDING_DIMENSIONS,
    RAGService,
    chunk_text,
)


class FakeEmbeddingProvider:
    def __init__(self) -> None:
        self.calls = []

    async def embed(self, texts):
        self.calls.append(list(texts))
        return [[float(index)] * EMBEDDING_DIMENSIONS for index, _ in enumerate(texts)]


class NoReportRAGService(RAGService):
    def _has_reports_sync(self, patient_id, session_id):
        return False


class RAGServiceTests(unittest.IsolatedAsyncioTestCase):
    def test_chunk_text_uses_bounded_overlapping_chunks(self) -> None:
        chunks = chunk_text("word " * 500, chunk_size=200, overlap=30)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(1 <= len(chunk) <= 200 for chunk in chunks))
        self.assertTrue(set(chunks[0].split()) & set(chunks[1].split()))

    async def test_embed_document_keeps_chunk_order(self) -> None:
        provider = FakeEmbeddingProvider()
        service = RAGService(provider=provider, database_url="unused")
        chunks = await service.embed_document("finding " * 300)

        self.assertGreater(len(chunks), 1)
        self.assertEqual([chunk.index for chunk in chunks], list(range(len(chunks))))
        self.assertEqual(len(provider.calls), 1)

    async def test_no_report_skips_query_embedding(self) -> None:
        provider = FakeEmbeddingProvider()
        service = NoReportRAGService(provider=provider, database_url="unused")

        result = await service.retrieve(uuid4(), uuid4(), "patient question")

        self.assertEqual(result, [])
        self.assertEqual(provider.calls, [])


if __name__ == "__main__":
    unittest.main()
