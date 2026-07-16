import asyncio
import os
from collections.abc import Mapping
from typing import Any
from uuid import UUID

import httpx
import jwt
from dotenv import load_dotenv

from app.models.auth import AuthenticatedUser, PatientSignupResponse, UserRole


class AuthenticationError(RuntimeError):
    pass


class AuthConfigurationError(RuntimeError):
    pass


class AuthServiceError(RuntimeError):
    pass


class SignupError(RuntimeError):
    pass


class SupabaseAuthService:
    """Supabase JWT verification and backend-only patient provisioning."""

    def __init__(
        self,
        *,
        jwt_secret: str | None = None,
        supabase_url: str | None = None,
        service_role_key: str | None = None,
    ) -> None:
        load_dotenv()
        self._jwt_secret = jwt_secret or os.getenv("SUPABASE_JWT_SECRET")
        self._supabase_url = supabase_url or os.getenv("SUPABASE_URL")
        self._service_role_key = service_role_key or os.getenv(
            "SUPABASE_SERVICE_ROLE_KEY"
        )
        self._jwks_client = (
            jwt.PyJWKClient(
                f"{self._supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
            )
            if self._supabase_url
            else None
        )

    async def authenticate(self, token: str) -> AuthenticatedUser:
        claims = await asyncio.to_thread(self._verify_token, token)
        try:
            user_id = UUID(str(claims["sub"]))
            app_metadata = claims["app_metadata"]
            if not isinstance(app_metadata, Mapping):
                raise TypeError("app_metadata must be an object")
            role = UserRole(app_metadata["role"])
        except (KeyError, TypeError, ValueError) as exc:
            raise AuthenticationError(
                "The access token does not contain a valid application role."
            ) from exc

        if claims.get("role") != "authenticated":
            raise AuthenticationError("Invalid access token role.")
        return AuthenticatedUser(id=user_id, role=role)

    def _verify_token(self, token: str) -> Mapping[str, Any]:
        if not self._supabase_url:
            raise AuthConfigurationError(
                "SUPABASE_URL must be configured."
            )

        try:
            algorithm = jwt.get_unverified_header(token).get("alg")
            if algorithm == "HS256":
                if not self._jwt_secret:
                    raise AuthConfigurationError(
                        "SUPABASE_JWT_SECRET must be configured for HS256 tokens."
                    )
                verification_key = self._jwt_secret
            elif algorithm in {"ES256", "RS256"}:
                if self._jwks_client is None:
                    raise AuthConfigurationError(
                        "Supabase JWKS verification is not configured."
                    )
                verification_key = self._jwks_client.get_signing_key_from_jwt(
                    token
                ).key
            else:
                raise AuthenticationError("Unsupported access token algorithm.")

            return jwt.decode(
                token,
                verification_key,
                algorithms=[algorithm],
                audience="authenticated",
                issuer=f"{self._supabase_url.rstrip('/')}/auth/v1",
                options={"require": ["exp", "sub", "aud", "iss"]},
            )
        except jwt.InvalidTokenError as exc:
            raise AuthenticationError("Invalid or expired access token.") from exc

    async def create_patient(
        self, *, email: str, password: str, name: str
    ) -> PatientSignupResponse:
        if not self._supabase_url or not self._service_role_key:
            raise AuthConfigurationError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be configured."
            )

        headers = {
            "apikey": self._service_role_key,
            "Authorization": f"Bearer {self._service_role_key}",
        }
        payload = {
            "email": email.strip(),
            "password": password,
            "email_confirm": True,
            "app_metadata": {"role": UserRole.PATIENT.value},
            "user_metadata": {"name": name.strip()},
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    f"{self._supabase_url.rstrip('/')}/auth/v1/admin/users",
                    headers=headers,
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise AuthServiceError(
                "Could not reach the Supabase Auth service."
            ) from exc

        if response.status_code >= 400:
            raise SignupError("Supabase could not create the patient account.")

        data = response.json()
        user_data = data.get("user", data)
        try:
            return PatientSignupResponse(
                user_id=UUID(str(user_data["id"])),
                email=str(user_data["email"]),
                role=UserRole.PATIENT,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AuthServiceError(
                "Supabase returned an invalid user response."
            ) from exc
