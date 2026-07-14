from functools import lru_cache

from fastapi import APIRouter, HTTPException, status

from app.models.chats import ChatRequest, ChatResponse, MedicalSummary, SummaryRequest
from app.services.chat_service import (
    ChatService,
    EmptyConversationError,
    InvalidSummaryError,
)
from app.services.conversation_store import conversation_store
from app.services.llm_client import (
    LLMClient,
    LLMConfigurationError,
    LLMProviderError,
)


router = APIRouter(tags=["chat"])


@lru_cache
def get_chat_service() -> ChatService:
    return ChatService(store=conversation_store, llm=LLMClient())


def service_unavailable(exc: Exception) -> HTTPException:
    if isinstance(exc, LLMConfigurationError):
        detail = str(exc)
    else:
        detail = "The language model service is temporarily unavailable."
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=detail,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        service = get_chat_service()
        return await service.chat(request.session_id, request.message)
    except (LLMConfigurationError, LLMProviderError) as exc:
        raise service_unavailable(exc) from exc


@router.post("/summary", response_model=MedicalSummary)
async def summary(request: SummaryRequest) -> MedicalSummary:
    try:
        service = get_chat_service()
        return await service.summarize(request.session_id)
    except EmptyConversationError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No conversation exists for that session id.",
        ) from exc
    except InvalidSummaryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except (LLMConfigurationError, LLMProviderError) as exc:
        raise service_unavailable(exc) from exc
