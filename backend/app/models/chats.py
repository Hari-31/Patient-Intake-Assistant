from uuid import UUID

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: UUID | None = None
    message: str = Field(min_length=1, max_length=10_000)


class ChatResponse(BaseModel):
    session_id: UUID
    reply: str
    emergency_triggered: bool


class SummaryRequest(BaseModel):
    session_id: UUID


class MedicalSummary(BaseModel):
    chief_complaint: str = Field(description="Brief summary of the primary reason the patient is seeking care.")
    symptom_timeline: str = Field(description="Onset, duration, and progression of the symptoms.")
    relevant_history: str = Field(description="Any relevant past history, chronic conditions, or medications mentioned.")
    red_flags: list[str] = Field(
        description=(
            "Alarming findings actually reported by this patient in the conversation. "
            "Exclude denied, absent, hypothetical, and future symptoms; use an empty "
            "list when none were reported."
        )
    )
    warning_signs_to_watch: list[str] = Field(
        description=(
            "Symptoms or changes that would warrant urgent care if they appear later. "
            "Do not include these in red_flags unless the patient already reported them."
        )
    )
    possible_directions: list[str] = Field(
        description=(
            "Potential non-diagnostic considerations, next steps, or care levels. "
            "Do not place future warning signs in this field."
        )
    )
    suggested_questions_for_doctor: list[str] = Field(description="Helpful questions the patient should ask their healthcare provider.")
