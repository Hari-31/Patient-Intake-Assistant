import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.chat_service import ChatService
from app.services.conversation_store import InMemoryConversationStore


class FakeLLM:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, messages, *, response_model=None):
        self.calls += 1
        if response_model is not None:
            return json.dumps(
                {
                    "chief_complaint": "Headache",
                    "symptom_timeline": "Started this morning.",
                    "relevant_history": "No relevant history reported.",
                    "red_flags": [],
                    "possible_directions": ["Clinical assessment is appropriate."],
                    "suggested_questions_for_doctor": ["What warning signs should I watch for?"],
                }
            )
        return "When did the headache begin?"


class ChatApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.llm = FakeLLM()
        self.service = ChatService(InMemoryConversationStore(), self.llm)
        self.service_patch = patch(
            "app.routers.chats.get_chat_service", return_value=self.service
        )
        self.service_patch.start()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.service_patch.stop()

    def test_chat_and_summary(self) -> None:
        chat_response = self.client.post(
            "/chat",
            json={"session_id": "session-1", "message": "I have a headache."},
        )
        self.assertEqual(chat_response.status_code, 200)
        self.assertEqual(
            chat_response.json(),
            {
                "reply": "When did the headache begin?",
                "emergency_triggered": False,
            },
        )

        summary_response = self.client.post(
            "/summary", json={"session_id": "session-1"}
        )
        self.assertEqual(summary_response.status_code, 200)
        self.assertEqual(summary_response.json()["chief_complaint"], "Headache")
        self.assertEqual(self.llm.calls, 2)

    def test_red_flag_short_circuits_llm(self) -> None:
        response = self.client.post(
            "/chat",
            json={"session_id": "urgent", "message": "I have chest pain."},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["emergency_triggered"])
        self.assertIn("call emergency services", response.json()["reply"])
        self.assertEqual(self.llm.calls, 0)

    def test_summary_requires_a_conversation(self) -> None:
        response = self.client.post(
            "/summary", json={"session_id": "does-not-exist"}
        )
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
