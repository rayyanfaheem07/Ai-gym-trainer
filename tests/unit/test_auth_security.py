from datetime import timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.errors import AuthenticationError, DuplicateEntityError
from backend.app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from backend.app.models.user import User
from backend.app.schemas.auth import UserLogin, UserRegister, UserResponse
from backend.app.services.auth_service import AuthService


def test_password_hashing_and_verification():
    raw_password = "SuperSecureP@ssw0rd!2026"
    hashed = hash_password(raw_password)

    # 1. Verify bcrypt format
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
    assert hashed != raw_password

    # 2. Verify correct password matches
    assert verify_password(raw_password, hashed) is True

    # 3. Verify incorrect password fails
    assert verify_password("WrongPassword123!", hashed) is False

    # 4. Verify empty or corrupted hash fails gracefully
    assert verify_password(raw_password, "invalid_hash_string") is False


def test_jwt_creation_and_decoding():
    token = create_access_token(subject="user_12345", email="test@gymtrainer.com")
    assert isinstance(token, str)

    payload = decode_access_token(token)
    assert payload["sub"] == "user_12345"
    assert payload["email"] == "test@gymtrainer.com"
    assert "exp" in payload
    assert "iat" in payload


def test_jwt_expired_token_rejected():
    expired_token = create_access_token(
        subject="user_12345",
        email="test@gymtrainer.com",
        expires_delta=-timedelta(minutes=10),
    )

    with pytest.raises(AuthenticationError) as exc_info:
        decode_access_token(expired_token)
    assert "expired" in str(exc_info.value).lower()


def test_jwt_tampered_or_invalid_signature_rejected():
    token = create_access_token(subject="user_12345", email="test@gymtrainer.com")
    tampered_token = token[:-5] + "ABCDE"

    with pytest.raises(AuthenticationError):
        decode_access_token(tampered_token)

    with pytest.raises(AuthenticationError):
        decode_access_token("completely.malformed.token")


def test_user_registration_schema_validation():
    # 1. Valid registration
    valid_payload = UserRegister(
        email=" Athlete@Example.COM  ",
        password="ValidPassword123!",
        full_name="Alex Athlete",
    )
    assert valid_payload.email == "athlete@example.com"

    # 2. Invalid emails rejected
    invalid_emails = ["not-an-email", "@missinguser.com", "user@", "spaces in@mail.com"]
    for bad_email in invalid_emails:
        with pytest.raises(ValidationError):
            UserRegister(email=bad_email, password="ValidPassword123!")

    # 3. Weak passwords rejected (<8 chars, purely numbers, purely letters)
    with pytest.raises(ValidationError):
        UserRegister(email="valid@test.com", password="short")

    with pytest.raises(ValidationError):
        UserRegister(email="valid@test.com", password="1234567890")

    with pytest.raises(ValidationError):
        UserRegister(email="valid@test.com", password="allletterspassword")


def test_user_response_schema_never_exposes_password():
    user = User(
        id="usr_999",
        email="safe@gym.com",
        password_hash="$2b$12$eX4mpL3H4sh3dStr1ng",
        full_name="Safe User",
        is_active=True,
    )

    response_model = UserResponse.model_validate(user)
    dumped = response_model.model_dump()

    assert "password" not in dumped
    assert "password_hash" not in dumped
    assert dumped["id"] == "usr_999"
    assert dumped["email"] == "safe@gym.com"


@pytest.mark.asyncio
async def test_auth_service_registration_and_login_flow(db_session: AsyncSession):
    auth_service = AuthService(db_session)

    # 1. Register new user
    register_data = UserRegister(
        email="new_lifter@gym.com",
        password="StrongLifterPass1!",
        full_name="New Lifter",
    )
    user = await auth_service.register(register_data)
    assert user.id is not None
    assert user.email == "new_lifter@gym.com"
    assert user.password_hash != "StrongLifterPass1!"
    assert verify_password("StrongLifterPass1!", user.password_hash)

    # 2. Duplicate registration rejected
    with pytest.raises(DuplicateEntityError):
        await auth_service.register(register_data)

    # 3. Login success
    login_data = UserLogin(email="NEW_LIFTER@GYM.COM", password="StrongLifterPass1!")
    token, logged_user = await auth_service.authenticate(login_data)
    assert token is not None
    assert logged_user.id == user.id

    # 4. Login with wrong password rejected
    wrong_pw = UserLogin(email="new_lifter@gym.com", password="WrongPassword999!")
    with pytest.raises(AuthenticationError):
        await auth_service.authenticate(wrong_pw)

    # 5. Login with non-existent email rejected
    non_existent = UserLogin(email="unknown@gym.com", password="StrongLifterPass1!")
    with pytest.raises(AuthenticationError):
        await auth_service.authenticate(non_existent)
