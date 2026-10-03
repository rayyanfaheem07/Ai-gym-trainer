import enum
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FitnessGoalEnum(str, enum.Enum):
    STRENGTH = "strength"
    MUSCLE_GAIN = "muscle_gain"
    FAT_LOSS = "fat_loss"
    GENERAL_FITNESS = "general_fitness"
    ENDURANCE = "endurance"


class ExperienceLevelEnum(str, enum.Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class PreferredFocusEnum(str, enum.Enum):
    FORM = "form"
    STRENGTH = "strength"
    CONSISTENCY = "consistency"
    ENDURANCE = "endurance"
    BALANCED = "balanced"


class CoachingStyleEnum(str, enum.Enum):
    CONCISE = "concise"
    SUPPORTIVE = "supportive"
    DETAILED = "detailed"
    TECHNICAL = "technical"


class PersonalTrendDirection(str, enum.Enum):
    IMPROVING = "improving"
    DECLINING = "declining"
    STABLE = "stable"
    INSUFFICIENT_DATA = "insufficient_data"


class UserProfileUpdate(BaseModel):
    fitness_goal: FitnessGoalEnum | None = Field(default=None, description="Target fitness objective")
    experience_level: ExperienceLevelEnum | None = Field(default=None, description="Lifting or exercise experience")
    preferred_focus: PreferredFocusEnum | None = Field(default=None, description="Primary emphasis during workouts")
    coaching_style: CoachingStyleEnum | None = Field(default=None, description="Desired coaching tone and depth")


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    fitness_goal: str
    experience_level: str
    preferred_focus: str
    coaching_style: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PersonalTrend(BaseModel):
    """
    Structured, deterministic performance trend comparing recent vs historical metrics.
    Calculated exclusively in the backend without LLM hallucination.
    """
    metric: str = Field(description="Name of the tracked metric, e.g. overall_form_score")
    exercise: str | None = Field(default=None, description="Specific exercise name or None for global")
    current_value: float | None = Field(default=None, description="Current or recent performance score")
    previous_value: float | None = Field(default=None, description="Baseline or previous performance score")
    change: float | None = Field(default=None, description="Difference between current and previous values")
    direction: PersonalTrendDirection = Field(
        default=PersonalTrendDirection.INSUFFICIENT_DATA,
        description="Trend classification: improving, declining, stable, or insufficient_data",
    )
    sufficient_data: bool = Field(
        default=False,
        description="True if enough historical sessions exist to establish a valid trend",
    )
    message: str | None = Field(
        default=None,
        description="Deterministic human-readable explanation of the trend",
    )


class PersonalHistoryContext(BaseModel):
    """
    Verified historical workout telemetry summarizing user longitudinal performance.
    """
    workouts_completed: int = Field(default=0, description="Total lifetime workouts completed")
    recent_workout_count: int = Field(default=0, description="Workouts completed in the last 30 days")
    recent_form_score: float | None = Field(default=None, description="Average form score over recent sessions")
    previous_form_score: float | None = Field(default=None, description="Average form score over prior baseline sessions")
    recurring_form_issues: list[str] = Field(
        default_factory=list,
        description="Form faults observed repeatedly across multiple past workouts",
    )
    most_practiced_exercise: str | None = Field(default=None, description="Exercise performed most frequently")
    valid_rep_percentage: float | None = Field(default=None, description="Overall lifetime valid repetition rate")
    has_previous_workouts: bool = Field(default=False, description="True if at least one prior workout exists")
    comparison_available: bool = Field(default=False, description="True if baseline comparison could be computed")


class PersonalizationContext(BaseModel):
    """
    Unified personalization container passed to CoachService.
    """
    profile: UserProfileResponse
    history: PersonalHistoryContext
    trends: list[PersonalTrend] = Field(default_factory=list)
