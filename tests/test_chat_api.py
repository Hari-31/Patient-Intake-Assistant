import json
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.services.chat_service import ChatService
from app.services.conversation_store import Message, SessionNotFoundError


class FakeConversationStore:
    def __init__(self) -> None:
        self.conversations = {}
        self.summaries = {}

    async def create_session(self):
        session_id = uuid4()
        self.conversations[session_id] = []
        return session_id

    async def add(self, session_id, message):
        if session_id not in self.conversations:
            raise SessionNotFoundError(str(session_id))
        self.conversations.setdefault(session_id, []).append(message)
        self.summaries.pop(session_id, None)

    async def get(self, session_id):
        return list(self.conversations.get(session_id, []))

    async def get_summary(self, session_id):
        return self.summaries.get(session_id)

    async def save_summary(self, session_id, summary):
        self.summaries[session_id] = summary


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
                    "red_flags": ["Watch for vomiting blood in the future."],
                    "possible_directions": [
                        "Seek urgent evaluation if warning signs develop."
                    ],
                    "suggested_questions_for_doctor": ["What warning signs should I watch for?"],
                }
            )
        return "When did the headache begin?"


class ChatApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.llm = FakeLLM()
        self.store = FakeConversationStore()
        self.service = ChatService(self.store, self.llm)
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
            json={"message": "I have a headache."},
        )
        self.assertEqual(chat_response.status_code, 200)
        response_body = chat_response.json()
        session_id = response_body.pop("session_id")
        UUID(session_id)
        self.assertEqual(
            response_body,
            {
                "reply": "When did the headache begin?",
                "emergency_triggered": False,
            },
        )

        summary_response = self.client.post(
            "/summary", json={"session_id": session_id}
        )
        self.assertEqual(summary_response.status_code, 200)
        self.assertEqual(summary_response.json()["chief_complaint"], "Headache")
        self.assertEqual(summary_response.json()["red_flags"], [])
        self.assertEqual(self.llm.calls, 2)

        repeated_summary = self.client.post(
            "/summary", json={"session_id": session_id}
        )
        self.assertEqual(repeated_summary.status_code, 200)
        self.assertEqual(self.llm.calls, 2)

        self.client.post(
            "/chat",
            json={"session_id": session_id, "message": "It is getting worse."},
        )
        refreshed_summary = self.client.post(
            "/summary", json={"session_id": session_id}
        )
        self.assertEqual(refreshed_summary.status_code, 200)
        self.assertEqual(self.llm.calls, 4)

    def test_red_flag_short_circuits_llm(self) -> None:
        response = self.client.post(
            "/chat",
            json={"message": "I have chest pain."},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["emergency_triggered"])
        self.assertIn("call emergency services", response.json()["reply"])
        self.assertEqual(self.llm.calls, 0)
        session_id = response.json()["session_id"]

        summary_response = self.client.post(
            "/summary", json={"session_id": session_id}
        )
        self.assertEqual(
            summary_response.json()["red_flags"],
            ["possible heart or breathing emergency"],
        )

    def test_denied_red_flag_does_not_trigger_emergency(self) -> None:
        response = self.client.post(
            "/chat",
            json={
                "message": "I have a headache but no chest pain or trouble breathing.",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["emergency_triggered"])

    def test_old_cached_summary_red_flags_are_corrected(self) -> None:
        session_id = uuid4()
        self.store.conversations[session_id] = [
            Message(role="user", content="I have a mild headache.")
        ]
        self.store.summaries[session_id] = {
            "chief_complaint": "Mild headache",
            "symptom_timeline": "Today",
            "relevant_history": "None reported",
            "red_flags": ["Watch for weakness or slurred speech."],
            "possible_directions": ["Arrange clinical review."],
            "suggested_questions_for_doctor": [],
        }

        response = self.client.post(
            "/summary", json={"session_id": str(session_id)}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["red_flags"], [])
        self.assertEqual(self.store.summaries[session_id]["red_flags"], [])

    def test_summary_requires_a_conversation(self) -> None:
        response = self.client.post(
            "/summary", json={"session_id": str(uuid4())}
        )
        self.assertEqual(response.status_code, 404)

    def test_chat_rejects_unknown_session(self) -> None:
        response = self.client.post(
            "/chat",
            json={
                "session_id": str(uuid4()),
                "message": "Continue my intake.",
            },
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("Omit session_id", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
