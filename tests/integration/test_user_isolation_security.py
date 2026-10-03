"""Integration tests for Backend API Security, Authentication, and Multi-Tenant User Isolation.

Verifies:
- Strict user isolation across workouts, exercise sessions, analytics, trends, coach feedback, and profile
- Prevention of resource-ID manipulation / IDOR attacks (User A specifying User B's IDs)
- Password hash privacy (hashes never exposed in responses)
- Rejection of tampered, expired, or invalid JWTs
- Safe error responses without leaking stack traces or internal filesystem paths
"""

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import create_access_token
from backend.app.models.user import User
from backend.app.models.workout import (
    ExerciseResult,
    ExerciseSession,
    Workout,
    WorkoutStatus,
)


@pytest.fixture
async def user_b_workout(db_session: AsyncSession, second_user: User) -> Workout:
    """Creates a workout owned exclusively by User B (second_user)."""
    workout = Workout(
        user_id=second_user.id,
        status=WorkoutStatus.IN_PROGRESS,
        total_duration_sec=600.0,
        overall_form_score=92.0,
        notes="User B Private Session",
    )
    db_session.add(workout)
    await db_session.flush()

    sess = ExerciseSession(
        workout_id=workout.id,
        exercise_name="pushup",
        session_order=1,
        completed_reps=15,
        valid_reps=14,
        invalid_reps=1,
        average_form_score=92.0,
    )
    db_session.add(sess)
    await db_session.flush()

    rep = ExerciseResult(
        exercise_session_id=sess.id,
        rep_number=1,
        is_valid=1,
        form_score=95.0,
        duration_sec=2.0,
    )
    db_session.add(rep)
    await db_session.commit()
    await db_session.refresh(workout)
    return workout


# ==============================================================================
# 1. Workout Resource Isolation & IDOR Protection
# ==============================================================================


@pytest.mark.asyncio
async def test_user_a_cannot_view_user_b_workout_by_id(
    authenticated_async_client: AsyncClient,
    user_b_workout: Workout,
):
    """User A cannot access User B's workout details via direct ID lookup."""
    resp = await authenticated_async_client.get(f"/api/v1/workouts/{user_b_workout.id}")
    assert resp.status_code == 403
    data = resp.json()
    assert "detail" in data
    assert "permission" in data["detail"].lower() or "forbidden" in data["detail"].lower()
    # Ensure no workout data is leaked
    assert "User B Private Session" not in resp.text


@pytest.mark.asyncio
async def test_user_a_cannot_finish_user_b_workout(
    authenticated_async_client: AsyncClient,
    user_b_workout: Workout,
):
    """User A cannot finish or modify User B's active workout."""
    payload = {
        "overall_form_score": 50.0,
        "notes": "Malicious modification attempt",
    }
    resp = await authenticated_async_client.post(
        f"/api/v1/workouts/{user_b_workout.id}/finish",
        json=payload,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_user_a_workout_list_excludes_user_b_workouts(
    authenticated_async_client: AsyncClient,
    user_b_workout: Workout,
):
    """User A's workout list and history must never contain User B's workouts."""
    # List endpoint
    list_resp = await authenticated_async_client.get("/api/v1/workouts")
    assert list_resp.status_code == 200
    user_a_workouts = list_resp.json()
    assert all(w["id"] != user_b_workout.id for w in user_a_workouts)

    # History endpoint
    hist_resp = await authenticated_async_client.get("/api/v1/workouts/history")
    assert hist_resp.status_code == 200
    hist_items = hist_resp.json()["items"]
    assert all(w["id"] != user_b_workout.id for w in hist_items)


# ==============================================================================
# 2. Analytics & Trend Isolation
# ==============================================================================


@pytest.mark.asyncio
async def test_user_b_workout_does_not_contaminate_user_a_analytics(
    authenticated_async_client: AsyncClient,
    user_b_workout: Workout,
):
    """User B's 15 pushups must not appear in User A's analytics summary or breakdown."""
    summary_resp = await authenticated_async_client.get("/api/v1/analytics/summary")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    # User A has 0 workouts, so total_reps must remain 0
    assert summary["total_reps"] == 0
    assert summary["total_workouts"] == 0

    # Pushup specific analytics
    pushup_resp = await authenticated_async_client.get("/api/v1/analytics/exercises/pushup")
    assert pushup_resp.status_code == 200
    pushup_data = pushup_resp.json()
    assert pushup_data["total_reps"] == 0


# ==============================================================================
# 3. AI Coach Isolation
# ==============================================================================


@pytest.mark.asyncio
async def test_user_a_cannot_request_coaching_for_user_b_workout(
    authenticated_async_client: AsyncClient,
    user_b_workout: Workout,
):
    """User A cannot generate coach feedback for User B's workout."""
    eval_resp = await authenticated_async_client.post(
        "/api/v1/coach/evaluate",
        json={"session_id": user_b_workout.id},
    )
    assert eval_resp.status_code == 403

    session_resp = await authenticated_async_client.post(
        f"/api/v1/coach/session/{user_b_workout.id}"
    )
    assert session_resp.status_code == 403


# ==============================================================================
# 4. Auth, JWT Security & Information Leakage Prevention
# ==============================================================================


@pytest.mark.asyncio
async def test_unauthenticated_requests_fail_safely(async_client: AsyncClient):
    """Endpoints require valid Bearer token and return 401."""
    get_endpoints = [
        "/api/v1/workouts",
        "/api/v1/workouts/history",
        "/api/v1/analytics/summary",
        "/api/v1/analytics/trends",
        "/api/v1/profile",
    ]
    for ep in get_endpoints:
        res = await async_client.get(ep)
        assert res.status_code == 401, f"Expected 401 for GET {ep}, got {res.status_code}"

    # POST endpoints
    post_res = await async_client.post("/api/v1/coach/evaluate", json={"session_id": "any-id"})
    assert post_res.status_code == 401


@pytest.mark.asyncio
async def test_tampered_and_expired_jwt_tokens(
    async_client: AsyncClient,
    test_user: User,
):
    """Tampered or expired tokens are rejected with 401 without 500 error."""
    # 1. Expired token
    expired = create_access_token(
        subject=test_user.id,
        email=test_user.email,
        expires_delta=timedelta(minutes=-10),
    )
    res_exp = await async_client.get(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert res_exp.status_code == 401

    # 2. Tampered token (modified signature)
    valid_token = create_access_token(subject=test_user.id, email=test_user.email)
    tampered = valid_token[:-5] + "XXXXX"
    res_tamp = await async_client.get(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {tampered}"},
    )
    assert res_tamp.status_code == 401


@pytest.mark.asyncio
async def test_sensitive_data_never_leaked_in_responses(
    authenticated_async_client: AsyncClient,
):
    """Password hashes, server paths, and stack traces must never leak into JSON responses."""
    # Profile response
    prof_res = await authenticated_async_client.get("/api/v1/profile")
    assert prof_res.status_code == 200
    assert "password_hash" not in prof_res.text
    assert "hashed_password" not in prof_res.text

    # Trigger validation error with malformed payload
    val_res = await authenticated_async_client.put(
        "/api/v1/profile",
        json={"fitness_goal": "INVALID_GOAL_ENUM_VALUE"},
    )
    assert val_res.status_code == 422
    assert "Traceback" not in val_res.text
    assert "ai_gym.db" not in val_res.text
