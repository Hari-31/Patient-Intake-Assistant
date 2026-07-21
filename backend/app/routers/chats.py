from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import require_patient
from app.models.auth import AuthenticatedUser
from app.models.chats import ChatRequest, ChatResponse, MedicalSummary, SummaryRequest
from app.services.chat_service import (
    ChatService,
    EmptyConversationError,
    InvalidIntakeDecisionError,
    IntakeIncompleteError,
    InvalidSummaryError,
)
from app.services.conversation_store import (
    ConversationStoreConfigurationError,
    ConversationStoreError,
    SessionClosedError,
    SessionNotFoundError,
    conversation_store,
)
from app.services.llm_client import (
    LLMClient,
    LLMConfigurationError,
    LLMProviderError,
)
from app.services.rag_service import (
    RAGConfigurationError,
    RAGProviderError,
    RAGStoreError,
    get_rag_service,
)


router = APIRouter(tags=["chat"])


@lru_cache
def get_chat_service() -> ChatService:
    return ChatService(
        store=conversation_store,
        llm=LLMClient(),
        rag=get_rag_service(),
    )


def service_unavailable(exc: Exception) -> HTTPException:
    if isinstance(
        exc,
        (
            ConversationStoreConfigurationError,
            LLMConfigurationError,
            RAGConfigurationError,
        ),
    ):
        detail = str(exc)
    else:
        detail = "A required backend service is temporarily unavailable."
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=detail,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    patient: AuthenticatedUser = Depends(require_patient),
) -> ChatResponse:
    try:
        service = get_chat_service()
        return await service.chat(patient.id, request.session_id, request.message)
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "That session does not exist. Omit session_id to start a new "
                "conversation, or use the UUID returned by the first /chat call."
            ),
        ) from exc
    except SessionClosedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This intake is closed. Start a new intake for a new concern.",
        ) from exc
    except InvalidIntakeDecisionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The intake assistant returned an invalid response.",
        ) from exc
    except InvalidSummaryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The intake assistant returned an invalid summary.",
        ) from exc
    except (
        LLMConfigurationError,
        LLMProviderError,
        ConversationStoreError,
        RAGConfigurationError,
        RAGProviderError,
        RAGStoreError,
    ) as exc:
        raise service_unavailable(exc) from exc


@router.post("/summary", response_model=MedicalSummary)
async def summary(
    request: SummaryRequest,
    patient: AuthenticatedUser = Depends(require_patient),
) -> MedicalSummary:
    try:
        service = get_chat_service()
        return await service.summarize(patient.id, request.session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No conversation exists for that session id.",
        ) from exc
    except EmptyConversationError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No conversation exists for that session id.",
        ) from exc
    except InvalidIntakeDecisionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The intake assistant returned an invalid response.",
        ) from exc
    except IntakeIncompleteError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except InvalidSummaryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except (
        LLMConfigurationError,
        LLMProviderError,
        ConversationStoreError,
        RAGConfigurationError,
        RAGProviderError,
        RAGStoreError,
    ) as exc:
        raise service_unavailable(exc) from exc
