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
            "Urgent warning signs actually reported by this patient. Exclude denied, "
            "absent, hypothetical, and future symptoms; use an empty list when none "
            "were reported."
        )
    )
    possible_directions: list[str] = Field(
        description=(
            "Potential non-diagnostic directions, care levels, and future warning "
            "signs that should prompt urgent evaluation."
        )
    )
    suggested_questions_for_doctor: list[str] = Field(description="Helpful questions the patient should ask their healthcare provider.")
