import asyncio
import logging
import re
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth.exceptions import TransportError as GoogleTransportError
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token as google_id_token
from pymongo.errors import DuplicateKeyError
from bson import ObjectId

from auth_utils import (
    create_access_token,
    decode_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from database import (
    auth_indexes_ready,
    database_is_connected,
    get_buyer_profile_collection,
    get_farmer_profile_collection,
    get_user_collection,
    settings,
)
from models.farmer import (
    GoogleLogin,
    UserCreate,
    UserLogin,
    UserRegistrationResponse,
    UserResponse,
)
from normalization import normalize_email, normalize_mobile

router = APIRouter()
_optional_bearer = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)
_GOOGLE_TOKEN_CLOCK_SKEW_SECONDS = 60
_MOBILE_ALREADY_REGISTERED_DETAIL = (
    "This mobile number already belongs to an account. Log in with that account "
    "or use a different number; one mobile number cannot be used for separate "
    "Farmer and Buyer accounts."
)

_GOOGLE_ERROR_CATEGORIES = {
    "invalid_grant",
    "invalid_client",
    "redirect_uri_mismatch",
    "unauthorized_client",
    "invalid_request",
    "unsupported_grant_type",
    "temporarily_unavailable",
    "server_error",
}


def _google_error_category(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    description = payload.get("error_description")
    text = " ".join(
        value.lower()
        for value in (error, description)
        if isinstance(value, str)
    )
    if "redirect_uri_mismatch" in text or (
        "redirect" in text and "uri" in text and "mismatch" in text
    ):
        return "redirect_uri_mismatch"
    category = error.lower() if isinstance(error, str) else ""
    return category if category in _GOOGLE_ERROR_CATEGORIES else None


def _google_id_token_failure(exc: ValueError) -> tuple[str, str, str]:
    verification_error = str(exc).lower()
    if "expired" in verification_error:
        return (
            "GOOGLE_ID_TOKEN_EXPIRED",
            "expired",
            "Google sign-in expired before it could be verified. Please start sign-in again.",
        )
    if "audience" in verification_error or "recipient" in verification_error:
        return (
            "GOOGLE_ID_TOKEN_AUDIENCE_MISMATCH",
            "audience_mismatch",
            "Google sign-in could not verify this application. Ask the administrator "
            "to confirm the frontend and backend use the same OAuth client ID.",
        )
    if "issuer" in verification_error:
        return (
            "GOOGLE_ID_TOKEN_ISSUER_INVALID",
            "issuer_invalid",
            "Google returned an invalid identity token. Please start sign-in again.",
        )
    if any(term in verification_error for term in ("signature", "pem", "key id", "kid")):
        return (
            "GOOGLE_ID_TOKEN_SIGNATURE_INVALID",
            "signature_or_signing_key_invalid",
            "Google could not verify the identity token signature. Please try again; "
            "if the problem continues, ask the administrator to check Google token verification.",
        )
    if any(term in verification_error for term in ("too early", "used too early", "iat")):
        return (
            "GOOGLE_ID_TOKEN_NOT_YET_VALID",
            "not_yet_valid",
            "Google sign-in could not be verified yet. Check your device clock and try again.",
        )
    if any(term in verification_error for term in ("jwt", "token", "segment", "decode")):
        return (
            "GOOGLE_ID_TOKEN_MALFORMED",
            "malformed",
            "Google returned an invalid identity token. Please start sign-in again.",
        )
    return (
        "GOOGLE_ID_TOKEN_INVALID",
        "unclassified_verification_failure",
        "Google returned an invalid identity token. Please start sign-in again.",
    )


def _google_auth_failure(
    *,
    stage: str,
    code: str,
    message: str,
    status_code: int,
    google_status: int | None = None,
    google_error: str | None = None,
    **diagnostics,
) -> HTTPException:
    log_fields = {
        "auth_provider": "google",
        "auth_stage": stage,
        "error_code": code,
    }
    if google_status is not None:
        log_fields["google_http_status"] = google_status
    if google_error is not None:
        log_fields["google_error_category"] = google_error
    log_fields.update(diagnostics)
    logger.warning("Google authentication failed", extra=log_fields)
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


async def _profile_is_complete(user: dict) -> bool:
    user_id = user["_id"]
    farmer_profile = await get_farmer_profile_collection().find_one({"user_id": user_id})
    buyer_profile = await get_buyer_profile_collection().find_one({"user_id": user_id})
    if user.get("role") == "farmer":
        complete = farmer_profile is not None
    elif user.get("role") == "buyer":
        complete = buyer_profile is not None
    else:
        complete = farmer_profile is not None or buyer_profile is not None
    await get_user_collection().update_one(
        {"_id": user_id}, {"$set": {"profile_complete": complete}}
    )
    return complete


async def _profile_role(user: dict) -> str:
    role = user.get("role")
    if role in {"farmer", "buyer"}:
        return role
    user_id = user["_id"]
    farmer_profile = await get_farmer_profile_collection().find_one({"user_id": user_id})
    buyer_profile = await get_buyer_profile_collection().find_one({"user_id": user_id})
    role = "farmer" if farmer_profile or not buyer_profile else "buyer"
    await get_user_collection().update_one({"_id": user_id}, {"$set": {"role": role}})
    return role


async def _optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
) -> dict | None:
    if credentials is None:
        return None
    token_claims = decode_access_token(credentials.credentials)
    user_id = token_claims.get("user_id") if token_claims else None
    try:
        user_oid = ObjectId(user_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid application session.",
        ) from exc
    user = await get_user_collection().find_one({"_id": user_oid})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Application account not found.",
        )
    if int(token_claims.get("token_version", 0)) != int(user.get("token_version", 0)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid application session.",
        )
    return user


