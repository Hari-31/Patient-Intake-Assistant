import unittest

from app.services.database import require_postgres_url


class DatabaseConfigurationTests(unittest.TestCase):
    def test_accepts_postgres_urls(self) -> None:
        self.assertEqual(
            require_postgres_url("postgresql://user:pass@example.com:5432/db"),
            "postgresql://user:pass@example.com:5432/db",
        )
        self.assertEqual(
            require_postgres_url("postgres://user:pass@example.com:5432/db"),
            "postgres://user:pass@example.com:5432/db",
        )

    def test_rejects_missing_or_https_urls(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be set"):
            require_postgres_url(None)

        with self.assertRaisesRegex(ValueError, "Postgres connection string"):
            require_postgres_url("https://example.supabase.co")


if __name__ == "__main__":
    unittest.main()
