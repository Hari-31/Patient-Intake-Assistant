import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import jwt
from fastapi import HTTPException

from app.dependencies.auth import require_doctor, require_patient
from app.models.auth import AuthenticatedUser, UserRole
from app.services.auth import AuthenticationError, SupabaseAuthService


class FakeAdminClient:
    last_instance = None

    def __init__(self, **kwargs):
        self.options = kwargs
        self.request = None
        FakeAdminClient.last_instance = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def post(self, url, **kwargs):
        self.request = {"url": url, **kwargs}
        return SimpleNamespace(
            status_code=200,
            json=lambda: {
                "id": "17314f7e-7f23-4fe8-83f0-b731ad7f0001",
                "email": "patient@example.com",
            },
        )


class SupabaseAuthServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.secret = "test-secret-that-is-at-least-32-bytes"
        self.supabase_url = "https://example.supabase.co"
        self.user_id = uuid4()
        self.service = SupabaseAuthService(
            jwt_secret=self.secret,
            supabase_url=self.supabase_url,
            service_role_key="backend-only-service-key",
        )

    def make_token(
        self,
        *,
        app_metadata=None,
        user_metadata=None,
        expires_in: timedelta = timedelta(minutes=5),
        signing_secret: str | None = None,
    ) -> str:
        return jwt.encode(
            {
                "sub": str(self.user_id),
                "role": "authenticated",
                "aud": "authenticated",
                "iss": f"{self.supabase_url}/auth/v1",
                "exp": datetime.now(timezone.utc) + expires_in,
                "app_metadata": app_metadata or {},
                "user_metadata": user_metadata or {},
            },
            signing_secret or self.secret,
            algorithm="HS256",
        )

    async def test_role_comes_from_app_metadata_not_user_metadata(self) -> None:
        token = self.make_token(
            app_metadata={"role": "patient"},
            user_metadata={"role": "doctor"},
        )
        user = await self.service.authenticate(token)
        self.assertEqual(user.id, self.user_id)
        self.assertIs(user.role, UserRole.PATIENT)

    async def test_user_metadata_role_alone_is_rejected(self) -> None:
        token = self.make_token(user_metadata={"role": "patient"})
        with self.assertRaises(AuthenticationError):
            await self.service.authenticate(token)

    async def test_expired_or_wrongly_signed_tokens_are_rejected(self) -> None:
        with self.assertRaises(AuthenticationError):
            await self.service.authenticate(
                self.make_token(
                    app_metadata={"role": "patient"},
                    expires_in=timedelta(seconds=-1),
                )
            )
        with self.assertRaises(AuthenticationError):
            await self.service.authenticate(
                self.make_token(
                    app_metadata={"role": "patient"},
                    signing_secret="a-different-secret-that-is-32-bytes",
                )
            )

    async def test_doctor_cannot_use_patient_dependency(self) -> None:
        doctor = AuthenticatedUser(id=uuid4(), role=UserRole.DOCTOR)
        with self.assertRaises(HTTPException) as context:
            await require_patient(doctor)
        self.assertEqual(context.exception.status_code, 403)

    async def test_patient_cannot_use_doctor_dependency(self) -> None:
        patient = AuthenticatedUser(id=uuid4(), role=UserRole.PATIENT)
        with self.assertRaises(HTTPException) as context:
            await require_doctor(patient)
        self.assertEqual(context.exception.status_code, 403)

    async def test_patient_signup_sets_role_only_in_app_metadata(self) -> None:
        with patch("app.services.auth.httpx.AsyncClient", FakeAdminClient):
            created = await self.service.create_patient(
                email="patient@example.com",
                password="secure-password",
                name="Test Patient",
            )

        request = FakeAdminClient.last_instance.request
        self.assertEqual(
            request["json"]["app_metadata"], {"role": "patient"}
        )
        self.assertNotIn("role", request["json"]["user_metadata"])
        self.assertEqual(
            request["headers"]["Authorization"],
            "Bearer backend-only-service-key",
        )
        self.assertEqual(created.role, UserRole.PATIENT)


if __name__ == "__main__":
    unittest.main()
