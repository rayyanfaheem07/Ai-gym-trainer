import enum
from dataclasses import dataclass
from typing import Any, Dict

import numpy as np

from ai.exercises.base import BaseExerciseAnalyzer, ExerciseAnalysisResult
from ai.form_analysis.engine import FormAnalysisResult, SquatFormAnalysisEngine
from ai.geometry.angles import calculate_angle_2d
from ai.pose.landmarks import LandmarkIndex


class SquatPhase(str, enum.Enum):
    """5-stage Squat State Machine Phases."""
    STANDING = "standing"
    DESCENDING = "descending"
    BOTTOM = "bottom"
    ASCENDING = "ascending"
    COMPLETED_REP = "completed_rep"


@dataclass
class SquatConfig:
    """Configurable thresholds for biomechanical squat analysis."""
    standing_knee_angle: float = 160.0       # Lockout angle (degrees) to qualify as standing
    descending_threshold: float = 145.0      # Knee angle below which descent begins
    bottom_knee_angle: float = 95.0          # Target bottom depth (<= 95 deg is valid parallel/below)
    ascending_threshold: float = 110.0       # Angle above which ascent is confirmed from bottom
    hysteresis_deg: float = 5.0              # Guard band to prevent state oscillation from micro-jitter
    min_bottom_dwell_frames: int = 1         # Minimum frames at bottom to confirm depth
    min_rep_duration_sec: float = 0.5        # Minimum valid time for a full rep (anti-jitter)
    min_landmark_confidence: float = 0.5     # Visibility confidence threshold
    max_safe_torso_lean_deg: float = 45.0    # Forward lean threshold relative to vertical


@dataclass
class SquatAnalysisResult(ExerciseAnalysisResult):
    """Structured output returned from frame-by-frame squat analysis with backwards-compatible angle fields."""
    current_knee_angle: float = 180.0
    current_hip_angle: float = 180.0
    min_knee_angle_in_rep: float = 180.0

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["current_knee_angle"] = round(self.current_knee_angle, 1)
        d["current_hip_angle"] = round(self.current_hip_angle, 1)
        d["min_knee_angle_in_rep"] = round(self.min_knee_angle_in_rep, 1)
        return d


