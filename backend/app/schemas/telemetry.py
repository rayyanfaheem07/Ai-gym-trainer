from typing import Any

from pydantic import BaseModel, Field


class LandmarkPoint(BaseModel):
    x: float
    y: float
    z: float = 0.0
    visibility: float = 1.0


class PoseTelemetryInput(BaseModel):
    timestamp_ms: float = 0.0
    landmarks: list[LandmarkPoint] | None = Field(default_factory=list)
    exercise_override: str | None = None
    type: str | None = None  # e.g., "telemetry", "set_exercise", "reset"


class JointAngleData(BaseModel):
    joint_name: str
    angle_deg: float
    is_within_normal_rom: bool = True


class RealTimeFeedbackOutput(BaseModel):
    timestamp_ms: float
    detected_exercise: str
    stage: str  # e.g., "standing", "descending", "bottom", "ascending", "completed_rep", etc.
    rep_count: int = 0
    valid_reps: int = 0
    invalid_reps: int = 0
    is_valid_rep: bool = True
    confidence: float = 0.0
    current_angles: dict[str, float] = Field(default_factory=dict)
    primary_angle: float = 0.0
    form_score: float = 100.0
    warnings: list[str] = Field(default_factory=list)
    feedback: list[str] = Field(default_factory=list)
    audio_cue: str | None = None
    rep_duration_sec: float = 0.0
    metrics: dict[str, Any] = Field(default_factory=dict)


# Aliases
StreamClientMessage = PoseTelemetryInput
StreamFeedbackResponse = RealTimeFeedbackOutput
