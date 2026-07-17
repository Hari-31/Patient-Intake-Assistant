import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.dependencies.auth import require_patient
from app.main import app
from app.models.auth import AuthenticatedUser, UserRole
from app.models.reports import ReportUploadResponse
from app.routers.reports import get_report_service
from app.services.conversation_store import SessionNotFoundError


class FakeReportService:
    def __init__(self) -> None:
        self.calls = []
        self.reject_session = False

    async def upload_pdf(self, **kwargs):
        self.calls.append(kwargs)
        if self.reject_session:
            raise SessionNotFoundError(str(kwargs["session_id"]))
        return ReportUploadResponse(
            report_id=uuid4(),
            session_id=kwargs["session_id"],
            filename=kwargs["filename"],
            chunk_count=3,
        )


class ReportApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.patient = AuthenticatedUser(id=uuid4(), role=UserRole.PATIENT)
        self.service = FakeReportService()
        app.dependency_overrides[require_patient] = lambda: self.patient
        app.dependency_overrides[get_report_service] = lambda: self.service
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.pop(require_patient, None)
        app.dependency_overrides.pop(get_report_service, None)

    def test_patient_uploads_pdf_to_owned_session(self) -> None:
        session_id = uuid4()
        response = self.client.post(
            "/upload",
            data={"session_id": str(session_id)},
            files={"file": ("labs.pdf", b"%PDF-test", "application/pdf")},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["chunk_count"], 3)
        call = self.service.calls[0]
        self.assertEqual(call["patient_id"], self.patient.id)
        self.assertEqual(call["session_id"], session_id)

    def test_unauthenticated_upload_is_rejected_before_service(self) -> None:
        app.dependency_overrides.pop(require_patient, None)
        response = self.client.post(
            "/upload",
            data={"session_id": str(uuid4())},
            files={"file": ("labs.pdf", b"%PDF-test", "application/pdf")},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.service.calls, [])

    def test_other_patients_session_is_not_found(self) -> None:
        self.service.reject_session = True
        response = self.client.post(
            "/upload",
            data={"session_id": str(uuid4())},
            files={"file": ("labs.pdf", b"%PDF-test", "application/pdf")},
        )
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