async def _link_google_account(
    users,
    user: dict,
    subject: str,
) -> dict:
    linked_subject = user.get("google_sub")
    if linked_subject and linked_subject != subject:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email is already linked to a different Google account.",
        )
    if not linked_subject:
        result = await users.update_one(
            {"_id": user["_id"], "google_sub": {"$in": [None, subject]}},
            {"$set": {"google_sub": subject, "updated_at": datetime.utcnow()}},
        )
        user = await users.find_one({"_id": user["_id"]}) or user
        if not result.modified_count and user.get("google_sub") != subject:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This account was linked to a different Google account. Sign in with your existing method.",
            )
    return user


async def _get_or_create_google_user(claims: dict, current_user: dict | None = None) -> dict:
    users = get_user_collection()
    subject = str(claims.get("sub", "")).strip()
    try:
        email = normalize_email(str(claims.get("email", "")))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google did not return a valid email address.",
        ) from exc
    if not subject or not email or claims.get("email_verified") is not True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google did not return a verified account identity.",
        )

    user = await users.find_one({"google_sub": subject})
    if user:
        if current_user and str(user["_id"]) != str(current_user["_id"]):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This Google account is linked to a different application account.",
            )
        return user

    if current_user:
        if str(current_user.get("email", "")).strip().lower() != email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The Google email does not match the signed-in application account.",
            )
        return await _link_google_account(
            users, current_user, subject
        )

    user = await users.find_one({"email_normalized": email})
    if not user:
        user = await users.find_one({"email": email})
    if user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "An account with this email already exists. Sign in with your existing "
                "password, then connect Google from your profile."
            ),
        )

    display_name = str(claims.get("name") or email.partition("@")[0]).strip()
    if len(display_name) < 2:
        display_name = "Google User"
    user_document = {
        "full_name": display_name,
        "email": email,
        "email_normalized": email,
        "google_sub": subject,
        "role": "farmer",
        "profile_complete": False,
        "token_version": 0,
        "created_at": datetime.utcnow(),
    }
    try:
        result = await users.insert_one(user_document)
    except DuplicateKeyError:
        user = await users.find_one({"google_sub": subject})
        if user:
            return user
        user = await users.find_one({"email_normalized": email})
        if not user:
            user = await users.find_one({"email": email})
        if user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "An account with this email already exists. Sign in with your existing "
                    "password, then connect Google from your profile."
                ),
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This Google account could not be linked to a user record.",
        )
    user_document["_id"] = result.inserted_id
    return user_document


