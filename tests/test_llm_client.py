import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.models.chats import MedicalSummary
from app.services.conversation_store import Message
from app.services.llm_client import LLMClient


class FakeAsyncModels:
    def __init__(self) -> None:
        self.request = None

    async def generate_content(self, **kwargs):
        self.request = kwargs
        return SimpleNamespace(text='{"chief_complaint": "Headache"}')


class FakeAsyncClient:
    def __init__(self) -> None:
        self.models = FakeAsyncModels()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None


class FakeGeminiClient:
    last_instance = None

    def __init__(self, *, api_key):
        self.api_key = api_key
        self.aio = FakeAsyncClient()
        self.closed = False
        FakeGeminiClient.last_instance = self

    def close(self):
        self.closed = True


class LLMClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_converts_history_and_requests_structured_output(self) -> None:
        with (
            patch.dict(
                os.environ,
                {"GEMINI_API_KEY": "test-key", "GEMINI_MODEL": "test-model"},
            ),
            patch(
                "app.services.llm_client.genai.Client",
                FakeGeminiClient,
            ),
        ):
            client = LLMClient()
            response = await client.complete(
                [
                    Message(role="system", content="System instructions"),
                    Message(role="user", content="Patient message"),
                    Message(role="assistant", content="Follow-up question"),
                ],
                response_model=MedicalSummary,
            )

        fake_client = FakeGeminiClient.last_instance
        request = fake_client.aio.models.request
        self.assertEqual(response, '{"chief_complaint": "Headache"}')
        self.assertEqual(request["model"], "test-model")
        self.assertEqual(
            [content.role for content in request["contents"]], ["user", "model"]
        )
        self.assertEqual(
            request["config"].system_instruction, "System instructions"
        )
        self.assertEqual(request["config"].response_schema, MedicalSummary)
        self.assertEqual(
            request["config"].response_mime_type, "application/json"
        )
        self.assertTrue(fake_client.closed)


if __name__ == "__main__":
    unittest.main()
