from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
from backend.app.core.config import settings
from backend.app.core.errors import AuthenticationError


def hash_password(password: str) -> str:
    """
    Hashes a plaintext password using bcrypt with salt.
    """
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plaintext password against a stored bcrypt hash.
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def create_access_token(
    subject: str,
    email: str,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Generates a cryptographically signed JWT access token.
    """
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": str(subject),
        "email": str(email),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "iss": settings.PROJECT_NAME,
    }

    encoded_jwt = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decodes and validates a JWT access token.
    Raises AuthenticationError on signature, expiration, or format failures.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.PROJECT_NAME,
        )
        sub = payload.get("sub")
        if not sub:
            raise AuthenticationError("Token payload is missing subject claim ('sub').")
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Authentication token has expired. Please log in again.")
    except jwt.InvalidTokenError as e:
        raise AuthenticationError(f"Invalid authentication token: {e!s}")
