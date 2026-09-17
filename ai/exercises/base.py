from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List

import numpy as np


@dataclass
class ExerciseAnalysisResult:
    """
    Standardized, structured output returned by all exercise analyzers.
    """
    exercise: str
    phase: str
    rep_count: int = 0
    valid_reps: int = 0
    invalid_reps: int = 0
    confidence: float = 0.0
    primary_angle: float = 0.0
    current_angles: Dict[str, float] = field(default_factory=dict)
    form_score: int = 100
    is_valid_rep: bool = True
    issues: List[Dict[str, Any]] = field(default_factory=list)
    feedback: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    rep_duration_sec: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to serializable dictionary matching API schema."""
        return {
            "exercise": self.exercise,
            "phase": self.phase,
            "rep_count": self.rep_count,
            "valid_reps": self.valid_reps,
            "invalid_reps": self.invalid_reps,
            "confidence": round(self.confidence, 3),
            "primary_angle": round(self.primary_angle, 1),
            "current_angles": {k: round(v, 1) for k, v in self.current_angles.items()},
            "form_score": int(self.form_score),
            "is_valid_rep": self.is_valid_rep,
            "issues": self.issues,
            "feedback": self.feedback,
            "metrics": {k: round(v, 3) if isinstance(v, float) else v for k, v in self.metrics.items()},
            "rep_duration_sec": round(self.rep_duration_sec, 2),
        }


@dataclass
class ExerciseState:
    """Legacy state container kept for backward compatibility."""
    stage: str = "START"
    rep_count: int = 0
    valid_reps: int = 0
    invalid_reps: int = 0
    current_form_score: float = 100.0
    primary_angle: float = 0.0
    current_angles: Dict[str, float] = field(default_factory=dict)
    active_warnings: List[str] = field(default_factory=list)
    audio_cue: str | None = None
    rep_duration_sec: float = 0.0


class BaseExerciseAnalyzer(ABC):
    """
    Common Abstract Base Class for all gym exercise analyzers.
    Provides shared utilities for landmark visibility confidence, angle calculation,
    repetition state tracking, form penalty calculation, and feedback generation.
    """

    def __init__(self, name: str):
        self.name = name
        self.rep_count: int = 0
        self.valid_reps: int = 0
        self.invalid_reps: int = 0
        self.state: ExerciseState = ExerciseState()

        # Rep tracking buffer
        self._rep_start_time_ms: float = 0.0
        self._current_rep_trajectory: List[np.ndarray] = []
        self._last_completed_rep_result: ExerciseAnalysisResult | None = None

    @abstractmethod
    def analyze_frame(
        self,
        landmarks: np.ndarray,
        timestamp_ms: float | None = None,
    ) -> ExerciseAnalysisResult:
        """
        Processes normalized 33-point landmarks, updates phase FSM, counts reps,
        and computes explainable form analysis metrics.
        """
        pass

    def evaluate_frame(
        self,
        landmarks: np.ndarray,
        timestamp_ms: float = 0.0,
    ) -> ExerciseState:
        """
        Legacy adapter evaluating frame and populating ExerciseState.
        """
        result = self.analyze_frame(landmarks, timestamp_ms)
        self.state.stage = result.phase
        self.state.rep_count = result.rep_count
        self.state.valid_reps = result.valid_reps
        self.state.invalid_reps = result.invalid_reps
        self.state.current_form_score = float(result.form_score)
        self.state.primary_angle = result.primary_angle
        self.state.current_angles = result.current_angles
        self.state.active_warnings = [issue.get("details", "") for issue in result.issues]
        self.state.audio_cue = result.feedback[0] if result.feedback else None
        self.state.rep_duration_sec = result.rep_duration_sec
        return self.state

    def reset(self) -> None:
        """Reset internal rep counts, trajectory buffers, and state machine."""
        self.rep_count = 0
        self.valid_reps = 0
        self.invalid_reps = 0
        self.state = ExerciseState()
        self._rep_start_time_ms = 0.0
        self._current_rep_trajectory = []
        self._last_completed_rep_result = None

    @staticmethod
    def compute_landmark_confidence(
        landmarks: np.ndarray, indices: List[int]
    ) -> float:
        """Computes mean visibility confidence across specified landmark indices."""
        if landmarks is None or len(landmarks) < 33:
            return 0.0
        confs = [landmarks[idx, 3] if landmarks.shape[1] > 3 else 1.0 for idx in indices]
        return float(np.mean(confs)) if confs else 0.0

    @staticmethod
    def clamp_form_score(score: float) -> int:
        """Clamps score strictly between 0 and 100."""
        return int(max(0, min(100, round(score))))


# Backwards compatibility alias
BaseExercise = BaseExerciseAnalyzer
