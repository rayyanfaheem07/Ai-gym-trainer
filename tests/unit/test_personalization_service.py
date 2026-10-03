from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.base import get_utc_now
from backend.app.models.user import User
from backend.app.models.workout import (
    ExerciseResult,
    ExerciseSession,
    ExerciseType,
    FormIssue,
    IssueSeverity,
    Workout,
    WorkoutStatus,
)
from backend.app.schemas.profile import (
    CoachingStyleEnum,
    ExperienceLevelEnum,
    FitnessGoalEnum,
    PersonalTrendDirection,
    PreferredFocusEnum,
    UserProfileUpdate,
)
from backend.app.services.personalization_service import PersonalizationService


@pytest.mark.asyncio
async def test_get_profile_creates_default(db_session: AsyncSession, test_user: User):
    profile = await PersonalizationService.get_profile(db_session, user_id=test_user.id)
    assert profile.user_id == test_user.id
    assert profile.fitness_goal == "general_fitness"
    assert profile.experience_level == "beginner"
    assert profile.preferred_focus == "form"
    assert profile.coaching_style == "supportive"


@pytest.mark.asyncio
async def test_update_profile(db_session: AsyncSession, test_user: User):
    update_data = UserProfileUpdate(
        fitness_goal=FitnessGoalEnum.STRENGTH,
        experience_level=ExperienceLevelEnum.ADVANCED,
        preferred_focus=PreferredFocusEnum.STRENGTH,
        coaching_style=CoachingStyleEnum.TECHNICAL,
    )
    updated = await PersonalizationService.update_profile(
        db_session, user_id=test_user.id, update_data=update_data
    )
    assert updated.fitness_goal == "strength"
    assert updated.experience_level == "advanced"
    assert updated.preferred_focus == "strength"
    assert updated.coaching_style == "technical"

    # Verify retrieval returns the updated values
    fetched = await PersonalizationService.get_profile(db_session, user_id=test_user.id)
    assert fetched.fitness_goal == "strength"
    assert fetched.coaching_style == "technical"


@pytest.mark.asyncio
async def test_trends_with_zero_workouts(db_session: AsyncSession, test_user: User):
    history, trends = await PersonalizationService.calculate_personal_trends(
        db_session, user_id=test_user.id
    )
    assert history.workouts_completed == 0
    assert history.has_previous_workouts is False
    assert history.comparison_available is False
    assert len(trends) == 1
    assert trends[0].direction == PersonalTrendDirection.INSUFFICIENT_DATA
    assert trends[0].sufficient_data is False


@pytest.mark.asyncio
async def test_trends_with_one_workout(db_session: AsyncSession, test_user: User):
    now = get_utc_now()
    workout = Workout(
        user_id=test_user.id,
        status=WorkoutStatus.COMPLETED,
        started_at=now,
        overall_form_score=85.0,
        total_duration_sec=300.0,
    )
    db_session.add(workout)
    await db_session.commit()

    history, trends = await PersonalizationService.calculate_personal_trends(
        db_session, user_id=test_user.id
    )
    assert history.workouts_completed == 1
    assert history.has_previous_workouts is True
    assert history.comparison_available is False
    assert history.recent_form_score == 85.0
    assert trends[0].direction == PersonalTrendDirection.INSUFFICIENT_DATA
    assert trends[0].sufficient_data is False


@pytest.mark.asyncio
async def test_trends_improving_metric(db_session: AsyncSession, test_user: User):
    base_time = get_utc_now() - timedelta(days=5)

    # Baseline workout 1: Form score 75%
    w1 = Workout(
        user_id=test_user.id,
        status=WorkoutStatus.COMPLETED,
        started_at=base_time,
        overall_form_score=75.0,
        total_duration_sec=300.0,
    )
    s1 = ExerciseSession(
        workout=w1,
        exercise_name=ExerciseType.SQUAT.value,
        completed_reps=10,
        valid_reps=7,
        invalid_reps=3,
        average_form_score=75.0,
    )
    db_session.add_all([w1, s1])

    # Recent workout 2: Form score 88%
    w2 = Workout(
        user_id=test_user.id,
        status=WorkoutStatus.COMPLETED,
        started_at=base_time + timedelta(days=2),
        overall_form_score=88.0,
        total_duration_sec=300.0,
    )
    s2 = ExerciseSession(
        workout=w2,
        exercise_name=ExerciseType.SQUAT.value,
        completed_reps=10,
        valid_reps=9,
        invalid_reps=1,
        average_form_score=88.0,
    )
    db_session.add_all([w2, s2])
    await db_session.commit()

    history, trends = await PersonalizationService.calculate_personal_trends(
        db_session, user_id=test_user.id
    )
    assert history.workouts_completed == 2
    assert history.has_previous_workouts is True
    assert history.comparison_available is True
    assert history.recent_form_score == 88.0
    assert history.previous_form_score == 75.0

    form_trend = next(t for t in trends if t.metric == "overall_form_score")
    assert form_trend.direction == PersonalTrendDirection.IMPROVING
    assert form_trend.change == 13.0
    assert form_trend.sufficient_data is True