class SquatDetector(BaseExerciseAnalyzer):
    """
    Production-grade Biomechanical Squat Analyzer and 5-stage Finite State Machine.
    Integrates with the explainable Form Analysis Engine.
    """

    def __init__(
        self,
        config: SquatConfig | None = None,
        form_engine: SquatFormAnalysisEngine | None = None,
    ):
        super().__init__(name="squat")
        self.config = config or SquatConfig()
        self.form_engine = form_engine or SquatFormAnalysisEngine()

        self.phase = SquatPhase.STANDING
        self._min_knee_angle: float = 180.0
        self._bottom_frames_count: int = 0
        self._bottom_reached: bool = False
        self._last_form_result: FormAnalysisResult | None = None
        self._last_completed_rep_time_ms: float = 0.0

    def analyze_frame(
        self,
        landmarks: np.ndarray,
        timestamp_ms: float | None = None,
    ) -> SquatAnalysisResult:
        """
        Processes normalized/world 33-point landmarks, updates FSM, and performs form analysis.
        """
        now_ms = timestamp_ms if timestamp_ms is not None else 0.0

        if landmarks is None or len(landmarks) < 33:
            return SquatAnalysisResult(
                exercise="squat",
                phase=self.phase.value,
                rep_count=self.rep_count,
                valid_reps=self.valid_reps,
                invalid_reps=self.invalid_reps,
                confidence=0.0,
                feedback=["No landmarks detected"],
            )

        # 1. Compute Knee & Hip Angles with visibility confidence
        left_knee_conf = min(landmarks[LandmarkIndex.LEFT_HIP, 3], landmarks[LandmarkIndex.LEFT_KNEE, 3], landmarks[LandmarkIndex.LEFT_ANKLE, 3])
        right_knee_conf = min(landmarks[LandmarkIndex.RIGHT_HIP, 3], landmarks[LandmarkIndex.RIGHT_KNEE, 3], landmarks[LandmarkIndex.RIGHT_ANKLE, 3])

        left_knee_angle = calculate_angle_2d(
            landmarks[LandmarkIndex.LEFT_HIP],
            landmarks[LandmarkIndex.LEFT_KNEE],
            landmarks[LandmarkIndex.LEFT_ANKLE],
        )
        right_knee_angle = calculate_angle_2d(
            landmarks[LandmarkIndex.RIGHT_HIP],
            landmarks[LandmarkIndex.RIGHT_KNEE],
            landmarks[LandmarkIndex.RIGHT_ANKLE],
        )

        left_hip_angle = calculate_angle_2d(
            landmarks[LandmarkIndex.LEFT_SHOULDER],
            landmarks[LandmarkIndex.LEFT_HIP],
            landmarks[LandmarkIndex.LEFT_KNEE],
        )
        right_hip_angle = calculate_angle_2d(
            landmarks[LandmarkIndex.RIGHT_SHOULDER],
            landmarks[LandmarkIndex.RIGHT_HIP],
            landmarks[LandmarkIndex.RIGHT_KNEE],
        )

        if left_knee_conf >= self.config.min_landmark_confidence and right_knee_conf >= self.config.min_landmark_confidence:
            knee_angle = (left_knee_angle + right_knee_angle) / 2.0
            hip_angle = (left_hip_angle + right_hip_angle) / 2.0
            overall_conf = float((left_knee_conf + right_knee_conf) / 2.0)
        elif left_knee_conf >= self.config.min_landmark_confidence:
            knee_angle = left_knee_angle
            hip_angle = left_hip_angle
            overall_conf = float(left_knee_conf)
        elif right_knee_conf >= self.config.min_landmark_confidence:
            knee_angle = right_knee_angle
            hip_angle = right_hip_angle
            overall_conf = float(right_knee_conf)
        else:
            return SquatAnalysisResult(
                exercise="squat",
                phase=self.phase.value,
                rep_count=self.rep_count,
                valid_reps=self.valid_reps,
                invalid_reps=self.invalid_reps,
                confidence=float(max(left_knee_conf, right_knee_conf)),
                feedback=["Low tracking confidence on legs"],
            )

        # 2. Finite State Machine (FSM) Transitions
        if self.phase == SquatPhase.COMPLETED_REP:
            self.phase = SquatPhase.STANDING

        # Accumulate trajectory when rep is active
        if self.phase in [SquatPhase.DESCENDING, SquatPhase.BOTTOM, SquatPhase.ASCENDING]:
            self._current_rep_trajectory.append(landmarks.copy())

        if self.phase == SquatPhase.STANDING:
            if knee_angle < (self.config.descending_threshold - self.config.hysteresis_deg):
                self.phase = SquatPhase.DESCENDING
                self._rep_start_time_ms = now_ms
                self._min_knee_angle = knee_angle
                self._bottom_reached = False
                self._bottom_frames_count = 0
                self._current_rep_trajectory = [landmarks.copy()]

        elif self.phase == SquatPhase.DESCENDING:
            if knee_angle < self._min_knee_angle:
                self._min_knee_angle = knee_angle

            if knee_angle <= self.config.bottom_knee_angle:
                self._bottom_frames_count += 1
                if self._bottom_frames_count >= self.config.min_bottom_dwell_frames:
                    self.phase = SquatPhase.BOTTOM
                    self._bottom_reached = True

            elif knee_angle > (self._min_knee_angle + self.config.hysteresis_deg * 2.0):
                self.phase = SquatPhase.ASCENDING

        elif self.phase == SquatPhase.BOTTOM:
            if knee_angle < self._min_knee_angle:
                self._min_knee_angle = knee_angle

            if knee_angle > (self.config.bottom_knee_angle + self.config.hysteresis_deg):
                self.phase = SquatPhase.ASCENDING

        elif self.phase == SquatPhase.ASCENDING:
            if knee_angle >= (self.config.standing_knee_angle - self.config.hysteresis_deg):
                rep_duration = (now_ms - self._rep_start_time_ms) / 1000.0 if self._rep_start_time_ms > 0 else 1.0

                if rep_duration >= self.config.min_rep_duration_sec and self._bottom_reached:
                    self.rep_count += 1
                    # Evaluate full trajectory form
                    form_eval = self.form_engine.analyze_trajectory(self._current_rep_trajectory)
                    self._last_form_result = form_eval

                    is_valid = form_eval.form_score >= 70 and len(form_eval.issues) == 0
                    if is_valid:
                        self.valid_reps += 1
                    else:
                        self.invalid_reps += 1

                    self.phase = SquatPhase.COMPLETED_REP
                    self._last_completed_rep_time_ms = now_ms
                else:
                    self.phase = SquatPhase.STANDING

                self._min_knee_angle = 180.0
                self._bottom_reached = False
                self._current_rep_trajectory = []

            elif knee_angle < (self.config.bottom_knee_angle + self.config.hysteresis_deg):
                self.phase = SquatPhase.BOTTOM

        rep_duration_now = (now_ms - self._rep_start_time_ms) / 1000.0 if self._rep_start_time_ms > 0 else 0.0

        # Frame-level live form feedback
        live_form = self.form_engine.analyze_frame(landmarks)

        current_score = self._last_form_result.form_score if self._last_form_result else live_form.form_score
        current_issues = self._last_form_result.issues if self._last_form_result and self.phase == SquatPhase.COMPLETED_REP else live_form.issues
        current_feedback = self._last_form_result.feedback if self._last_form_result and self.phase == SquatPhase.COMPLETED_REP else live_form.feedback

        return SquatAnalysisResult(
            exercise="squat",
            phase=self.phase.value,
            rep_count=self.rep_count,
            valid_reps=self.valid_reps,
            invalid_reps=self.invalid_reps,
            confidence=overall_conf,
            primary_angle=float(knee_angle),
            current_angles={
                "knee": float(knee_angle),
                "hip": float(hip_angle),
                "left_knee": float(left_knee_angle),
                "right_knee": float(right_knee_angle),
            },
            current_knee_angle=float(knee_angle),
            current_hip_angle=float(hip_angle),
            min_knee_angle_in_rep=float(self._min_knee_angle),
            form_score=current_score,
            is_valid_rep=(len(current_issues) == 0),
            issues=current_issues,
            feedback=current_feedback,
            metrics=live_form.metrics,
            rep_duration_sec=float(rep_duration_now),
        )

    def reset(self):
        """Reset internal counters and FSM state."""
        super().reset()
        self.phase = SquatPhase.STANDING
        self._min_knee_angle = 180.0
        self._bottom_frames_count = 0
        self._bottom_reached = False
        self._last_form_result = None


# Alias for backward compatibility
SquatExercise = SquatDetector
