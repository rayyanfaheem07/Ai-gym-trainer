from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import create_access_token
from backend.app.models.user import User


@pytest.mark.asyncio
async def test_user_registration_success(async_client: AsyncClient, db_session: AsyncSession):
    # 1. Register new user
    payload = {
        "email": "NewUser@Exercise.com",
        "password": "SecurePassword123!",
        "full_name": "New Gym User",
    }
    res = await async_client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201

    data = res.json()
    assert data["email"] == "newuser@exercise.com"
    assert data["full_name"] == "New Gym User"
    assert data["is_active"] is True
    assert "id" in data
    # Ensure password and hash are never exposed
    assert "password" not in data
    assert "password_hash" not in data

    # 2. Check in database that password is stored hashed and NOT plaintext
    stmt = select(User).where(User.email == "newuser@exercise.com")
    result = await db_session.execute(stmt)
    db_user = result.scalar_one_or_none()
    assert db_user is not None
    assert db_user.password_hash != "SecurePassword123!"
    assert db_user.password_hash.startswith("$2b$") or db_user.password_hash.startswith("$2a$")


@pytest.mark.asyncio
async def test_duplicate_registration_rejected(async_client: AsyncClient):
    payload = {
        "email": "duplicate@test.com",
        "password": "Password123!",
        "full_name": "First Instance",
    }
    # Initial registration
    res1 = await async_client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    # Duplicate registration attempt with case variation
    payload_dup = {
        "email": " DUPLICATE@test.com ",
        "password": "Password123!",
        "full_name": "Duplicate Instance",
    }
    res2 = await async_client.post("/api/v1/auth/register", json=payload_dup)
    assert res2.status_code == 409
    data = res2.json()
    assert "already exists" in data["detail"].lower()


@pytest.mark.asyncio
async def test_registration_validation_errors(async_client: AsyncClient):
    # 1. Invalid email
    bad_email_payload = {
        "email": "not-an-email",
        "password": "ValidPassword123!",
    }
    res = await async_client.post("/api/v1/auth/register", json=bad_email_payload)
    assert res.status_code == 422

    # 2. Short / weak password
    short_pw_payload = {
        "email": "test@valid.com",
        "password": "short",
    }
    res = await async_client.post("/api/v1/auth/register", json=short_pw_payload)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_user_login_flow(async_client: AsyncClient):
    # 1. Register user
    reg_payload = {
        "email": "login_test@gym.com",
        "password": "CorrectPassword123!",
        "full_name": "Login Tester",
    }
    reg_res = await async_client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201

    # 2. Login with valid credentials
    login_payload = {
        "email": "LOGIN_TEST@GYM.COM",
        "password": "CorrectPassword123!",
    }
    login_res = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    assert token_data["user"]["email"] == "login_test@gym.com"
    assert "password" not in token_data["user"]
    assert "password_hash" not in token_data["user"]

    # 3. Login with wrong password -> 401
    wrong_payload = {
        "email": "login_test@gym.com",
        "password": "IncorrectPassword999!",
    }
    wrong_res = await async_client.post("/api/v1/auth/login", json=wrong_payload)
    assert wrong_res.status_code == 401

    # 4. Login with non-existent email -> 401 (generic message)
    nonexistent_payload = {
        "email": "nonexistent_ghost@gym.com",
        "password": "CorrectPassword123!",
    }
    ghost_res = await async_client.post("/api/v1/auth/login", json=nonexistent_payload)
    assert ghost_res.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_me_endpoint(
    async_client: AsyncClient,
    test_user: User,
    auth_headers: dict[str, str],
):
    # 1. Access /me without token -> 401
    unauth_res = await async_client.get("/api/v1/auth/me")
    assert unauth_res.status_code == 401

    # 2. Access /me with valid Bearer token -> 200
    auth_res = await async_client.get("/api/v1/auth/me", headers=auth_headers)
    assert auth_res.status_code == 200
    user_data = auth_res.json()
    assert user_data["id"] == test_user.id
    assert user_data["email"] == test_user.email
    assert "password" not in user_data
    assert "password_hash" not in user_data


@pytest.mark.asyncio
async def test_protected_endpoints_token_validation(
    async_client: AsyncClient,
    test_user: User,
    auth_headers: dict[str, str],
):
    # 1. Missing token -> 401
    res_no_token = await async_client.post("/api/v1/workouts/start", json={"notes": "No token test"})
    assert res_no_token.status_code == 401

    # 2. Malformed token -> 401
    malformed_headers = {"Authorization": "Bearer malformed.jwt.token"}
    res_malformed = await async_client.post(
        "/api/v1/workouts/start",
        json={"notes": "Malformed token test"},
        headers=malformed_headers,
    )
    assert res_malformed.status_code == 401

    # 3. Expired token -> 401
    expired_token = create_access_token(
        subject=test_user.id,
        email=test_user.email,
        expires_delta=-timedelta(minutes=30),
    )
    expired_headers = {"Authorization": f"Bearer {expired_token}"}
    res_expired = await async_client.post(
        "/api/v1/workouts/start",
        json={"notes": "Expired token test"},
        headers=expired_headers,
    )
    assert res_expired.status_code == 401

    # 4. Valid token succeeds -> 201
    res_valid = await async_client.post(
        "/api/v1/workouts/start",
        json={"notes": "Valid token test"},
        headers=auth_headers,
    )
    assert res_valid.status_code == 201
    workout = res_valid.json()
    assert workout["user_id"] == test_user.id


@pytest.mark.asyncio
async def test_user_ownership_cross_tenant_isolation(
    async_client: AsyncClient,
    test_user: User,
    second_user: User,
    auth_headers: dict[str, str],
    second_auth_headers: dict[str, str],
):
    # 1. User A starts a workout
    create_res = await async_client.post(
        "/api/v1/workouts/start",
        json={"notes": "User A Private Session"},
        headers=auth_headers,
    )
    assert create_res.status_code == 201
    workout_a_id = create_res.json()["id"]

    # 2. User A can retrieve their own workout
    get_a = await async_client.get(f"/api/v1/workouts/{workout_a_id}", headers=auth_headers)
    assert get_a.status_code == 200

    # 3. User B attempts to retrieve User A's workout -> 403 Forbidden
    get_b = await async_client.get(f"/api/v1/workouts/{workout_a_id}", headers=second_auth_headers)
    assert get_b.status_code == 403

    # 4. User B attempts to finish User A's workout -> 403 Forbidden
    finish_b = await async_client.post(
        f"/api/v1/workouts/{workout_a_id}/finish",
        json={"notes": "Unauthorized finish"},
        headers=second_auth_headers,
    )
    assert finish_b.status_code == 403

    # 5. User B attempts to evaluate User A's workout -> 403 Forbidden
    eval_b = await async_client.post(
        "/api/v1/coach/evaluate",
        json={"session_id": workout_a_id, "target_focus": "form_improvement"},
        headers=second_auth_headers,
    )
    assert eval_b.status_code == 403

    # 6. User A lists workouts and sees only their own workouts
    list_a = await async_client.get("/api/v1/workouts", headers=auth_headers)
    assert list_a.status_code == 200
    a_workouts = list_a.json()
    assert all(w["user_id"] == test_user.id for w in a_workouts)

    # 7. User B lists workouts and does NOT see User A's workout
    list_b = await async_client.get("/api/v1/workouts", headers=second_auth_headers)
    assert list_b.status_code == 200
    b_workouts = list_b.json()
    assert all(w["id"] != workout_a_id for w in b_workouts)
