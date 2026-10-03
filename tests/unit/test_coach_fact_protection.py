"""Unit tests for AI Coach Fact-Protection and Adversarial LLM Hallucination Resistance.

Verifies:
- The LLM cannot alter or overwrite authoritative backend telemetry (reps, form score, duration)
- Adversarial LLM responses attempting to inject invented reps, scores, PRs, or calories do not corrupt DB state
- Backend verified metrics remain the single source of truth across workouts, sessions, and analytics
- Ollama timeouts, connection failures, and malformed outputs safely trigger deterministic fallback
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

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
    CoachProviderError,
    CoachProviderUnavailableError,
)
from backend.app.services.coach_service import CoachService
from backend.app.services.workout_service import WorkoutService


class AdversarialHallucinatingProvider(BaseCoachProvider):
    """
    Simulates a rogue/adversarial LLM that outputs completely fabricated metrics:
    - Claims 100 reps (actual was 5)
    - Claims 99.9 form score (actual was 65.0)
    - Claims 3000 calories burned and invented world-record PRs
    """

    async def generate_coaching(self, context):
        return CoachStructuredOutput(
            summary=(
                "INCREDIBLE! You completed 100 reps with a perfect 99.9% form score, "
                "burning 3000 calories! New World Record set in overhead squats!"
            ),
            strengths=["World-record velocity", "100 unbroken repetitions"],
            areas_to_improve=["Nothing to improve, you are superhuman"],
            next_session_focus="Attempt 200 reps next time",
            safety_note="No rest needed",
        )


class MalformedResponseProvider(BaseCoachProvider):
    """Simulates an LLM throwing parsing or schema errors."""

    async def generate_coaching(self, context):
        raise CoachProviderError("JSONDecodeError: Unterminated string at line 1")


class TimeoutProvider(BaseCoachProvider):
    """Simulates Ollama request timing out."""

    async def generate_coaching(self, context):
        raise CoachProviderUnavailableError("Request timed out after 30.0s")


@pytest.fixture
async def verified_workout(db_session: AsyncSession, test_user: User) -> Workout:
    """Sets up a workout with rigorously verified ground truth telemetry."""
    workout = Workout(
        user_id=test_user.id,
        status=WorkoutStatus.COMPLETED,
        total_duration_sec=120.0,
        overall_form_score=65.0,  # Mediocre form score
        total_calories=85.0,
        notes="Ground truth telemetry session",
    )
    db_session.add(workout)
    await db_session.flush()

    sess = ExerciseSession(
        workout_id=workout.id,
        exercise_name="squat",
        session_order=1,
        completed_reps=5,  # Exactly 5 reps
        valid_reps=3,      # Exactly 3 valid
        invalid_reps=2,    # Exactly 2 invalid
        average_form_score=65.0,
    )
    db_session.add(sess)
    await db_session.flush()

    for i in range(5):
        rep = ExerciseResult(
            exercise_session_id=sess.id,
            rep_number=i + 1,
            is_valid=1 if i < 3 else 0,
            form_score=75.0 if i < 3 else 50.0,
            duration_sec=2.0,
        )
        db_session.add(rep)

    await db_session.commit()
    await db_session.refresh(workout)
    return workout


# ==============================================================================
# 1. Adversarial Fact-Protection Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_adversarial_llm_cannot_corrupt_database_metrics(
    db_session: AsyncSession,
    test_user: User,
    verified_workout: Workout,
):
    """
    Even when the LLM hallucinates 100 reps and 3000 calories, the verified
    database metrics (reps, score, duration, calories) must remain strictly unaltered.
    """
    adversarial_provider = AdversarialHallucinatingProvider()

    # Generate coaching with adversarial provider
    feedback = await CoachService.generate_feedback(
        db=db_session,
        session_id=verified_workout.id,
        user_id=test_user.id,
        provider=adversarial_provider,
    )

    # 1. Feedback was created and captured LLM text
    assert feedback.workout_id == verified_workout.id
    assert "100 reps" in feedback.summary

    # 2. RELOAD workout and verify telemetry in DB is completely UNTOUCHED
    reloaded_workout = await WorkoutService.get_workout(
        db=db_session,
        workout_id=verified_workout.id,
        user_id=test_user.id,
    )
    assert reloaded_workout.overall_form_score == 65.0  # NOT 99.9
    assert reloaded_workout.total_calories == 85.0      # NOT 3000
    assert reloaded_workout.total_duration_sec == 120.0

    # 3. Exercise session counts must remain unchanged
    sess = reloaded_workout.exercise_sessions[0]
    assert sess.completed_reps == 5                     # NOT 100
    assert sess.valid_reps == 3                         # NOT 100
    assert sess.invalid_reps == 2
    assert sess.average_form_score == 65.0


@pytest.mark.asyncio
async def test_coach_context_construction_preserves_verified_facts(
    db_session: AsyncSession,
    test_user: User,
    verified_workout: Workout,
):
    """
    Verifies that the CoachContext generated by backend for the LLM prompt
    always contains ground-truth backend numbers, never invented data.
    """
    reloaded_workout = await WorkoutService.get_workout(
        db=db_session,
        workout_id=verified_workout.id,
        user_id=test_user.id,
    )
    context = CoachService.build_coach_context(
        workout=reloaded_workout,
        target_focus="form_improvement",
    )

    assert context.workout_id == verified_workout.id
    assert context.total_reps == 5
    assert context.valid_reps == 3
    assert context.invalid_reps == 2
    assert context.overall_form_score == 65.0
    assert context.total_duration_sec == 120.0
    assert len(context.exercises) == 1
    assert context.exercises[0].exercise_name == "squat"
    assert context.exercises[0].total_reps == 5


# ==============================================================================
# 2. Fallback Reliability on Malformed Responses & Timeouts
# ==============================================================================


@pytest.mark.asyncio
async def test_coach_fallback_on_malformed_llm_output(
    db_session: AsyncSession,
    test_user: User,
    verified_workout: Workout,
):
    """When LLM returns malformed output, service engages deterministic rule-based fallback."""
    feedback = await CoachService.generate_feedback(
        db=db_session,
        session_id=verified_workout.id,
        user_id=test_user.id,
        provider=MalformedResponseProvider(),
    )

    assert feedback.workout_id == verified_workout.id
    dto = CoachService.to_response_dto(feedback)
    assert dto.is_fallback is True
    # Fallback summary should deterministically report true rep counts (5 total reps)
    assert "5 total repetitions" in feedback.summary


@pytest.mark.asyncio
async def test_coach_fallback_on_llm_timeout(
    db_session: AsyncSession,
    test_user: User,
    verified_workout: Workout,
):
    """When LLM times out, service engages deterministic rule-based fallback without throwing 500."""
    feedback = await CoachService.generate_feedback(
        db=db_session,
        session_id=verified_workout.id,
        user_id=test_user.id,
        provider=TimeoutProvider(),
    )

    assert feedback.workout_id == verified_workout.id
    dto = CoachService.to_response_dto(feedback)
    assert dto.is_fallback is True
    assert "5 total repetitions" in feedback.summary
