from uuid import UUID

from pydantic import BaseModel


class ReportUploadResponse(BaseModel):
    report_id: UUID
    session_id: UUID
    filename: str
    chunk_count: int
    markdown_char_count: int
