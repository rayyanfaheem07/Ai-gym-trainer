from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.user import User
from backend.app.models.workout import (
    ExerciseResult,
    ExerciseSession,
    FormIssue,
    IssueSeverity,
    Workout,
    WorkoutStatus,
)
from backend.app.services.analytics_service import AnalyticsService


@pytest.mark.asyncio
async def test_analytics_summary_empty_database(db_session: AsyncSession):
    """Verify analytics summary returns safe default zeros when no workouts exist."""
    user = User(
        email="empty_analytics@gym.com",
        password_hash="hashed_pw_test",
        full_name="Empty Athlete",
    )
    db_session.add(user)
    await db_session.commit()

    summary = await AnalyticsService.get_summary(db=db_session, user_id=user.id)

    assert summary.total_workouts == 0
    assert summary.total_reps == 0
    assert summary.total_valid_reps == 0
    assert summary.total_invalid_reps == 0
    assert summary.valid_rep_percentage == 100.0
    assert summary.average_form_score == 0.0
    assert summary.total_duration_sec == 0.0
    assert summary.most_practiced_exercise is None
    assert summary.recent_workout_count == 0
    assert len(summary.exercise_breakdown) == 0


@pytest.mark.asyncio
async def test_analytics_summary_with_real_workouts(db_session: AsyncSession):
    """Verify aggregated statistics across multiple completed workout sessions."""
    user = User(
        email="real_analytics@gym.com",
        password_hash="hashed_pw_test",
        full_name="Power Athlete",
    )
    db_session.add(user)
    await db_session.flush()

    # Workout 1: Squats
    w1 = Workout(
        user_id=user.id,
        status=WorkoutStatus.COMPLETED,
        started_at=datetime.now(UTC) - timedelta(days=2),
        ended_at=datetime.now(UTC) - timedelta(days=2, hours=-1),
        total_duration_sec=360.0,
        overall_form_score=92.0,
    )
    db_session.add(w1)
    await db_session.flush()

    s1 = ExerciseSession(
        workout_id=w1.id,
        exercise_name="squat",
        completed_reps=10,
        valid_reps=9,
        invalid_reps=1,
        average_form_score=92.0,
        average_tempo_sec=2.2,
    )
    db_session.add(s1)
    await db_session.flush()

    # Workout 2: Push-ups
    w2 = Workout(
        user_id=user.id,
        status=WorkoutStatus.COMPLETED,
        started_at=datetime.now(UTC) - timedelta(days=1),
        ended_at=datetime.now(UTC) - timedelta(days=1, hours=-1),
        total_duration_sec=240.0,
        overall_form_score=88.0,
    )
    db_session.add(w2)
    await db_session.flush()

    s2 = ExerciseSession(
        workout_id=w2.id,
        exercise_name="pushup",
        completed_reps=15,
        valid_reps=12,
        invalid_reps=3,
        average_form_score=88.0,
        average_tempo_sec=1.8,
    )
    db_session.add(s2)
    await db_session.commit()

    summary = await AnalyticsService.get_summary(db=db_session, user_id=user.id)

    assert summary.total_workouts == 2
    assert summary.total_reps == 25
    assert summary.total_valid_reps == 21
    assert summary.total_invalid_reps == 4
    assert summary.valid_rep_percentage == 84.0
    assert summary.total_duration_sec == 600.0
    assert summary.recent_workout_count == 2
    assert len(summary.exercise_breakdown) == 2


@pytest.mark.asyncio
async def test_exercise_analytics_and_fault_detection(db_session: AsyncSession):
    """Verify exercise-specific breakdown captures common fault frequencies."""
    user = User(
        email="fault_test@gym.com",
        password_hash="hashed_pw_test",
        full_name="Fault Tester",
    )
    db_session.add(user)
    await db_session.flush()

    w = Workout(
        user_id=user.id,
        status=WorkoutStatus.COMPLETED,
        started_at=datetime.now(UTC),
        total_duration_sec=300.0,
        overall_form_score=85.0,
    )
    db_session.add(w)
    await db_session.flush()

    sess = ExerciseSession(
        workout_id=w.id,
        exercise_name="squat",
        completed_reps=5,
        valid_reps=4,
        invalid_reps=1,
        average_form_score=85.0,
    )
    db_session.add(sess)
    await db_session.flush()

    rep = ExerciseResult(
        exercise_session_id=sess.id,
        rep_number=1,
        is_valid=0,
        form_score=70.0,
        duration_sec=2.5,
    )
    db_session.add(rep)
    await db_session.flush()

    issue = FormIssue(
        exercise_result_id=rep.id,
        issue_code="KNEE_VALGUS",
        severity=IssueSeverity.MODERATE,
        feedback_text="Knees collapsing inward during ascent",
    )
    db_session.add(issue)
    await db_session.commit()

    ex_analytics = await AnalyticsService.get_exercise_analytics(
        db=db_session, user_id=user.id, exercise_name="squat"
    )

    assert ex_analytics.exercise_name == "squat"
    assert ex_analytics.total_sessions == 1
    assert ex_analytics.total_reps == 5
    assert ex_analytics.valid_reps == 4
    assert ex_analytics.invalid_reps == 1
    assert ex_analytics.best_form_score == 85.0
    assert len(ex_analytics.common_faults) == 1
    assert ex_analytics.common_faults[0]["issue_code"] == "KNEE_VALGUS"


@pytest.mark.asyncio
async def test_trends_time_series_points(db_session: AsyncSession):
    """Verify trend data points are properly chronological and accurate."""
    user = User(
        email="trends_test@gym.com",
        password_hash="hashed_pw_test",
        full_name="Trend Tester",
    )
    db_session.add(user)
    await db_session.flush()

    t1 = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
    w1 = Workout(
        user_id=user.id,
        status=WorkoutStatus.COMPLETED,
        started_at=t1,
        total_duration_sec=120.0,
        overall_form_score=90.0,
    )
    db_session.add(w1)
    await db_session.flush()

    s1 = ExerciseSession(
        workout_id=w1.id,
        exercise_name="bicep_curl",
        completed_reps=8,
        valid_reps=8,
        average_form_score=90.0,
    )
    db_session.add(s1)
    await db_session.commit()

    trends = await AnalyticsService.get_trends(db=db_session, user_id=user.id, period="all")

    assert trends.total_points == 1
    point = trends.points[0]
    assert point.date == "2026-09-01"
    assert point.form_score == 90.0
    assert point.total_reps == 8
    assert point.valid_reps == 8
    assert point.valid_rep_percentage == 100.0
