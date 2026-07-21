import unittest

from fastapi.testclient import TestClient

from app.main import app


class CorsTests(unittest.TestCase):
    def test_local_frontend_can_preflight_signup(self) -> None:
        response = TestClient(app).options(
            "/auth/signup",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://127.0.0.1:5173",
        )

    def test_unknown_origin_is_not_allowed(self) -> None:
        response = TestClient(app).options(
            "/auth/signup",
            headers={
                "Origin": "https://untrusted.example",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        self.assertNotIn("access-control-allow-origin", response.headers)


if __name__ == "__main__":
    unittest.main()
