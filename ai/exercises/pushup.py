import enum
from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np

from ai.exercises.base import BaseExerciseAnalyzer, ExerciseAnalysisResult
from ai.geometry.angles import calculate_angle_2d
from ai.pose.landmarks import LandmarkIndex


class PushupPhase(str, enum.Enum):
    PLANK = "plank"
    DESCENDING = "descending"
    BOTTOM = "bottom"
    ASCENDING = "ascending"
    COMPLETED_REP = "completed_rep"


@dataclass
class PushupConfig:
    """Configurable biomechanical thresholds for Push-up analysis."""
    plank_elbow_angle: float = 155.0        # Lockout angle (degrees) in top plank position
    descending_threshold: float = 145.0     # Angle below which descent begins
    bottom_elbow_angle: float = 90.0        # Chest-to-floor bottom depth target (<= 90 deg)
    ascending_threshold: float = 105.0      # Angle above which ascent begins
    min_body_line_angle: float = 155.0      # Shoulder-Hip-Ankle alignment (< 155 deg = sagging hips)
    max_body_line_angle: float = 195.0      # Shoulder-Hip-Ankle alignment (> 195 deg = piking hips)
    max_elbow_flare_deg: float = 75.0       # Angle between torso and upper arm
    asymmetry_threshold_deg: float = 12.0   # Left vs right elbow delta
    hysteresis_deg: float = 5.0             # Guard band to prevent jitter
    min_rep_duration_sec: float = 0.5       # Anti-bounce/jitter time
    min_landmark_confidence: float = 0.45


