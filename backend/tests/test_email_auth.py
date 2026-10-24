import hashlib
import re
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bson import ObjectId
from fastapi import HTTPException

from auth_utils import hash_password
from models.farmer import UserCreate, UserLogin
from routes import auth


class FakeUsers:
    def __init__(self):
        self.documents = []

    async def find_one(self, query):
        for document in self.documents:
            for key, expected in query.items():
                value = document.get(key)
                if isinstance(expected, re.Pattern):
                    if not isinstance(value, str) or not expected.fullmatch(value):
                        break
                elif value != expected:
                    break
            else:
                return dict(document)
        return None

    def find(self, query):
        users = self

        class Cursor:
            async def to_list(self, length=None):
                matches = []
                for document in users.documents:
                    if all(
                        expected.fullmatch(document.get(key, ""))
                        if isinstance(expected, re.Pattern)
                        else document.get(key) == expected
                        for key, expected in query.items()
                    ):
                        matches.append(dict(document))
                        if length and len(matches) >= length:
                            break
                return matches

        return Cursor()

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


class EmailAuthenticationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.users = FakeUsers()

    def registration(self, *, email="  Farmer@Example.com ", mobile="9876543210"):
        return UserCreate(
            full_name="Test Farmer",
            mobile=mobile,
            email=email,
            password="correct horse battery staple",
            role="farmer",
        )

    def test_registration_schema_accepts_missing_null_and_blank_email(self):
        registration_data = {
            "full_name": "Test Farmer",
            "mobile": "9876543210",
            "password": "correct horse battery staple",
            "role": "farmer",
        }

        self.assertIsNone(UserCreate(**registration_data).email)
        self.assertIsNone(UserCreate(**registration_data, email=None).email)
        self.assertIsNone(UserCreate(**registration_data, email="").email)

    async def test_registration_normalizes_email_and_duplicate_does_not_create_user(self):
        with (
            patch.object(auth, "database_is_connected", return_value=True),
            patch.object(auth, "auth_indexes_ready", return_value=True),
            patch.object(auth, "get_user_collection", return_value=self.users),
        ):
            created = await auth.register(self.registration())
            with self.assertRaises(HTTPException) as duplicate:
                await auth.register(self.registration(
                    email="FARMER@example.com",
                    mobile="9123456780",
                ))

        self.assertEqual(created.email, "farmer@example.com")
        self.assertEqual(len(self.users.documents), 1)
        self.assertEqual(self.users.documents[0]["email"], "farmer@example.com")
        self.assertEqual(self.users.documents[0]["email_normalized"], "farmer@example.com")
        self.assertEqual(duplicate.exception.status_code, 409)
        self.assertIn("email is already registered", duplicate.exception.detail)

    async def test_registered_password_logs_in_with_trimmed_mixed_case_email(self):
        with (
            patch.object(auth, "database_is_connected", return_value=True),
            patch.object(auth, "auth_indexes_ready", return_value=True),
            patch.object(auth, "get_user_collection", return_value=self.users),
        ):
            created = await auth.register(self.registration())

        with (
            patch.object(auth, "get_user_collection", return_value=self.users),
            patch.object(auth, "_profile_role", new=AsyncMock(return_value="farmer")),
            patch.object(auth, "_profile_is_complete", new=AsyncMock(return_value=False)),
            patch.object(auth, "create_access_token", return_value="test-session-token"),
        ):
            result = await auth.login(UserLogin(
                mobile_or_email="  FARMER@Example.COM ",
                password="correct horse battery staple",
            ))

        self.assertEqual(result.id, created.id)
        self.assertEqual(result.email, "farmer@example.com")
        self.assertEqual(result.token, "test-session-token")

    async def test_registration_without_email_stores_bcrypt_hash_and_logs_in(self):
        password = "  correct horse battery staple  "
        with (
            patch.object(auth, "database_is_connected", return_value=True),
            patch.object(auth, "auth_indexes_ready", return_value=True),
            patch.object(auth, "get_user_collection", return_value=self.users),
            self.assertLogs(auth.logger, level="INFO") as registration_logs,
        ):
            created = await auth.register(UserCreate(
                full_name="Mobile Farmer",
                mobile="+91 98765-43210",
                email="",
                password=password,
                role="farmer",
            ))
        self.assertIn("registration persisted", registration_logs.output[0])
        self.assertIn("collection=users", registration_logs.output[0])
        self.assertNotIn("9876543210", registration_logs.output[0])
        self.assertNotIn(password, registration_logs.output[0])

        saved_user = self.users.documents[0]
        self.assertEqual(saved_user["mobile"], "9876543210")
        self.assertNotIn("email", saved_user)
        self.assertTrue(saved_user["password"].startswith("$2"))
        self.assertNotEqual(saved_user["password"], password)
        self.assertTrue(auth.verify_password(password, saved_user["password"]))
        self.assertFalse(
            auth.verify_password("incorrect password", saved_user["password"])
        )

        with (
            patch.object(auth, "get_user_collection", return_value=self.users),
            patch.object(auth, "_profile_role", new=AsyncMock(return_value="farmer")),
            patch.object(auth, "_profile_is_complete", new=AsyncMock(return_value=False)),
            patch.object(auth, "create_access_token", return_value="test-session-token"),
        ):
            result = await auth.login(UserLogin(
                mobile_or_email="09876543210",
                password=password,
            ))
            with self.assertRaises(HTTPException) as wrong_password:
                await auth.login(UserLogin(
                    mobile_or_email="9876543210",
                    password=password.strip(),
                ))

        self.assertEqual(result.id, created.id)
        self.assertEqual(result.token, "test-session-token")
        self.assertEqual(wrong_password.exception.status_code, 401)
        self.assertEqual(
            wrong_password.exception.detail,
            "Invalid mobile number/email or password.",
        )

    async def test_registered_mobile_logs_in_with_same_normalized_number(self):
        with (
            patch.object(auth, "database_is_connected", return_value=True),
            patch.object(auth, "auth_indexes_ready", return_value=True),
            patch.object(auth, "get_user_collection", return_value=self.users),
        ):
            created = await auth.register(UserCreate(
                full_name="Mobile Farmer",
                mobile="+91 98765-43210",
                email="mobile@example.com",
                password="correct horse battery staple",
                role="farmer",
            ))
            with self.assertRaises(HTTPException) as duplicate:
                await auth.register(UserCreate(
                    full_name="Another Farmer",
                    mobile="09876543210",
                    email="another@example.com",
                    password="correct horse battery staple",
                    role="farmer",
                ))

        self.assertEqual(created.mobile, "9876543210")
        self.assertEqual(duplicate.exception.status_code, 409)
        self.assertIn("already belongs to an account", duplicate.exception.detail)
        self.assertIn("Log in with that account", duplicate.exception.detail)
        self.assertIn("separate Farmer and Buyer accounts", duplicate.exception.detail)
        self.assertEqual(len(self.users.documents), 1)

        with (
            patch.object(auth, "get_user_collection", return_value=self.users),
            patch.object(auth, "_profile_role", new=AsyncMock(return_value="farmer")),
            patch.object(auth, "_profile_is_complete", new=AsyncMock(return_value=False)),
            patch.object(auth, "create_access_token", return_value="test-session-token"),
        ):
            result = await auth.login(UserLogin(
                mobile_or_email=" +91 98765-43210 ",
                password="correct horse battery staple",
            ))

        self.assertEqual(result.id, created.id)
        self.assertEqual(result.mobile, "9876543210")
        self.assertEqual(result.token, "test-session-token")

    async def test_distinct_farmer_and_buyer_accounts_keep_their_roles_on_login(self):
        with (
            patch.object(auth, "database_is_connected", return_value=True),
            patch.object(auth, "auth_indexes_ready", return_value=True),
            patch.object(auth, "get_user_collection", return_value=self.users),
        ):
            farmer = await auth.register(UserCreate(
                full_name="Test Farmer",
                mobile="9876543210",
                email="farmer@example.com",
                password="correct horse battery staple",
                role="farmer",
            ))
            buyer = await auth.register(UserCreate(
                full_name="Test Buyer",
                mobile="9876543211",
                email="buyer@example.com",
                password="correct horse battery staple",
                role="buyer",
            ))

        self.assertEqual(
            [document["role"] for document in self.users.documents],
            ["farmer", "buyer"],
        )

        with (
            patch.object(auth, "get_user_collection", return_value=self.users),
            patch.object(auth, "_profile_is_complete", new=AsyncMock(return_value=False)),
            patch.object(auth, "create_access_token", return_value="test-session-token"),
        ):
            farmer_login = await auth.login(UserLogin(
                mobile_or_email=farmer.mobile,
                password="correct horse battery staple",
            ))
            buyer_login = await auth.login(UserLogin(
                mobile_or_email=buyer.mobile,
                password="correct horse battery staple",
            ))

        self.assertEqual(farmer_login.role, "farmer")
        self.assertEqual(buyer_login.role, "buyer")

    async def test_registered_mobile_with_wrong_password_reports_password_error(self):
        self.users.documents.append({
            "_id": ObjectId(),
            "full_name": "Test Farmer",
            "mobile": "9876543210",
            "mobile_normalized": "9876543210",
            "password": hash_password("correct horse battery staple"),
            "role": "farmer",
            "token_version": 0,
        })
        with patch.object(auth, "get_user_collection", return_value=self.users):
            with self.assertRaises(HTTPException) as raised:
                await auth.login(UserLogin(
                    mobile_or_email="9876543210",
                    password="wrong password",
                ))

        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(
            raised.exception.detail,
            "Invalid mobile number/email or password.",
        )

    async def test_legacy_sha256_password_is_verified_then_upgraded_to_bcrypt(self):
        password = "legacy compatible password"
        salt = auth.settings.SECRET_KEY[:8] or "salt1234"
        self.users.documents.append({
            "_id": ObjectId(),
            "full_name": "Legacy Farmer",
            "mobile": "9876543210",
            "mobile_normalized": "9876543210",
            "password": "sha256$" + hashlib.sha256(
                (password + salt).encode("utf-8")
            ).hexdigest(),
            "role": "farmer",
            "token_version": 0,
        })
        with (
            patch.object(auth, "get_user_collection", return_value=self.users),
            patch.object(auth, "_profile_role", new=AsyncMock(return_value="farmer")),
            patch.object(auth, "_profile_is_complete", new=AsyncMock(return_value=False)),
            patch.object(auth, "create_access_token", return_value="test-session-token"),
        ):
            result = await auth.login(UserLogin(
                mobile_or_email="9876543210",
                password=password,
            ))

        self.assertEqual(result.token, "test-session-token")
        self.assertTrue(self.users.documents[0]["password"].startswith("$2"))
        self.assertTrue(
            auth.verify_password(password, self.users.documents[0]["password"])
        )

    async def test_formatted_legacy_mobile_without_normalized_field_can_log_in(self):
        user = {
            "_id": ObjectId(),
            "full_name": "Legacy Farmer",
            "mobile": "+91 98765-43210",
            "password": hash_password("correct horse battery staple"),
            "role": "farmer",
            "token_version": 0,
        }
        self.users.documents.append(user)
        with (
            patch.object(auth, "auth_indexes_ready", return_value=False),
            patch.object(auth, "get_user_collection", return_value=self.users),
            patch.object(auth, "_profile_role", new=AsyncMock(return_value="farmer")),
            patch.object(auth, "_profile_is_complete", new=AsyncMock(return_value=False)),
            patch.object(auth, "create_access_token", return_value="test-session-token"),
        ):
            result = await auth.login(UserLogin(
                mobile_or_email="9876543210",
                password="correct horse battery staple",
            ))

        self.assertEqual(result.id, str(user["_id"]))
        self.assertEqual(result.token, "test-session-token")

    async def test_google_linked_mobile_without_password_explains_sign_in_method(self):
        self.users.documents.append({
            "_id": ObjectId(),
            "full_name": "Google Farmer",
            "mobile": "9876543210",
            "mobile_normalized": "9876543210",
            "google_sub": "google-test-subject",
            "role": "farmer",
        })
        with (
            patch.object(auth, "get_user_collection", return_value=self.users),
            patch.object(auth, "verify_password") as verify_password,
        ):
            with self.assertRaises(HTTPException) as raised:
                await auth.login(UserLogin(
                    mobile_or_email="9876543210",
                    password="test-password-not-used",
                ))

        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(
            raised.exception.detail,
            "This mobile number is linked to a Google account without a password. "
            "Sign in with Google.",
        )
        verify_password.assert_not_called()

    async def test_unregistered_mobile_reports_not_registered(self):
        with patch.object(auth, "get_user_collection", return_value=self.users):
            with self.assertRaises(HTTPException) as raised:
                await auth.login(UserLogin(
                    mobile_or_email="9876543210",
                    password="correct horse battery staple",
                ))

        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(
            raised.exception.detail,
            "Invalid mobile number/email or password.",
        )

    async def test_login_failure_logs_stage_without_credentials_or_identifiers(self):
        self.users.documents.append({
            "_id": ObjectId(),
            "full_name": "Test Farmer",
            "mobile": "9876543210",
            "mobile_normalized": "9876543210",
            "password": hash_password("correct horse battery staple"),
            "role": "farmer",
            "token_version": 0,
        })
        with patch.object(auth, "get_user_collection", return_value=self.users):
            with self.assertLogs(auth.logger, level="WARNING") as password_logs:
                with self.assertRaises(HTTPException):
                    await auth.login(UserLogin(
                        mobile_or_email="9876543210",
                        password="incorrect secret",
                    ))

            self.users.documents.clear()
            with self.assertLogs(auth.logger, level="WARNING") as lookup_logs:
                with self.assertRaises(HTTPException):
                    await auth.login(UserLogin(
                        mobile_or_email="9876543210",
                        password="incorrect secret",
                    ))

        self.assertIn("stage=password_verification", password_logs.output[0])
        self.assertIn("stage=account_lookup", lookup_logs.output[0])
        for output in (password_logs.output[0], lookup_logs.output[0]):
            self.assertNotIn("9876543210", output)
            self.assertNotIn("incorrect secret", output)
            self.assertNotIn("correct horse battery staple", output)

    async def test_invalid_mobile_format_has_validation_error(self):
        with patch.object(auth, "get_user_collection", return_value=self.users):
            with self.assertRaises(HTTPException) as raised:
                await auth.login(UserLogin(
                    mobile_or_email="12345",
                    password="correct horse battery staple",
                ))

        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(
            raised.exception.detail,
            "Enter a valid 10-digit Indian mobile number.",
        )

    async def test_legacy_mixed_case_email_without_normalized_field_is_not_found(self):
        user = {
            "_id": ObjectId(),
            "full_name": "Legacy Farmer",
            "email": "Legacy.Farmer@Example.com",
            "mobile": "9876543210",
            "password": hash_password("correct horse battery staple"),
            "role": "farmer",
            "token_version": 0,
        }
        self.users.documents.append(user)

        with (
            patch.object(auth, "get_user_collection", return_value=self.users),
        ):
            with self.assertRaises(HTTPException) as raised:
                await auth.login(UserLogin(
                    mobile_or_email=" legacy.farmer@example.COM ",
                    password="correct horse battery staple",
                ))

        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(
            raised.exception.detail,
            "Invalid mobile number/email or password.",
        )

    async def test_unknown_email_and_wrong_password_share_previous_message(self):
        self.users.documents.append({
            "_id": ObjectId(),
            "full_name": "Test Farmer",
            "email": "farmer@example.com",
            "email_normalized": "farmer@example.com",
            "mobile": "9876543210",
            "password": hash_password("correct horse battery staple"),
            "role": "farmer",
            "token_version": 0,
        })
        with patch.object(auth, "get_user_collection", return_value=self.users):
            with self.assertRaises(HTTPException) as unknown:
                await auth.login(UserLogin(
                    mobile_or_email="unknown@example.com",
                    password="correct horse battery staple",
                ))
            with self.assertRaises(HTTPException) as wrong_password:
                await auth.login(UserLogin(
                    mobile_or_email="farmer@example.com",
                    password="incorrect password",
                ))

        self.assertEqual(unknown.exception.status_code, 401)
        self.assertEqual(unknown.exception.detail, "Invalid mobile number/email or password.")
        self.assertEqual(wrong_password.exception.status_code, 401)
        self.assertEqual(wrong_password.exception.detail, unknown.exception.detail)
