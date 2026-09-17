from datetime import datetime

from backend.app.models.workout import IssueSeverity, WorkoutStatus
from pydantic import BaseModel, ConfigDict, Field


class FormIssueCreate(BaseModel):
    issue_code: str
    severity: IssueSeverity = IssueSeverity.MODERATE
    feedback_text: str
    timestamp_ms: float = 0.0


class FormIssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    issue_code: str
    severity: IssueSeverity
    feedback_text: str
    timestamp_ms: float
    created_at: datetime


class ExerciseResultCreate(BaseModel):
    rep_number: int
    is_valid: int = 1
    form_score: float = Field(default=100.0, ge=0.0, le=100.0)
    duration_sec: float = Field(default=0.0, ge=0.0)
    eccentric_duration_sec: float = Field(default=0.0, ge=0.0)
    concentric_duration_sec: float = Field(default=0.0, ge=0.0)
    min_joint_angle: float | None = None
    max_joint_angle: float | None = None
    faults_detected: list[str] = Field(default_factory=list)
    form_issues: list[FormIssueCreate] = Field(default_factory=list)


class ExerciseResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    rep_number: int
    is_valid: int
    form_score: float
    duration_sec: float
    eccentric_duration_sec: float
    concentric_duration_sec: float
    min_joint_angle: float | None = None
    max_joint_angle: float | None = None
    faults_detected: list[str] = Field(default_factory=list)
    form_issues: list[FormIssueResponse] = Field(default_factory=list)
    created_at: datetime


# Backward compatibility aliases
RepRecordCreate = ExerciseResultCreate
RepRecordResponse = ExerciseResultResponse


class ExerciseSessionCreate(BaseModel):
    exercise_name: str | None = None
    exercise_type: str | None = None
    session_order: int = 1
    set_number: int | None = None
    target_reps: int | None = None
    completed_reps: int = Field(default=0, ge=0)
    valid_reps: int = Field(default=0, ge=0)
    invalid_reps: int = Field(default=0, ge=0)
    average_form_score: float = Field(default=0.0, ge=0.0, le=100.0)
    average_tempo_sec: float = Field(default=0.0, ge=0.0)
    results: list[ExerciseResultCreate] = Field(default_factory=list)
    reps: list[RepRecordCreate] = Field(default_factory=list)

    def get_effective_exercise_name(self) -> str:
        return self.exercise_name or self.exercise_type or "squat"

    def get_effective_results(self) -> list[ExerciseResultCreate]:
        return self.results or self.reps


class ExerciseSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workout_id: str
    exercise_name: str
    session_order: int
    status: WorkoutStatus
    target_reps: int | None = None
    completed_reps: int
    valid_reps: int
    invalid_reps: int
    average_form_score: float
    average_tempo_sec: float
    results: list[ExerciseResultResponse] = Field(default_factory=list)
    reps: list[ExerciseResultResponse] = Field(default_factory=list)
    created_at: datetime


# Backward compatibility aliases
ExerciseSetCreate = ExerciseSessionCreate
ExerciseSetResponse = ExerciseSessionResponse


class WorkoutStartRequest(BaseModel):
    user_id: str | None = None
    notes: str | None = None


class WorkoutFinishRequest(BaseModel):
    notes: str | None = None
    total_duration_sec: float | None = Field(default=None, ge=0.0)
    total_calories: float | None = Field(default=None, ge=0.0)
    overall_form_score: float | None = Field(default=None, ge=0.0, le=100.0)


class WorkoutResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str | None = None
    status: WorkoutStatus
    started_at: datetime
    ended_at: datetime | None = None
    total_duration_sec: float
    total_calories: float
    overall_form_score: float
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class WorkoutDetailResponse(WorkoutResponse):
    exercise_sessions: list[ExerciseSessionResponse] = Field(default_factory=list)
    sets: list[ExerciseSessionResponse] = Field(default_factory=list)


class WorkoutListResponse(BaseModel):
    workouts: list[WorkoutResponse]
    total_count: int


# Backward compatibility aliases
WorkoutSessionCreate = WorkoutStartRequest
WorkoutSessionUpdate = WorkoutFinishRequest
WorkoutSessionResponse = WorkoutDetailResponse
