
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.errors import EntityNotFoundError, ForbiddenAccessError
from backend.app.models.user import User
from backend.app.models.workout import (
    ExerciseResult,
    ExerciseSession,
    Workout,
    WorkoutStatus,
)
from backend.app.schemas.coach import CoachStructuredOutput
from backend.app.services.coach_provider import (
    BaseCoachProvider,
    CoachProviderUnavailableError,
)
from backend.app.services.coach_service import CoachService


class MockSuccessfulProvider(BaseCoachProvider):
    async def generate_coaching(self, context):
        return CoachStructuredOutput(
            summary=f"Great job on your {context.total_reps} reps!",
            strengths=["Excellent form consistency"],
            areas_to_improve=["Keep core engaged"],
            next_session_focus="Maintain tempo control",
            safety_note="Ensure adequate warm-up",
        )


class MockFailingProvider(BaseCoachProvider):
    async def generate_coaching(self, context):
        raise CoachProviderUnavailableError("Ollama is offline")


@pytest.mark.asyncio
async def test_coach_service_generate_feedback_success(db_session: AsyncSession, test_user: User):
    # Setup test workout
    workout = Workout(
        user_id=test_user.id,
        status=WorkoutStatus.COMPLETED,
        total_duration_sec=180.0,
        overall_form_score=90.0,
    )
    db_session.add(workout)
    await db_session.flush()

    sess = ExerciseSession(
        workout_id=workout.id,
        exercise_name="squat",
        session_order=1,
        completed_reps=10,
        valid_reps=9,
        invalid_reps=1,
        average_form_score=90.0,
    )
    db_session.add(sess)
    await db_session.flush()

    res1 = ExerciseResult(
        exercise_session_id=sess.id,
        rep_number=1,
        is_valid=1,
        form_score=90.0,
        duration_sec=2.0,
    )
    db_session.add(res1)
    await db_session.commit()

    # Generate feedback using mock provider
    feedback = await CoachService.generate_feedback(
        db=db_session,
        session_id=workout.id,
        user_id=test_user.id,
        provider=MockSuccessfulProvider(),
    )

    assert feedback.workout_id == workout.id
    assert "10 reps" in feedback.summary
    assert feedback.strengths == ["Excellent form consistency"]
    assert "Next Session Focus: Maintain tempo control" in (feedback.recovery_advice or "")

    dto = CoachService.to_response_dto(feedback)
    assert dto.session_id == workout.id
    assert dto.next_session_focus == "Maintain tempo control"
    assert dto.safety_note == "Ensure adequate warm-up"
    assert dto.is_fallback is False


@pytest.mark.asyncio
async def test_coach_service_triggers_deterministic_fallback(db_session: AsyncSession, test_user: User):
    workout = Workout(
        user_id=test_user.id,
        status=WorkoutStatus.COMPLETED,
        total_duration_sec=120.0,
        overall_form_score=80.0,
    )
    db_session.add(workout)
    await db_session.flush()

    sess = ExerciseSession(
        workout_id=workout.id,
        exercise_name="pushup",
        session_order=1,
        completed_reps=8,
        valid_reps=6,
        invalid_reps=2,
        average_form_score=80.0,
    )
    db_session.add(sess)
    await db_session.commit()

    # Call with failing provider to test deterministic fallback
    feedback = await CoachService.generate_feedback(
        db=db_session,
        session_id=workout.id,
        user_id=test_user.id,
        provider=MockFailingProvider(),
    )

    assert feedback.workout_id == workout.id
    assert "deterministic-fallback" in feedback.llm_model.lower() or "fallback" in feedback.llm_model.lower()
    assert "8 total repetitions" in feedback.summary
    assert len(feedback.strengths) > 0

    dto = CoachService.to_response_dto(feedback)
    assert dto.is_fallback is True


@pytest.mark.asyncio
async def test_coach_service_rejects_unauthorized_user(
    db_session: AsyncSession, test_user: User, second_user: User
):
    # Workout belongs to test_user
    workout = Workout(
        user_id=test_user.id,
        status=WorkoutStatus.COMPLETED,
    )
    db_session.add(workout)
    await db_session.commit()

    # second_user attempts to generate coaching for test_user's workout
    with pytest.raises(ForbiddenAccessError):
        await CoachService.generate_feedback(
            db=db_session,
            session_id=workout.id,
            user_id=second_user.id,
            provider=MockSuccessfulProvider(),
        )


@pytest.mark.asyncio
async def test_coach_service_nonexistent_workout(db_session: AsyncSession, test_user: User):
    with pytest.raises(EntityNotFoundError):
        await CoachService.generate_feedback(
            db=db_session,
            session_id="non-existent-workout-id",
            user_id=test_user.id,
            provider=MockSuccessfulProvider(),
        )
