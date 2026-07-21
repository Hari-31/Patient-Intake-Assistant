from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.dependencies.auth import require_patient
from app.models.auth import AuthenticatedUser
from app.models.chats import ActiveSessionResponse, SessionMessage, SessionStatus
from app.services.conversation_store import (
    ConversationStoreError,
    ConversationStore,
    SessionClosedError,
    SessionNotFoundError,
    conversation_store,
)


router = APIRouter(prefix="/sessions", tags=["sessions"])


def get_conversation_store() -> ConversationStore:
    return conversation_store


@router.get("/active", response_model=ActiveSessionResponse)
async def active_session(
    patient: AuthenticatedUser = Depends(require_patient),
    store: ConversationStore = Depends(get_conversation_store),
) -> ActiveSessionResponse:
    try:
        session = await store.get_active_session(patient.id)
    except ConversationStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Conversation storage is temporarily unavailable.",
        ) from exc
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active intake was found.",
        )
    return ActiveSessionResponse(
        session_id=session.session_id,
        status=SessionStatus.active,
        messages=[
            SessionMessage(
                role=message.role,
                content=message.content,
                created_at=message.created_at,
            )
            for message in session.messages
        ],
    )


@router.post("/{session_id}/abandon", status_code=status.HTTP_204_NO_CONTENT)
async def abandon_session(
    session_id: UUID,
    patient: AuthenticatedUser = Depends(require_patient),
    store: ConversationStore = Depends(get_conversation_store),
) -> Response:
    try:
        await store.close_session(
            patient.id, session_id, "abandoned"
        )
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested resource was not found or is unavailable.",
        ) from exc
    except SessionClosedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This intake is already closed.",
        ) from exc
    except ConversationStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Conversation storage is temporarily unavailable.",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
