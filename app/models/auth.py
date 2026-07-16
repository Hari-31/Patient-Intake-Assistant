from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class UserRole(str, Enum):
    PATIENT = "patient"
    DOCTOR = "doctor"


@dataclass(frozen=True)
class AuthenticatedUser:
    id: UUID
    role: UserRole


class PatientSignupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=200)


class PatientSignupResponse(BaseModel):
    user_id: UUID
    email: str
    role: UserRole
