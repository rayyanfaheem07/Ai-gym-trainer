import pytest

from backend.app.schemas.coach import (
    CoachContext,
    ExerciseSessionContext,
    FormIssueSummary,
)
from backend.app.schemas.profile import (
    PersonalHistoryContext,
    PersonalTrend,
    PersonalTrendDirection,
    UserProfileResponse,
)
from backend.app.services.coach_provider import (
    DeterministicFallbackCoachProvider,
    OllamaCoachProvider,
)


@pytest.mark.asyncio
async def test_deterministic_fallback_personalization_strengths_and_style():
    profile = UserProfileResponse(
        id="prof-1",
        user_id="user-1",
        fitness_goal="strength",
        experience_level="advanced",
        preferred_focus="strength",
        coaching_style="technical",
    )
    history = PersonalHistoryContext(
        workouts_completed=5,
        recent_workout_count=3,
        recurring_form_issues=["shallow_depth"],
        has_previous_workouts=True,
        comparison_available=True,
    )
    trends = [
        PersonalTrend(
            metric="overall_form_score",
            change=5.5,
            direction=PersonalTrendDirection.IMPROVING,
            sufficient_data=True,
            message="Form score improved by +5.5%",
        )
    ]

    context = CoachContext(
        workout_id="wk-100",
        total_duration_sec=360.0,
        overall_form_score=88.0,
        total_reps=12,
        valid_reps=10,
        invalid_reps=2,
        exercises=[
            ExerciseSessionContext(
                exercise_name="squat",
                total_reps=12,
                valid_reps=10,
                invalid_reps=2,
                average_form_score=88.0,
                form_issues=[
                    FormIssueSummary(issue_type="shallow_depth", count=2, severity="moderate")
                ],
            )
        ],
        top_form_issues=[
            FormIssueSummary(issue_type="shallow_depth", count=2, severity="moderate")
        ],
        profile=profile,
        personal_history=history,
        personal_trends=trends,
    )

    provider = DeterministicFallbackCoachProvider()
    output = await provider.generate_coaching(context)

    # Verify technical phrasing and summary
    assert "Biomechanical validity" in output.summary or "form integrity" in output.summary

    # Verify improving trend is acknowledged in strengths
    assert any("Positive progression" in s for s in output.strengths)

    # Verify recurring fault note in areas to improve
    assert any("recurring pattern" in a for a in output.areas_to_improve)

    # Verify advanced safety note
    assert "kinetic load" in (output.safety_note or "")


def test_ollama_prompt_payload_includes_personalization():
    profile = UserProfileResponse(
        id="prof-2",
        user_id="user-2",
        fitness_goal="fat_loss",
        experience_level="beginner",
        preferred_focus="consistency",
        coaching_style="concise",
    )
    history = PersonalHistoryContext(
        workouts_completed=3,
        recent_workout_count=2,
        recurring_form_issues=["forward_lean"],
        has_previous_workouts=True,
        comparison_available=True,
    )
    trends = [
        PersonalTrend(
            metric="overall_form_score",
            change=-3.0,
            direction=PersonalTrendDirection.DECLINING,
            sufficient_data=True,
            message="Form score declined by 3.0%",
        )
    ]

    context = CoachContext(
        workout_id="wk-200",
        total_duration_sec=200.0,
        overall_form_score=80.0,
        total_reps=8,
        valid_reps=6,
        invalid_reps=2,
        exercises=[],
        profile=profile,
        personal_history=history,
        personal_trends=trends,
    )

    provider = OllamaCoachProvider()
    payload = provider._build_prompt_payload(context)

    assert "ATHLETE FITNESS PROFILE & PREFERENCES" in payload
    assert "Fitness Goal: fat_loss" in payload
    assert "Coaching Style: concise" in payload
    assert "VERIFIED PERSONAL HISTORY & TRENDS" in payload
    assert "Lifetime Workouts Completed: 3" in payload
    assert "Recurring Biomechanical Faults: forward_lean" in payload
