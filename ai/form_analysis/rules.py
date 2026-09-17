import enum
from dataclasses import dataclass
from typing import List

from ai.form_analysis.features import SquatKinematicFeatures


class IssueType(str, enum.Enum):
    INSUFFICIENT_DEPTH = "insufficient_depth"
    KNEE_ALIGNMENT = "knee_alignment_problem"
    EXCESSIVE_TORSO_LEAN = "excessive_torso_lean"
    ASYMMETRY = "left_right_asymmetry"
    MOVEMENT_INSTABILITY = "movement_instability"


class Severity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class FormIssue:
    """Represents a specific biomechanical form violation detected during movement."""
    type: str
    severity: str
    confidence: float
    details: str
    penalty_points: float


@dataclass
class SquatFormRuleConfig:
    """Configurable thresholds and rules for squat form evaluation."""
    # 1. Depth thresholds (knee angle at bottom)
    depth_target_deg: float = 95.0          # <= 95 deg is full depth
    depth_shallow_warn_deg: float = 105.0   # 96 - 105 deg: low severity
    depth_shallow_bad_deg: float = 120.0    # 106 - 120 deg: medium, > 120: high

    # 2. Knee alignment / Valgus thresholds (ratio of knee width / ankle width)
    valgus_safe_ratio: float = 0.90         # >= 0.90: clean alignment
    valgus_mild_ratio: float = 0.78         # 0.78 - 0.89: low severity
    valgus_severe_ratio: float = 0.65       # < 0.65: high severity

    # 3. Torso lean thresholds (degrees inclination from vertical)
    torso_safe_lean_deg: float = 35.0       # <= 35 deg: upright/safe
    torso_moderate_lean_deg: float = 48.0   # 36 - 48 deg: low/medium
    torso_severe_lean_deg: float = 60.0     # > 60 deg: high severity

    # 4. Asymmetry thresholds (delta degrees between limbs)
    asymmetry_warn_deg: float = 8.0         # > 8 deg: low severity
    asymmetry_severe_deg: float = 16.0      # > 16 deg: high severity

    # 5. Instability thresholds (standard deviation of horizontal trajectory sway)
    instability_warn_std: float = 0.035     # > 0.035: low severity
    instability_severe_std: float = 0.070   # > 0.070: high severity


class SquatRuleEvaluator:
    """
    Evaluates kinematic features against explainable biomechanical rules.
    """

    def __init__(self, config: SquatFormRuleConfig | None = None):
        self.config = config or SquatFormRuleConfig()

    def evaluate(self, features: SquatKinematicFeatures) -> List[FormIssue]:
        """
        Evaluates kinematic features and returns a list of detected FormIssue objects.
        """
        issues: List[FormIssue] = []
        conf = features.tracking_confidence

        # 1. Insufficient Depth Check
        if features.min_knee_angle > self.config.depth_target_deg:
            angle = features.min_knee_angle
            if angle > self.config.depth_shallow_bad_deg:
                severity = Severity.HIGH
                penalty = 25.0
            elif angle > self.config.depth_shallow_warn_deg:
                severity = Severity.MEDIUM
                penalty = 15.0
            else:
                severity = Severity.LOW
                penalty = 8.0

            issues.append(FormIssue(
                type=IssueType.INSUFFICIENT_DEPTH.value,
                severity=severity.value,
                confidence=min(1.0, conf * 0.95),
                details=f"Minimum knee flexion was {angle:.1f}° (target: <= {self.config.depth_target_deg:.1f}°).",
                penalty_points=penalty,
            ))

        # 2. Knee Alignment / Valgus Check
        if features.knee_valgus_index < self.config.valgus_safe_ratio:
            ratio = features.knee_valgus_index
            if ratio < self.config.valgus_severe_ratio:
                severity = Severity.HIGH
                penalty = 20.0
            elif ratio < self.config.valgus_mild_ratio:
                severity = Severity.MEDIUM
                penalty = 12.0
            else:
                severity = Severity.LOW
                penalty = 6.0

            issues.append(FormIssue(
                type=IssueType.KNEE_ALIGNMENT.value,
                severity=severity.value,
                confidence=min(1.0, conf * 0.90),
                details=f"Knees caved inward (valgus ratio: {ratio:.2f}, recommended: >= {self.config.valgus_safe_ratio:.2f}).",
                penalty_points=penalty,
            ))

        # 3. Excessive Torso Lean Check
        if features.max_torso_lean_deg > self.config.torso_safe_lean_deg:
            lean = features.max_torso_lean_deg
            if lean > self.config.torso_severe_lean_deg:
                severity = Severity.HIGH
                penalty = 20.0
            elif lean > self.config.torso_moderate_lean_deg:
                severity = Severity.MEDIUM
                penalty = 12.0
            else:
                severity = Severity.LOW
                penalty = 6.0

            issues.append(FormIssue(
                type=IssueType.EXCESSIVE_TORSO_LEAN.value,
                severity=severity.value,
                confidence=min(1.0, conf * 0.92),
                details=f"Torso leaned forward by {lean:.1f}° from vertical (recommended limit: <= {self.config.torso_safe_lean_deg:.1f}°).",
                penalty_points=penalty,
            ))

        # 4. Left/Right Asymmetry Check
        if features.symmetry_delta_deg > self.config.asymmetry_warn_deg:
            delta = features.symmetry_delta_deg
            if delta > self.config.asymmetry_severe_deg:
                severity = Severity.HIGH
                penalty = 15.0
            else:
                severity = Severity.MEDIUM
                penalty = 8.0

            issues.append(FormIssue(
                type=IssueType.ASYMMETRY.value,
                severity=severity.value,
                confidence=min(1.0, conf * 0.88),
                details=f"Bilateral limb asymmetry of {delta:.1f}° detected between left and right knee depths.",
                penalty_points=penalty,
            ))

        # 5. Excessive Movement Instability Check
        if features.lateral_instability_std > self.config.instability_warn_std:
            std = features.lateral_instability_std
            if std > self.config.instability_severe_std:
                severity = Severity.HIGH
                penalty = 15.0
            else:
                severity = Severity.MEDIUM
                penalty = 8.0

            issues.append(FormIssue(
                type=IssueType.MOVEMENT_INSTABILITY.value,
                severity=severity.value,
                confidence=min(1.0, conf * 0.85),
                details=f"Lateral bar/hip trajectory sway instability (std: {std:.3f}).",
                penalty_points=penalty,
            ))

        return issues
