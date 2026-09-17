from typing import Any

from backend.app.schemas.workout import WorkoutResponse
from pydantic import BaseModel, ConfigDict, Field


class ExerciseBreakdownItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    exercise_name: str
    total_sessions: int = Field(default=0, ge=0)
    total_reps: int = Field(default=0, ge=0)
    valid_reps: int = Field(default=0, ge=0)
    invalid_reps: int = Field(default=0, ge=0)
    accuracy_percentage: float = Field(default=100.0, ge=0.0, le=100.0)
    average_form_score: float = Field(default=0.0, ge=0.0, le=100.0)
    best_form_score: float = Field(default=0.0, ge=0.0, le=100.0)
    total_duration_sec: float = Field(default=0.0, ge=0.0)


class AnalyticsSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_workouts: int = Field(default=0, ge=0)
    total_reps: int = Field(default=0, ge=0)
    total_valid_reps: int = Field(default=0, ge=0)
    total_invalid_reps: int = Field(default=0, ge=0)
    valid_rep_percentage: float = Field(default=100.0, ge=0.0, le=100.0)
    average_form_score: float = Field(default=0.0, ge=0.0, le=100.0)
    total_duration_sec: float = Field(default=0.0, ge=0.0)
    most_practiced_exercise: str | None = None
    recent_workout_count: int = Field(default=0, ge=0)
    exercise_breakdown: list[ExerciseBreakdownItem] = Field(default_factory=list)


class ExerciseAnalyticsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    exercise_name: str
    total_sessions: int = Field(default=0, ge=0)
    total_reps: int = Field(default=0, ge=0)
    valid_reps: int = Field(default=0, ge=0)
    invalid_reps: int = Field(default=0, ge=0)
    valid_rep_percentage: float = Field(default=100.0, ge=0.0, le=100.0)
    average_form_score: float = Field(default=0.0, ge=0.0, le=100.0)
    best_form_score: float = Field(default=0.0, ge=0.0, le=100.0)
    average_duration_sec: float = Field(default=0.0, ge=0.0)
    common_faults: list[dict[str, Any]] = Field(default_factory=list)
    recent_sessions: list[WorkoutResponse] = Field(default_factory=list)


class TrendPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: str
    timestamp: float
    workout_id: str
    exercise_name: str | None = None
    form_score: float = Field(default=0.0, ge=0.0, le=100.0)
    total_reps: int = Field(default=0, ge=0)
    valid_reps: int = Field(default=0, ge=0)
    valid_rep_percentage: float = Field(default=100.0, ge=0.0, le=100.0)
    duration_sec: float = Field(default=0.0, ge=0.0)


class AnalyticsTrendsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    period: str = "all"
    exercise: str | None = None
    total_points: int = 0
    points: list[TrendPoint] = Field(default_factory=list)


class PaginatedWorkoutResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[WorkoutResponse] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1)
    total_pages: int = Field(default=1, ge=0)