@router.post(
    "/register",
    response_model=UserRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(user_data: UserCreate):
    if not database_is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is unavailable. Start the configured database and try again.",
        )
    if not auth_indexes_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Registration is temporarily unavailable because account uniqueness could not be verified.",
        )
    users = get_user_collection()
    email = normalize_email(user_data.email) if user_data.email else None
    mobile = normalize_mobile(user_data.mobile)

    if await users.find_one({"mobile_normalized": mobile}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_MOBILE_ALREADY_REGISTERED_DETAIL,
        )

    if email and await users.find_one({"email_normalized": email}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email is already registered. Please log in.",
        )

    user_doc = {
        "full_name": user_data.full_name.strip(),
        "mobile": mobile,
        "mobile_normalized": mobile,
        "password": hash_password(user_data.password),
        "role": user_data.role,
        "profile_complete": False,
        "token_version": 0,
        "created_at": datetime.utcnow(),
    }
    if email:
        user_doc["email"] = email
        user_doc["email_normalized"] = email

    try:
        result = await users.insert_one(user_doc)
    except DuplicateKeyError as exc:
        if email and await users.find_one({"email_normalized": email}):
            detail = "This email is already registered. Please log in."
        elif await users.find_one({"mobile_normalized": mobile}):
            detail = _MOBILE_ALREADY_REGISTERED_DETAIL
        else:
            detail = "This account is already registered. Please log in."
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        ) from exc
    logger.info(
        "Authentication registration persisted database=%s collection=users.",
        settings.DATABASE_NAME,
    )
    user_id = str(result.inserted_id)
    return UserRegistrationResponse(
        id=user_id,
        full_name=user_doc["full_name"],
        mobile=user_doc["mobile"],
        email=email,
        profile_complete=False,
        role=user_data.role,
    )


