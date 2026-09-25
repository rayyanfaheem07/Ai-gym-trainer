from datetime import datetime, timezone

from backend.app.models.workout import (
    ExerciseResult,
    ExerciseSession,
    FormIssue,
    IssueSeverity,
    Workout,
    WorkoutStatus,
)
from backend.app.services.coach_service import CoachService


def test_coach_context_builder_single_set():
    workout = Workout(
        id="workout-ctx-01",
        user_id="user-123",
        status=WorkoutStatus.COMPLETED,
        started_at=datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc),
        total_duration_sec=320.5,
        overall_form_score=88.0,
        notes="Morning Squat Session",
    )

    sess = ExerciseSession(
        id="sess-01",
        workout_id=workout.id,
        exercise_name="squat",
        session_order=1,
        completed_reps=10,
        valid_reps=8,
        invalid_reps=2,
        average_form_score=88.0,
        average_tempo_sec=2.4,
    )

    # Rep 1: valid
    r1 = ExerciseResult(
        id="rep-01",
        exercise_session_id=sess.id,
        rep_number=1,
        is_valid=1,
        form_score=95.0,
        duration_sec=2.3,
        faults_detected=[],
    )

    # Rep 2: invalid with shallow_depth
    r2 = ExerciseResult(
        id="rep-02",
        exercise_session_id=sess.id,
        rep_number=2,
        is_valid=0,
        form_score=75.0,
        duration_sec=2.5,
        faults_detected=["shallow_depth"],
    )
    iss1 = FormIssue(
        id="issue-01",
        exercise_result_id=r2.id,
        issue_code="shallow_depth",
        severity=IssueSeverity.MODERATE,
        feedback_text="Squat depth was above parallel",
    )
    r2.form_issues = [iss1]

    # Rep 3: invalid with shallow_depth and knee_valgus
    r3 = ExerciseResult(
        id="rep-03",
        exercise_session_id=sess.id,
        rep_number=3,
        is_valid=0,
        form_score=70.0,
        duration_sec=2.4,
        faults_detected=["shallow_depth", "knee_valgus"],
    )
    iss2 = FormIssue(
        id="issue-02",
        exercise_result_id=r3.id,
        issue_code="shallow_depth",
        severity=IssueSeverity.MODERATE,
        feedback_text="Squat depth was above parallel",
    )
    iss3 = FormIssue(
        id="issue-03",
        exercise_result_id=r3.id,
        issue_code="knee_valgus",
        severity=IssueSeverity.SEVERE,
        feedback_text="Knees caved inwards during ascent",
    )
    r3.form_issues = [iss2, iss3]

    sess.results = [r1, r2, r3]
    workout.exercise_sessions = [sess]

    # Build context
    ctx = CoachService.build_coach_context(workout, target_focus="depth_consistency")

    assert ctx.workout_id == "workout-ctx-01"
    assert ctx.total_reps == 10
    assert ctx.valid_reps == 8
    assert ctx.invalid_reps == 2
    assert ctx.total_duration_sec == 320.5
    assert ctx.overall_form_score == 88.0
    assert ctx.target_focus == "depth_consistency"
    assert len(ctx.exercises) == 1
    assert ctx.exercises[0].exercise_name == "squat"

    # Verify form issues aggregation
    assert len(ctx.top_form_issues) == 2
    top_issue = ctx.top_form_issues[0]
    assert top_issue.issue_type == "shallow_depth"
    assert top_issue.count == 2
    assert "Squat depth was above parallel" in top_issue.feedback_samples

    second_issue = ctx.top_form_issues[1]
    assert second_issue.issue_type == "knee_valgus"
    assert second_issue.count == 1
    assert second_issue.severity == "severe"


def test_coach_context_builder_multi_exercise():
    workout = Workout(
        id="workout-multi",
        user_id="user-456",
        status=WorkoutStatus.COMPLETED,
        total_duration_sec=600.0,
        overall_form_score=92.0,
    )

    s1 = ExerciseSession(
        id="s1",
        workout_id=workout.id,
        exercise_name="pushup",
        session_order=1,
        completed_reps=15,
        valid_reps=14,
        invalid_reps=1,
        average_form_score=90.0,
        average_tempo_sec=1.8,
    )
    s1.results = []

    s2 = ExerciseSession(
        id="s2",
        workout_id=workout.id,
        exercise_name="bicep_curl",
        session_order=2,
        completed_reps=12,
        valid_reps=12,
        invalid_reps=0,
        average_form_score=94.0,
        average_tempo_sec=2.2,
    )
    s2.results = []

    workout.exercise_sessions = [s1, s2]

    ctx = CoachService.build_coach_context(workout)

    assert ctx.total_reps == 27
    assert ctx.valid_reps == 26
    assert ctx.invalid_reps == 1
    assert len(ctx.exercises) == 2
    assert ctx.exercises[0].exercise_name == "pushup"
    assert ctx.exercises[1].exercise_name == "bicep_curl"
    assert len(ctx.top_form_issues) == 0


def test_coach_context_builder_empty_workout():
    workout = Workout(
        id="workout-empty",
        user_id="user-789",
        status=WorkoutStatus.COMPLETED,
        total_duration_sec=0.0,
        overall_form_score=0.0,
    )
    workout.exercise_sessions = []

    ctx = CoachService.build_coach_context(workout)
    assert ctx.workout_id == "workout-empty"
    assert ctx.total_reps == 0
    assert ctx.valid_reps == 0
    assert ctx.invalid_reps == 0
    assert len(ctx.exercises) == 0
    assert len(ctx.top_form_issues) == 0
