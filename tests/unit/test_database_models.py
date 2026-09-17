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


@pytest.mark.asyncio
async def test_database_models_hierarchy_and_relationships(db_session: AsyncSession):
    # 1. Create User
    user = User(email="testuser@aigym.com", full_name="Test Athlete")
    db_session.add(user)
    await db_session.flush()
    assert user.id is not None

    # 2. Create Workout
    workout = Workout(
        user_id=user.id,
        status=WorkoutStatus.IN_PROGRESS,
        notes="Leg day heavy session",
    )
    db_session.add(workout)
    await db_session.flush()
    assert workout.id is not None
    assert workout.user_id == user.id

    # 3. Create ExerciseSession
    exercise_session = ExerciseSession(
        workout_id=workout.id,
        exercise_name="squat",
        session_order=1,
        target_reps=10,
        completed_reps=5,
        valid_reps=4,
        invalid_reps=1,
        average_form_score=88.5,
    )
    db_session.add(exercise_session)
    await db_session.flush()
    assert exercise_session.id is not None
    assert exercise_session.workout_id == workout.id

    # 4. Create ExerciseResult
    exercise_result = ExerciseResult(
        exercise_session_id=exercise_session.id,
        rep_number=1,
        is_valid=1,
        form_score=92.0,
        duration_sec=2.4,
        eccentric_duration_sec=1.4,
        concentric_duration_sec=1.0,
        min_joint_angle=82.0,
        max_joint_angle=175.0,
        faults_detected=["knee_valgus_minor"],
    )
    db_session.add(exercise_result)
    await db_session.flush()
    assert exercise_result.id is not None

    # 5. Create FormIssue
    form_issue = FormIssue(
        exercise_result_id=exercise_result.id,
        issue_code="knee_valgus",
        severity=IssueSeverity.MINOR,
        feedback_text="Keep your knees tracking directly over your toes during ascent.",
        timestamp_ms=2400.0,
    )
    db_session.add(form_issue)
    await db_session.commit()

    from sqlalchemy.orm import selectinload

    # Query back and verify relationships
    stmt = (
        select(Workout)
        .where(Workout.id == workout.id)
        .options(
            selectinload(Workout.user),
            selectinload(Workout.exercise_sessions)
            .selectinload(ExerciseSession.results)
            .selectinload(ExerciseResult.form_issues),
        )
    )
    res = await db_session.execute(stmt)
    fetched_workout = res.scalar_one()

    assert fetched_workout.user.email == "testuser@aigym.com"
    assert len(fetched_workout.exercise_sessions) == 1
    assert fetched_workout.exercise_sessions[0].exercise_name == "squat"
    assert len(fetched_workout.exercise_sessions[0].results) == 1
    assert fetched_workout.exercise_sessions[0].results[0].form_score == 92.0
    assert len(fetched_workout.exercise_sessions[0].results[0].form_issues) == 1
    assert fetched_workout.exercise_sessions[0].results[0].form_issues[0].issue_code == "knee_valgus"


@pytest.mark.asyncio
async def test_database_cascade_delete(db_session: AsyncSession):
    user = User(email="cascade@aigym.com", full_name="Cascade Athlete")
    db_session.add(user)
    await db_session.flush()

    workout = Workout(user_id=user.id, status=WorkoutStatus.IN_PROGRESS)
    db_session.add(workout)
    await db_session.flush()

    session_obj = ExerciseSession(workout_id=workout.id, exercise_name="pushup")
    db_session.add(session_obj)
    await db_session.flush()

    result_obj = ExerciseResult(exercise_session_id=session_obj.id, rep_number=1)
    db_session.add(result_obj)
    await db_session.flush()

    issue_obj = FormIssue(
        exercise_result_id=result_obj.id,
        issue_code="sagging_hips",
        severity=IssueSeverity.SEVERE,
        feedback_text="Engage your core to prevent hip sagging.",
    )
    db_session.add(issue_obj)
    await db_session.commit()

    # Delete workout and verify child records deleted
    await db_session.delete(workout)
    await db_session.commit()

    # Verify children no longer exist
    res_session = await db_session.get(ExerciseSession, session_obj.id)
    assert res_session is None
    res_result = await db_session.get(ExerciseResult, result_obj.id)
    assert res_result is None
    res_issue = await db_session.get(FormIssue, issue_obj.id)
    assert res_issue is None
