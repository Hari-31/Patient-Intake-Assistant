import unittest
from pathlib import Path


class SessionLifecycleMigrationTests(unittest.TestCase):
    def test_database_enforces_one_active_session_per_patient(self) -> None:
        migration_dir = Path(__file__).parents[1] / "supabase" / "migrations"
        migration = "\n".join(
            (
                migration_dir / filename
            ).read_text(encoding="utf-8")
            for filename in (
                "202607210001_session_lifecycle.sql",
                "202607210002_submitted_request_lifecycle.sql",
                "202607210003_completed_intakes_are_terminal.sql",
            )
        )
        normalized = " ".join(migration.lower().split())

        self.assertIn("sessions_one_active_per_patient_idx", normalized)
        self.assertIn("sessions_one_open_per_patient_idx", normalized)
        self.assertIn("unique index", normalized)
        self.assertIn("on public.sessions (patient_id)", normalized)
        self.assertIn("where status = 'active'", normalized)
        self.assertIn(
            "drop index if exists public.sessions_one_open_per_patient_idx",
            normalized,
        )
        self.assertIn(
            "thank you. your intake request has been sent for doctor review%",
            normalized,
        )
        self.assertIn(
            "drop constraint if exists sessions_patient_id_required",
            normalized,
        )
        self.assertIn(
            "add constraint sessions_patient_id_required check (patient_id is not null) not valid",
            normalized,
        )
        self.assertIn("'submitted'", normalized)
        self.assertIn("'completed'", normalized)
        self.assertIn("'escalated'", normalized)
        self.assertIn("'abandoned'", normalized)


if __name__ == "__main__":
    unittest.main()
