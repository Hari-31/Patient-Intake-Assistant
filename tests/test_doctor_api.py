import unittest
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.dependencies.auth import get_current_user, require_doctor
from app.main import app
from app.models.auth import AuthenticatedUser, UserRole
from app.models.chats import MedicalSummary
from app.models.doctors import (
    DoctorPatient,
    DoctorSessionCompletion,
    DoctorSessionTranscript,
    DoctorSummary,
    TranscriptMessage,
)
from app.routers.doctors import get_doctor_reader
from app.services.doctor_service import DoctorResourceNotFound, DoctorSessionNotCompletable


def sample_summary() -> MedicalSummary:
    return MedicalSummary(
        chief_complaint="Headache",
        symptom_timeline="Started yesterday.",
        relevant_history="No relevant history reported.",
        red_flags=[],
        warning_signs_to_watch=["Sudden severe worsening"],
        possible_directions=["Discuss with a clinician"],
        suggested_questions_for_doctor=["Could this be a migraine?"],
    )


class FakeDoctorReader:
    def __init__(self) -> None:
        self.patient_id = uuid4()
        self.session_id = uuid4()
        self.now = datetime.now(timezone.utc)
        self.calls: list[tuple] = []
        self.status = "submitted"

    async def list_patients(self, doctor_id: UUID):
        self.calls.append(("patients", doctor_id))
        return [
            DoctorPatient(
                patient_id=self.patient_id,
                name="Test Patient",
                assigned_at=self.now,
            )
        ]

    async def list_summaries(
        self, doctor_id: UUID, patient_id: UUID | None = None
    ):
        self.calls.append(("summaries", doctor_id, patient_id))
        if patient_id is not None and patient_id != self.patient_id:
            raise DoctorResourceNotFound(str(patient_id))
        return [
            DoctorSummary(
                session_id=self.session_id,
                patient_id=self.patient_id,
                patient_name="Test Patient",
                status=self.status,
                summary=sample_summary(),
                created_at=self.now,
                updated_at=self.now,
            )
        ]

    async def get_session(self, doctor_id: UUID, session_id: UUID):
        self.calls.append(("session", doctor_id, session_id))
        if session_id != self.session_id:
            raise DoctorResourceNotFound(str(session_id))
        return DoctorSessionTranscript(
            session_id=self.session_id,
            patient_id=self.patient_id,
            patient_name="Test Patient",
            status=self.status,
            created_at=self.now,
            messages=[
                TranscriptMessage(
                    role="patient", content="My head hurts.", created_at=self.now
                ),
                TranscriptMessage(
                    role="assistant",
                    content="When did it start?",
                    created_at=self.now,
                ),
            ],
            summary=sample_summary(),
        )

    async def complete_session(self, doctor_id: UUID, session_id: UUID):
        self.calls.append(("complete", doctor_id, session_id))
        if session_id != self.session_id:
            raise DoctorResourceNotFound(str(session_id))
        if self.status not in {"active", "submitted", "completed"}:
            raise DoctorSessionNotCompletable(str(session_id))
        self.status = "completed"
        return DoctorSessionCompletion(
            session_id=self.session_id,
            status=self.status,
        )


class DoctorApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.doctor = AuthenticatedUser(id=uuid4(), role=UserRole.DOCTOR)
        self.reader = FakeDoctorReader()
        app.dependency_overrides[require_doctor] = lambda: self.doctor
        app.dependency_overrides[get_doctor_reader] = lambda: self.reader
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.pop(require_doctor, None)
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_doctor_reader, None)

    def test_doctor_lists_only_reader_scoped_patients(self) -> None:
        response = self.client.get("/doctor/patients")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["patient_id"], str(self.reader.patient_id))
        self.assertEqual(self.reader.calls[0], ("patients", self.doctor.id))

    def test_doctor_filters_summaries_by_assigned_patient(self) -> None:
        response = self.client.get(
            "/doctor/summaries", params={"patient_id": str(self.reader.patient_id)}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["summary"]["red_flags"], [])
        self.assertEqual(
            self.reader.calls[0],
            ("summaries", self.doctor.id, self.reader.patient_id),
        )

    def test_doctor_reads_ordered_full_transcript_and_summary(self) -> None:
        response = self.client.get(f"/doctor/sessions/{self.reader.session_id}")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "submitted")
        self.assertEqual(
            [message["role"] for message in body["messages"]],
            ["patient", "assistant"],
        )
        self.assertEqual(body["summary"]["chief_complaint"], "Headache")

    def test_doctor_marks_assigned_session_completed(self) -> None:
        response = self.client.post(
            f"/doctor/sessions/{self.reader.session_id}/complete"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "completed")
        self.assertEqual(
            self.reader.calls[-1],
            ("complete", self.doctor.id, self.reader.session_id),
        )

    def test_unassigned_patient_and_session_are_not_found(self) -> None:
        summaries = self.client.get(
            "/doctor/summaries", params={"patient_id": str(uuid4())}
        )
        transcript = self.client.get(f"/doctor/sessions/{uuid4()}")

        self.assertEqual(summaries.status_code, 404)
        self.assertEqual(transcript.status_code, 404)

    def test_patient_token_is_blocked_from_every_doctor_route(self) -> None:
        app.dependency_overrides.pop(require_doctor, None)
        patient = AuthenticatedUser(id=uuid4(), role=UserRole.PATIENT)
        app.dependency_overrides[get_current_user] = lambda: patient

        responses = [
            self.client.get("/doctor/patients"),
            self.client.get("/doctor/summaries"),
            self.client.get(f"/doctor/sessions/{uuid4()}"),
            self.client.post(f"/doctor/sessions/{uuid4()}/complete"),
        ]

        self.assertTrue(all(response.status_code == 403 for response in responses))
        self.assertEqual(self.reader.calls, [])

    def test_doctor_routes_expose_only_completion_write(self) -> None:
        self.assertEqual(self.client.post("/doctor/patients").status_code, 405)
        self.assertEqual(
            self.client.delete(f"/doctor/sessions/{self.reader.session_id}").status_code,
            405,
        )


if __name__ == "__main__":
    unittest.main()
