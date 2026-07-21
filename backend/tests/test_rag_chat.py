import json
import unittest
from uuid import uuid4

from app.models.chats import IntakeTurnDecision, MedicalSummary
from app.services.chat_service import ChatService
from app.services.conversation_store import Message


class MemoryStore:
    def __init__(self, patient_id, session_id):
        self.patient_id = patient_id
        self.session_id = session_id
        self.messages = []
        self.summary = None
        self.status = "active"

    async def create_session(self, patient_id):
        self.patient_id = patient_id
        self.session_id = uuid4()
        return self.session_id

    async def get_or_create_active_session(self, patient_id):
        return self.session_id, True

    async def get_session_status(self, patient_id, session_id):
        return self.status

    async def submit_session(self, patient_id, session_id):
        self.status = "submitted"

    async def close_session(self, patient_id, session_id, status):
        self.status = status

    async def add(self, patient_id, session_id, message):
        self.messages.append(message)
        self.summary = None

    async def add_and_close(self, patient_id, session_id, message, status):
        await self.add(patient_id, session_id, message)
        await self.close_session(patient_id, session_id, status)

    async def get(self, patient_id, session_id):
        return list(self.messages)

    async def get_summary(self, patient_id, session_id):
        return self.summary

    async def save_summary(self, patient_id, session_id, summary):
        self.summary = summary


class FakeRAG:
    def __init__(self):
        self.calls = []

    async def retrieve(self, patient_id, session_id, query, *, top_k):
        self.calls.append((patient_id, session_id, query, top_k))
        return ["Laboratory report: HbA1c was 8.2% on June 10."]


class CapturingLLM:
    def __init__(self):
        self.calls = []
        self.intake_complete = False

    async def complete(self, messages, *, response_model=None):
        self.calls.append((messages, response_model))
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
                    "report_question_answered": not covered,
                    "transition": (
                        "Your uploaded report lists an HbA1c of 8.2%."
                        if not covered
                        else ""
                    ),
                    "follow_up_question": (
                        None
                    ),
                }
            )
        if response_model is MedicalSummary:
            return json.dumps(
                {
                    "chief_complaint": "Increased thirst",
                    "symptom_timeline": "Recently reported.",
                    "relevant_history": "Uploaded report lists HbA1c 8.2%.",
                    "red_flags": [],
                    "warning_signs_to_watch": [],
                    "possible_directions": ["Clinical review of elevated HbA1c."],
                    "suggested_questions_for_doctor": [],
                }
            )
        raise AssertionError("Unexpected unstructured LLM request")


class RAGChatTests(unittest.IsolatedAsyncioTestCase):
    async def test_chat_and_summary_receive_retrieved_report_context(self) -> None:
        patient_id = uuid4()
        session_id = uuid4()
        store = MemoryStore(patient_id, session_id)
        rag = FakeRAG()
        llm = CapturingLLM()
        service = ChatService(store=store, llm=llm, rag=rag)

        response = await service.chat(
            patient_id, session_id, "Could my report relate to increased thirst?"
        )
        llm.intake_complete = True
        summary = await service.summarize(patient_id, session_id)

        self.assertIn("HbA1c of 8.2%", response.reply)
        self.assertNotIn("?", response.reply)
        self.assertNotIn("When did", response.reply)
        self.assertIn("HbA1c 8.2%", summary.relevant_history)
        self.assertEqual(len(rag.calls), 2)
        context_calls = [
            messages
            for messages, response_model in llm.calls
            if response_model is MedicalSummary
            or any(
                "REPORT EXCERPTS:" in message.content
                for message in messages
                if message.role == "system"
            )
        ]
        for call in context_calls:
            context = "\n".join(
                message.content for message in call if message.role == "system"
            )
            self.assertIn("HbA1c was 8.2%", context)
            self.assertIn("untrusted reference data", context)


if __name__ == "__main__":
    unittest.main()
