from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_auth_service
from app.models.auth import PatientSignupRequest, PatientSignupResponse
from app.services.auth import (
    AuthConfigurationError,
    AuthServiceError,
    SignupError,
    SupabaseAuthService,
)


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/signup",
    response_model=PatientSignupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def signup_patient(
    request: PatientSignupRequest,
    auth_service: SupabaseAuthService = Depends(get_auth_service),
) -> PatientSignupResponse:
    try:
        return await auth_service.create_patient(
            email=request.email,
            password=request.password,
            name=request.name,
        )
    except SignupError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not create that patient account.",
        ) from exc
    except (AuthConfigurationError, AuthServiceError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable.",
        ) from exc
