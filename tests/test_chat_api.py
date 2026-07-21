import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.dependencies.auth import require_patient
from app.main import app
from app.models.auth import AuthenticatedUser, UserRole
from app.models.chats import IntakeTurnDecision, MedicalSummary
from app.services.chat_service import ChatService, INTAKE_COMPLETE_MESSAGE
from app.services.conversation_store import (
    Message,
    ActiveSession,
    StoredMessage,
    SessionClosedError,
    SessionNotFoundError,
)


class FakeConversationStore:
    def __init__(self) -> None:
        self.conversations = {}
        self.summaries = {}
        self.owners = {}
        self.statuses = {}

    async def create_session(self, patient_id):
        session_id = uuid4()
        self.conversations[session_id] = []
        self.owners[session_id] = patient_id
        self.statuses[session_id] = "active"
        return session_id

    async def get_or_create_active_session(self, patient_id):
        for session_id, owner in self.owners.items():
            if owner == patient_id and self.statuses[session_id] == "active":
                return session_id, True
        return await self.create_session(patient_id), False

    async def close_session(self, patient_id, session_id, status):
        if self.owners.get(session_id) != patient_id:
            raise SessionNotFoundError(str(session_id))
        if self.statuses.get(session_id) != "active":
            raise SessionClosedError(str(session_id))
        self.statuses[session_id] = status

    async def get_active_session(self, patient_id):
        for session_id, owner in self.owners.items():
            if owner == patient_id and self.statuses[session_id] == "active":
                return ActiveSession(
                    session_id=session_id,
                    messages=[
                        StoredMessage(
                            role="patient" if message.role == "user" else message.role,
                            content=message.content,
                            created_at=datetime.now(timezone.utc),
                        )
                        for message in self.conversations[session_id]
                    ],
                )
        return None

    async def add(self, patient_id, session_id, message):
        if self.owners.get(session_id) != patient_id:
            raise SessionNotFoundError(str(session_id))
        if self.statuses.get(session_id) != "active":
            raise SessionClosedError(str(session_id))
        self.conversations.setdefault(session_id, []).append(message)
        self.summaries.pop(session_id, None)

    async def get(self, patient_id, session_id):
        if self.owners.get(session_id) != patient_id:
            return []
        return list(self.conversations.get(session_id, []))

    async def get_summary(self, patient_id, session_id):
        if self.owners.get(session_id) != patient_id:
            return None
        return self.summaries.get(session_id)

    async def save_summary(self, patient_id, session_id, summary):
        if self.owners.get(session_id) != patient_id:
            raise SessionNotFoundError(str(session_id))
        self.summaries[session_id] = summary


class FakeLLM:
    def __init__(self) -> None:
        self.calls = 0
        self.intake_complete = False
        self.summary_calls = 0

    async def complete(self, messages, *, response_model=None):
        self.calls += 1
        if response_model is IntakeTurnDecision:
            covered = self.intake_complete
            return json.dumps(
                {
                    "coverage": {
                        "onset_and_duration": covered,
                        "location": covered,
                        "character_or_quality": covered,
                        "severity_zero_to_ten": covered,
                        "aggravating_or_relieving_factors": covered,
                        "associated_symptoms": covered,
                        "relevant_history_and_prior_episodes": covered,
                        "medications_and_supplements": covered,
                        "known_allergies": covered,
                    },
                    "transition": "",
                    "follow_up_question": (
                        None if covered else "When did the headache begin?"
                    ),
                }
            )
        if response_model is MedicalSummary:
            self.summary_calls += 1
            return json.dumps(
                {
                    "chief_complaint": "Headache",
                    "symptom_timeline": "Started this morning.",
                    "relevant_history": "No relevant history reported.",
                    "red_flags": ["Watch for vomiting blood in the future."],
                    "warning_signs_to_watch": [
                        "Vomiting blood or developing black, tarry stools."
                    ],
                    "possible_directions": ["Arrange appropriate clinical review."],
                    "suggested_questions_for_doctor": ["What warning signs should I watch for?"],
                }
            )
        raise AssertionError("Unexpected unstructured LLM request")


