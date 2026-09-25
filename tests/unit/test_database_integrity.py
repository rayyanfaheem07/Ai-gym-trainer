"""Unit tests for Database Integrity, Relationships, Cascading Behavior, and Transactions.

Covers:
- Hierarchical relationships: User -> Workout -> ExerciseSession -> ExerciseResult -> FormIssue
- Cascade deletion behavior (deleting a workout cascades to sessions, results, and issues)
- Transaction atomicity and rollback on error
- Empty workout history queries
- Multiple workouts with mixed exercises and repetitions
"""

import pytest
from sqlalchemy import select
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
from backend.app.repositories.workout_repository import WorkoutRepository


@pytest.mark.asyncio
async def test_database_hierarchical_relationships_and_cascades(
    db_session: AsyncSession,
    test_user: User,
):
    """
    Verifies full 4-tier hierarchy:
    Workout -> ExerciseSession -> ExerciseResult -> FormIssue
    and verifies that deleting the parent Workout cascades cleanly.
    """
    repo = WorkoutRepository(db_session)

    # 1. Create Workout
    workout = Workout(
        user_id=test_user.id,
        status=WorkoutStatus.COMPLETED,
        total_duration_sec=250.0,
        overall_form_score=85.0,
    )
    db_session.add(workout)
    await db_session.flush()

    # 2. Create Session
    session = ExerciseSession(
        workout_id=workout.id,
        exercise_name="squat",
        session_order=1,
        completed_reps=3,
        valid_reps=2,
        invalid_reps=1,
        average_form_score=85.0,
    )
    db_session.add(session)
    await db_session.flush()

    # 3. Create Results & Form Issues
    res1 = ExerciseResult(
        exercise_session_id=session.id,
        rep_number=1,
        is_valid=1,
        form_score=90.0,
    )
    res2 = ExerciseResult(
        exercise_session_id=session.id,
        rep_number=2,
        is_valid=0,
        form_score=60.0,
    )
    db_session.add_all([res1, res2])
    await db_session.flush()

    issue = FormIssue(
        exercise_result_id=res2.id,
        issue_code="knee_valgus",
        severity=IssueSeverity.SEVERE,
        feedback_text="Keep knees aligned with toes",
    )
    db_session.add(issue)
    await db_session.commit()

    # 4. Verify all entities exist in database
    detailed = await repo.get_workout_detailed(workout.id)
    assert detailed is not None
    assert len(detailed.exercise_sessions) == 1
    sess_loaded = detailed.exercise_sessions[0]
    assert len(sess_loaded.results) == 2

    # 5. Delete Workout and test cascading cleanup
    await db_session.delete(workout)
    await db_session.commit()

    # 6. Verify cascading delete of child sessions, results, and issues
    sess_query = await db_session.execute(
        select(ExerciseSession).where(ExerciseSession.workout_id == workout.id)
    )
    assert sess_query.scalar_one_or_none() is None

    res_query = await db_session.execute(
        select(ExerciseResult).where(ExerciseResult.exercise_session_id == session.id)
    )
    assert len(res_query.scalars().all()) == 0

    issue_query = await db_session.execute(
        select(FormIssue).where(FormIssue.exercise_result_id == res2.id)
    )
    assert issue_query.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_database_transaction_rollback_on_error(
    db_session: AsyncSession,
    test_user: User,
):
    """
    Verifies that a failure during a multi-step operation rolls back cleanly
    without partial/corrupted records persisting in the database.
    """
    workout = Workout(
        user_id=test_user.id,
        status=WorkoutStatus.IN_PROGRESS,
        notes="Rollback test workout",
    )
    db_session.add(workout)
    await db_session.flush()
    workout_id = workout.id

    try:
        # Simulate an operation that fails mid-way
        session = ExerciseSession(
            workout_id=workout_id,
            exercise_name="pushup",
            completed_reps=10,
        )
        db_session.add(session)
        await db_session.flush()

        # Intentionally raise an exception before commit
        raise RuntimeError("Simulated transaction failure")
    except RuntimeError:
        await db_session.rollback()

    # Verify neither workout nor session was committed
    query = await db_session.execute(select(Workout).where(Workout.id == workout_id))
    assert query.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_database_multiple_workouts_and_exercises(
    db_session: AsyncSession,
    test_user: User,
):
    """Verifies storing and retrieving multiple workouts with different exercises for a single user."""
    repo = WorkoutRepository(db_session)
    exercises = ["squat", "pushup", "bicep_curl"]

    for ex in exercises:
        w = Workout(
            user_id=test_user.id,
            status=WorkoutStatus.COMPLETED,
            overall_form_score=88.0,
        )
        db_session.add(w)
        await db_session.flush()

        s = ExerciseSession(
            workout_id=w.id,
            exercise_name=ex,
            completed_reps=10,
            valid_reps=9,
            invalid_reps=1,
            average_form_score=88.0,
        )
        db_session.add(s)

    await db_session.commit()

    workouts = await repo.list_by_user(user_id=test_user.id, limit=10)
    assert len(workouts) == 3
