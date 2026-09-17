import enum
from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np

from ai.exercises.base import BaseExerciseAnalyzer, ExerciseAnalysisResult
from ai.geometry.angles import calculate_angle_2d
from ai.geometry.metrics import calculate_vertical_alignment
from ai.pose.landmarks import LandmarkIndex


class LungePhase(str, enum.Enum):
    STANDING = "standing"
    DESCENDING = "descending"
    BOTTOM = "bottom"
    ASCENDING = "ascending"
    COMPLETED_REP = "completed_rep"


@dataclass
class LungeConfig:
    """Configurable biomechanical thresholds for Lunge analysis."""
    standing_knee_angle: float = 160.0       # Upright standing angle (degrees)
    descending_threshold: float = 140.0      # Front knee angle below which descent starts
    bottom_knee_angle: float = 95.0          # Target lead knee flexion at bottom (<= 95 deg)
    ascending_threshold: float = 110.0       # Front knee angle above which ascent begins
    max_torso_lean_deg: float = 25.0         # Excessive forward chest tilt
    max_trail_knee_angle: float = 125.0      # Rear knee angle at bottom (should bend towards 90-100 deg)
    instability_warn_std: float = 0.040      # Lateral hip/balance sway threshold
    hysteresis_deg: float = 5.0              # Anti-jitter threshold
    min_rep_duration_sec: float = 0.5        # Minimum rep duration anti-cheat
    min_landmark_confidence: float = 0.45