@router.post("/login", response_model=UserResponse)
async def login(login_data: UserLogin):
    users = get_user_collection()
    credential = login_data.mobile_or_email.strip()
    is_mobile_login = "@" not in credential
    identifier_type = "mobile" if is_mobile_login else "email"
    if not is_mobile_login:
        try:
            email = normalize_email(credential)
            user = await users.find_one({"email_normalized": email})
            if not user:
                user = await users.find_one({"email": email})
        except ValueError:
            user = None
    else:
        try:
            mobile = normalize_mobile(credential)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Enter a valid 10-digit Indian mobile number.",
            ) from exc
        user = await users.find_one({"mobile_normalized": mobile})
        if not user:
            user = await users.find_one({"mobile": mobile})
        if not user and not auth_indexes_ready():
            # Legacy records may retain punctuation or a country prefix in `mobile`.
            number_pattern = r"\D*".join(re.escape(digit) for digit in mobile)
            legacy_mobile_pattern = re.compile(
                rf"^\D*(?:(?:9\D*1\D*)|0\D*)?{number_pattern}\D*$"
            )
            candidates = await users.find(
                {"mobile": legacy_mobile_pattern}
            ).to_list(length=2)
            matches = []
            for candidate in candidates:
                stored_mobile = candidate.get("mobile")
                if not isinstance(stored_mobile, str):
                    continue
                try:
                    if normalize_mobile(stored_mobile) == mobile:
                        matches.append(candidate)
                except ValueError:
                    continue
            if len(matches) > 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This mobile number matches multiple existing accounts. Please contact support.",
                )
            if matches:
                user = matches[0]

    if not user:
        logger.warning(
            "Authentication failed at stage=account_lookup database=%s "
            "collection=users identifier_type=%s.",
            settings.DATABASE_NAME,
            identifier_type,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid mobile number/email or password.",
        )

    password_hash = user.get("password")
    if not password_hash:
        logger.warning(
            "Authentication failed at stage=stored_hash_lookup identifier_type=%s.",
            identifier_type,
        )
        if is_mobile_login and user.get("google_sub"):
            detail = (
                "This mobile number is linked to a Google account without a password. "
                "Sign in with Google."
            )
        elif is_mobile_login:
            detail = "No password is set for this mobile account. Use account recovery."
        else:
            detail = "This account does not have a password set."
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )

    if not verify_password(login_data.password, password_hash):
        logger.warning(
            "Authentication failed at stage=password_verification identifier_type=%s.",
            identifier_type,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid mobile number/email or password.",
        )

    if user["password"].startswith("sha256$") and len(login_data.password.encode("utf-8")) <= 72:
        await users.update_one(
            {"_id": user["_id"]}, {"$set": {"password": hash_password(login_data.password)}}
        )

    user_id = str(user["_id"])
    role = await _profile_role(user)
    user["role"] = role
    profile_complete = await _profile_is_complete(user)
    token = create_access_token(
        data={"user_id": user_id, "token_version": int(user.get("token_version", 0))},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return UserResponse(
        id=user_id,
        full_name=user["full_name"],
        mobile=user.get("mobile") or "",
        email=user.get("email"),
        token=token,
        profile_complete=profile_complete,
        role=role,
    )


@router.post("/google", response_model=UserResponse)
async def google_login(
    login_data: GoogleLogin,
    request: Request,
    current_user: dict | None = Depends(_optional_current_user),
):
    if not database_is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is unavailable. Start the configured database and try again.",
        )
    if not auth_indexes_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sign-in is temporarily unavailable because account uniqueness could not be verified.",
        )
    client_id = settings.GOOGLE_CLIENT_ID.strip()
    client_secret = settings.GOOGLE_CLIENT_SECRET.strip()
    expected_redirect_uri = settings.GOOGLE_REDIRECT_URI.strip().rstrip("/")
    redirect_uri = login_data.redirect_uri.strip().rstrip("/")
    origin = request.headers.get("origin", "").strip().rstrip("/")
    missing_configuration = [
        name
        for name, value in (
            ("GOOGLE_CLIENT_ID", client_id),
            ("GOOGLE_CLIENT_SECRET", client_secret),
            ("GOOGLE_REDIRECT_URI", expected_redirect_uri),
        )
        if not value
    ]
    if missing_configuration:
        raise _google_auth_failure(
            stage="configuration",
            code="GOOGLE_CONFIGURATION_MISSING",
            message=(
                "Google sign-in is not configured on the server. "
                "Ask the administrator to verify the Google OAuth settings."
            ),
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            missing_variables=missing_configuration,
        )
    if request.headers.get("x-requested-with", "") != "XmlHttpRequest":
        raise _google_auth_failure(
            stage="request_validation",
            code="GOOGLE_REQUEST_HEADER_MISSING",
            message="Google sign-in could not be verified. Refresh the page and try again.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if redirect_uri != expected_redirect_uri or (origin and origin != expected_redirect_uri):
        raise _google_auth_failure(
            stage="origin_validation",
            code="GOOGLE_REDIRECT_URI_MISMATCH",
            message=(
                "The frontend address does not match the server's Google sign-in "
                "configuration. Open the configured frontend address or ask the "
                "administrator to align GOOGLE_REDIRECT_URI and CORS_ORIGINS."
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": login_data.code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            response.raise_for_status()
            try:
                token_data = response.json()
            except ValueError as exc:
                raise _google_auth_failure(
                    stage="authorization_code_exchange",
                    code="GOOGLE_TOKEN_RESPONSE_MALFORMED",
                    message="Google returned an unexpected sign-in response. Please try again.",
                    status_code=status.HTTP_502_BAD_GATEWAY,
                ) from exc
    except httpx.HTTPStatusError as exc:
        google_error = _google_error_category(exc.response)
        if google_error == "invalid_grant":
            failure_code = "GOOGLE_AUTHORIZATION_CODE_REJECTED"
            failure_message = (
                "Google rejected this sign-in attempt. It may have expired or already "
                "been used; restart Google sign-in and try again."
            )
            failure_status = status.HTTP_401_UNAUTHORIZED
        elif google_error == "invalid_client":
            failure_code = "GOOGLE_OAUTH_CLIENT_INVALID"
            failure_message = (
                "Google sign-in is misconfigured on the server. Ask the administrator "
                "to verify the OAuth client ID and secret."
            )
            failure_status = status.HTTP_503_SERVICE_UNAVAILABLE
        elif google_error == "redirect_uri_mismatch":
            failure_code = "GOOGLE_REDIRECT_URI_MISMATCH"
            failure_message = (
                "Google rejected the configured sign-in address. Ask the administrator "
                "to align GOOGLE_REDIRECT_URI with the authorized Google redirect URI."
            )
            failure_status = status.HTTP_400_BAD_REQUEST
        elif google_error in {"temporarily_unavailable", "server_error"}:
            failure_code = "GOOGLE_AUTHORIZATION_TEMPORARILY_UNAVAILABLE"
            failure_message = "Google sign-in is temporarily unavailable. Please try again."
            failure_status = status.HTTP_503_SERVICE_UNAVAILABLE
        else:
            failure_code = "GOOGLE_AUTHORIZATION_EXCHANGE_FAILED"
            failure_message = (
                "Google could not complete authorization. Verify the OAuth client "
                "configuration and try again."
            )
            failure_status = (
                status.HTTP_401_UNAUTHORIZED
                if exc.response.status_code < 500
                else status.HTTP_503_SERVICE_UNAVAILABLE
            )
        raise _google_auth_failure(
            stage="authorization_code_exchange",
            code=failure_code,
            message=failure_message,
            status_code=failure_status,
            google_status=exc.response.status_code,
            google_error=google_error or "unclassified_google_error",
        ) from exc
    except httpx.TimeoutException as exc:
        raise _google_auth_failure(
            stage="authorization_code_exchange",
            code="GOOGLE_EXCHANGE_TIMEOUT",
            message="Google sign-in timed out. Please try again.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            exception_type=type(exc).__name__,
        ) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise _google_auth_failure(
            stage="authorization_code_exchange",
            code="GOOGLE_EXCHANGE_UNAVAILABLE",
            message="Unable to contact Google sign-in. Please try again.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            exception_type=type(exc).__name__,
        ) from exc

    logger.info(
        "Google authorization code exchanged",
        extra={"auth_provider": "google", "auth_stage": "authorization_code_exchange"},
    )
    if not isinstance(token_data, dict):
        raise _google_auth_failure(
            stage="authorization_code_exchange",
            code="GOOGLE_TOKEN_RESPONSE_MALFORMED",
            message="Google returned an unexpected sign-in response. Please try again.",
            status_code=status.HTTP_502_BAD_GATEWAY,
        )
    encoded_id_token = token_data.get("id_token")
    if not isinstance(encoded_id_token, str) or not encoded_id_token:
        raise _google_auth_failure(
            stage="authorization_code_exchange",
            code="GOOGLE_ID_TOKEN_MISSING",
            message="Google did not return the required identity token. Please try again.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        claims = await asyncio.to_thread(
            google_id_token.verify_oauth2_token,
            encoded_id_token,
            GoogleAuthRequest(),
            client_id,
            clock_skew_in_seconds=_GOOGLE_TOKEN_CLOCK_SKEW_SECONDS,
        )
    except GoogleTransportError as exc:
        raise _google_auth_failure(
            stage="id_token_verification",
            code="GOOGLE_ID_TOKEN_VERIFICATION_UNAVAILABLE",
            message="Unable to verify your Google sign-in right now. Please try again.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            exception_type=type(exc).__name__,
        ) from exc
    except ValueError as exc:
        failure_code, verification_error, failure_message = _google_id_token_failure(exc)
        raise _google_auth_failure(
            stage="id_token_verification",
            code=failure_code,
            message=failure_message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            verification_error_category=verification_error,
        ) from exc
    if claims.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
        raise _google_auth_failure(
            stage="id_token_verification",
            code="GOOGLE_ID_TOKEN_ISSUER_INVALID",
            message="Google returned an invalid identity token. Please try again.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    logger.info(
        "Google identity token verified",
        extra={"auth_provider": "google", "auth_stage": "id_token_verification"},
    )

    user = await _get_or_create_google_user(claims, current_user)
    role = await _profile_role(user)

    token = create_access_token(
        data={
            "user_id": str(user["_id"]),
            "token_version": int(user.get("token_version", 0)),
        },
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return UserResponse(
        id=str(user["_id"]),
        full_name=user["full_name"],
        mobile=user.get("mobile") or "",
        email=user.get("email"),
        token=token,
        profile_complete=await _profile_is_complete(user),
        role=role,
    )


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    await get_user_collection().update_one(
        {"_id": ObjectId(current_user["id"])}, {"$inc": {"token_version": 1}}
    )
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    token = create_access_token(
        data={
            "user_id": current_user["id"],
            "token_version": current_user.get("token_version", 0),
        },
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return UserResponse(
        id=current_user["id"],
        full_name=current_user["full_name"],
        mobile=current_user.get("mobile") or "",
        email=current_user.get("email"),
        token=token,
        profile_complete=await _profile_is_complete({"_id": ObjectId(current_user["id"])}),
        role=current_user["role"],
    )
