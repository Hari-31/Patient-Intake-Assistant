import json
import unittest
from uuid import uuid4

from app.models.chats import MedicalSummary
from app.services.chat_service import ChatService
from app.services.conversation_store import Message


class MemoryStore:
    def __init__(self, patient_id, session_id):
        self.patient_id = patient_id
        self.session_id = session_id
        self.messages = []
        self.summary = None

    async def create_session(self, patient_id):
        self.patient_id = patient_id
        self.session_id = uuid4()
        return self.session_id

    async def add(self, patient_id, session_id, message):
        self.messages.append(message)
        self.summary = None

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

    async def complete(self, messages, *, response_model=None):
        self.calls.append(messages)
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
        return "Your uploaded report lists an HbA1c of 8.2%. When did the thirst begin?"


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
        summary = await service.summarize(patient_id, session_id)

        self.assertIn("HbA1c of 8.2%", response.reply)
        self.assertIn("HbA1c 8.2%", summary.relevant_history)
        self.assertEqual(len(rag.calls), 2)
        for call in llm.calls:
            context = "\n".join(
                message.content for message in call if message.role == "system"
            )
            self.assertIn("HbA1c was 8.2%", context)
            self.assertIn("untrusted reference data", context)


if __name__ == "__main__":
    unittest.main()
