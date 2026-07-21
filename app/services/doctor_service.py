import asyncio
import os
from typing import Protocol
from uuid import UUID

import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Jsonb

from app.models.chats import MedicalSummary
from app.models.doctors import (
    DoctorSessionCompletion,
    DoctorPatient,
    DoctorSessionTranscript,
    DoctorSummary,
    TranscriptMessage,
)
from app.services.database import require_postgres_url


class DoctorStoreError(RuntimeError):
    pass


class DoctorResourceNotFound(DoctorStoreError):
    pass


class DoctorSessionNotCompletable(DoctorStoreError):
    pass


class DoctorReader(Protocol):
    async def list_patients(self, doctor_id: UUID) -> list[DoctorPatient]: ...

    async def list_summaries(
        self, doctor_id: UUID, patient_id: UUID | None = None
    ) -> list[DoctorSummary]: ...

    async def get_session(
        self, doctor_id: UUID, session_id: UUID
    ) -> DoctorSessionTranscript: ...

    async def complete_session(
        self, doctor_id: UUID, session_id: UUID
    ) -> DoctorSessionCompletion: ...


class PostgresDoctorReader:
    """Read-only queries scoped through an explicit patient-doctor assignment."""

    def __init__(self, database_url: str | None = None) -> None:
        load_dotenv()
        self._database_url = database_url or os.getenv("DATABASE_URL")

    def _connection(self) -> psycopg.Connection:
        try:
            database_url = require_postgres_url(self._database_url)
        except ValueError as exc:
            raise DoctorStoreError(str(exc)) from exc
        return psycopg.connect(
            database_url,
            connect_timeout=10,
            application_name="patient-intake-doctor-reader",
        )

    async def list_patients(self, doctor_id: UUID) -> list[DoctorPatient]:
        return await asyncio.to_thread(self._list_patients_sync, doctor_id)

    def _list_patients_sync(self, doctor_id: UUID) -> list[DoctorPatient]:
        try:
            with self._connection() as connection:
                connection.execute("set transaction read only")
                rows = connection.execute(
                    """
                    select assignment.patient_id, profile.name,
                           assignment.created_at
                    from public.patient_doctor as assignment
                    left join public.profiles as profile
                      on profile.id = assignment.patient_id
                    where assignment.doctor_id = %s
                    order by profile.name nulls last, assignment.patient_id
                    """,
                    (doctor_id,),
                ).fetchall()
            return [
                DoctorPatient(patient_id=row[0], name=row[1], assigned_at=row[2])
                for row in rows
            ]
        except psycopg.Error as exc:
            raise DoctorStoreError("Could not load assigned patients.") from exc

    async def list_summaries(
        self, doctor_id: UUID, patient_id: UUID | None = None
    ) -> list[DoctorSummary]:
        return await asyncio.to_thread(
            self._list_summaries_sync, doctor_id, patient_id
        )

    def _list_summaries_sync(
        self, doctor_id: UUID, patient_id: UUID | None
    ) -> list[DoctorSummary]:
        try:
            with self._connection() as connection:
                connection.execute("set transaction read only")
                if patient_id is not None:
                    assigned = connection.execute(
                        """
                        select 1
                        from public.patient_doctor
                        where doctor_id = %s and patient_id = %s
                        """,
                        (doctor_id, patient_id),
                    ).fetchone()
                    if assigned is None:
                        raise DoctorResourceNotFound(str(patient_id))

                rows = connection.execute(
                    """
                    select session.id, session.patient_id, profile.name,
                           session.status, summary_record.summary,
                           coalesce(summary_record.created_at, session.created_at),
                           coalesce(summary_record.updated_at, session.created_at)
                    from public.sessions as session
                    left join public.summaries as summary_record
                      on summary_record.session_id = session.id
                    join public.patient_doctor as assignment
                      on assignment.patient_id = session.patient_id
                     and assignment.doctor_id = %s
                    left join public.profiles as profile
                      on profile.id = session.patient_id
                    where (%s::uuid is null or session.patient_id = %s)
                      and session.status in ('submitted', 'completed', 'escalated')
                    order by coalesce(summary_record.updated_at, session.created_at) desc,
                             session.id
                    """,
                    (doctor_id, patient_id, patient_id),
                ).fetchall()
            return [
                DoctorSummary(
                    session_id=row[0],
                    patient_id=row[1],
                    patient_name=row[2],
                    status=row[3],
                    summary=(
                        MedicalSummary.model_validate(row[4])
                        if row[4] is not None
                        else None
                    ),
                    created_at=row[5],
                    updated_at=row[6],
                )
                for row in rows
            ]
        except DoctorResourceNotFound:
            raise
        except psycopg.Error as exc:
            raise DoctorStoreError("Could not load patient summaries.") from exc

    async def get_session(
        self, doctor_id: UUID, session_id: UUID
    ) -> DoctorSessionTranscript:
        return await asyncio.to_thread(self._get_session_sync, doctor_id, session_id)

    def _get_session_sync(
        self, doctor_id: UUID, session_id: UUID
    ) -> DoctorSessionTranscript:
        try:
            with self._connection() as connection:
                connection.execute("set transaction read only")
                session = connection.execute(
                    """
                    select session.id, session.patient_id, profile.name,
                           session.status, session.created_at,
                           summary_record.summary
                    from public.sessions as session
                    join public.patient_doctor as assignment
                      on assignment.patient_id = session.patient_id
                     and assignment.doctor_id = %s
                    left join public.profiles as profile
                      on profile.id = session.patient_id
                    left join public.summaries as summary_record
                      on summary_record.session_id = session.id
                    where session.id = %s
                    """,
                    (doctor_id, session_id),
                ).fetchone()
                if session is None:
                    raise DoctorResourceNotFound(str(session_id))

                messages = connection.execute(
                    """
                    select role, content, created_at
                    from public.messages
                    where session_id = %s
                    order by created_at, id
                    """,
                    (session_id,),
                ).fetchall()

            return DoctorSessionTranscript(
                session_id=session[0],
                patient_id=session[1],
                patient_name=session[2],
                status=session[3],
                created_at=session[4],
                messages=[
                    TranscriptMessage(role=row[0], content=row[1], created_at=row[2])
                    for row in messages
                ],
                summary=(
                    MedicalSummary.model_validate(session[5])
                    if session[5] is not None
                    else None
                ),
            )
        except DoctorResourceNotFound:
            raise
        except psycopg.Error as exc:
            raise DoctorStoreError("Could not load the session transcript.") from exc

    async def complete_session(
        self, doctor_id: UUID, session_id: UUID
    ) -> DoctorSessionCompletion:
        return await asyncio.to_thread(
            self._complete_session_sync, doctor_id, session_id
        )

    def _complete_session_sync(
        self, doctor_id: UUID, session_id: UUID
    ) -> DoctorSessionCompletion:
        try:
            with self._connection() as connection:
                with connection.cursor() as cursor:
                    updated = cursor.execute(
                        """
                        update public.sessions as session
                        set status = 'completed'
                        from public.patient_doctor as assignment
                        where session.id = %s
                          and assignment.patient_id = session.patient_id
                          and assignment.doctor_id = %s
                          and session.status in ('active', 'submitted')
                        returning session.id, session.status
                        """,
                        (session_id, doctor_id),
                    ).fetchone()
                    if updated is not None:
                        cursor.execute(
                            """
                            insert into public.audit_log
                                (session_id, event_type, content)
                            values (%s, 'session.completed_by_doctor', %s)
                            """,
                            (session_id, Jsonb({"status": "completed"})),
                        )
                        return DoctorSessionCompletion(
                            session_id=updated[0],
                            status=updated[1],
                        )

                    current = cursor.execute(
                        """
                        select session.status
                        from public.sessions as session
                        join public.patient_doctor as assignment
                          on assignment.patient_id = session.patient_id
                         and assignment.doctor_id = %s
                        where session.id = %s
                        """,
                        (doctor_id, session_id),
                    ).fetchone()
                    if current is None:
                        raise DoctorResourceNotFound(str(session_id))
                    if current[0] == "completed":
                        return DoctorSessionCompletion(
                            session_id=session_id,
                            status=current[0],
                        )
                    raise DoctorSessionNotCompletable(str(session_id))
        except (DoctorResourceNotFound, DoctorSessionNotCompletable):
            raise
        except psycopg.Error as exc:
            raise DoctorStoreError("Could not complete the session.") from exc
