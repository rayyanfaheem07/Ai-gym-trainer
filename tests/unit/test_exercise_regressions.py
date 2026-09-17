import numpy as np
import pytest

from ai.exercises.base import BaseExerciseAnalyzer, ExerciseAnalysisResult
from ai.exercises.bicep_curl import BicepCurlExercise, BicepCurlPhase
from ai.exercises.lunge import LungeExercise, LungePhase
from ai.exercises.pushup import PushupExercise, PushupPhase
from ai.exercises.registry import ExerciseRegistry
from ai.exercises.shoulder_press import ShoulderPressExercise, ShoulderPressPhase
from ai.exercises.squat import SquatDetector, SquatPhase
from tests.unit.test_bicep_curl_analysis import generate_bicep_curl_frame
from tests.unit.test_lunge_analysis import generate_lunge_frame
from tests.unit.test_pushup_analysis import generate_pushup_frame
from tests.unit.test_shoulder_press_analysis import generate_shoulder_press_frame
from tests.unit.test_squat_analysis import generate_squat_frame


@pytest.fixture
def all_exercises():
    return [
        ("squat", SquatDetector()),
        ("pushup", PushupExercise()),
        ("bicep_curl", BicepCurlExercise()),
        ("lunge", LungeExercise()),
        ("shoulder_press", ShoulderPressExercise()),
    ]


def test_all_exercises_inherit_base_analyzer(all_exercises):
    """Verify Phase 5 architecture: All 5 exercises inherit from BaseExerciseAnalyzer."""
    for name, analyzer in all_exercises:
        assert isinstance(analyzer, BaseExerciseAnalyzer), f"{name} does not inherit from BaseExerciseAnalyzer"
        assert analyzer.name == name
        assert analyzer.rep_count == 0
        assert analyzer.valid_reps == 0
        assert analyzer.invalid_reps == 0


def test_all_exercises_return_standard_contract(all_exercises):
    """Verify Phase 5 architecture: All 5 exercises return ExerciseAnalysisResult with matching schema."""
    generators = {
        "squat": lambda: generate_squat_frame(175.0),
        "pushup": lambda: generate_pushup_frame(160.0),
        "bicep_curl": lambda: generate_bicep_curl_frame(155.0),
        "lunge": lambda: generate_lunge_frame(165.0, trail_knee_deg=165.0),
        "shoulder_press": lambda: generate_shoulder_press_frame(80.0),
    }

    for name, analyzer in all_exercises:
        frame = generators[name]()
        result = analyzer.analyze_frame(frame, timestamp_ms=100.0)

        assert isinstance(result, ExerciseAnalysisResult)
        assert result.exercise == name
        assert isinstance(result.phase, str)
        assert isinstance(result.rep_count, int)
        assert isinstance(result.valid_reps, int)
        assert isinstance(result.invalid_reps, int)
        assert isinstance(result.confidence, float)
        assert isinstance(result.primary_angle, float)
        assert isinstance(result.current_angles, dict)
        assert isinstance(result.form_score, int)
        assert isinstance(result.is_valid_rep, bool)
        assert isinstance(result.issues, list)
        assert isinstance(result.feedback, list)
        assert isinstance(result.metrics, dict)
        assert isinstance(result.rep_duration_sec, float)

        # Verify serialization dict matches API schema
        d = result.to_dict()
        assert d["exercise"] == name
        assert "phase" in d
        assert "rep_count" in d
        assert "form_score" in d
        assert "feedback" in d
        assert "metrics" in d