@pytest.mark.asyncio
async def test_trends_declining_metric(db_session: AsyncSession, test_user: User):
    base_time = get_utc_now() - timedelta(days=5)

    # Baseline workout 1: Form score 90%
    w1 = Workout(
        user_id=test_user.id,
        status=WorkoutStatus.COMPLETED,
        started_at=base_time,
        overall_form_score=90.0,
        total_duration_sec=300.0,
    )
    s1 = ExerciseSession(
        workout=w1,
        exercise_name=ExerciseType.PUSHUP.value,
        completed_reps=10,
        valid_reps=10,
        invalid_reps=0,
        average_form_score=90.0,
    )
    db_session.add_all([w1, s1])

    # Recent workout 2: Form score 80%
    w2 = Workout(
        user_id=test_user.id,
        status=WorkoutStatus.COMPLETED,
        started_at=base_time + timedelta(days=2),
        overall_form_score=80.0,
        total_duration_sec=300.0,
    )
    s2 = ExerciseSession(
        workout=w2,
        exercise_name=ExerciseType.PUSHUP.value,
        completed_reps=10,
        valid_reps=7,
        invalid_reps=3,
        average_form_score=80.0,
    )
    db_session.add_all([w2, s2])
    await db_session.commit()

    history, trends = await PersonalizationService.calculate_personal_trends(
        db_session, user_id=test_user.id
    )
    form_trend = next(t for t in trends if t.metric == "overall_form_score")
    assert form_trend.direction == PersonalTrendDirection.DECLINING
    assert form_trend.change == -10.0
    assert form_trend.sufficient_data is True


@pytest.mark.asyncio
async def test_trends_stable_metric(db_session: AsyncSession, test_user: User):
    base_time = get_utc_now() - timedelta(days=5)

    # Baseline workout 1: Form score 85%
    w1 = Workout(
        user_id=test_user.id,
        status=WorkoutStatus.COMPLETED,
        started_at=base_time,
        overall_form_score=85.0,
        total_duration_sec=300.0,
    )
    db_session.add(w1)

    # Recent workout 2: Form score 85.5%
    w2 = Workout(
        user_id=test_user.id,
        status=WorkoutStatus.COMPLETED,
        started_at=base_time + timedelta(days=2),
        overall_form_score=85.5,
        total_duration_sec=300.0,
    )
    db_session.add(w2)
    await db_session.commit()

    history, trends = await PersonalizationService.calculate_personal_trends(
        db_session, user_id=test_user.id
    )
    form_trend = next(t for t in trends if t.metric == "overall_form_score")
    assert form_trend.direction == PersonalTrendDirection.STABLE
    assert form_trend.sufficient_data is True


@pytest.mark.asyncio
async def test_recurring_form_issues_detection(db_session: AsyncSession, test_user: User):
    base_time = get_utc_now() - timedelta(days=10)

    # Session 1 with knee_valgus fault
    w1 = Workout(user_id=test_user.id, started_at=base_time, status=WorkoutStatus.COMPLETED)
    s1 = ExerciseSession(workout=w1, exercise_name="squat", completed_reps=1, valid_reps=0, invalid_reps=1)
    r1 = ExerciseResult(exercise_session=s1, rep_number=1, is_valid=0)
    iss1 = FormIssue(exercise_result=r1, issue_code="knee_valgus", severity=IssueSeverity.MODERATE, feedback_text="Knees collapsing inward")
    db_session.add_all([w1, s1, r1, iss1])

    # Session 2 also with knee_valgus fault
    w2 = Workout(user_id=test_user.id, started_at=base_time + timedelta(days=2), status=WorkoutStatus.COMPLETED)
    s2 = ExerciseSession(workout=w2, exercise_name="squat", completed_reps=1, valid_reps=0, invalid_reps=1)
    r2 = ExerciseResult(exercise_session=s2, rep_number=1, is_valid=0)
    iss2 = FormIssue(exercise_result=r2, issue_code="knee_valgus", severity=IssueSeverity.MODERATE, feedback_text="Knees collapsing inward")
    db_session.add_all([w2, s2, r2, iss2])

    await db_session.commit()

    history, trends = await PersonalizationService.calculate_personal_trends(
        db_session, user_id=test_user.id
    )
    assert "knee_valgus" in history.recurring_form_issues
