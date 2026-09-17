import enum
from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np

from ai.exercises.base import BaseExerciseAnalyzer, ExerciseAnalysisResult
from ai.geometry.angles import calculate_angle_2d
from ai.geometry.metrics import calculate_vertical_alignment
from ai.pose.landmarks import LandmarkIndex


class BicepCurlPhase(str, enum.Enum):
    EXTENDED = "extended"
    CONCENTRIC = "concentric"
    PEAK_FLEXION = "peak_flexion"
    ECCENTRIC = "eccentric"
    COMPLETED_REP = "completed_rep"


@dataclass
class BicepCurlConfig:
    """Configurable biomechanical thresholds for Bicep Curl analysis."""
    extension_angle: float = 150.0          # Fully extended arm (degrees)
    concentric_threshold: float = 135.0     # Angle below which upward curl begins
    peak_curl_angle: float = 55.0           # Target peak contraction angle (<= 55 deg)
    eccentric_threshold: float = 75.0       # Angle above which lowering begins
    max_shoulder_sway_deg: float = 20.0     # Upper arm drift from torso
    max_torso_sway_deg: float = 15.0        # Torso momentum/backward lean
    asymmetry_threshold_deg: float = 15.0   # Left vs right arm angle delta
    hysteresis_deg: float = 5.0             # Guard band to prevent jitter
    min_rep_duration_sec: float = 0.5       # Minimum rep duration anti-cheat
    min_landmark_confidence: float = 0.45