class PushupExercise(BaseExerciseAnalyzer):
    """
    Biomechanical Push-up Analyzer with 5-phase State Machine,
    joint angle tracking, explainable rule evaluation, and actionable coaching cues.
    """

    def __init__(self, config: PushupConfig | None = None):
        super().__init__(name="pushup")
        self.config = config or PushupConfig()
        self.phase = PushupPhase.PLANK

        self._min_elbow_angle: float = 180.0
        self._min_body_line_angle: float = 180.0
        self._max_elbow_flare: float = 0.0
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
                exercise="pushup",
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

        # 2. Body Alignment (Shoulder - Hip - Ankle)
        left_body = calculate_angle_2d(
            landmarks[LandmarkIndex.LEFT_SHOULDER],
            landmarks[LandmarkIndex.LEFT_HIP],
            landmarks[LandmarkIndex.LEFT_ANKLE],
        )
        right_body = calculate_angle_2d(
            landmarks[LandmarkIndex.RIGHT_SHOULDER],
            landmarks[LandmarkIndex.RIGHT_HIP],
            landmarks[LandmarkIndex.RIGHT_ANKLE],
        )
        body_line_angle = (left_body + right_body) / 2.0

        # Relative vertical displacement to distinguish piking (hips raised) vs sagging (hips lowered)
        shoulder_y = float((landmarks[LandmarkIndex.LEFT_SHOULDER, 1] + landmarks[LandmarkIndex.RIGHT_SHOULDER, 1]) / 2.0)
        ankle_y = float((landmarks[LandmarkIndex.LEFT_ANKLE, 1] + landmarks[LandmarkIndex.RIGHT_ANKLE, 1]) / 2.0)
        hip_y = float((landmarks[LandmarkIndex.LEFT_HIP, 1] + landmarks[LandmarkIndex.RIGHT_HIP, 1]) / 2.0)
        expected_hip_y = (shoulder_y + ankle_y) / 2.0
        is_piking = hip_y < expected_hip_y

        # 3. Upper Arm Flare (Hip - Shoulder - Elbow)
        left_flare = calculate_angle_2d(
            landmarks[LandmarkIndex.LEFT_HIP],
            landmarks[LandmarkIndex.LEFT_SHOULDER],
            landmarks[LandmarkIndex.LEFT_ELBOW],
        )
        right_flare = calculate_angle_2d(
            landmarks[LandmarkIndex.RIGHT_HIP],
            landmarks[LandmarkIndex.RIGHT_SHOULDER],
            landmarks[LandmarkIndex.RIGHT_ELBOW],
        )
        elbow_flare = (left_flare + right_flare) / 2.0

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
                exercise="pushup",
                phase=self.phase.value,
                rep_count=self.rep_count,
                valid_reps=self.valid_reps,
                invalid_reps=self.invalid_reps,
                confidence=conf,
                feedback=["Low tracking visibility on upper body."],
            )

        # 4. State Machine Transitions
        if self.phase == PushupPhase.COMPLETED_REP:
            self.phase = PushupPhase.PLANK

        if self.phase in [PushupPhase.DESCENDING, PushupPhase.BOTTOM, PushupPhase.ASCENDING]:
            self._current_rep_trajectory.append(landmarks.copy())
            if body_line_angle < self._min_body_line_angle:
                self._min_body_line_angle = body_line_angle
                self._rep_is_piking = is_piking
            if elbow_flare > self._max_elbow_flare:
                self._max_elbow_flare = elbow_flare

        if self.phase == PushupPhase.PLANK:
            if elbow_angle < (self.config.descending_threshold - self.config.hysteresis_deg):
                self.phase = PushupPhase.DESCENDING
                self._rep_start_time_ms = now_ms
                self._min_elbow_angle = elbow_angle
                self._min_body_line_angle = body_line_angle
                self._rep_is_piking = is_piking
                self._max_elbow_flare = elbow_flare
                self._bottom_reached = False
                self._rep_initiated = True
                self._current_rep_trajectory = [landmarks.copy()]

        elif self.phase == PushupPhase.DESCENDING:
            if elbow_angle < self._min_elbow_angle:
                self._min_elbow_angle = elbow_angle

            if elbow_angle <= self.config.bottom_elbow_angle:
                self.phase = PushupPhase.BOTTOM
                self._bottom_reached = True
            elif elbow_angle > (self._min_elbow_angle + self.config.hysteresis_deg * 2.0):
                self.phase = PushupPhase.ASCENDING

        elif self.phase == PushupPhase.BOTTOM:
            if elbow_angle < self._min_elbow_angle:
                self._min_elbow_angle = elbow_angle

            if elbow_angle > (self.config.bottom_elbow_angle + self.config.hysteresis_deg):
                self.phase = PushupPhase.ASCENDING

        elif self.phase == PushupPhase.ASCENDING:
            if elbow_angle >= (self.config.plank_elbow_angle - self.config.hysteresis_deg):
                rep_duration = (now_ms - self._rep_start_time_ms) / 1000.0 if self._rep_start_time_ms > 0 else 1.0

                if rep_duration >= self.config.min_rep_duration_sec and (self._bottom_reached or self._min_elbow_angle < (self.config.descending_threshold - 10.0)):
                    self.rep_count += 1

                    # Evaluate completed rep issues
                    issues, feedback, score = self._evaluate_form(
                        min_elbow=self._min_elbow_angle,
                        body_line=self._min_body_line_angle,
                        flare=self._max_elbow_flare,
                        asym=asymmetry_delta,
                        is_piking=getattr(self, "_rep_is_piking", is_piking),
                        conf=conf,
                    )

                    is_valid = len(issues) == 0 and score >= 70
                    if is_valid:
                        self.valid_reps += 1
                    else:
                        self.invalid_reps += 1

                    self.phase = PushupPhase.COMPLETED_REP
                    self._last_completed_rep_result = ExerciseAnalysisResult(
                        exercise="pushup",
                        phase=self.phase.value,
                        rep_count=self.rep_count,
                        valid_reps=self.valid_reps,
                        invalid_reps=self.invalid_reps,
                        confidence=conf,
                        primary_angle=float(elbow_angle),
                        current_angles={
                            "elbow": float(elbow_angle),
                            "body_alignment": float(body_line_angle),
                            "elbow_flare": float(elbow_flare),
                            "left_elbow": float(left_elbow),
                            "right_elbow": float(right_elbow),
                        },
                        form_score=score,
                        is_valid_rep=is_valid,
                        issues=issues,
                        feedback=feedback,
                        metrics={
                            "min_elbow_angle": float(self._min_elbow_angle),
                            "body_line_deg": float(self._min_body_line_angle),
                            "elbow_flare_deg": float(self._max_elbow_flare),
                            "asymmetry_delta_deg": float(asymmetry_delta),
                        },
                        rep_duration_sec=float(rep_duration),
                    )
                else:
                    self.phase = PushupPhase.PLANK

                self._min_elbow_angle = 180.0
                self._min_body_line_angle = 180.0
                self._max_elbow_flare = 0.0
                self._bottom_reached = False
                self._rep_initiated = False
                self._rep_is_piking = False
                self._current_rep_trajectory = []

        rep_duration_now = (now_ms - self._rep_start_time_ms) / 1000.0 if self._rep_start_time_ms > 0 else 0.0

        # Live frame form analysis
        live_issues, live_feedback, live_score = self._evaluate_form(
            min_elbow=self._min_elbow_angle if self.phase != PushupPhase.PLANK else elbow_angle,
            body_line=body_line_angle,
            flare=elbow_flare,
            asym=asymmetry_delta,
            is_piking=is_piking,
            conf=conf,
        )

        current_score = self._last_completed_rep_result.form_score if (self._last_completed_rep_result and self.phase == PushupPhase.COMPLETED_REP) else live_score
        current_issues = self._last_completed_rep_result.issues if (self._last_completed_rep_result and self.phase == PushupPhase.COMPLETED_REP) else live_issues
        current_feedback = self._last_completed_rep_result.feedback if (self._last_completed_rep_result and self.phase == PushupPhase.COMPLETED_REP) else live_feedback

        return ExerciseAnalysisResult(
            exercise="pushup",
            phase=self.phase.value,
            rep_count=self.rep_count,
            valid_reps=self.valid_reps,
            invalid_reps=self.invalid_reps,
            confidence=conf,
            primary_angle=float(elbow_angle),
            current_angles={
                "elbow": float(elbow_angle),
                "body_alignment": float(body_line_angle),
                "elbow_flare": float(elbow_flare),
                "left_elbow": float(left_elbow),
                "right_elbow": float(right_elbow),
            },
            form_score=current_score,
            is_valid_rep=(len(current_issues) == 0),
            issues=current_issues,
            feedback=current_feedback,
            metrics={
                "min_elbow_angle": float(self._min_elbow_angle),
                "body_line_deg": float(body_line_angle),
                "elbow_flare_deg": float(elbow_flare),
                "asymmetry_delta_deg": float(asymmetry_delta),
            },
            rep_duration_sec=float(rep_duration_now),
        )

    def _evaluate_form(
        self,
        min_elbow: float,
        body_line: float,
        flare: float,
        asym: float,
        is_piking: bool,
        conf: float,
    ) -> tuple[List[Dict[str, Any]], List[str], int]:
        issues: List[Dict[str, Any]] = []
        feedback: List[str] = []
        penalties: float = 0.0

        # 1. Depth check (bottom elbow angle)
        if min_elbow > self.config.bottom_elbow_angle + 5.0:
            if min_elbow > 120.0:
                sev = "high"
                pen = 25.0
                msg = "Chest must go much lower. Aim for 90° elbow bend at bottom."
            elif min_elbow > 105.0:
                sev = "medium"
                pen = 15.0
                msg = "Increase pushup depth; lower chest closer to floor."
            else:
                sev = "low"
                pen = 8.0
                msg = "Drop slightly deeper to complete full range of motion."
            issues.append({
                "type": "insufficient_depth",
                "severity": sev,
                "confidence": round(conf * 0.95, 2),
                "details": f"Elbow reached only {min_elbow:.1f}° (target: <= {self.config.bottom_elbow_angle:.1f}°).",
            })
            feedback.append(msg)
            penalties += pen

        # 2. Body alignment check (Sagging vs Piking)
        if body_line < self.config.min_body_line_angle:
            if is_piking:
                issues.append({
                    "type": "hips_piking",
                    "severity": "medium" if body_line < 145.0 else "low",
                    "confidence": round(conf * 0.90, 2),
                    "details": f"Hips are elevated/piked upward (body line: {body_line:.1f}°).",
                })
                feedback.append("Flatten hips to maintain straight plank line; avoid piking hips upward.")
                penalties += 12.0
            else:
                issues.append({
                    "type": "hips_sagging",
                    "severity": "medium" if body_line < 145.0 else "low",
                    "confidence": round(conf * 0.90, 2),
                    "details": f"Hips are sagging downward (body line: {body_line:.1f}°).",
                })
                feedback.append("Keep core engaged; do not let hips sag towards floor.")
                penalties += 15.0

        # 3. Elbow flare check
        if flare > self.config.max_elbow_flare_deg:
            issues.append({
                "type": "excessive_elbow_flare",
                "severity": "medium" if flare > 85.0 else "low",
                "confidence": round(conf * 0.88, 2),
                "details": f"Elbows flaring excessively wide ({flare:.1f}° from torso).",
            })
            feedback.append("Tuck elbows closer to ribs (around 45°-60° from torso) to protect shoulders.")
            penalties += 12.0

        # 4. Left/Right arm asymmetry
        if asym > self.config.asymmetry_threshold_deg:
            issues.append({
                "type": "arm_asymmetry",
                "severity": "medium",
                "confidence": round(conf * 0.85, 2),
                "details": f"Unequal arm extension ({asym:.1f}° delta between left and right).",
            })
            feedback.append("Distribute pushing force equally through both arms.")
            penalties += 10.0


        if not feedback:
            feedback.append("Great pushup form! Clean plank line and full depth.")

        score = self.clamp_form_score(100.0 - penalties)
        return issues, feedback, score

    def reset(self):
        super().reset()
        self.phase = PushupPhase.PLANK
        self._min_elbow_angle = 180.0
        self._min_body_line_angle = 180.0
        self._max_elbow_flare = 0.0
        self._bottom_reached = False
        self._rep_initiated = False
