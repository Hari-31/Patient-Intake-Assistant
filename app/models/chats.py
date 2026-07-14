from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=10_000)


class ChatResponse(BaseModel):
    reply: str
    emergency_triggered: bool


class SummaryRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)


class MedicalSummary(BaseModel):
    chief_complaint: str = Field(description="Brief summary of the primary reason the patient is seeking care.")
    symptom_timeline: str = Field(description="Onset, duration, and progression of the symptoms.")
    relevant_history: str = Field(description="Any relevant past history, chronic conditions, or medications mentioned.")
    red_flags: list[str] = Field(description="Any emergency red flags or severe symptoms identified.")
    possible_directions: list[str] = Field(description="Potential non-diagnostic directions or care levels to consider.")
    suggested_questions_for_doctor: list[str] = Field(description="Helpful questions the patient should ask their healthcare provider.")
