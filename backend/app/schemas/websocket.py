import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class WSClientMessageType(str, Enum):
    POSE_FRAME = "pose_frame"
    START_SESSION = "start_session"
    STOP_SESSION = "stop_session"
    PING = "ping"
    SET_EXERCISE = "set_exercise"
    RESET = "reset"


class WSServerMessageType(str, Enum):
    CONNECTED = "connected"
    ANALYSIS_RESULT = "analysis_result"
    SESSION_STARTED = "session_started"
    SESSION_STOPPED = "session_stopped"
    PONG = "pong"
    ERROR = "error"


class LandmarkPoint(BaseModel):
    x: float
    y: float
    z: float = 0.0
    visibility: float = 1.0


class PoseFramePayload(BaseModel):
    type: str = WSClientMessageType.POSE_FRAME.value
    timestamp: float | None = None
    timestamp_ms: float | None = None
    exercise: str | None = None
    exercise_override: str | None = None
    landmarks: list[LandmarkPoint] | list[dict[str, Any]] | list[list[float]] = Field(
        default_factory=list
    )

    def get_timestamp_ms(self) -> float:
        if self.timestamp_ms is not None:
            return float(self.timestamp_ms)
        if self.timestamp is not None:
            # If timestamp is in seconds (e.g. < 1e11), convert to ms
            return float(self.timestamp * 1000.0 if self.timestamp < 1e11 else self.timestamp)
        return float(time.time() * 1000.0)

    def get_effective_exercise(self) -> str | None:
        return self.exercise or self.exercise_override


class StartSessionPayload(BaseModel):
    type: str = WSClientMessageType.START_SESSION.value
    exercise: str = "squat"
    workout_id: str | None = None
    notes: str | None = None


class StopSessionPayload(BaseModel):
    type: str = WSClientMessageType.STOP_SESSION.value
    session_id: str | None = None
    save_to_db: bool = True


class PingPayload(BaseModel):
    type: str = WSClientMessageType.PING.value
    timestamp: float | None = None


class SetExercisePayload(BaseModel):
    type: str = WSClientMessageType.SET_EXERCISE.value
    exercise: str


class ResetPayload(BaseModel):
    type: str = WSClientMessageType.RESET.value


# --- Server Message Models ---


class ConnectedResponse(BaseModel):
    type: str = WSServerMessageType.CONNECTED.value
    status: str = "authenticated"
    user_id: str
    session_id: str
    message: str = "WebSocket connected and authenticated successfully."


class AnalysisResultResponse(BaseModel):
    type: str = WSServerMessageType.ANALYSIS_RESULT.value
    timestamp: float
    timestamp_ms: float
    exercise: str
    detected_exercise: str
    stage: str
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
    issues: list[dict[str, Any]] = Field(default_factory=list)
    audio_cue: str | None = None
    rep_duration_sec: float = 0.0
    metrics: dict[str, Any] = Field(default_factory=dict)


class SessionStartedResponse(BaseModel):
    type: str = WSServerMessageType.SESSION_STARTED.value
    session_id: str
    exercise: str
    workout_id: str | None = None
    started_at: str


class SessionStoppedResponse(BaseModel):
    type: str = WSServerMessageType.SESSION_STOPPED.value
    session_id: str
    summary: dict[str, Any]


class PongResponse(BaseModel):
    type: str = WSServerMessageType.PONG.value
    timestamp: float


class ErrorResponse(BaseModel):
    type: str = WSServerMessageType.ERROR.value
    code: str
    message: str