def test_regression_missing_landmarks_all_exercises(all_exercises):
    """Verify missing landmarks (None, empty array, short array) are handled safely across all 5 exercises."""
    for name, analyzer in all_exercises:
        # None
        r_none = analyzer.analyze_frame(None, timestamp_ms=0)
        assert r_none.confidence == 0.0
        assert r_none.exercise == name
        assert len(r_none.feedback) > 0

        # Empty array
        r_empty = analyzer.analyze_frame(np.zeros((0, 4), dtype=np.float32), timestamp_ms=10)
        assert r_empty.confidence == 0.0
        assert r_empty.exercise == name

        # Short landmark array (e.g. 15 landmarks)
        r_short = analyzer.analyze_frame(np.zeros((15, 4), dtype=np.float32), timestamp_ms=20)
        assert r_short.confidence == 0.0
        assert r_short.exercise == name


def test_regression_low_visibility_all_exercises(all_exercises):
    """Verify low visibility confidence (< threshold) is handled safely across all 5 exercises."""
    generators = {
        "squat": lambda: generate_squat_frame(175.0, visibility=0.05),
        "pushup": lambda: generate_pushup_frame(160.0, visibility=0.05),
        "bicep_curl": lambda: generate_bicep_curl_frame(155.0, visibility=0.05),
        "lunge": lambda: generate_lunge_frame(165.0, trail_knee_deg=165.0, visibility=0.05),
        "shoulder_press": lambda: generate_shoulder_press_frame(80.0, visibility=0.05),
    }

    for name, analyzer in all_exercises:
        frame = generators[name]()
        res = analyzer.analyze_frame(frame, timestamp_ms=100.0)
        assert res.confidence < 0.45
        assert res.rep_count == 0
        assert any("low tracking" in f.lower() or "visibility" in f.lower() or "confidence" in f.lower() for f in res.feedback)


def test_regression_extremely_fast_movements_all_exercises():
    """Verify movements faster than min_rep_duration_sec (0.5s) are rejected across all 5 exercises."""
    # 1. Squat (100ms)
    sq = SquatDetector()
    sq.analyze_frame(generate_squat_frame(175.0), timestamp_ms=0)
    sq.analyze_frame(generate_squat_frame(88.0), timestamp_ms=50)
    sq.analyze_frame(generate_squat_frame(170.0), timestamp_ms=100)
    assert sq.rep_count == 0

    # 2. Pushup (100ms)
    pu = PushupExercise()
    pu.analyze_frame(generate_pushup_frame(160.0), timestamp_ms=0)
    pu.analyze_frame(generate_pushup_frame(85.0), timestamp_ms=50)
    pu.analyze_frame(generate_pushup_frame(160.0), timestamp_ms=100)
    assert pu.rep_count == 0

    # 3. Bicep Curl (100ms)
    bc = BicepCurlExercise()
    bc.analyze_frame(generate_bicep_curl_frame(155.0), timestamp_ms=0)
    bc.analyze_frame(generate_bicep_curl_frame(45.0), timestamp_ms=50)
    bc.analyze_frame(generate_bicep_curl_frame(155.0), timestamp_ms=100)
    assert bc.rep_count == 0

    # 4. Lunge (100ms)
    lu = LungeExercise()
    lu.analyze_frame(generate_lunge_frame(165.0, trail_knee_deg=165.0), timestamp_ms=0)
    lu.analyze_frame(generate_lunge_frame(88.0, trail_knee_deg=92.0), timestamp_ms=50)
    lu.analyze_frame(generate_lunge_frame(165.0, trail_knee_deg=165.0), timestamp_ms=100)
    assert lu.rep_count == 0

    # 5. Shoulder Press (100ms)
    sp = ShoulderPressExercise()
    sp.analyze_frame(generate_shoulder_press_frame(80.0), timestamp_ms=0)
    sp.analyze_frame(generate_shoulder_press_frame(165.0), timestamp_ms=50)
    sp.analyze_frame(generate_shoulder_press_frame(80.0), timestamp_ms=100)
    assert sp.rep_count == 0


