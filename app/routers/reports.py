from functools import lru_cache
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.dependencies.auth import require_patient
from app.models.auth import AuthenticatedUser
from app.models.reports import ReportUploadResponse
from app.services.conversation_store import SessionClosedError, SessionNotFoundError
from app.services.rag_service import (
    RAGConfigurationError,
    RAGProviderError,
    RAGStoreError,
)
from app.services.report_service import (
    MAX_REPORT_BYTES,
    ReportService,
    ReportServiceError,
    ReportValidationError,
)


router = APIRouter(tags=["reports"])


@lru_cache
def get_report_service() -> ReportService:
    return ReportService()


@router.post(
    "/upload",
    response_model=ReportUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_report(
    session_id: UUID = Form(...),
    file: UploadFile = File(...),
    patient: AuthenticatedUser = Depends(require_patient),
    service: ReportService = Depends(get_report_service),
) -> ReportUploadResponse:
    content = await file.read(MAX_REPORT_BYTES + 1)
    try:
        return await service.upload_pdf(
            patient_id=patient.id,
            session_id=session_id,
            filename=file.filename or "report.pdf",
            content_type=file.content_type,
            content=content,
        )
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No conversation exists for that session id.",
        ) from exc
    except SessionClosedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This intake is closed. Start a new intake for a new concern.",
        ) from exc
    except ReportValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except (
        ReportServiceError,
        RAGConfigurationError,
        RAGProviderError,
        RAGStoreError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Report processing is temporarily unavailable.",
        ) from exc
    finally:
        await file.close()
