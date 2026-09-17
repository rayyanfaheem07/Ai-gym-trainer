from pydantic import BaseModel, Field


class LandmarkPoint(BaseModel):
    x: float
    y: float
    z: float = 0.0
    visibility: float = 1.0


class FormIssueItem(BaseModel):
    code: str
    severity: str = "moderate"
    message: str
    timestamp_ms: float = 0.0


class AnalysisRequest(BaseModel):
    landmarks: list[list[float]] | list[LandmarkPoint] | list[list[LandmarkPoint]] = Field(
        description="List of 33 pose landmarks for single frame, or sequence of frames for temporal ML."
    )
    exercise_hint: str | None = Field(
        default=None,
        description="Optional exercise override/hint (e.g. squat, pushup, bicep_curl, lunge, shoulder_press)."
    )
    timestamp_ms: float = Field(
        default=0.0,
        description="Timestamp of frame in milliseconds."
    )


class AnalysisResponse(BaseModel):
    detected_exercise: str = Field(description="Predicted canonical exercise or 'other'")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence of detection")
    probabilities: dict[str, float] = Field(default_factory=dict, description="Class probabilities")
    stage: str = Field(default="idle", description="Current movement phase (e.g. standing, descending, bottom, ascending, completed_rep)")
    rep_count: int = Field(default=0, ge=0, description="Total completed repetitions")
    valid_reps: int = Field(default=0, ge=0, description="Valid repetitions completed")
    invalid_reps: int = Field(default=0, ge=0, description="Invalid repetitions completed")
    form_score: float = Field(default=100.0, ge=0.0, le=100.0, description="Repetition or live form score")
    form_issues: list[FormIssueItem] = Field(default_factory=list, description="Detected biomechanical faults")
    is_stub: bool = Field(default=False, description="Flag indicating if prediction used fallback/stub due to missing trained model")
    model_info: str = Field(default="production", description="Model version / pipeline identifier")
