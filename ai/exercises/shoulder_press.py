import enum
from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np

from ai.exercises.base import BaseExerciseAnalyzer, ExerciseAnalysisResult
from ai.geometry.angles import calculate_angle_2d
from ai.geometry.metrics import calculate_vertical_alignment
from ai.pose.landmarks import LandmarkIndex


class ShoulderPressPhase(str, enum.Enum):
    RACK_POSITION = "rack_position"
    ASCENDING = "ascending"
    OVERHEAD_LOCKOUT = "overhead_lockout"
    DESCENDING = "descending"
    COMPLETED_REP = "completed_rep"


@dataclass
class ShoulderPressConfig:
    """Configurable biomechanical thresholds for Overhead / Shoulder Press analysis."""
    rack_elbow_angle: float = 90.0           # Bottom start position at clavicle level (<= 90 deg)
    ascending_threshold: float = 105.0       # Angle above which press begins
    lockout_elbow_angle: float = 155.0       # Overhead lockout target (>= 155 deg)
    descending_threshold: float = 145.0      # Angle below which lowering begins
    max_lumbar_arch_deg: float = 15.0        # Backward torso arch / hyperextension
    asymmetry_threshold_deg: float = 12.0    # Left vs right arm angle delta
    instability_warn_std: float = 0.040      # Lateral wrist sway threshold
    hysteresis_deg: float = 5.0              # Anti-jitter threshold
    min_rep_duration_sec: float = 0.5        # Anti-bounce/jitter time
    min_landmark_confidence: float = 0.45


