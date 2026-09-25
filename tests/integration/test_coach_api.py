from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.user import User
from backend.app.models.workout import (
    ExerciseResult,
    ExerciseSession,
    Workout,
    WorkoutStatus,
)
from backend.app.schemas.coach import CoachStructuredOutput
from backend.app.services.coach_provider import CoachProviderUnavailableError


@pytest.fixture
async def user_workout(db_session: AsyncSession, test_user: User) -> Workout:
    workout = Workout(
        user_id=test_user.id,
        status=WorkoutStatus.COMPLETED,
        total_duration_sec=300.0,
        overall_form_score=88.5,
    )
    db_session.add(workout)
    await db_session.flush()

    sess = ExerciseSession(
        workout_id=workout.id,
        exercise_name="squat",
        session_order=1,
        completed_reps=10,
        valid_reps=8,
        invalid_reps=2,
        average_form_score=88.5,
    )
    db_session.add(sess)
    await db_session.flush()

    rep = ExerciseResult(
        exercise_session_id=sess.id,
        rep_number=1,
        is_valid=1,
        form_score=90.0,
        duration_sec=2.5,
    )
    db_session.add(rep)
    await db_session.commit()
    await db_session.refresh(workout)
    return workout


@pytest.fixture
async def second_user_workout(db_session: AsyncSession, second_user: User) -> Workout:
    workout = Workout(
        user_id=second_user.id,
        status=WorkoutStatus.COMPLETED,
        total_duration_sec=200.0,
        overall_form_score=95.0,
    )
    db_session.add(workout)
    await db_session.commit()
    await db_session.refresh(workout)
    return workout


@pytest.mark.asyncio
async def test_coach_endpoint_unauthenticated(
    async_client: AsyncClient, user_workout: Workout
):
    # Missing Bearer token should be rejected with 401
    resp = await async_client.post(
        "/api/v1/coach/evaluate",
        json={"session_id": user_workout.id},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_coach_session_endpoint_unauthenticated(
    async_client: AsyncClient, user_workout: Workout
):
    resp = await async_client.post(f"/api/v1/coach/session/{user_workout.id}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_coach_user_isolation(
    authenticated_async_client: AsyncClient,
    second_user_workout: Workout,
):
    # Primary user attempts to access second user's workout
    resp = await authenticated_async_client.post(
        "/api/v1/coach/evaluate",
        json={"session_id": second_user_workout.id},
    )
    # Should be rejected with 403 Forbidden
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_coach_evaluate_success_with_mocked_ollama(
    authenticated_async_client: AsyncClient,
    user_workout: Workout,
):
    mock_output = CoachStructuredOutput(
        summary="Solid squat workout completed with 10 total reps.",
        strengths=["Good control on eccentric descent"],
        areas_to_improve=["Ensure full hip extension at top"],
        next_session_focus="Focus on driving hips evenly",
        safety_note="Keep knees stable throughout the ascent",
    )

    with patch(
        "backend.app.services.coach_service.OllamaCoachProvider.generate_coaching",
        new_callable=AsyncMock,
    ) as mock_generate:
        mock_generate.return_value = mock_output
        resp = await authenticated_async_client.post(
            "/api/v1/coach/evaluate",
            json={"session_id": user_workout.id, "target_focus": "form_improvement"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == user_workout.id
        assert data["summary"] == mock_output.summary
        assert data["strengths"] == mock_output.strengths
        assert data["areas_to_improve"] == mock_output.areas_to_improve
        assert data["next_session_focus"] == mock_output.next_session_focus
        assert data["safety_note"] == mock_output.safety_note
        assert data["is_fallback"] is False


@pytest.mark.asyncio
async def test_coach_evaluate_session_endpoint(
    authenticated_async_client: AsyncClient,
    user_workout: Workout,
):
    mock_output = CoachStructuredOutput(
        summary="Session completed successfully.",
        strengths=["Consistent tempo"],
        areas_to_improve=["Watch knee tracking"],
        next_session_focus="Warm up ankles and hips",
        safety_note="Maintain neutral spine",
    )

    with patch(
        "backend.app.services.coach_service.OllamaCoachProvider.generate_coaching",
        new_callable=AsyncMock,
    ) as mock_generate:
        mock_generate.return_value = mock_output
        resp = await authenticated_async_client.post(
            f"/api/v1/coach/session/{user_workout.id}?target_focus=tempo",
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == user_workout.id
        assert data["summary"] == mock_output.summary


@pytest.mark.asyncio
async def test_coach_evaluate_offline_fallback(
    authenticated_async_client: AsyncClient,
    user_workout: Workout,
):
    # Simulate Ollama being completely offline (CoachProviderUnavailableError)
    with patch(
        "backend.app.services.coach_service.OllamaCoachProvider.generate_coaching",
        side_effect=CoachProviderUnavailableError("Connection refused to Ollama"),
    ):
        resp = await authenticated_async_client.post(
            "/api/v1/coach/evaluate",
            json={"session_id": user_workout.id},
        )

        # Must NOT return 500 internal server error
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == user_workout.id
        assert data["is_fallback"] is True
        assert "fallback" in data["llm_model"].lower()
        # Verify deterministic facts are included
        assert "10 total repetitions" in data["summary"]


@pytest.mark.asyncio
async def test_coach_get_existing_coaching(
    authenticated_async_client: AsyncClient,
    user_workout: Workout,
):
    # First generate feedback (using fallback or mock)
    with patch(
        "backend.app.services.coach_service.OllamaCoachProvider.generate_coaching",
        side_effect=CoachProviderUnavailableError("Offline"),
    ):
        post_resp = await authenticated_async_client.post(
            f"/api/v1/coach/session/{user_workout.id}",
        )
        assert post_resp.status_code == 200

    # Then retrieve via GET
    get_resp = await authenticated_async_client.get(
        f"/api/v1/coach/session/{user_workout.id}",
    )
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["session_id"] == user_workout.id
    assert "10 total repetitions" in data["summary"]
