import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.errors import (
    AIInferenceError,
    EntityNotFoundError,
    ForbiddenAccessError,
    InvalidStateTransitionError,
)
from backend.app.models.user import User
from backend.app.models.workout import WorkoutStatus
from backend.app.schemas.analysis import AnalysisRequest
from backend.app.schemas.workout import WorkoutFinishRequest, WorkoutStartRequest
from backend.app.services.analysis_service import AnalysisService
from backend.app.services.exercise_service import ExerciseService
from backend.app.services.workout_service import WorkoutService


@pytest.mark.asyncio
async def test_exercise_service_supported_exercises():
    response = ExerciseService.get_supported_exercises()
    assert response.count >= 5
    exercise_names = [e.name for e in response.exercises]
    assert "squat" in exercise_names
    assert "pushup" in exercise_names
    assert "bicep_curl" in exercise_names
    assert "lunge" in exercise_names
    assert "shoulder_press" in exercise_names

    squat_item = next(e for e in response.exercises if e.name == "squat")
    assert len(squat_item.target_muscles) > 0
    assert len(squat_item.form_rules) > 0


@pytest.mark.asyncio
async def test_workout_service_lifecycle_and_validation(db_session: AsyncSession):
    user1 = User(email="user1@gym.com")
    user2 = User(email="user2@gym.com")
    db_session.add_all([user1, user2])
    await db_session.commit()

    # 1. Start workout
    start_req = WorkoutStartRequest(user_id=user1.id, notes="Initial test session")
    workout = await WorkoutService.start_workout(db_session, start_req)
    assert workout.id is not None
    assert workout.status == WorkoutStatus.IN_PROGRESS
    assert workout.user_id == user1.id

    # 2. Retrieve workout by owner
    fetched = await WorkoutService.get_workout(db_session, workout.id, user_id=user1.id)
    assert fetched.id == workout.id

    # 3. Retrieve workout by non-owner -> Forbidden
    with pytest.raises(ForbiddenAccessError):
        await WorkoutService.get_workout(db_session, workout.id, user_id=user2.id)

    # 4. Finish workout by non-owner -> Forbidden
    finish_req = WorkoutFinishRequest(overall_form_score=95.0, total_calories=120.0)
    with pytest.raises(ForbiddenAccessError):
        await WorkoutService.finish_workout(db_session, workout.id, finish_req, user_id=user2.id)

    # 5. Finish workout successfully by owner
    finished = await WorkoutService.finish_workout(db_session, workout.id, finish_req, user_id=user1.id)
    assert finished.status == WorkoutStatus.COMPLETED
    assert finished.overall_form_score == 95.0
    assert finished.total_calories == 120.0
    assert finished.ended_at is not None

    # 6. Attempt duplicate finish -> InvalidStateTransitionError
    with pytest.raises(InvalidStateTransitionError):
        await WorkoutService.finish_workout(db_session, workout.id, finish_req, user_id=user1.id)

    # 7. Attempt finish on nonexistent ID -> EntityNotFoundError
    with pytest.raises(EntityNotFoundError):
        await WorkoutService.finish_workout(db_session, "nonexistent-id-12345", finish_req)


@pytest.mark.asyncio
async def test_analysis_service_with_synthetic_landmarks():
    # 33 landmarks for a standing posture
    landmarks = [[0.5, 0.5 + i * 0.01, 0.0, 0.95] for i in range(33)]

    # 1. Analysis with hint
    req = AnalysisRequest(
        landmarks=landmarks,
        exercise_hint="squat",
        timestamp_ms=100.0,
    )
    res = AnalysisService.process_analysis(req)
    assert res.detected_exercise in ["squat", "other"]
    assert res.confidence >= 0.0
    assert 0.0 <= res.form_score <= 100.0
    assert isinstance(res.form_issues, list)

    # 2. Empty landmarks error handling
    with pytest.raises(AIInferenceError):
        bad_req = AnalysisRequest(landmarks=[], exercise_hint="squat")
        AnalysisService.process_analysis(bad_req)