class ShoulderPressExercise(BaseExerciseAnalyzer):
    """
    Biomechanical Overhead / Shoulder Press Analyzer with 5-phase State Machine,
    elbow extension tracking, shoulder elevation, lumbar hyperextension prevention,
    and actionable coaching cues.
    """

    def __init__(self, config: ShoulderPressConfig | None = None):
        super().__init__(name="shoulder_press")
        self.config = config or ShoulderPressConfig()
        self.phase = ShoulderPressPhase.RACK_POSITION

        self._max_elbow_angle: float = 0.0
        self._min_elbow_angle: float = 180.0
        self._max_torso_lean: float = 0.0
        self._lockout_reached: bool = False
        self._rep_initiated: bool = False

    def analyze_frame(
        self,
        landmarks: np.ndarray,
        timestamp_ms: float | None = None,
    ) -> ExerciseAnalysisResult:
        now_ms = timestamp_ms if timestamp_ms is not None else 0.0

        if landmarks is None or len(landmarks) < 33:
            return ExerciseAnalysisResult(
                exercise="shoulder_press",
                phase=self.phase.value,
                rep_count=self.rep_count,
                valid_reps=self.valid_reps,
                invalid_reps=self.invalid_reps,
                confidence=0.0,
                feedback=["No pose landmarks detected."],
            )

        # 1. Compute Elbow Extension Angles (Shoulder - Elbow - Wrist)
        left_elbow = calculate_angle_2d(
            landmarks[LandmarkIndex.LEFT_SHOULDER],
            landmarks[LandmarkIndex.LEFT_ELBOW],
            landmarks[LandmarkIndex.LEFT_WRIST],
        )
        right_elbow = calculate_angle_2d(
            landmarks[LandmarkIndex.RIGHT_SHOULDER],
            landmarks[LandmarkIndex.RIGHT_ELBOW],
            landmarks[LandmarkIndex.RIGHT_WRIST],
        )
        elbow_angle = (left_elbow + right_elbow) / 2.0
        asymmetry_delta = abs(left_elbow - right_elbow)

        # 2. Shoulder Elevation / Abduction (Hip - Shoulder - Elbow)
        left_shoulder_elev = calculate_angle_2d(
            landmarks[LandmarkIndex.LEFT_HIP],
            landmarks[LandmarkIndex.LEFT_SHOULDER],
            landmarks[LandmarkIndex.LEFT_ELBOW],
        )
        right_shoulder_elev = calculate_angle_2d(
            landmarks[LandmarkIndex.RIGHT_HIP],
            landmarks[LandmarkIndex.RIGHT_SHOULDER],
            landmarks[LandmarkIndex.RIGHT_ELBOW],
        )
        shoulder_elevation = (left_shoulder_elev + right_shoulder_elev) / 2.0

        # 3. Torso Lean / Lumbar Arch
        shoulder_mid = (landmarks[LandmarkIndex.LEFT_SHOULDER, :2] + landmarks[LandmarkIndex.RIGHT_SHOULDER, :2]) / 2.0
        hip_mid = (landmarks[LandmarkIndex.LEFT_HIP, :2] + landmarks[LandmarkIndex.RIGHT_HIP, :2]) / 2.0
        torso_lean = calculate_vertical_alignment(shoulder_mid, hip_mid)

        # Confidence
        conf = self.compute_landmark_confidence(
            landmarks,
            [
                LandmarkIndex.LEFT_SHOULDER, LandmarkIndex.RIGHT_SHOULDER,
                LandmarkIndex.LEFT_ELBOW, LandmarkIndex.RIGHT_ELBOW,
                LandmarkIndex.LEFT_WRIST, LandmarkIndex.RIGHT_WRIST,
                LandmarkIndex.LEFT_HIP, LandmarkIndex.RIGHT_HIP,
            ],
        )

        if conf < self.config.min_landmark_confidence:
            return ExerciseAnalysisResult(
                exercise="shoulder_press",
                phase=self.phase.value,
                rep_count=self.rep_count,
                valid_reps=self.valid_reps,
                invalid_reps=self.invalid_reps,
                confidence=conf,
                feedback=["Low tracking visibility on upper body."],
            )

        # 4. State Machine Transitions
        if self.phase == ShoulderPressPhase.COMPLETED_REP:
            self.phase = ShoulderPressPhase.RACK_POSITION

        if self.phase in [ShoulderPressPhase.ASCENDING, ShoulderPressPhase.OVERHEAD_LOCKOUT, ShoulderPressPhase.DESCENDING]:
            self._current_rep_trajectory.append(landmarks.copy())
            if elbow_angle > self._max_elbow_angle:
                self._max_elbow_angle = elbow_angle
            if elbow_angle < self._min_elbow_angle:
                self._min_elbow_angle = elbow_angle
            if torso_lean > self._max_torso_lean:
                self._max_torso_lean = torso_lean

        if self.phase == ShoulderPressPhase.RACK_POSITION:
            if elbow_angle > (self.config.ascending_threshold + self.config.hysteresis_deg):
                self.phase = ShoulderPressPhase.ASCENDING
                self._rep_start_time_ms = now_ms
                self._max_elbow_angle = elbow_angle
                self._min_elbow_angle = elbow_angle
                self._max_torso_lean = torso_lean
                self._lockout_reached = False
                self._rep_initiated = True
                self._current_rep_trajectory = [landmarks.copy()]

        elif self.phase == ShoulderPressPhase.ASCENDING:
            if elbow_angle >= self.config.lockout_elbow_angle:
                self.phase = ShoulderPressPhase.OVERHEAD_LOCKOUT
                self._lockout_reached = True
            elif elbow_angle < (self._max_elbow_angle - self.config.hysteresis_deg * 2.0):
                self.phase = ShoulderPressPhase.DESCENDING

        elif self.phase == ShoulderPressPhase.OVERHEAD_LOCKOUT:
            if elbow_angle < (self.config.lockout_elbow_angle - self.config.hysteresis_deg):
                self.phase = ShoulderPressPhase.DESCENDING

        elif self.phase == ShoulderPressPhase.DESCENDING:
            if elbow_angle <= (self.config.rack_elbow_angle + self.config.hysteresis_deg):
                rep_duration = (now_ms - self._rep_start_time_ms) / 1000.0 if self._rep_start_time_ms > 0 else 1.0

                if rep_duration >= self.config.min_rep_duration_sec and (self._lockout_reached or self._max_elbow_angle > (self.config.ascending_threshold + 10.0)):
                    self.rep_count += 1

                    # Instability from trajectory
                    wrist_xs = [float((lm[LandmarkIndex.LEFT_WRIST, 0] + lm[LandmarkIndex.RIGHT_WRIST, 0]) / 2.0) for lm in self._current_rep_trajectory]
                    instability_std = float(np.std(wrist_xs)) if len(wrist_xs) > 1 else 0.0

                    issues, feedback, score = self._evaluate_form(
                        max_elbow=self._max_elbow_angle,
                        min_elbow=self._min_elbow_angle,
                        torso_lean=self._max_torso_lean,
                        asym=asymmetry_delta,
                        instability_std=instability_std,
                        conf=conf,
                    )

                    is_valid = len(issues) == 0 and score >= 70
                    if is_valid:
                        self.valid_reps += 1
                    else:
                        self.invalid_reps += 1

                    self.phase = ShoulderPressPhase.COMPLETED_REP
                    self._last_completed_rep_result = ExerciseAnalysisResult(
                        exercise="shoulder_press",
                        phase=self.phase.value,
                        rep_count=self.rep_count,
                        valid_reps=self.valid_reps,
                        invalid_reps=self.invalid_reps,
                        confidence=conf,
                        primary_angle=float(elbow_angle),
                        current_angles={
                            "elbow": float(elbow_angle),
                            "shoulder_elevation": float(shoulder_elevation),
                            "torso_lean": float(torso_lean),
                            "left_elbow": float(left_elbow),
                            "right_elbow": float(right_elbow),
                        },
                        form_score=score,
                        is_valid_rep=is_valid,
                        issues=issues,
                        feedback=feedback,
                        metrics={
                            "max_elbow_angle": float(self._max_elbow_angle),
                            "min_elbow_angle": float(self._min_elbow_angle),
                            "torso_lean_deg": float(self._max_torso_lean),
                            "asymmetry_delta_deg": float(asymmetry_delta),
                            "instability_std": float(instability_std),
                        },
                        rep_duration_sec=float(rep_duration),
                    )
                else:
                    self.phase = ShoulderPressPhase.RACK_POSITION

                self._max_elbow_angle = 0.0
                self._min_elbow_angle = 180.0
                self._max_torso_lean = 0.0
                self._lockout_reached = False
                self._rep_initiated = False
                self._current_rep_trajectory = []

        rep_duration_now = (now_ms - self._rep_start_time_ms) / 1000.0 if self._rep_start_time_ms > 0 else 0.0

        # Live frame form feedback
        live_issues, live_feedback, live_score = self._evaluate_form(
            max_elbow=self._max_elbow_angle if self.phase != ShoulderPressPhase.RACK_POSITION else elbow_angle,
            min_elbow=self._min_elbow_angle,
            torso_lean=torso_lean,
            asym=asymmetry_delta,
            instability_std=0.0,
            conf=conf,
        )

        current_score = self._last_completed_rep_result.form_score if (self._last_completed_rep_result and self.phase == ShoulderPressPhase.COMPLETED_REP) else live_score
        current_issues = self._last_completed_rep_result.issues if (self._last_completed_rep_result and self.phase == ShoulderPressPhase.COMPLETED_REP) else live_issues
        current_feedback = self._last_completed_rep_result.feedback if (self._last_completed_rep_result and self.phase == ShoulderPressPhase.COMPLETED_REP) else live_feedback

        return ExerciseAnalysisResult(
            exercise="shoulder_press",
            phase=self.phase.value,
            rep_count=self.rep_count,
            valid_reps=self.valid_reps,
            invalid_reps=self.invalid_reps,
            confidence=conf,
            primary_angle=float(elbow_angle),
            current_angles={
                "elbow": float(elbow_angle),
                "shoulder_elevation": float(shoulder_elevation),
                "torso_lean": float(torso_lean),
                "left_elbow": float(left_elbow),
                "right_elbow": float(right_elbow),
            },
            form_score=current_score,
            is_valid_rep=(len(current_issues) == 0),
            issues=current_issues,
            feedback=current_feedback,
            metrics={
                "max_elbow_angle": float(self._max_elbow_angle),
                "min_elbow_angle": float(self._min_elbow_angle),
                "torso_lean_deg": float(torso_lean),
                "asymmetry_delta_deg": float(asymmetry_delta),
                "instability_std": 0.0,
            },
            rep_duration_sec=float(rep_duration_now),
        )

    def _evaluate_form(
        self,
        max_elbow: float,
        min_elbow: float,
        torso_lean: float,
        asym: float,
        instability_std: float,
        conf: float,
    ) -> tuple[List[Dict[str, Any]], List[str], int]:
        issues: List[Dict[str, Any]] = []
        feedback: List[str] = []
        penalties: float = 0.0

        # 1. Lockout completion check
        if max_elbow > 0.0 and max_elbow < self.config.lockout_elbow_angle - 5.0:
            if max_elbow < 135.0:
                sev = "high"
                pen = 20.0
                msg = "Press fully overhead to reach complete elbow lockout."
            else:
                sev = "medium"
                pen = 12.0
                msg = "Extend arms slightly further at top of press."
            issues.append({
                "type": "incomplete_lockout",
                "severity": sev,
                "confidence": round(conf * 0.95, 2),
                "details": f"Overhead lockout reached only {max_elbow:.1f}° (target: >= {self.config.lockout_elbow_angle:.1f}°).",
            })
            feedback.append(msg)
            penalties += pen

        # 2. Lumbar hyperextension / backward arch check
        if torso_lean > self.config.max_lumbar_arch_deg:
            issues.append({
                "type": "lumbar_hyperextension",
                "severity": "medium" if torso_lean > 25.0 else "low",
                "confidence": round(conf * 0.90, 2),
                "details": f"Excessive lower back arch ({torso_lean:.1f}° torso inclination).",
            })
            feedback.append("Squeeze glutes and brace core to prevent overarching lower back.")
            penalties += 15.0

        # 3. Bilateral asymmetry
        if asym > self.config.asymmetry_threshold_deg:
            issues.append({
                "type": "arm_asymmetry",
                "severity": "medium",
                "confidence": round(conf * 0.88, 2),
                "details": f"Unequal arm lockout ({asym:.1f}° delta between arms).",
            })
            feedback.append("Press both arms up evenly at the same speed.")
            penalties += 10.0

        # 4. Instability / bar path sway
        if instability_std > self.config.instability_warn_std:
            issues.append({
                "type": "movement_instability",
                "severity": "medium",
                "confidence": round(conf * 0.85, 2),
                "details": f"Lateral bar path sway detected (std: {instability_std:.3f}).",
            })
            feedback.append("Stabilize press trajectory along a clean vertical path.")
            penalties += 10.0

        if not feedback:
            feedback.append("Solid press! Full overhead lockout and stable core.")

        score = self.clamp_form_score(100.0 - penalties)
        return issues, feedback, score

    def reset(self):
        super().reset()
        self.phase = ShoulderPressPhase.RACK_POSITION
        self._max_elbow_angle = 0.0
        self._min_elbow_angle = 180.0
        self._max_torso_lean = 0.0
        self._lockout_reached = False
        self._rep_initiated = False
