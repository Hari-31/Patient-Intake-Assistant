from functools import lru_cache
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies.auth import require_doctor
from app.models.auth import AuthenticatedUser
from app.models.doctors import DoctorPatient, DoctorSessionTranscript, DoctorSummary
from app.services.doctor_service import (
    DoctorReader,
    DoctorResourceNotFound,
    DoctorStoreError,
    PostgresDoctorReader,
)


router = APIRouter(prefix="/doctor", tags=["doctor"])


@lru_cache
def get_doctor_reader() -> DoctorReader:
    return PostgresDoctorReader()


def _not_found(exc: DoctorResourceNotFound) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="The requested patient or session was not found.",
    )


def _unavailable(exc: DoctorStoreError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Doctor data is temporarily unavailable.",
    )


@router.get("/patients", response_model=list[DoctorPatient])
async def list_patients(
    doctor: AuthenticatedUser = Depends(require_doctor),
    reader: DoctorReader = Depends(get_doctor_reader),
) -> list[DoctorPatient]:
    try:
        return await reader.list_patients(doctor.id)
    except DoctorStoreError as exc:
        raise _unavailable(exc) from exc


@router.get("/summaries", response_model=list[DoctorSummary])
async def list_summaries(
    patient_id: UUID | None = Query(default=None),
    doctor: AuthenticatedUser = Depends(require_doctor),
    reader: DoctorReader = Depends(get_doctor_reader),
) -> list[DoctorSummary]:
    try:
        return await reader.list_summaries(doctor.id, patient_id)
    except DoctorResourceNotFound as exc:
        raise _not_found(exc) from exc
    except DoctorStoreError as exc:
        raise _unavailable(exc) from exc


@router.get(
    "/sessions/{session_id}", response_model=DoctorSessionTranscript
)
async def get_session(
    session_id: UUID,
    doctor: AuthenticatedUser = Depends(require_doctor),
    reader: DoctorReader = Depends(get_doctor_reader),
) -> DoctorSessionTranscript:
    try:
        return await reader.get_session(doctor.id, session_id)
    except DoctorResourceNotFound as exc:
        raise _not_found(exc) from exc
    except DoctorStoreError as exc:
        raise _unavailable(exc) from exc