def test_regression_threshold_jitter_no_duplicate_counting():
    """Verify hysteresis bands prevent oscillatory false reps from threshold jitter across all 5 exercises."""
    # Squat jitter around 160 deg
    sq = SquatDetector()
    for i, a in enumerate([160.0, 158.0, 162.0, 159.0, 161.0]):
        sq.analyze_frame(generate_squat_frame(a), timestamp_ms=i * 100)
    assert sq.rep_count == 0

    # Pushup jitter around 155 deg
    pu = PushupExercise()
    for i, a in enumerate([155.0, 153.0, 157.0, 154.0, 156.0]):
        pu.analyze_frame(generate_pushup_frame(a), timestamp_ms=i * 100)
    assert pu.rep_count == 0

    # Bicep curl jitter around 150 deg
    bc = BicepCurlExercise()
    for i, a in enumerate([150.0, 148.0, 152.0, 149.0, 151.0]):
        bc.analyze_frame(generate_bicep_curl_frame(a), timestamp_ms=i * 100)
    assert bc.rep_count == 0

    # Lunge jitter around 160 deg
    lu = LungeExercise()
    for i, a in enumerate([160.0, 158.0, 162.0, 159.0, 161.0]):
        lu.analyze_frame(generate_lunge_frame(a, trail_knee_deg=a), timestamp_ms=i * 100)
    assert lu.rep_count == 0

    # Shoulder press jitter around 90 deg
    sp = ShoulderPressExercise()
    for i, a in enumerate([90.0, 88.0, 92.0, 89.0, 91.0]):
        sp.analyze_frame(generate_shoulder_press_frame(a), timestamp_ms=i * 100)
    assert sp.rep_count == 0


def test_regression_reset_behavior_all_exercises(all_exercises):
    """Verify reset() properly clears rep counters, valid/invalid counts, trajectories, and FSM states."""
    for name, analyzer in all_exercises:
        # Simulate dirty state
        analyzer.rep_count = 5
        analyzer.valid_reps = 3
        analyzer.invalid_reps = 2
        analyzer._current_rep_trajectory = [np.zeros((33, 4))]

        analyzer.reset()

        assert analyzer.rep_count == 0
        assert analyzer.valid_reps == 0
        assert analyzer.invalid_reps == 0
        assert len(analyzer._current_rep_trajectory) == 0
        assert analyzer._rep_start_time_ms == 0.0

        if name == "squat":
            assert analyzer.phase == SquatPhase.STANDING
        elif name == "pushup":
            assert analyzer.phase == PushupPhase.PLANK
        elif name == "bicep_curl":
            assert analyzer.phase == BicepCurlPhase.EXTENDED
        elif name == "lunge":
            assert analyzer.phase == LungePhase.STANDING
        elif name == "shoulder_press":
            assert analyzer.phase == ShoulderPressPhase.RACK_POSITION


def test_exercise_switching_and_reset_workflow():
    """Verify dynamic switching between exercises via ExerciseRegistry and fresh state isolation."""
    exercise_names = ["squat", "pushup", "bicep_curl", "lunge", "shoulder_press"]

    for ex_name in exercise_names:
        analyzer = ExerciseRegistry.get_exercise(ex_name)
        assert analyzer is not None
        assert analyzer.name == ex_name
        assert analyzer.rep_count == 0

        # Perform 1 frame analysis
        if ex_name == "squat":
            r = analyzer.analyze_frame(generate_squat_frame(175.0), timestamp_ms=100)
        elif ex_name == "pushup":
            r = analyzer.analyze_frame(generate_pushup_frame(160.0), timestamp_ms=100)
        elif ex_name == "bicep_curl":
            r = analyzer.analyze_frame(generate_bicep_curl_frame(155.0), timestamp_ms=100)
        elif ex_name == "lunge":
            r = analyzer.analyze_frame(generate_lunge_frame(165.0, trail_knee_deg=165.0), timestamp_ms=100)
        elif ex_name == "shoulder_press":
            r = analyzer.analyze_frame(generate_shoulder_press_frame(80.0), timestamp_ms=100)

        assert r.exercise == ex_name
        assert r.rep_count == 0
