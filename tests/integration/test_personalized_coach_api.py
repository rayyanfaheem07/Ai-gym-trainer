import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.user import User
from backend.app.models.workout import (
    ExerciseResult,
    ExerciseSession,
    ExerciseType,
    Workout,
    WorkoutStatus,
)


@pytest.mark.asyncio
async def test_personalized_coach_evaluation_flow(
    authenticated_async_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
):
    # 1. Update user profile to strength & concise
    await authenticated_async_client.put(
        "/api/v1/profile",
        json={
            "fitness_goal": "strength",
            "experience_level": "intermediate",
            "preferred_focus": "form",
            "coaching_style": "concise",
        },
    )

    # 2. Seed a completed workout session
    workout = Workout(
        user_id=test_user.id,
        status=WorkoutStatus.COMPLETED,
        overall_form_score=87.5,
        total_duration_sec=240.0,
    )
    sess = ExerciseSession(
        workout=workout,
        exercise_name=ExerciseType.SQUAT.value,
        completed_reps=8,
        valid_reps=7,
        invalid_reps=1,
        average_form_score=87.5,
    )
    rep = ExerciseResult(
        exercise_session=sess,
        rep_number=1,
        is_valid=1,
        form_score=90.0,
    )
    db_session.add_all([workout, sess, rep])
    await db_session.commit()

    # 3. Call AI Coach evaluate endpoint
    response = await authenticated_async_client.post(
        f"/api/v1/coach/session/{workout.id}",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == workout.id
    assert "summary" in data
    assert len(data["strengths"]) > 0
    assert data["is_fallback"] is True or "llama3.2" in data["llm_model"]


@pytest.mark.asyncio
async def test_cross_user_coach_evaluation_forbidden(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    second_auth_headers: dict[str, str],
):
    # Workout belongs to test_user (User 1)
    workout = Workout(
        user_id=test_user.id,
        status=WorkoutStatus.COMPLETED,
        overall_form_score=80.0,
    )
    db_session.add(workout)
    await db_session.commit()

    # User 2 attempts to trigger AI coach evaluation on User 1's workout
    response = await async_client.post(
        f"/api/v1/coach/session/{workout.id}",
        headers=second_auth_headers,
    )
    # Must be rejected with 403 or 404 (ownership violation)
    assert response.status_code in [403, 404]
