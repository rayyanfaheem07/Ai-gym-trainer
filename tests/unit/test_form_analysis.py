import pytest

from ai.form_analysis.engine import SquatFormAnalysisEngine
from ai.form_analysis.features import SquatKinematicFeatures
from ai.form_analysis.rules import (
    IssueType,
    Severity,
    SquatRuleEvaluator,
)
from tests.unit.test_squat_analysis import generate_squat_frame


# 1. Perfect Form Test
def test_perfect_squat_form():
    engine = SquatFormAnalysisEngine()
    perfect_features = SquatKinematicFeatures(
        min_knee_angle=90.0,            # Good depth <= 95
        max_torso_lean_deg=25.0,        # Safe lean <= 35
        knee_valgus_index=0.96,         # Clean knee tracking >= 0.90
        symmetry_delta_deg=2.0,         # Low asymmetry <= 8.0
        lateral_instability_std=0.012,  # Low sway <= 0.035
        tracking_confidence=0.95,
    )

    result = engine.analyze_features(perfect_features)
    assert result.form_score == 100
    assert len(result.issues) == 0
    assert len(result.feedback) == 1
    assert "Excellent form" in result.feedback[0]


# 2. Insufficient Depth Test (Severity Scaling)
def test_insufficient_depth_severities():
    evaluator = SquatRuleEvaluator()

    # Low severity (knee = 100 deg, target <= 95)
    f_low = SquatKinematicFeatures(min_knee_angle=100.0)
    issues_low = evaluator.evaluate(f_low)
    assert len(issues_low) == 1
    assert issues_low[0].type == IssueType.INSUFFICIENT_DEPTH.value
    assert issues_low[0].severity == Severity.LOW.value

    # Medium severity (knee = 115 deg)
    f_med = SquatKinematicFeatures(min_knee_angle=115.0)
    issues_med = evaluator.evaluate(f_med)
    assert issues_med[0].severity == Severity.MEDIUM.value

    # High severity (knee = 135 deg)
    f_high = SquatKinematicFeatures(min_knee_angle=135.0)
    issues_high = evaluator.evaluate(f_high)
    assert issues_high[0].severity == Severity.HIGH.value


# 3. Knee Alignment / Valgus Test
def test_knee_valgus_detection():
    engine = SquatFormAnalysisEngine()

    # Severe knee caving (valgus ratio = 0.60, threshold < 0.65)
    valgus_features = SquatKinematicFeatures(
        min_knee_angle=90.0,
        knee_valgus_index=0.60,
        max_torso_lean_deg=20.0,
    )

    result = engine.analyze_features(valgus_features)
    assert any(i["type"] == IssueType.KNEE_ALIGNMENT.value for i in result.issues)
    assert any("valgus" in i["details"].lower() or "knees caved" in i["details"].lower() for i in result.issues)
    assert result.form_score < 100
    assert any("knees" in f.lower() for f in result.feedback)


# 4. Excessive Torso Lean Test
def test_excessive_torso_lean_detection():
    engine = SquatFormAnalysisEngine()

    # Torso lean = 52 deg (limit <= 35 deg)
    lean_features = SquatKinematicFeatures(
        min_knee_angle=90.0,
        max_torso_lean_deg=52.0,
    )

    result = engine.analyze_features(lean_features)
    assert any(i["type"] == IssueType.EXCESSIVE_TORSO_LEAN.value for i in result.issues)
    assert result.form_score <= 88
    assert any("torso" in f.lower() or "chest" in f.lower() for f in result.feedback)


# 5. Bilateral Asymmetry Test
def test_bilateral_asymmetry_detection():
    engine = SquatFormAnalysisEngine()

    # Asymmetry delta = 18 deg (> 16 deg severe)
    asym_features = SquatKinematicFeatures(
        min_knee_angle=90.0,
        symmetry_delta_deg=18.0,
    )

    result = engine.analyze_features(asym_features)
    assert any(i["type"] == IssueType.ASYMMETRY.value for i in result.issues)
    assert result.form_score < 100
    assert any("asymmetry" in f.lower() or "weight distribution" in f.lower() or "imbalance" in f.lower() for f in result.feedback)


# 6. Movement Instability Test
def test_movement_instability_detection():
    engine = SquatFormAnalysisEngine()

    # High trajectory sway = 0.085 (> 0.070 severe)
    instable_features = SquatKinematicFeatures(
        min_knee_angle=90.0,
        lateral_instability_std=0.085,
    )

    result = engine.analyze_features(instable_features)
    assert any(i["type"] == IssueType.MOVEMENT_INSTABILITY.value for i in result.issues)
    assert result.form_score < 100
    assert any("balance" in f.lower() or "stabilize" in f.lower() or "instability" in f.lower() for f in result.feedback)


# 7. Multiple Cumulative Violations & Score Clamping (0 - 100)
def test_cumulative_violations_and_score_bounds():
    engine = SquatFormAnalysisEngine()

    # Terrible form: all violations present with high severity
    bad_features = SquatKinematicFeatures(
        min_knee_angle=140.0,           # High depth issue (~31 pts)
        knee_valgus_index=0.50,          # High valgus (~25 pts)
        max_torso_lean_deg=65.0,         # High torso lean (~25 pts)
        symmetry_delta_deg=22.0,         # High asymmetry (~18.75 pts)
        lateral_instability_std=0.095,   # High instability (~18.75 pts)
    )

    result = engine.analyze_features(bad_features)
    # Total penalties > 100, must be clamped to 0
    assert result.form_score == 0
    assert len(result.issues) == 5
    assert len(result.feedback) >= 5


# 8. Trajectory Analysis Integration
def test_trajectory_analysis_integration():
    engine = SquatFormAnalysisEngine()

    # Generate sequence of frames representing a squat rep
    trajectory = [
        generate_squat_frame(175.0, hip_angle_deg=170.0),
        generate_squat_frame(135.0, hip_angle_deg=155.0),
        generate_squat_frame(90.0, hip_angle_deg=145.0),
        generate_squat_frame(135.0, hip_angle_deg=155.0),
        generate_squat_frame(170.0, hip_angle_deg=170.0),
    ]

    result = engine.analyze_trajectory(trajectory)
    assert isinstance(result.form_score, int)
    assert 0 <= result.form_score <= 100
    assert "min_knee_angle" in result.metrics
    assert result.metrics["min_knee_angle"] == pytest.approx(90.0, 1.0)


# 9. Structured Output Schema Conformance
def test_structured_output_conformance():
    engine = SquatFormAnalysisEngine()
    features = SquatKinematicFeatures(min_knee_angle=110.0)
    result = engine.analyze_features(features)

    d = result.to_dict()
    assert "form_score" in d
    assert "issues" in d
    assert "feedback" in d
    assert "metrics" in d
    assert isinstance(d["form_score"], int)
    assert isinstance(d["issues"], list)
    assert isinstance(d["feedback"], list)
    if d["issues"]:
        assert "type" in d["issues"][0]
        assert "severity" in d["issues"][0]
        assert "confidence" in d["issues"][0]
        assert "details" in d["issues"][0]
