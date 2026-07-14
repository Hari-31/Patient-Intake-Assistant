import asyncio
from dataclasses import dataclass


@dataclass(frozen=True)
class Message:
    role: str
    content: str


class InMemoryConversationStore:
    """Process-local storage. Restarting the API clears every conversation."""

    def __init__(self) -> None:
        self._conversations: dict[str, list[Message]] = {}
        self._lock = asyncio.Lock()

    async def add(self, session_id: str, message: Message) -> None:
        async with self._lock:
            self._conversations.setdefault(session_id, []).append(message)

    async def get(self, session_id: str) -> list[Message]:
        async with self._lock:
            return list(self._conversations.get(session_id, []))


conversation_store = InMemoryConversationStore()
