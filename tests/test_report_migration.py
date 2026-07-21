import unittest
from pathlib import Path


class ReportMigrationTests(unittest.TestCase):
    def test_existing_session_owner_key_is_not_dropped(self) -> None:
        migration = (
            Path(__file__).parents[1]
            / "supabase"
            / "migrations"
            / "202607170001_patient_reports_rag.sql"
        ).read_text(encoding="utf-8")
        normalized = " ".join(migration.lower().split())

        self.assertNotIn(
            "drop constraint if exists sessions_id_patient_id_key",
            normalized,
        )
        self.assertIn("from pg_constraint", normalized)
        self.assertIn("conname = 'sessions_id_patient_id_key'", normalized)


if __name__ == "__main__":
    unittest.main()
