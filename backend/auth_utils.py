from datetime import datetime, timedelta
from typing import Optional
import hashlib
import hmac
import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from bson import ObjectId

from database import (
    settings,
    get_buyer_profile_collection,
    get_farmer_profile_collection,
    get_user_collection,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def assert_user_role(user: dict, required_role: str) -> None:
    if user.get("role") != required_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This action requires a {required_role} account.",
        )


def validate_jwt_secret() -> None:
    secret = settings.SECRET_KEY.strip()
    if len(secret) < 32 or any(marker in secret.lower() for marker in ("change-me", "your-secret", "placeholder")):
        raise RuntimeError("Configure a random SECRET_KEY of at least 32 characters in backend/.env.")


def _truncate_pw(password: str) -> bytes:
    encoded = password.encode("utf-8")
    if len(encoded) > 72:
        return encoded[:72]
    return encoded


def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password must be 72 bytes or fewer.")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        if hashed_password.startswith("sha256$"):
            salt = settings.SECRET_KEY[:8] or "salt1234"
            expected = hashlib.sha256((plain_password + salt).encode("utf-8")).hexdigest()
            return hmac.compare_digest(hashed_password[7:], expected)
        return bcrypt.checkpw(_truncate_pw(plain_password), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    validate_jwt_secret()
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    validate_jwt_secret()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> dict:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: Optional[str] = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
        )

    users = get_user_collection()
    user = await users.find_one({"_id": oid})
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if int(payload.get("token_version", 0)) != int(user.get("token_version", 0)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.get("role") not in {"farmer", "buyer"}:
        farmer_profile = await get_farmer_profile_collection().find_one({"user_id": oid})
        buyer_profile = await get_buyer_profile_collection().find_one({"user_id": oid})
        # Accounts created before role selection existed were farmer accounts by default.
        role = "farmer" if farmer_profile or not buyer_profile else "buyer"
        await users.update_one({"_id": oid}, {"$set": {"role": role}})
        user["role"] = role

    user["_id"] = str(user["_id"])
    user["id"] = user["_id"]
    user["token_version"] = int(user.get("token_version", 0))
    if "password" in user:
        del user["password"]
    return user
