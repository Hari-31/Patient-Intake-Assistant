import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.models.chats import MedicalSummary
from app.services.conversation_store import Message
from app.services.llm_client import LLMClient


class FakeResponses:
    def __init__(self) -> None:
        self.create_request = None
        self.parse_request = None

    async def create(self, **kwargs):
        self.create_request = kwargs
        return SimpleNamespace(output_text="When did the headache begin?")

    async def parse(self, **kwargs):
        self.parse_request = kwargs
        return SimpleNamespace(
            output_parsed=MedicalSummary(
                chief_complaint="Headache",
                symptom_timeline="Started today",
                relevant_history="None reported",
                red_flags=[],
                possible_directions=[],
                suggested_questions_for_doctor=[],
            )
        )


class FakeOpenAIClient:
    last_instance = None

    def __init__(self, **kwargs):
        self.client_options = kwargs
        self.responses = FakeResponses()
        FakeOpenAIClient.last_instance = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None


class LLMClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_sends_history_through_responses_api(self) -> None:
        with (
            patch.dict(
                os.environ,
                {"OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "test-model"},
            ),
            patch("app.services.llm_client.AsyncOpenAI", FakeOpenAIClient),
        ):
            client = LLMClient()
            response = await client.complete(
                [
                    Message(role="system", content="System instructions"),
                    Message(role="user", content="Patient message"),
                    Message(role="assistant", content="Follow-up question"),
                ]
            )

        fake_client = FakeOpenAIClient.last_instance
        request = fake_client.responses.create_request
        self.assertEqual(response, "When did the headache begin?")
        self.assertEqual(request["model"], "test-model")
        self.assertEqual(request["instructions"], "System instructions")
        self.assertFalse(request["store"])
        self.assertEqual(
            [message["role"] for message in request["input"]],
            ["user", "assistant"],
        )

    async def test_requests_native_structured_output(self) -> None:
        with (
            patch.dict(
                os.environ,
                {"OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "test-model"},
            ),
            patch("app.services.llm_client.AsyncOpenAI", FakeOpenAIClient),
        ):
            client = LLMClient()
            response = await client.complete(
                [
                    Message(role="system", content="Summary instructions"),
                    Message(role="user", content="Conversation transcript"),
                ],
                response_model=MedicalSummary,
            )

        fake_client = FakeOpenAIClient.last_instance
        request = fake_client.responses.parse_request
        self.assertEqual(json.loads(response)["chief_complaint"], "Headache")
        self.assertEqual(request["model"], "test-model")
        self.assertIs(request["text_format"], MedicalSummary)
        self.assertFalse(request["store"])


if __name__ == "__main__":
    unittest.main()
