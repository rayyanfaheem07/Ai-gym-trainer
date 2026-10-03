from datetime import datetime

from backend.app.schemas.profile import (
    PersonalHistoryContext,
    PersonalTrend,
    UserProfileResponse,
)
from pydantic import BaseModel, ConfigDict, Field


class FormIssueSummary(BaseModel):
    """Aggregated summary of biomechanical form deviations."""
    issue_type: str = Field(description="Normalized issue identifier or code")
    count: int = Field(ge=1, description="Number of times this issue occurred")
    severity: str = Field(default="moderate", description="Highest or representative severity")
    feedback_samples: list[str] = Field(
        default_factory=list,
        description="Sample deterministic feedback strings generated for this issue",
    )


class ExerciseSessionContext(BaseModel):
    """Fact-checked metrics for an individual exercise set within the session."""
    exercise_name: str
    session_order: int = 1
    total_reps: int = 0
    valid_reps: int = 0
    invalid_reps: int = 0
    average_form_score: float = 0.0
    average_tempo_sec: float = 0.0
    form_issues: list[FormIssueSummary] = Field(default_factory=list)


class CoachContext(BaseModel):
    """
    Secure, bounded factual context provided to LLM and coach providers.
    Ensures that ONLY verified database facts reach the coaching layer.
    """
    workout_id: str
    session_date: datetime | str | None = None
    total_duration_sec: float = 0.0
    overall_form_score: float = 0.0
    total_reps: int = 0
    valid_reps: int = 0
    invalid_reps: int = 0
    exercises: list[ExerciseSessionContext] = Field(default_factory=list)
    top_form_issues: list[FormIssueSummary] = Field(default_factory=list)
    target_focus: str = "form_improvement"
    historical_notes: str | None = None
    profile: UserProfileResponse | None = None
    personal_history: PersonalHistoryContext | None = None
    personal_trends: list[PersonalTrend] = Field(default_factory=list)


class CoachStructuredOutput(BaseModel):
    """Structured Pydantic model for LLM generation and validation."""
    summary: str = Field(description="Concise 1-3 sentence performance summary")
    strengths: list[str] = Field(
        default_factory=list,
        description="Observed movement strengths grounded in telemetry",
    )
    areas_to_improve: list[str] = Field(
        default_factory=list,
        description="Targeted form corrections based on recorded faults",
    )
    next_session_focus: str | None = Field(
        default=None,
        description="Key cue or emphasis for the athlete's upcoming workout",
    )
    safety_note: str | None = Field(
        default=None,
        description="Biomechanical safety reminder (non-medical)",
    )


class CoachFeedbackRequest(BaseModel):
    session_id: str = Field(max_length=64, description="Target workout session identifier")
    target_focus: str | None = Field(default="form_improvement", max_length=64, description="Primary focus area for the coaching assessment")


class CoachFeedbackResponse(BaseModel):
    """Public API response returned to clients."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    llm_model: str
    summary: str
    strengths: list[str] = Field(default_factory=list)
    areas_to_improve: list[str] = Field(default_factory=list)
    recovery_advice: str | None = None
    next_session_focus: str | None = None
    safety_note: str | None = None
    is_fallback: bool = False
    created_at: datetime
