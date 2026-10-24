import asyncio
import base64
import json
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from bson import ObjectId
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi import HTTPException
from pydantic import ValidationError

from models.farmer import GoogleLogin
from routes import auth


class FakeUsers:
    def __init__(self, documents=()):
        self.documents = [dict(document) for document in documents]

    async def find_one(self, query):
        for document in self.documents:
            for key, expected in query.items():
                value = document.get(key)
                if isinstance(expected, dict) and "$in" in expected:
                    if value not in expected["$in"]:
                        break
                elif value != expected:
                    break
            else:
                return dict(document)
        return None

    async def insert_one(self, document):
        saved = dict(document, _id=ObjectId())
        self.documents.append(saved)
        return SimpleNamespace(inserted_id=saved["_id"])

    async def update_one(self, query, update):
        found = await self.find_one(query)
        if found is None:
            return SimpleNamespace(modified_count=0)
        for document in self.documents:
            if document["_id"] == found["_id"]:
                document.update(update.get("$set", {}))
                return SimpleNamespace(modified_count=1)
        return SimpleNamespace(modified_count=0)


class FakeGoogleCertRequest:
    def __init__(self, certificate):
        self.certificate = certificate

    def __call__(self, *_args, **_kwargs):
        return SimpleNamespace(
            status=200,
            data=json.dumps({"google-test-key": self.certificate}).encode(),
        )


class FakeGoogleTokenResponse:
    def __init__(self, id_token=None, *, payload=None, status_code=200):
        self.payload = payload if payload is not None else {"id_token": id_token}
        self.status_code = status_code
        self.request = httpx.Request("POST", "https://oauth2.googleapis.com/token")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "mock Google token endpoint failure",
                request=self.request,
                response=httpx.Response(
                    self.status_code,
                    request=self.request,
                    json=self.payload,
                ),
            )

    def json(self):
        return self.payload


class FakeGoogleOAuthClient:
    def __init__(self, id_token=None, *, response=None, post_error=None):
        self.response = response or FakeGoogleTokenResponse(id_token)
        self.post_error = post_error
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.post_error:
            raise self.post_error
        return self.response


class GoogleAuthTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.claims = {
            "sub": "google-sub-123",
            "email": "user@example.com",
            "email_verified": True,
            "name": "Google User",
        }
        self.signing_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        self.public_key = self.signing_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

    @staticmethod
    def _encode_segment(value):
        encoded = json.dumps(value, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(encoded).rstrip(b"=").decode()

    def _signed_token(self, **claim_overrides):
        header = self._encode_segment(
            {"alg": "RS256", "kid": "google-test-key", "typ": "JWT"}
        )
        claims = {
            **self.claims,
            "iss": "https://accounts.google.com",
            "aud": "test-client-id",
            "iat": int(time.time()),
            "exp": int(time.time()) + 600,
            **claim_overrides,
        }
        payload = self._encode_segment(claims)
        signing_input = f"{header}.{payload}".encode()
        signature = self.signing_key.sign(
            signing_input,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
        return f"{header}.{payload}.{encoded_signature}"

    @staticmethod
    def _request(origin="http://localhost:5173"):
        from starlette.requests import Request

        return Request({
            "type": "http",
            "method": "POST",
            "scheme": "http",
            "path": "/api/auth/google",
            "headers": [
                (b"origin", origin.encode()),
                (b"x-requested-with", b"XmlHttpRequest"),
            ],
        })

    async def _google_login(self, id_token, users=None):
        with (
            patch.object(auth, "database_is_connected", return_value=True),
            patch.object(auth, "auth_indexes_ready", return_value=True),
            patch.object(auth.settings, "GOOGLE_CLIENT_ID", "test-client-id"),
            patch.object(auth.settings, "GOOGLE_CLIENT_SECRET", "test-client-secret"),
            patch.object(
                auth.settings,
                "GOOGLE_REDIRECT_URI",
                "http://localhost:5173",
            ),
            patch.object(
                auth.httpx,
                "AsyncClient",
                return_value=FakeGoogleOAuthClient(id_token),
            ),
            patch.object(
                auth,
                "GoogleAuthRequest",
                return_value=FakeGoogleCertRequest(self.public_key),
            ),
            patch.object(
                auth,
                "get_user_collection",
                return_value=users if users is not None else FakeUsers(),
            ),
            patch.object(
                auth, "_profile_is_complete", new=AsyncMock(return_value=False)
            ),
            patch.object(auth, "_profile_role", new=AsyncMock(return_value="farmer")),
            patch.object(auth, "create_access_token", return_value="app-session-token"),
        ):
            return await auth.google_login(
                GoogleLogin(
                    code="fake-authorization-code-for-test",
                    redirect_uri="http://localhost:5173",
                ),
                self._request(),
                None,
            )

    async def _google_login_with_exchange(
        self,
        oauth_client,
        *,
        users=None,
        verification_error=None,
        verification_result=None,
        request=None,
        client_id="test-client-id",
        client_secret="test-client-secret",
    ):
        with (
            patch.object(auth, "database_is_connected", return_value=True),
            patch.object(auth, "auth_indexes_ready", return_value=True),
            patch.object(auth.settings, "GOOGLE_CLIENT_ID", client_id),
            patch.object(auth.settings, "GOOGLE_CLIENT_SECRET", client_secret),
            patch.object(
                auth.settings,
                "GOOGLE_REDIRECT_URI",
                "http://localhost:5173",
            ),
            patch.object(auth.httpx, "AsyncClient", return_value=oauth_client),
            patch.object(
                auth.google_id_token,
                "verify_oauth2_token",
                side_effect=verification_error,
                return_value=verification_result,
            ) as verifier,
            patch.object(
                auth,
                "get_user_collection",
                return_value=users if users is not None else FakeUsers(),
            ),
            patch.object(
                auth, "_profile_is_complete", new=AsyncMock(return_value=False)
            ),
            patch.object(auth, "_profile_role", new=AsyncMock(return_value="farmer")),
            patch.object(auth, "create_access_token", return_value="app-session-token"),
        ):
            response = await auth.google_login(
                GoogleLogin(
                    code="authorization-code-for-mocked-test",
                    redirect_uri="http://localhost:5173",
                ),
                request or self._request(),
                None,
            )
            return response, verifier

    async def test_invalid_id_token_is_rejected(self):
        with self.assertRaises(HTTPException) as raised:
            await self._google_login("invalid-google-id-token-abcdef")

        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(
            raised.exception.detail,
            {
                "code": "GOOGLE_ID_TOKEN_MALFORMED",
                "message": "Google returned an invalid identity token. Please start sign-in again.",
            },
        )

    async def test_missing_authorization_code_is_rejected_by_request_schema(self):
        with self.assertRaises(ValidationError):
            GoogleLogin.model_validate({})

    async def test_expired_token_is_rejected(self):
        with self.assertRaises(HTTPException) as raised:
            await self._google_login(self._signed_token(exp=int(time.time()) - 600))

        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(
            raised.exception.detail,
            {
                "code": "GOOGLE_ID_TOKEN_EXPIRED",
                "message": (
                    "Google sign-in expired before it could be verified. "
                    "Please start sign-in again."
                ),
            },
        )

    async def test_valid_recently_issued_token_is_accepted(self):
        users = FakeUsers()
        response = await self._google_login(self._signed_token(), users)

        self.assertEqual(response.token, "app-session-token")
        self.assertEqual(len(users.documents), 1)

    async def test_small_future_clock_difference_is_allowed_by_google_verifier(self):
        response = await self._google_login(
            self._signed_token(iat=int(time.time()) + 30)
        )

        self.assertEqual(response.token, "app-session-token")

    async def test_exchange_success_uses_authorization_code_and_configured_oauth_values(self):
        oauth_client = FakeGoogleOAuthClient("mocked-id-token")
        response, verifier = await self._google_login_with_exchange(
            oauth_client,
            verification_result={**self.claims, "iss": "https://accounts.google.com"},
        )

        self.assertEqual(response.token, "app-session-token")
        self.assertEqual(len(oauth_client.calls), 1)
        url, request = oauth_client.calls[0]
        self.assertEqual(url, "https://oauth2.googleapis.com/token")
        self.assertEqual(
            request["data"],
            {
                "code": "authorization-code-for-mocked-test",
                "client_id": "test-client-id",
                "client_secret": "test-client-secret",
                "redirect_uri": "http://localhost:5173",
                "grant_type": "authorization_code",
            },
        )
        verifier.assert_called_once()
        self.assertEqual(verifier.call_args.args[0], "mocked-id-token")
        self.assertEqual(verifier.call_args.args[2], "test-client-id")
        self.assertEqual(
            verifier.call_args.kwargs["clock_skew_in_seconds"],
            auth._GOOGLE_TOKEN_CLOCK_SKEW_SECONDS,
        )

    async def test_invalid_grant_returns_safe_expired_code_message(self):
        oauth_client = FakeGoogleOAuthClient(
            response=FakeGoogleTokenResponse(
                payload={"error": "invalid_grant"},
                status_code=400,
            )
        )

        with self.assertLogs("routes.auth", level="WARNING") as logs:
            with self.assertRaises(HTTPException) as raised:
                await self._google_login_with_exchange(oauth_client)

        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(
            raised.exception.detail["code"],
            "GOOGLE_AUTHORIZATION_CODE_REJECTED",
        )
        self.assertIn("restart Google sign-in", raised.exception.detail["message"])
        self.assertEqual(logs.records[0].auth_stage, "authorization_code_exchange")
        self.assertEqual(logs.records[0].google_error_category, "invalid_grant")
        self.assertNotIn("authorization-code-for-mocked-test", logs.output[0])
        self.assertNotIn("test-client-secret", logs.output[0])

    async def test_invalid_client_returns_server_configuration_message(self):
        oauth_client = FakeGoogleOAuthClient(
            response=FakeGoogleTokenResponse(
                payload={"error": "invalid_client"},
                status_code=401,
            )
        )

        with self.assertRaises(HTTPException) as raised:
            await self._google_login_with_exchange(oauth_client)

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(raised.exception.detail["code"], "GOOGLE_OAUTH_CLIENT_INVALID")
        self.assertIn("OAuth client ID and secret", raised.exception.detail["message"])

    async def test_google_redirect_uri_mismatch_is_classified(self):
        oauth_client = FakeGoogleOAuthClient(
            response=FakeGoogleTokenResponse(
                payload={
                    "error": "invalid_grant",
                    "error_description": "redirect_uri_mismatch",
                },
                status_code=400,
            )
        )

        with self.assertRaises(HTTPException) as raised:
            await self._google_login_with_exchange(oauth_client)

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail["code"], "GOOGLE_REDIRECT_URI_MISMATCH")
        self.assertIn("GOOGLE_REDIRECT_URI", raised.exception.detail["message"])

    async def test_request_origin_mismatch_is_rejected_before_exchange(self):
        oauth_client = FakeGoogleOAuthClient("unused-token")
        request = self._request("http://127.0.0.1:5173")

        with self.assertRaises(HTTPException) as raised:
            await self._google_login_with_exchange(oauth_client, request=request)

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail["code"], "GOOGLE_REDIRECT_URI_MISMATCH")
        self.assertEqual(oauth_client.calls, [])

    async def test_token_exchange_timeout_returns_retryable_error(self):
        oauth_client = FakeGoogleOAuthClient(
            post_error=httpx.TimeoutException("mock timeout")
        )

        with self.assertRaises(HTTPException) as raised:
            await self._google_login_with_exchange(oauth_client)

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(raised.exception.detail["code"], "GOOGLE_EXCHANGE_TIMEOUT")
        self.assertIn("timed out", raised.exception.detail["message"])

    async def test_malformed_token_response_is_rejected_without_verification(self):
        oauth_client = FakeGoogleOAuthClient(
            response=FakeGoogleTokenResponse(payload=["unexpected", "response"])
        )

        with self.assertRaises(HTTPException) as raised:
            await self._google_login_with_exchange(
                oauth_client,
                verification_result=self.claims,
            )

        self.assertEqual(raised.exception.status_code, 502)
        self.assertEqual(
            raised.exception.detail["code"],
            "GOOGLE_TOKEN_RESPONSE_MALFORMED",
        )

    async def test_id_token_verification_failure_returns_safe_audience_diagnostic(self):
        oauth_client = FakeGoogleOAuthClient("mocked-id-token")

        with self.assertLogs("routes.auth", level="WARNING") as logs:
            with self.assertRaises(HTTPException) as raised:
                await self._google_login_with_exchange(
                    oauth_client,
                    verification_error=ValueError("Wrong recipient, expected private value"),
                )

        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(
            raised.exception.detail["code"],
            "GOOGLE_ID_TOKEN_AUDIENCE_MISMATCH",
        )
        self.assertNotIn("private value", raised.exception.detail["message"])
        self.assertNotIn("private value", "\n".join(logs.output))

    async def test_missing_configuration_logs_variable_names_only(self):
        oauth_client = FakeGoogleOAuthClient("unused-token")

        with self.assertLogs("routes.auth", level="WARNING") as logs:
            with self.assertRaises(HTTPException) as raised:
                await self._google_login_with_exchange(
                    oauth_client,
                    client_id="",
                    client_secret="",
                )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(
            raised.exception.detail["code"],
            "GOOGLE_CONFIGURATION_MISSING",
        )
        self.assertIn("GOOGLE_CLIENT_ID", logs.records[0].missing_variables)
        self.assertIn("GOOGLE_CLIENT_SECRET", logs.records[0].missing_variables)
        self.assertNotIn("test-client-secret", logs.output[0])

    async def test_token_too_far_in_the_future_is_rejected(self):
        with self.assertRaises(HTTPException) as raised:
            await self._google_login(self._signed_token(iat=int(time.time()) + 120))

        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(
            raised.exception.detail,
            {
                "code": "GOOGLE_ID_TOKEN_NOT_YET_VALID",
                "message": (
                    "Google sign-in could not be verified yet. "
                    "Check your device clock and try again."
                ),
            },
        )

    async def test_wrong_audience_is_rejected(self):
        with self.assertRaises(HTTPException) as raised:
            await self._google_login(self._signed_token(aud="different-client-id"))

        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(
            raised.exception.detail,
            {
                "code": "GOOGLE_ID_TOKEN_AUDIENCE_MISMATCH",
                "message": (
                    "Google sign-in could not verify this application. Ask the administrator "
                    "to confirm the frontend and backend use the same OAuth client ID."
                ),
            },
        )

    async def test_wrong_issuer_is_rejected(self):
        with (
            patch.object(auth, "database_is_connected", return_value=True),
            patch.object(auth, "auth_indexes_ready", return_value=True),
            patch.object(auth.settings, "GOOGLE_CLIENT_ID", "test-client-id"),
            patch.object(auth.settings, "GOOGLE_CLIENT_SECRET", "test-client-secret"),
            patch.object(
                auth.settings,
                "GOOGLE_REDIRECT_URI",
                "http://localhost:5173",
            ),
            patch.object(
                auth.httpx,
                "AsyncClient",
                return_value=FakeGoogleOAuthClient("unused-test-token"),
            ),
            patch.object(
                auth.google_id_token,
                "verify_oauth2_token",
                return_value={**self.claims, "iss": "https://attacker.invalid"},
            ),
        ):
            with self.assertRaises(HTTPException) as raised:
                await auth.google_login(
                    GoogleLogin(
                        code="fake-authorization-code-for-test",
                        redirect_uri="http://localhost:5173",
                    ),
                    self._request(),
                    None,
                )

        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(
            raised.exception.detail,
            {
                "code": "GOOGLE_ID_TOKEN_ISSUER_INVALID",
                "message": "Google returned an invalid identity token. Please try again.",
            },
        )

    async def test_invalid_signature_is_rejected(self):
        token_parts = self._signed_token().split(".")
        token_parts[2] = ("A" if token_parts[2][0] != "A" else "B") + token_parts[2][1:]
        token = ".".join(token_parts)

        with self.assertRaises(HTTPException) as raised:
            await self._google_login(token)

        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(
            raised.exception.detail,
            {
                "code": "GOOGLE_ID_TOKEN_SIGNATURE_INVALID",
                "message": (
                    "Google could not verify the identity token signature. Please try again; "
                    "if the problem continues, ask the administrator to check Google token verification."
                ),
            },
        )

    async def test_malformed_token_is_rejected(self):
        with self.assertRaises(HTTPException) as raised:
            await self._google_login("this-is-not-a-well-formed-id-token")

        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(
            raised.exception.detail,
            {
                "code": "GOOGLE_ID_TOKEN_MALFORMED",
                "message": "Google returned an invalid identity token. Please start sign-in again.",
            },
        )

    async def test_unverified_email_is_rejected_without_creating_user(self):
        users = FakeUsers()
        with self.assertRaises(HTTPException) as raised:
            await self._google_login(
                self._signed_token(email_verified=False),
                users,
            )

        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(len(users.documents), 0)

    async def test_valid_token_creates_one_user_and_returns_application_session(self):
        users = FakeUsers()
        token = self._signed_token()

        first_response = await self._google_login(token, users)
        second_response = await self._google_login(token, users)

        self.assertEqual(first_response.token, "app-session-token")
        self.assertEqual(first_response.id, second_response.id)
        self.assertEqual(len(users.documents), 1)
        self.assertEqual(users.documents[0]["google_sub"], self.claims["sub"])

    async def test_google_login_fails_closed_when_database_is_unavailable(self):
        with patch.object(auth, "database_is_connected", return_value=False):
            with self.assertRaises(HTTPException) as raised:
                await auth.google_login(
                    GoogleLogin(
                        code="google-authorization-code-for-tests",
                        redirect_uri="http://localhost:5173",
                    ),
                    self._request(),
                    None,
                )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("MongoDB is unavailable", raised.exception.detail)

    async def test_creates_user_with_google_subject_and_default_farmer_role(self):
        users = FakeUsers()
        with patch.object(auth, "get_user_collection", return_value=users):
            created = await auth._get_or_create_google_user(self.claims)

        self.assertEqual(created["google_sub"], self.claims["sub"])
        self.assertEqual(created["role"], "farmer")

    async def test_existing_password_account_is_not_auto_linked(self):
        password_user = {
            "_id": ObjectId(),
            "email": self.claims["email"],
            "email_normalized": self.claims["email"],
            "password": "hashed-password",
            "role": "buyer",
        }
        users = FakeUsers([password_user])
        with patch.object(auth, "get_user_collection", return_value=users):
            with self.assertRaises(HTTPException) as raised:
                await auth._get_or_create_google_user(self.claims)

        self.assertEqual(raised.exception.status_code, 409)
        self.assertNotIn("google_sub", users.documents[0])

    async def test_authenticated_link_preserves_existing_role(self):
        password_user = {
            "_id": ObjectId(),
            "email": self.claims["email"],
            "email_normalized": self.claims["email"],
            "password": "hashed-password",
            "role": "buyer",
        }
        users = FakeUsers([password_user])
        with patch.object(auth, "get_user_collection", return_value=users):
            linked = await auth._get_or_create_google_user(
                self.claims,
                current_user=password_user,
            )

        self.assertEqual(linked["google_sub"], self.claims["sub"])
        self.assertEqual(linked["role"], "buyer")


if __name__ == "__main__":
    unittest.main()
