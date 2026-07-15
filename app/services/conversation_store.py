import asyncio
import os
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Jsonb


@dataclass(frozen=True)
class Message:
    role: str
    content: str


class ConversationStoreError(RuntimeError):
    pass


class ConversationStoreConfigurationError(ConversationStoreError):
    pass


class SessionNotFoundError(ConversationStoreError):
    pass


class ConversationStore(Protocol):
    async def create_session(self) -> UUID: ...

    async def add(self, session_id: UUID, message: Message) -> None: ...

    async def get(self, session_id: UUID) -> list[Message]: ...

    async def get_summary(self, session_id: UUID) -> dict[str, Any] | None: ...

    async def save_summary(
        self, session_id: UUID, summary: dict[str, Any]
    ) -> None: ...


class PostgresConversationStore:
    """Supabase Postgres-backed conversation and summary persistence."""

    def __init__(self, database_url: str | None = None) -> None:
        load_dotenv()
        self._database_url = database_url or os.getenv("DATABASE_URL")

    def _connection(self) -> psycopg.Connection:
        if not self._database_url:
            raise ConversationStoreConfigurationError(
                "DATABASE_URL must be set in the environment."
            )
        return psycopg.connect(
            self._database_url,
            connect_timeout=10,
            application_name="patient-intake-assistant",
        )

    async def create_session(self) -> UUID:
        return await asyncio.to_thread(self._create_session_sync)

    def _create_session_sync(self) -> UUID:
        try:
            with self._connection() as connection:
                row = connection.execute(
                    "insert into public.sessions default values returning id"
                ).fetchone()
                return row[0]
        except psycopg.Error as exc:
            raise ConversationStoreError("Could not create a conversation session.") from exc

    async def add(self, session_id: UUID, message: Message) -> None:
        await asyncio.to_thread(self._add_sync, session_id, message)

    def _add_sync(self, session_id: UUID, message: Message) -> None:
        database_role = "patient" if message.role == "user" else message.role
        try:
            with self._connection() as connection:
                with connection.cursor() as cursor:
                    session_exists = cursor.execute(
                        "select 1 from public.sessions where id = %s",
                        (session_id,),
                    ).fetchone()
                    if session_exists is None:
                        raise SessionNotFoundError(str(session_id))

                    cursor.execute(
                        """
                        insert into public.messages (session_id, role, content)
                        values (%s, %s, %s)
                        """,
                        (session_id, database_role, message.content),
                    )
                    cursor.execute(
                        "delete from public.summaries where session_id = %s",
                        (session_id,),
                    )
                    cursor.execute(
                        """
                        insert into public.audit_log (session_id, event_type, content)
                        values (%s, %s, %s)
                        """,
                        (
                            session_id,
                            f"message.{database_role}",
                            Jsonb(
                                {
                                    "role": database_role,
                                    "content": message.content,
                                }
                            ),
                        ),
                    )
        except psycopg.Error as exc:
            raise ConversationStoreError(
                "Could not save the conversation message."
            ) from exc

    async def get(self, session_id: UUID) -> list[Message]:
        return await asyncio.to_thread(self._get_sync, session_id)

    def _get_sync(self, session_id: UUID) -> list[Message]:
        try:
            with self._connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        select role, content
                        from public.messages
                        where session_id = %s
                        order by created_at, id
                        """,
                        (session_id,),
                    )
                    return [
                        Message(
                            role="user" if role == "patient" else role,
                            content=content,
                        )
                        for role, content in cursor.fetchall()
                    ]
        except psycopg.Error as exc:
            raise ConversationStoreError(
                "Could not load the conversation history."
            ) from exc

    async def get_summary(self, session_id: UUID) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._get_summary_sync, session_id)

    def _get_summary_sync(self, session_id: UUID) -> dict[str, Any] | None:
        try:
            with self._connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        select summary
                        from public.summaries
                        where session_id = %s
                        """,
                        (session_id,),
                    )
                    row = cursor.fetchone()
                    return row[0] if row else None
        except psycopg.Error as exc:
            raise ConversationStoreError(
                "Could not load the conversation summary."
            ) from exc

    async def save_summary(
        self, session_id: UUID, summary: dict[str, Any]
    ) -> None:
        await asyncio.to_thread(self._save_summary_sync, session_id, summary)

    def _save_summary_sync(
        self, session_id: UUID, summary: dict[str, Any]
    ) -> None:
        try:
            with self._connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        insert into public.summaries (session_id, summary)
                        values (%s, %s)
                        on conflict (session_id) do update
                        set summary = excluded.summary,
                            updated_at = now()
                        """,
                        (session_id, Jsonb(summary)),
                    )
                    cursor.execute(
                        """
                        insert into public.audit_log (session_id, event_type, content)
                        values (%s, 'summary.generated', %s)
                        """,
                        (session_id, Jsonb(summary)),
                    )
        except psycopg.Error as exc:
            raise ConversationStoreError(
                "Could not save the conversation summary."
            ) from exc


conversation_store = PostgresConversationStore()
