import asyncio
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Jsonb


@dataclass(frozen=True)
class Message:
    role: str
    content: str


@dataclass(frozen=True)
class StoredMessage:
    role: str
    content: str
    created_at: datetime


@dataclass(frozen=True)
class ActiveSession:
    session_id: UUID
    messages: list[StoredMessage]


class ConversationStoreError(RuntimeError):
    pass


class ConversationStoreConfigurationError(ConversationStoreError):
    pass


class SessionNotFoundError(ConversationStoreError):
    pass


class SessionClosedError(ConversationStoreError):
    pass


class ConversationStore(Protocol):
    async def create_session(self, patient_id: UUID) -> UUID: ...

    async def get_or_create_active_session(
        self, patient_id: UUID
    ) -> tuple[UUID, bool]: ...

    async def get_active_session(
        self, patient_id: UUID
    ) -> ActiveSession | None: ...

    async def close_session(
        self, patient_id: UUID, session_id: UUID, status: str
    ) -> None: ...

    async def add(
        self, patient_id: UUID, session_id: UUID, message: Message
    ) -> None: ...

    async def get(self, patient_id: UUID, session_id: UUID) -> list[Message]: ...

    async def get_summary(
        self, patient_id: UUID, session_id: UUID
    ) -> dict[str, Any] | None: ...

    async def save_summary(
        self, patient_id: UUID, session_id: UUID, summary: dict[str, Any]
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

    async def create_session(self, patient_id: UUID) -> UUID:
        session_id, _ = await self.get_or_create_active_session(patient_id)
        return session_id

    async def get_or_create_active_session(
        self, patient_id: UUID
    ) -> tuple[UUID, bool]:
        return await asyncio.to_thread(
            self._get_or_create_active_session_sync, patient_id
        )

    def _get_or_create_active_session_sync(
        self, patient_id: UUID
    ) -> tuple[UUID, bool]:
        try:
            with self._connection() as connection:
                row = connection.execute(
                    """
                    select id from public.sessions
                    where patient_id = %s and status = 'active'
                    """,
                    (patient_id,),
                ).fetchone()
                if row is not None:
                    return row[0], True

                row = connection.execute(
                    """
                    insert into public.sessions (patient_id)
                    values (%s)
                    on conflict (patient_id) where status = 'active'
                    do nothing
                    returning id
                    """,
                    (patient_id,),
                ).fetchone()
                if row is not None:
                    return row[0], False

                row = connection.execute(
                    """
                    select id from public.sessions
                    where patient_id = %s and status = 'active'
                    """,
                    (patient_id,),
                ).fetchone()
                if row is None:
                    raise ConversationStoreError(
                        "Could not resolve the active conversation session."
                    )
                return row[0], True
        except psycopg.Error as exc:
            raise ConversationStoreError(
                "Could not create or resume a conversation session."
            ) from exc

    async def get_active_session(
        self, patient_id: UUID
    ) -> ActiveSession | None:
        return await asyncio.to_thread(self._get_active_session_sync, patient_id)

    def _get_active_session_sync(
        self, patient_id: UUID
    ) -> ActiveSession | None:
        try:
            with self._connection() as connection:
                with connection.cursor() as cursor:
                    row = cursor.execute(
                        """
                        select id from public.sessions
                        where patient_id = %s and status = 'active'
                        """,
                        (patient_id,),
                    ).fetchone()
                    if row is None:
                        return None
                    session_id = row[0]
                    cursor.execute(
                        """
                        select role, content, created_at
                        from public.messages
                        where session_id = %s
                        order by created_at, id
                        """,
                        (session_id,),
                    )
                    return ActiveSession(
                        session_id=session_id,
                        messages=[StoredMessage(*message) for message in cursor.fetchall()],
                    )
        except psycopg.Error as exc:
            raise ConversationStoreError(
                "Could not load the active conversation session."
            ) from exc

    async def add(
        self, patient_id: UUID, session_id: UUID, message: Message
    ) -> None:
        await asyncio.to_thread(self._add_sync, patient_id, session_id, message)

    def _add_sync(
        self, patient_id: UUID, session_id: UUID, message: Message
    ) -> None:
        database_role = "patient" if message.role == "user" else message.role
        try:
            with self._connection() as connection:
                with connection.cursor() as cursor:
                    inserted_message = cursor.execute(
                        """
                        insert into public.messages (session_id, role, content)
                        select id, %s, %s
                        from public.sessions
                        where id = %s and patient_id = %s and status = 'active'
                        returning id
                        """,
                        (
                            database_role,
                            message.content,
                            session_id,
                            patient_id,
                        ),
                    ).fetchone()
                    if inserted_message is None:
                        self._raise_missing_or_closed(cursor, patient_id, session_id)

                    cursor.execute(
                        """
                        delete from public.summaries as summary_record
                        using public.sessions as session
                        where summary_record.session_id = session.id
                          and session.id = %s
                          and session.patient_id = %s
                        """,
                        (session_id, patient_id),
                    )
                    cursor.execute(
                        """
                        insert into public.audit_log (session_id, event_type, content)
                        select id, %s, %s
                        from public.sessions
                        where id = %s and patient_id = %s
                        """,
                        (
                            f"message.{database_role}",
                            Jsonb(
                                {
                                    "role": database_role,
                                    "content": message.content,
                                }
                            ),
                            session_id,
                            patient_id,
                        ),
                    )
        except psycopg.Error as exc:
            raise ConversationStoreError(
                "Could not save the conversation message."
            ) from exc

    async def close_session(
        self, patient_id: UUID, session_id: UUID, status: str
    ) -> None:
        if status not in {"completed", "escalated", "abandoned"}:
            raise ValueError("A session can only transition to a terminal status.")
        await asyncio.to_thread(
            self._close_session_sync, patient_id, session_id, status
        )

    def _close_session_sync(
        self, patient_id: UUID, session_id: UUID, status: str
    ) -> None:
        try:
            with self._connection() as connection:
                with connection.cursor() as cursor:
                    updated = cursor.execute(
                        """
                        update public.sessions
                        set status = %s
                        where id = %s and patient_id = %s and status = 'active'
                        returning id
                        """,
                        (status, session_id, patient_id),
                    ).fetchone()
                    if updated is None:
                        self._raise_missing_or_closed(cursor, patient_id, session_id)
                    cursor.execute(
                        """
                        insert into public.audit_log (session_id, event_type, content)
                        values (%s, %s, %s)
                        """,
                        (
                            session_id,
                            f"session.{status}",
                            Jsonb({"status": status}),
                        ),
                    )
        except psycopg.Error as exc:
            raise ConversationStoreError(
                "Could not update the conversation session."
            ) from exc

    @staticmethod
    def _raise_missing_or_closed(
        cursor: psycopg.Cursor, patient_id: UUID, session_id: UUID
    ) -> None:
        row = cursor.execute(
            """
            select status from public.sessions
            where id = %s and patient_id = %s
            """,
            (session_id, patient_id),
        ).fetchone()
        if row is None:
            raise SessionNotFoundError(str(session_id))
        raise SessionClosedError(str(session_id))

    async def get(self, patient_id: UUID, session_id: UUID) -> list[Message]:
        return await asyncio.to_thread(self._get_sync, patient_id, session_id)

    def _get_sync(self, patient_id: UUID, session_id: UUID) -> list[Message]:
        try:
            with self._connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        select role, content
                        from public.messages as message
                        join public.sessions as session
                          on session.id = message.session_id
                        where message.session_id = %s
                          and session.patient_id = %s
                        order by message.created_at, message.id
                        """,
                        (session_id, patient_id),
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

    async def get_summary(
        self, patient_id: UUID, session_id: UUID
    ) -> dict[str, Any] | None:
        return await asyncio.to_thread(
            self._get_summary_sync, patient_id, session_id
        )

    def _get_summary_sync(
        self, patient_id: UUID, session_id: UUID
    ) -> dict[str, Any] | None:
        try:
            with self._connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        select summary
                        from public.summaries as summary_record
                        join public.sessions as session
                          on session.id = summary_record.session_id
                        where summary_record.session_id = %s
                          and session.patient_id = %s
                        """,
                        (session_id, patient_id),
                    )
                    row = cursor.fetchone()
                    return row[0] if row else None
        except psycopg.Error as exc:
            raise ConversationStoreError(
                "Could not load the conversation summary."
            ) from exc

    async def save_summary(
        self, patient_id: UUID, session_id: UUID, summary: dict[str, Any]
    ) -> None:
        await asyncio.to_thread(
            self._save_summary_sync, patient_id, session_id, summary
        )

    def _save_summary_sync(
        self, patient_id: UUID, session_id: UUID, summary: dict[str, Any]
    ) -> None:
        try:
            with self._connection() as connection:
                with connection.cursor() as cursor:
                    saved_summary = cursor.execute(
                        """
                        insert into public.summaries (session_id, summary)
                        select id, %s
                        from public.sessions
                        where id = %s and patient_id = %s
                        on conflict (session_id) do update
                        set summary = excluded.summary,
                            updated_at = now()
                        returning id
                        """,
                        (Jsonb(summary), session_id, patient_id),
                    ).fetchone()
                    if saved_summary is None:
                        raise SessionNotFoundError(str(session_id))

                    cursor.execute(
                        """
                        insert into public.audit_log (session_id, event_type, content)
                        select id, 'summary.generated', %s
                        from public.sessions
                        where id = %s and patient_id = %s
                        """,
                        (Jsonb(summary), session_id, patient_id),
                    )
        except psycopg.Error as exc:
            raise ConversationStoreError(
                "Could not save the conversation summary."
            ) from exc


conversation_store = PostgresConversationStore()
