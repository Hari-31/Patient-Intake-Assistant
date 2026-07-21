import unittest
from pathlib import Path


class SessionLifecycleMigrationTests(unittest.TestCase):
    def test_database_enforces_one_active_session_per_patient(self) -> None:
        migration = (
            Path(__file__).parents[1]
            / "supabase"
            / "migrations"
            / "202607210001_session_lifecycle.sql"
        ).read_text(encoding="utf-8")
        normalized = " ".join(migration.lower().split())

        self.assertIn("sessions_one_active_per_patient_idx", normalized)
        self.assertIn("unique index", normalized)
        self.assertIn("on public.sessions (patient_id)", normalized)
        self.assertIn("where status = 'active'", normalized)
        self.assertIn(
            "drop constraint if exists sessions_patient_id_required",
            normalized,
        )
        self.assertIn(
            "add constraint sessions_patient_id_required check (patient_id is not null) not valid",
            normalized,
        )
        self.assertIn("'completed'", normalized)
        self.assertIn("'escalated'", normalized)
        self.assertIn("'abandoned'", normalized)


if __name__ == "__main__":
    unittest.main()