class BicepCurlExercise(BaseExerciseAnalyzer):
    """
    Biomechanical Bicep Curl Analyzer with 5-phase State Machine,
    elbow flexion tracking, shoulder swing detection, momentum prevention,
    and actionable coaching cues.
    """

    def __init__(self, config: BicepCurlConfig | None = None):
        super().__init__(name="bicep_curl")
        self.config = config or BicepCurlConfig()
        self.phase = BicepCurlPhase.EXTENDED

        self._min_elbow_angle: float = 180.0
        self._max_shoulder_sway: float = 0.0
        self._max_torso_lean: float = 0.0
        self._peak_reached: bool = False
        self._rep_initiated: bool = False

    def analyze_frame(
        self,
        landmarks: np.ndarray,
        timestamp_ms: float | None = None,
    ) -> ExerciseAnalysisResult:
        now_ms = timestamp_ms if timestamp_ms is not None else 0.0

        if landmarks is None or len(landmarks) < 33:
            return ExerciseAnalysisResult(
                exercise="bicep_curl",
                phase=self.phase.value,
                rep_count=self.rep_count,
                valid_reps=self.valid_reps,
                invalid_reps=self.invalid_reps,
                confidence=0.0,
                feedback=["No pose landmarks detected."],
            )

        # 1. Compute Elbow Flexion Angles (Shoulder - Elbow - Wrist)
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

        # 2. Upper Arm Sway / Shoulder Drift (Hip - Shoulder - Elbow)
        left_sway = calculate_angle_2d(
            landmarks[LandmarkIndex.LEFT_HIP],
            landmarks[LandmarkIndex.LEFT_SHOULDER],
            landmarks[LandmarkIndex.LEFT_ELBOW],
        )
        right_sway = calculate_angle_2d(
            landmarks[LandmarkIndex.RIGHT_HIP],
            landmarks[LandmarkIndex.RIGHT_SHOULDER],
            landmarks[LandmarkIndex.RIGHT_ELBOW],
        )
        shoulder_sway = (left_sway + right_sway) / 2.0

        # 3. Torso Lean / Momentum Sway
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
            ],
        )

        if conf < self.config.min_landmark_confidence:
            return ExerciseAnalysisResult(
                exercise="bicep_curl",
                phase=self.phase.value,
                rep_count=self.rep_count,
                valid_reps=self.valid_reps,
                invalid_reps=self.invalid_reps,
                confidence=conf,
                feedback=["Low tracking visibility on arms."],
            )

        # 4. State Machine Transitions
        if self.phase == BicepCurlPhase.COMPLETED_REP:
            self.phase = BicepCurlPhase.EXTENDED

        if self.phase in [BicepCurlPhase.CONCENTRIC, BicepCurlPhase.PEAK_FLEXION, BicepCurlPhase.ECCENTRIC]:
            self._current_rep_trajectory.append(landmarks.copy())
            if shoulder_sway > self._max_shoulder_sway:
                self._max_shoulder_sway = shoulder_sway
            if torso_lean > self._max_torso_lean:
                self._max_torso_lean = torso_lean

        if self.phase == BicepCurlPhase.EXTENDED:
            if elbow_angle < (self.config.concentric_threshold - self.config.hysteresis_deg):
                self.phase = BicepCurlPhase.CONCENTRIC
                self._rep_start_time_ms = now_ms
                self._min_elbow_angle = elbow_angle
                self._max_shoulder_sway = shoulder_sway
                self._max_torso_lean = torso_lean
                self._peak_reached = False
                self._rep_initiated = True
                self._current_rep_trajectory = [landmarks.copy()]

        elif self.phase == BicepCurlPhase.CONCENTRIC:
            if elbow_angle < self._min_elbow_angle:
                self._min_elbow_angle = elbow_angle

            if elbow_angle <= self.config.peak_curl_angle:
                self.phase = BicepCurlPhase.PEAK_FLEXION
                self._peak_reached = True
            elif elbow_angle > (self._min_elbow_angle + self.config.hysteresis_deg * 2.0):
                self.phase = BicepCurlPhase.ECCENTRIC

        elif self.phase == BicepCurlPhase.PEAK_FLEXION:
            if elbow_angle < self._min_elbow_angle:
                self._min_elbow_angle = elbow_angle

            if elbow_angle > (self.config.peak_curl_angle + self.config.hysteresis_deg):
                self.phase = BicepCurlPhase.ECCENTRIC

        elif self.phase == BicepCurlPhase.ECCENTRIC:
            if elbow_angle >= (self.config.extension_angle - self.config.hysteresis_deg):
                rep_duration = (now_ms - self._rep_start_time_ms) / 1000.0 if self._rep_start_time_ms > 0 else 1.0

                if rep_duration >= self.config.min_rep_duration_sec and (self._peak_reached or self._min_elbow_angle < (self.config.concentric_threshold - 10.0)):
                    self.rep_count += 1

                    issues, feedback, score = self._evaluate_form(
                        min_elbow=self._min_elbow_angle,
                        shoulder_sway=self._max_shoulder_sway,
                        torso_lean=self._max_torso_lean,
                        asym=asymmetry_delta,
                        conf=conf,
                    )

                    is_valid = len(issues) == 0 and score >= 70
                    if is_valid:
                        self.valid_reps += 1
                    else:
                        self.invalid_reps += 1

                    self.phase = BicepCurlPhase.COMPLETED_REP
                    self._last_completed_rep_result = ExerciseAnalysisResult(
                        exercise="bicep_curl",
                        phase=self.phase.value,
                        rep_count=self.rep_count,
                        valid_reps=self.valid_reps,
                        invalid_reps=self.invalid_reps,
                        confidence=conf,
                        primary_angle=float(elbow_angle),
                        current_angles={
                            "elbow": float(elbow_angle),
                            "shoulder_sway": float(shoulder_sway),
                            "torso_lean": float(torso_lean),
                            "left_elbow": float(left_elbow),
                            "right_elbow": float(right_elbow),
                        },
                        form_score=score,
                        is_valid_rep=is_valid,
                        issues=issues,
                        feedback=feedback,
                        metrics={
                            "min_elbow_angle": float(self._min_elbow_angle),
                            "shoulder_sway_deg": float(self._max_shoulder_sway),
                            "torso_lean_deg": float(self._max_torso_lean),
                            "asymmetry_delta_deg": float(asymmetry_delta),
                        },
                        rep_duration_sec=float(rep_duration),
                    )
                else:
                    self.phase = BicepCurlPhase.EXTENDED

                self._min_elbow_angle = 180.0
                self._max_shoulder_sway = 0.0
                self._max_torso_lean = 0.0
                self._peak_reached = False
                self._rep_initiated = False
                self._current_rep_trajectory = []

        rep_duration_now = (now_ms - self._rep_start_time_ms) / 1000.0 if self._rep_start_time_ms > 0 else 0.0

        # Live frame form feedback
        live_issues, live_feedback, live_score = self._evaluate_form(
            min_elbow=self._min_elbow_angle if self.phase != BicepCurlPhase.EXTENDED else elbow_angle,
            shoulder_sway=shoulder_sway,
            torso_lean=torso_lean,
            asym=asymmetry_delta,
            conf=conf,
        )

        current_score = self._last_completed_rep_result.form_score if (self._last_completed_rep_result and self.phase == BicepCurlPhase.COMPLETED_REP) else live_score
        current_issues = self._last_completed_rep_result.issues if (self._last_completed_rep_result and self.phase == BicepCurlPhase.COMPLETED_REP) else live_issues
        current_feedback = self._last_completed_rep_result.feedback if (self._last_completed_rep_result and self.phase == BicepCurlPhase.COMPLETED_REP) else live_feedback

        return ExerciseAnalysisResult(
            exercise="bicep_curl",
            phase=self.phase.value,
            rep_count=self.rep_count,
            valid_reps=self.valid_reps,
            invalid_reps=self.invalid_reps,
            confidence=conf,
            primary_angle=float(elbow_angle),
            current_angles={
                "elbow": float(elbow_angle),
                "shoulder_sway": float(shoulder_sway),
                "torso_lean": float(torso_lean),
                "left_elbow": float(left_elbow),
                "right_elbow": float(right_elbow),
            },
            form_score=current_score,
            is_valid_rep=(len(current_issues) == 0),
            issues=current_issues,
            feedback=current_feedback,
            metrics={
                "min_elbow_angle": float(self._min_elbow_angle),
                "shoulder_sway_deg": float(shoulder_sway),
                "torso_lean_deg": float(torso_lean),
                "asymmetry_delta_deg": float(asymmetry_delta),
            },
            rep_duration_sec=float(rep_duration_now),
        )

    def _evaluate_form(
        self,
        min_elbow: float,
        shoulder_sway: float,
        torso_lean: float,
        asym: float,
        conf: float,
    ) -> tuple[List[Dict[str, Any]], List[str], int]:
        issues: List[Dict[str, Any]] = []
        feedback: List[str] = []
        penalties: float = 0.0

        # 1. Peak flexion contraction check
        if min_elbow > self.config.peak_curl_angle + 5.0:
            if min_elbow > 85.0:
                sev = "high"
                pen = 20.0
                msg = "Curl higher. Squeeze bicep fully at top of movement."
            else:
                sev = "medium"
                pen = 12.0
                msg = "Increase curl range of motion to reach peak contraction."
            issues.append({
                "type": "incomplete_curl_flexion",
                "severity": sev,
                "confidence": round(conf * 0.92, 2),
                "details": f"Peak elbow flexion reached only {min_elbow:.1f}° (target: <= {self.config.peak_curl_angle:.1f}°).",
            })
            feedback.append(msg)
            penalties += pen

        # 2. Elbow swinging / shoulder sway check
        if shoulder_sway > self.config.max_shoulder_sway_deg:
            issues.append({
                "type": "elbow_swinging",
                "severity": "medium" if shoulder_sway > 30.0 else "low",
                "confidence": round(conf * 0.90, 2),
                "details": f"Elbow drifting forward/away from ribs ({shoulder_sway:.1f}° sway).",
            })
            feedback.append("Keep elbows pinned to your sides to isolate biceps.")
            penalties += 15.0

        # 3. Torso backward lean momentum check
        if torso_lean > self.config.max_torso_sway_deg:
            issues.append({
                "type": "torso_momentum",
                "severity": "medium",
                "confidence": round(conf * 0.88, 2),
                "details": f"Torso leaning backward to swing weight ({torso_lean:.1f}° pitch).",
            })
            feedback.append("Avoid leaning back; maintain an upright, stationary torso.")
            penalties += 15.0

        # 4. Asymmetry check
        if asym > self.config.asymmetry_threshold_deg:
            issues.append({
                "type": "arm_asymmetry",
                "severity": "medium",
                "confidence": round(conf * 0.85, 2),
                "details": f"Bilateral curl asymmetry ({asym:.1f}° difference between arms).",
            })
            feedback.append("Curl both arms evenly at the same tempo.")
            penalties += 10.0

        if not feedback:
            feedback.append("Perfect curl form! Full bicep isolation with stationary elbows.")

        score = self.clamp_form_score(100.0 - penalties)
        return issues, feedback, score

    def reset(self):
        super().reset()
        self.phase = BicepCurlPhase.EXTENDED
        self._min_elbow_angle = 180.0
        self._max_shoulder_sway = 0.0
        self._max_torso_lean = 0.0
        self._peak_reached = False
        self._rep_initiated = False