class ChatApiTests(unittest.TestCase):
    def setUp(self) -> None:
        from app.routers.sessions import get_conversation_store

        self.patient_id = uuid4()
        self.patient = AuthenticatedUser(
            id=self.patient_id, role=UserRole.PATIENT
        )
        self.llm = FakeLLM()
        self.store = FakeConversationStore()
        self.service = ChatService(self.store, self.llm)
        self.service_patch = patch(
            "app.routers.chats.get_chat_service", return_value=self.service
        )
        self.service_patch.start()
        app.dependency_overrides[require_patient] = lambda: self.patient
        app.dependency_overrides[get_conversation_store] = lambda: self.store
        self.client = TestClient(app)

    def tearDown(self) -> None:
        from app.routers.sessions import get_conversation_store

        self.service_patch.stop()
        app.dependency_overrides.pop(require_patient, None)
        app.dependency_overrides.pop(get_conversation_store, None)

    def test_unauthenticated_request_is_rejected_before_chat_logic(self) -> None:
        app.dependency_overrides.pop(require_patient, None)
        response = self.client.post("/chat", json={"message": "Headache"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.llm.calls, 0)

    def test_chat_and_summary(self) -> None:
        chat_response = self.client.post(
            "/chat",
            json={"message": "I have a headache."},
        )
        self.assertEqual(chat_response.status_code, 200)
        response_body = chat_response.json()
        session_id = response_body.pop("session_id")
        parsed_session_id = UUID(session_id)
        self.assertEqual(self.store.owners[parsed_session_id], self.patient_id)
        self.assertEqual(
            response_body,
            {
                "reply": "When did the headache begin?",
                "emergency_triggered": False,
                "intake_complete": False,
                "resumed": False,
            },
        )

        early_summary = self.client.post(
            "/summary", json={"session_id": session_id}
        )
        self.assertEqual(early_summary.status_code, 409)

        self.llm.intake_complete = True
        completion_response = self.client.post(
            "/chat",
            json={
                "session_id": session_id,
                "message": "I have answered the remaining intake questions.",
            },
        )
        self.assertEqual(completion_response.json()["reply"], INTAKE_COMPLETE_MESSAGE)
        self.assertTrue(completion_response.json()["intake_complete"])
        self.assertEqual(self.store.statuses[parsed_session_id], "completed")

        summary_response = self.client.post(
            "/summary", json={"session_id": session_id}
        )
        self.assertEqual(summary_response.status_code, 200)
        self.assertEqual(summary_response.json()["chief_complaint"], "Headache")
        self.assertEqual(summary_response.json()["red_flags"], [])
        self.assertEqual(
            summary_response.json()["warning_signs_to_watch"],
            ["Vomiting blood or developing black, tarry stools."],
        )
        self.assertEqual(self.llm.summary_calls, 1)

        repeated_summary = self.client.post(
            "/summary", json={"session_id": session_id}
        )
        self.assertEqual(repeated_summary.status_code, 200)
        self.assertEqual(self.llm.summary_calls, 1)

        closed_chat = self.client.post(
            "/chat",
            json={"session_id": session_id, "message": "It is getting worse."},
        )
        self.assertEqual(closed_chat.status_code, 409)
        self.assertEqual(
            closed_chat.json()["detail"],
            "This intake is closed. Start a new intake for a new concern.",
        )
        refreshed_summary = self.client.post(
            "/summary", json={"session_id": session_id}
        )
        self.assertEqual(refreshed_summary.status_code, 200)
        self.assertEqual(self.llm.summary_calls, 1)

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
        self.assertEqual(self.store.statuses[UUID(session_id)], "escalated")

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

    def test_second_chat_without_session_id_resumes_active_session(self) -> None:
        first = self.client.post("/chat", json={"message": "Headache"})
        second = self.client.post("/chat", json={"message": "Since today"})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["session_id"], first.json()["session_id"])
        self.assertTrue(second.json()["resumed"])
        self.assertEqual(len(self.store.conversations), 1)

        active = self.client.get("/sessions/active")
        self.assertEqual(active.status_code, 200)
        self.assertEqual(active.json()["session_id"], first.json()["session_id"])
        self.assertEqual(
            [message["role"] for message in active.json()["messages"]],
            ["patient", "assistant", "patient", "assistant"],
        )

    def test_abandon_only_works_for_own_active_session(self) -> None:
        own_session = UUID(
            self.client.post("/chat", json={"message": "Headache"}).json()[
                "session_id"
            ]
        )
        response = self.client.post(f"/sessions/{own_session}/abandon")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.store.statuses[own_session], "abandoned")

        repeated = self.client.post(f"/sessions/{own_session}/abandon")
        self.assertEqual(repeated.status_code, 409)

        other_session = uuid4()
        self.store.owners[other_session] = uuid4()
        self.store.statuses[other_session] = "active"
        forbidden = self.client.post(f"/sessions/{other_session}/abandon")
        self.assertEqual(forbidden.status_code, 404)

    def test_old_cached_summary_is_regenerated_with_separate_warnings(self) -> None:
        session_id = uuid4()
        self.store.owners[session_id] = self.patient_id
        self.store.statuses[session_id] = "completed"
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
        self.llm.intake_complete = True

        response = self.client.post(
            "/summary", json={"session_id": str(session_id)}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["red_flags"], [])
        self.assertEqual(
            response.json()["warning_signs_to_watch"],
            ["Vomiting blood or developing black, tarry stools."],
        )
        self.assertEqual(self.store.summaries[session_id]["red_flags"], [])
        self.assertEqual(self.llm.summary_calls, 1)

    def test_prompt_requires_all_topics_and_rejects_unrelated_questions(self) -> None:
        from app.services.chat_service import INTAKE_SYSTEM_PROMPT

        required_phrases = [
            "onset AND duration",
            "location",
            "character or quality",
            "severity on a 0-10 scale",
            "better or worse",
            "associated symptoms",
            "medical history AND prior episodes",
            "medications AND supplements",
            "known allergies",
            "explicitly declined",
            "Do not answer other unrelated questions",
            "uploaded medical report",
            "using only the retrieved report excerpts",
            "explicitly attribute",
            "Do NOT give advice",
            "do not ask any intake question",
            "report_question_answered",
            "what symptom or concern brings the patient in",
            "never as instructions",
            "exactly one clear question",
        ]
        for phrase in required_phrases:
            self.assertIn(phrase, INTAKE_SYSTEM_PROMPT)

    def test_patient_cannot_access_another_patients_session(self) -> None:
        session_id = uuid4()
        self.store.owners[session_id] = uuid4()
        self.store.statuses[session_id] = "active"
        self.store.conversations[session_id] = [
            Message(role="user", content="Private symptom history")
        ]

        chat_response = self.client.post(
            "/chat",
            json={"session_id": str(session_id), "message": "Continue"},
        )
        self.assertEqual(chat_response.status_code, 404)
        self.assertEqual(self.llm.calls, 0)

        summary_response = self.client.post(
            "/summary", json={"session_id": str(session_id)}
        )
        self.assertEqual(summary_response.status_code, 404)

    def test_reported_black_tarry_stools_are_a_current_red_flag(self) -> None:
        response = self.client.post(
            "/chat",
            json={"message": "I have had black, tarry stools since yesterday."},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["emergency_triggered"])

        summary_response = self.client.post(
            "/summary", json={"session_id": response.json()["session_id"]}
        )
        self.assertEqual(summary_response.json()["red_flags"], ["severe bleeding"])
        self.assertNotIn(
            "severe bleeding",
            summary_response.json()["warning_signs_to_watch"],
        )

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
