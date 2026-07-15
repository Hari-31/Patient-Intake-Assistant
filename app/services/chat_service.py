import json
from uuid import UUID

from pydantic import ValidationError

from app.models.chats import ChatResponse, MedicalSummary
from app.services.conversation_store import ConversationStore, Message
from app.services.llm_client import LLMClient
from app.services.safety import URGENT_CARE_MESSAGE, find_red_flags


INTAKE_SYSTEM_PROMPT = """You are an educational medical intake assistant gathering information before a clinician visit.

Your job is to collect a concise, accurate symptom history for clinician review. You provide decision support only: do not diagnose, prescribe, or claim certainty. Ask exactly ONE clear, relevant follow-up question per response.

Over the conversation, cover the chief concern, onset, duration, progression, severity, location, quality, associated symptoms, aggravating or relieving factors, relevant medical history, medications, allergies, and prior episodes. Do not mechanically repeat questions or ask for information already supplied. Be empathetic and concise.

When enough useful information has been collected, do not keep interviewing. Say that the intake has enough information for a preliminary summary and invite the patient to request the summary. Never hide urgent risk: advise immediate emergency help when the conversation suggests a potentially life-threatening situation. The final clinician must verify everything against the full transcript."""


SUMMARY_SYSTEM_PROMPT = """You create a structured medical intake summary for clinician review from the supplied transcript. This is decision support, not a diagnosis. Do not invent facts. Clearly represent missing or uncertain information. The red_flags field is only for urgent warning signs the patient affirmatively reported in this conversation. Never put denied symptoms, absent symptoms, hypothetical risks, or warning signs to watch for in red_flags; return an empty list when none were reported. Put future warning signs and escalation guidance in possible_directions instead. Possible directions must be cautious, non-diagnostic considerations or care levels, not definitive conclusions. Follow the supplied response schema."""


class EmptyConversationError(LookupError):
    pass


class InvalidSummaryError(RuntimeError):
    pass


class ChatService:
    def __init__(
        self,
        store: ConversationStore,
        llm: LLMClient,
    ) -> None:
        self.store = store
        self.llm = llm

    async def chat(
        self, session_id: UUID | None, patient_message: str
    ) -> ChatResponse:
        if session_id is None:
            session_id = await self.store.create_session()

        message = Message(role="user", content=patient_message.strip())
        await self.store.add(session_id, message)

        red_flags = find_red_flags(patient_message)
        if red_flags:
            await self.store.add(
                session_id,
                Message(role="assistant", content=URGENT_CARE_MESSAGE),
            )
            return ChatResponse(
                session_id=session_id,
                reply=URGENT_CARE_MESSAGE,
                emergency_triggered=True,
            )

        history = await self.store.get(session_id)
        reply = await self.llm.complete(
            [Message(role="system", content=INTAKE_SYSTEM_PROMPT), *history]
        )
        await self.store.add(session_id, Message(role="assistant", content=reply))
        return ChatResponse(
            session_id=session_id,
            reply=reply,
            emergency_triggered=False,
        )

    async def summarize(self, session_id: UUID) -> MedicalSummary:
        history = await self.store.get(session_id)
        if not history:
            raise EmptyConversationError(session_id)

        detected_flags = list(
            dict.fromkeys(
                flag
                for message in history
                if message.role == "user"
                for flag in find_red_flags(message.content)
            )
        )
        persisted_summary = await self.store.get_summary(session_id)
        if persisted_summary is not None:
            summary = MedicalSummary.model_validate(persisted_summary)
            if summary.red_flags != detected_flags:
                summary.red_flags = detected_flags
                await self.store.save_summary(
                    session_id, summary.model_dump(mode="json")
                )
            return summary

        transcript = "\n".join(
            f"{message.role.upper()}: {message.content}" for message in history
        )
        raw_summary = await self.llm.complete(
            [
                Message(role="system", content=SUMMARY_SYSTEM_PROMPT),
                Message(role="user", content=f"Conversation transcript:\n{transcript}"),
            ],
            response_model=MedicalSummary,
        )
        try:
            summary = MedicalSummary.model_validate(json.loads(raw_summary))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise InvalidSummaryError("The LLM returned an invalid summary.") from exc

        # Safety rules, not generic LLM advice, define patient-specific red flags.
        summary.red_flags = detected_flags
        await self.store.save_summary(session_id, summary.model_dump(mode="json"))
        return summary