class LungeExercise(BaseExerciseAnalyzer):
    """
    Biomechanical Lunge Analyzer with 5-phase State Machine,
    lead/trail knee angle tracking, torso alignment, stability metrics,
    and actionable coaching cues.
    """

    def __init__(self, config: LungeConfig | None = None):
        super().__init__(name="lunge")
        self.config = config or LungeConfig()
        self.phase = LungePhase.STANDING

        self._min_lead_knee_angle: float = 180.0
        self._min_trail_knee_angle: float = 180.0
        self._max_torso_lean: float = 0.0
        self._bottom_reached: bool = False
        self._rep_initiated: bool = False

    def analyze_frame(
        self,
        landmarks: np.ndarray,
        timestamp_ms: float | None = None,
    ) -> ExerciseAnalysisResult:
        now_ms = timestamp_ms if timestamp_ms is not None else 0.0

        if landmarks is None or len(landmarks) < 33:
            return ExerciseAnalysisResult(
                exercise="lunge",
                phase=self.phase.value,
                rep_count=self.rep_count,
                valid_reps=self.valid_reps,
                invalid_reps=self.invalid_reps,
                confidence=0.0,
                feedback=["No pose landmarks detected."],
            )

        # 1. Compute bilateral knee angles
        left_knee = calculate_angle_2d(
            landmarks[LandmarkIndex.LEFT_HIP],
            landmarks[LandmarkIndex.LEFT_KNEE],
            landmarks[LandmarkIndex.LEFT_ANKLE],
        )
        right_knee = calculate_angle_2d(
            landmarks[LandmarkIndex.RIGHT_HIP],
            landmarks[LandmarkIndex.RIGHT_KNEE],
            landmarks[LandmarkIndex.RIGHT_ANKLE],
        )

        # Determine Lead vs Trail leg dynamically (lower angle is lead leg)
        if left_knee <= right_knee:
            lead_knee = left_knee
            trail_knee = right_knee
        else:
            lead_knee = right_knee
            trail_knee = left_knee

        # 2. Torso Lean (Shoulder center to Hip center)
        shoulder_mid = (landmarks[LandmarkIndex.LEFT_SHOULDER, :2] + landmarks[LandmarkIndex.RIGHT_SHOULDER, :2]) / 2.0
        hip_mid = (landmarks[LandmarkIndex.LEFT_HIP, :2] + landmarks[LandmarkIndex.RIGHT_HIP, :2]) / 2.0
        torso_lean = calculate_vertical_alignment(shoulder_mid, hip_mid)

        # Confidence
        conf = self.compute_landmark_confidence(
            landmarks,
            [
                LandmarkIndex.LEFT_HIP, LandmarkIndex.RIGHT_HIP,
                LandmarkIndex.LEFT_KNEE, LandmarkIndex.RIGHT_KNEE,
                LandmarkIndex.LEFT_ANKLE, LandmarkIndex.RIGHT_ANKLE,
            ],
        )

        if conf < self.config.min_landmark_confidence:
            return ExerciseAnalysisResult(
                exercise="lunge",
                phase=self.phase.value,
                rep_count=self.rep_count,
                valid_reps=self.valid_reps,
                invalid_reps=self.invalid_reps,
                confidence=conf,
                feedback=["Low tracking visibility on legs."],
            )

        # 3. State Machine Transitions
        if self.phase == LungePhase.COMPLETED_REP:
            self.phase = LungePhase.STANDING

        if self.phase in [LungePhase.DESCENDING, LungePhase.BOTTOM, LungePhase.ASCENDING]:
            self._current_rep_trajectory.append(landmarks.copy())
            if lead_knee < self._min_lead_knee_angle:
                self._min_lead_knee_angle = lead_knee
            if trail_knee < self._min_trail_knee_angle:
                self._min_trail_knee_angle = trail_knee
            if torso_lean > self._max_torso_lean:
                self._max_torso_lean = torso_lean

        if self.phase == LungePhase.STANDING:
            if lead_knee < (self.config.descending_threshold - self.config.hysteresis_deg):
                self.phase = LungePhase.DESCENDING
                self._rep_start_time_ms = now_ms
                self._min_lead_knee_angle = lead_knee
                self._min_trail_knee_angle = trail_knee
                self._max_torso_lean = torso_lean
                self._bottom_reached = False
                self._rep_initiated = True
                self._current_rep_trajectory = [landmarks.copy()]

        elif self.phase == LungePhase.DESCENDING:
            if lead_knee <= self.config.bottom_knee_angle:
                self.phase = LungePhase.BOTTOM
                self._bottom_reached = True
            elif lead_knee > (self._min_lead_knee_angle + self.config.hysteresis_deg * 2.0):
                self.phase = LungePhase.ASCENDING

        elif self.phase == LungePhase.BOTTOM:
            if lead_knee > (self.config.bottom_knee_angle + self.config.hysteresis_deg):
                self.phase = LungePhase.ASCENDING

        elif self.phase == LungePhase.ASCENDING:
            if lead_knee >= (self.config.standing_knee_angle - self.config.hysteresis_deg):
                rep_duration = (now_ms - self._rep_start_time_ms) / 1000.0 if self._rep_start_time_ms > 0 else 1.0

                if rep_duration >= self.config.min_rep_duration_sec and (self._bottom_reached or self._min_lead_knee_angle < (self.config.descending_threshold - 10.0)):
                    self.rep_count += 1

                    # Compute sway instability from rep trajectory
                    hip_xs = [float((lm[LandmarkIndex.LEFT_HIP, 0] + lm[LandmarkIndex.RIGHT_HIP, 0]) / 2.0) for lm in self._current_rep_trajectory]
                    instability_std = float(np.std(hip_xs)) if len(hip_xs) > 1 else 0.0

                    issues, feedback, score = self._evaluate_form(
                        min_lead_knee=self._min_lead_knee_angle,
                        min_trail_knee=self._min_trail_knee_angle,
                        torso_lean=self._max_torso_lean,
                        instability_std=instability_std,
                        conf=conf,
                    )

                    is_valid = len(issues) == 0 and score >= 70
                    if is_valid:
                        self.valid_reps += 1
                    else:
                        self.invalid_reps += 1

                    self.phase = LungePhase.COMPLETED_REP
                    self._last_completed_rep_result = ExerciseAnalysisResult(
                        exercise="lunge",
                        phase=self.phase.value,
                        rep_count=self.rep_count,
                        valid_reps=self.valid_reps,
                        invalid_reps=self.invalid_reps,
                        confidence=conf,
                        primary_angle=float(lead_knee),
                        current_angles={
                            "lead_knee": float(lead_knee),
                            "trail_knee": float(trail_knee),
                            "torso_lean": float(torso_lean),
                            "left_knee": float(left_knee),
                            "right_knee": float(right_knee),
                        },
                        form_score=score,
                        is_valid_rep=is_valid,
                        issues=issues,
                        feedback=feedback,
                        metrics={
                            "min_lead_knee_angle": float(self._min_lead_knee_angle),
                            "min_trail_knee_angle": float(self._min_trail_knee_angle),
                            "torso_lean_deg": float(self._max_torso_lean),
                            "instability_std": float(instability_std),
                        },
                        rep_duration_sec=float(rep_duration),
                    )
                else:
                    self.phase = LungePhase.STANDING

                self._min_lead_knee_angle = 180.0
                self._min_trail_knee_angle = 180.0
                self._max_torso_lean = 0.0
                self._bottom_reached = False
                self._rep_initiated = False
                self._current_rep_trajectory = []

        rep_duration_now = (now_ms - self._rep_start_time_ms) / 1000.0 if self._rep_start_time_ms > 0 else 0.0

        # Live frame form feedback
        live_issues, live_feedback, live_score = self._evaluate_form(
            min_lead_knee=self._min_lead_knee_angle if self.phase != LungePhase.STANDING else lead_knee,
            min_trail_knee=trail_knee,
            torso_lean=torso_lean,
            instability_std=0.0,
            conf=conf,
        )

        current_score = self._last_completed_rep_result.form_score if (self._last_completed_rep_result and self.phase == LungePhase.COMPLETED_REP) else live_score
        current_issues = self._last_completed_rep_result.issues if (self._last_completed_rep_result and self.phase == LungePhase.COMPLETED_REP) else live_issues
        current_feedback = self._last_completed_rep_result.feedback if (self._last_completed_rep_result and self.phase == LungePhase.COMPLETED_REP) else live_feedback

        return ExerciseAnalysisResult(
            exercise="lunge",
            phase=self.phase.value,
            rep_count=self.rep_count,
            valid_reps=self.valid_reps,
            invalid_reps=self.invalid_reps,
            confidence=conf,
            primary_angle=float(lead_knee),
            current_angles={
                "lead_knee": float(lead_knee),
                "trail_knee": float(trail_knee),
                "torso_lean": float(torso_lean),
                "left_knee": float(left_knee),
                "right_knee": float(right_knee),
            },
            form_score=current_score,
            is_valid_rep=(len(current_issues) == 0),
            issues=current_issues,
            feedback=current_feedback,
            metrics={
                "min_lead_knee_angle": float(self._min_lead_knee_angle),
                "trail_knee_angle": float(trail_knee),
                "torso_lean_deg": float(torso_lean),
                "instability_std": 0.0,
            },
            rep_duration_sec=float(rep_duration_now),
        )

    def _evaluate_form(
        self,
        min_lead_knee: float,
        min_trail_knee: float,
        torso_lean: float,
        instability_std: float,
        conf: float,
    ) -> tuple[List[Dict[str, Any]], List[str], int]:
        issues: List[Dict[str, Any]] = []
        feedback: List[str] = []
        penalties: float = 0.0

        # 1. Lead knee depth check
        if min_lead_knee > self.config.bottom_knee_angle + 5.0:
            if min_lead_knee > 120.0:
                sev = "high"
                pen = 25.0
                msg = "Lunge deeper; lower front thigh parallel to floor."
            else:
                sev = "medium"
                pen = 15.0
                msg = "Increase lunge depth by dropping hips lower."
            issues.append({
                "type": "insufficient_depth",
                "severity": sev,
                "confidence": round(conf * 0.95, 2),
                "details": f"Lead knee flexion was {min_lead_knee:.1f}° (target: <= {self.config.bottom_knee_angle:.1f}°).",
            })
            feedback.append(msg)
            penalties += pen

        # 2. Torso forward lean check
        if torso_lean > self.config.max_torso_lean_deg:
            issues.append({
                "type": "excessive_torso_lean",
                "severity": "medium" if torso_lean > 35.0 else "low",
                "confidence": round(conf * 0.90, 2),
                "details": f"Torso tilted forward {torso_lean:.1f}° from vertical.",
            })
            feedback.append("Keep chest upright and shoulders stacked above hips.")
            penalties += 15.0

        # 3. Trail knee stiffness / short step check
        if min_trail_knee > self.config.max_trail_knee_angle:
            issues.append({
                "type": "stiff_trail_leg",
                "severity": "medium",
                "confidence": round(conf * 0.88, 2),
                "details": f"Rear knee did not bend sufficiently ({min_trail_knee:.1f}°).",
            })
            feedback.append("Bend rear knee towards floor to achieve balanced 90°/90° lunge.")
            penalties += 12.0

        # 4. Instability / balance check
        if instability_std > self.config.instability_warn_std:
            issues.append({
                "type": "movement_instability",
                "severity": "medium",
                "confidence": round(conf * 0.85, 2),
                "details": f"Lateral hip balance sway detected (std: {instability_std:.3f}).",
            })
            feedback.append("Maintain balance and a solid base of support.")
            penalties += 10.0

        if not feedback:
            feedback.append("Excellent lunge form! Perfect depth and upright posture.")

        score = self.clamp_form_score(100.0 - penalties)
        return issues, feedback, score

    def reset(self):
        super().reset()
        self.phase = LungePhase.STANDING
        self._min_lead_knee_angle = 180.0
        self._min_trail_knee_angle = 180.0
        self._max_torso_lean = 0.0
        self._bottom_reached = False
        self._rep_initiated = False
