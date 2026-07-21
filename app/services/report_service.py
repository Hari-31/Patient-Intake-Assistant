import asyncio
import io
import os
import re
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Jsonb
from pypdf import PdfReader

from app.models.reports import ReportUploadResponse
from app.services.conversation_store import SessionClosedError, SessionNotFoundError
from app.services.rag_service import EmbeddedChunk, RAGService, get_rag_service


REPORT_BUCKET = "medical-reports"
MAX_REPORT_BYTES = 10 * 1024 * 1024
MAX_EXTRACTED_TEXT_CHARS = 500_000


class ReportValidationError(ValueError):
    pass


class ReportServiceError(RuntimeError):
    pass


class ReportService:
    def __init__(
        self,
        rag: RAGService | None = None,
        *,
        database_url: str | None = None,
        supabase_url: str | None = None,
        service_role_key: str | None = None,
    ) -> None:
        load_dotenv()
        self._rag = rag or get_rag_service()
        self._database_url = database_url or os.getenv("DATABASE_URL")
        self._supabase_url = supabase_url or os.getenv("SUPABASE_URL")
        self._service_role_key = service_role_key or os.getenv(
            "SUPABASE_SERVICE_ROLE_KEY"
        )

    async def upload_pdf(
        self,
        *,
        patient_id: UUID,
        session_id: UUID,
        filename: str,
        content_type: str | None,
        content: bytes,
    ) -> ReportUploadResponse:
        self._validate_pdf(filename, content_type, content)
        await asyncio.to_thread(self._ensure_owned_session_sync, patient_id, session_id)

        extracted_text = await asyncio.to_thread(self._extract_pdf_text, content)
        embedded_chunks = await self._rag.embed_document(extracted_text)
        if not embedded_chunks:
            raise ReportValidationError(
                "The PDF does not contain extractable text. Scanned PDFs require OCR."
            )

        report_id = uuid4()
        safe_filename = _safe_filename(filename)
        storage_path = f"{patient_id}/{session_id}/{report_id}/{safe_filename}"
        await self._upload_storage(storage_path, content)
        try:
            await asyncio.to_thread(
                self._persist_report_sync,
                report_id,
                patient_id,
                session_id,
                filename,
                storage_path,
                embedded_chunks,
            )
        except Exception:
            await self._delete_storage(storage_path)
            raise

        return ReportUploadResponse(
            report_id=report_id,
            session_id=session_id,
            filename=filename,
            chunk_count=len(embedded_chunks),
        )

    def _connection(self) -> psycopg.Connection:
        if not self._database_url:
            raise ReportServiceError("DATABASE_URL must be configured.")
        return psycopg.connect(
            self._database_url,
            connect_timeout=10,
            application_name="patient-intake-reports",
        )

    def _ensure_owned_session_sync(
        self, patient_id: UUID, session_id: UUID
    ) -> None:
        try:
            with self._connection() as connection:
                row = connection.execute(
                    """
                    select status from public.sessions
                    where id = %s and patient_id = %s
                    """,
                    (session_id, patient_id),
                ).fetchone()
                if row is None:
                    raise SessionNotFoundError(str(session_id))
                if row[0] != "active":
                    raise SessionClosedError(str(session_id))
        except psycopg.Error as exc:
            raise ReportServiceError("Could not verify report ownership.") from exc

    def _persist_report_sync(
        self,
        report_id: UUID,
        patient_id: UUID,
        session_id: UUID,
        filename: str,
        storage_path: str,
        chunks: list[EmbeddedChunk],
    ) -> None:
        try:
            with self._connection() as connection:
                with connection.cursor() as cursor:
                    report = cursor.execute(
                        """
                        insert into public.reports
                            (id, patient_id, session_id, filename, storage_path)
                        select %s, patient_id, id, %s, %s
                        from public.sessions
                        where id = %s and patient_id = %s and status = 'active'
                        returning id
                        """,
                        (
                            report_id,
                            filename,
                            storage_path,
                            session_id,
                            patient_id,
                        ),
                    ).fetchone()
                    if report is None:
                        status_row = cursor.execute(
                            """
                            select status from public.sessions
                            where id = %s and patient_id = %s
                            """,
                            (session_id, patient_id),
                        ).fetchone()
                        if status_row is None:
                            raise SessionNotFoundError(str(session_id))
                        raise SessionClosedError(str(session_id))

                    cursor.executemany(
                        """
                        insert into public.report_chunks
                            (report_id, patient_id, chunk_index, chunk_text, embedding)
                        values (%s, %s, %s, %s, %s::extensions.vector)
                        """,
                        [
                            (
                                report_id,
                                patient_id,
                                chunk.index,
                                chunk.text,
                                _embedding_literal(chunk.embedding),
                            )
                            for chunk in chunks
                        ],
                    )
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
                        select id, 'report.uploaded', %s
                        from public.sessions
                        where id = %s and patient_id = %s
                        """,
                        (
                            Jsonb(
                                {
                                    "report_id": str(report_id),
                                    "filename": filename,
                                    "chunk_count": len(chunks),
                                }
                            ),
                            session_id,
                            patient_id,
                        ),
                    )
        except psycopg.Error as exc:
            raise ReportServiceError("Could not persist the medical report.") from exc

    async def _upload_storage(self, path: str, content: bytes) -> None:
        if not self._supabase_url or not self._service_role_key:
            raise ReportServiceError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be configured."
            )
        headers = {
            "apikey": self._service_role_key,
            "Authorization": f"Bearer {self._service_role_key}",
            "Content-Type": "application/pdf",
            "x-upsert": "false",
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self._supabase_url.rstrip('/')}/storage/v1/object/"
                    f"{REPORT_BUCKET}/{path}",
                    headers=headers,
                    content=content,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ReportServiceError("Could not upload the report to Storage.") from exc

    async def _delete_storage(self, path: str) -> None:
        if not self._supabase_url or not self._service_role_key:
            return
        headers = {
            "apikey": self._service_role_key,
            "Authorization": f"Bearer {self._service_role_key}",
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                await client.request(
                    "DELETE",
                    f"{self._supabase_url.rstrip('/')}/storage/v1/object/"
                    f"{REPORT_BUCKET}",
                    headers=headers,
                    json={"prefixes": [path]},
                )
        except httpx.HTTPError:
            pass

    @staticmethod
    def _validate_pdf(
        filename: str, content_type: str | None, content: bytes
    ) -> None:
        if not filename.lower().endswith(".pdf"):
            raise ReportValidationError("Only PDF reports are supported.")
        if content_type not in {"application/pdf", "application/octet-stream"}:
            raise ReportValidationError("The uploaded file must be a PDF.")
        if not content or not content.startswith(b"%PDF-"):
            raise ReportValidationError("The uploaded file is not a valid PDF.")
        if len(content) > MAX_REPORT_BYTES:
            raise ReportValidationError("PDF reports must be 10 MB or smaller.")

    @staticmethod
    def _extract_pdf_text(content: bytes) -> str:
        try:
            reader = PdfReader(io.BytesIO(content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            raise ReportValidationError("The PDF could not be read.") from exc
        text = text.strip()
        if not text:
            raise ReportValidationError(
                "The PDF does not contain extractable text. Scanned PDFs require OCR."
            )
        if len(text) > MAX_EXTRACTED_TEXT_CHARS:
            raise ReportValidationError("The extracted report text is too large.")
        return text


def _safe_filename(filename: str) -> str:
    name = Path(filename).name
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return safe or "report.pdf"


def _embedding_literal(embedding: list[float]) -> str:
    return "[" + ",".join(format(value, ".9g") for value in embedding) + "]"
