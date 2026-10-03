import pytest
from pydantic import ValidationError

from backend.app.schemas.profile import (
    CoachingStyleEnum,
    ExperienceLevelEnum,
    FitnessGoalEnum,
    PersonalHistoryContext,
    PersonalTrend,
    PersonalTrendDirection,
    PreferredFocusEnum,
    UserProfileResponse,
    UserProfileUpdate,
)


def test_user_profile_update_valid_enums():
    update = UserProfileUpdate(
        fitness_goal=FitnessGoalEnum.STRENGTH,
        experience_level=ExperienceLevelEnum.ADVANCED,
        preferred_focus=PreferredFocusEnum.FORM,
        coaching_style=CoachingStyleEnum.TECHNICAL,
    )
    assert update.fitness_goal == FitnessGoalEnum.STRENGTH
    assert update.experience_level == ExperienceLevelEnum.ADVANCED
    assert update.preferred_focus == PreferredFocusEnum.FORM
    assert update.coaching_style == CoachingStyleEnum.TECHNICAL


def test_user_profile_update_partial():
    update = UserProfileUpdate(fitness_goal=FitnessGoalEnum.MUSCLE_GAIN)
    assert update.fitness_goal == FitnessGoalEnum.MUSCLE_GAIN
    assert update.experience_level is None
    assert update.preferred_focus is None
    assert update.coaching_style is None


def test_user_profile_update_invalid_enum_rejected():
    with pytest.raises(ValidationError):
        UserProfileUpdate.model_validate({"fitness_goal": "invalid_goal_123"})

    with pytest.raises(ValidationError):
        UserProfileUpdate.model_validate({"experience_level": "super_expert"})


def test_user_profile_response_serialization():
    data = {
        "id": "prof-123",
        "user_id": "user-456",
        "fitness_goal": "strength",
        "experience_level": "intermediate",
        "preferred_focus": "consistency",
        "coaching_style": "supportive",
    }
    response = UserProfileResponse.model_validate(data)
    assert response.id == "prof-123"
    assert response.fitness_goal == "strength"
    assert response.experience_level == "intermediate"


def test_personal_trend_model_validation():
    trend = PersonalTrend(
        metric="overall_form_score",
        current_value=88.5,
        previous_value=82.0,
        change=6.5,
        direction=PersonalTrendDirection.IMPROVING,
        sufficient_data=True,
        message="Form score improved by +6.5%",
    )
    assert trend.metric == "overall_form_score"
    assert trend.direction == PersonalTrendDirection.IMPROVING
    assert trend.sufficient_data is True
    assert trend.change == 6.5


def test_personal_history_context_defaults():
    history = PersonalHistoryContext()
    assert history.workouts_completed == 0
    assert history.has_previous_workouts is False
    assert history.comparison_available is False
    assert history.recurring_form_issues == []
