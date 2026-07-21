from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.chats import MedicalSummary, SessionStatus


class DoctorPatient(BaseModel):
    patient_id: UUID
    name: str | None
    assigned_at: datetime


class DoctorSummary(BaseModel):
    session_id: UUID
    patient_id: UUID
    patient_name: str | None
    status: SessionStatus
    summary: MedicalSummary | None
    created_at: datetime
    updated_at: datetime


class TranscriptMessage(BaseModel):
    role: str
    content: str
    created_at: datetime


class DoctorSessionTranscript(BaseModel):
    session_id: UUID
    patient_id: UUID
    patient_name: str | None
    status: SessionStatus
    created_at: datetime
    messages: list[TranscriptMessage]
    summary: MedicalSummary | None


class DoctorSessionCompletion(BaseModel):
    session_id: UUID
    status: SessionStatus
