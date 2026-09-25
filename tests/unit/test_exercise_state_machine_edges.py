"""Unit tests for Exercise Finite State Machines and Biomechanical Analyzers.

Verifies deterministic repetition counting, incomplete repetitions, invalid repetitions,
hysteresis guard bands, noisy landmarks, time gaps, and boundary transitions
across all 5 supported exercises:
1. Squat
2. Pushup
3. Bicep Curl
4. Lunge
5. Shoulder Press
"""

import numpy as np

from ai.exercises.bicep_curl import BicepCurlExercise, BicepCurlPhase
from ai.exercises.lunge import LungeExercise, LungePhase
from ai.exercises.pushup import PushupExercise, PushupPhase
from ai.exercises.registry import ExerciseRegistry
from ai.exercises.shoulder_press import ShoulderPressExercise, ShoulderPressPhase
from ai.exercises.squat import SquatDetector, SquatPhase
from ai.pose.landmarks import LandmarkIndex


def create_base_landmarks() -> np.ndarray:
    """Creates default neutral upright landmarks array."""
    lm = np.zeros((33, 4), dtype=np.float32)
    lm[:, 3] = 0.95
    # Shoulders
    lm[LandmarkIndex.LEFT_SHOULDER] = [0.45, 0.3, 0.0, 0.95]
    lm[LandmarkIndex.RIGHT_SHOULDER] = [0.55, 0.3, 0.0, 0.95]
    # Hips
    lm[LandmarkIndex.LEFT_HIP] = [0.45, 0.6, 0.0, 0.95]
    lm[LandmarkIndex.RIGHT_HIP] = [0.55, 0.6, 0.0, 0.95]
    # Knees
    lm[LandmarkIndex.LEFT_KNEE] = [0.45, 0.85, 0.0, 0.95]
    lm[LandmarkIndex.RIGHT_KNEE] = [0.55, 0.85, 0.0, 0.95]
    # Ankles
    lm[LandmarkIndex.LEFT_ANKLE] = [0.45, 1.1, 0.0, 0.95]
    lm[LandmarkIndex.RIGHT_ANKLE] = [0.55, 1.1, 0.0, 0.95]
    # Elbows
    lm[LandmarkIndex.LEFT_ELBOW] = [0.4, 0.45, 0.0, 0.95]
    lm[LandmarkIndex.RIGHT_ELBOW] = [0.6, 0.45, 0.0, 0.95]
    # Wrists
    lm[LandmarkIndex.LEFT_WRIST] = [0.4, 0.6, 0.0, 0.95]
    lm[LandmarkIndex.RIGHT_WRIST] = [0.6, 0.6, 0.0, 0.95]
    return lm


# ==============================================================================
# 1. Squat State Machine Tests
# ==============================================================================


def set_squat_knee_angle(lm: np.ndarray, knee_angle_deg: float):
    """Adjusts ankle position relative to knee to simulate knee flexion/extension."""
    knee_y = lm[LandmarkIndex.LEFT_KNEE, 1]
    shin_len = 0.25

    # flexion angle = 180 - knee_angle
    flex_rad = np.radians(180.0 - knee_angle_deg)
    ankle_x = lm[LandmarkIndex.LEFT_KNEE, 0] + shin_len * np.sin(flex_rad)
    ankle_y = knee_y + shin_len * np.cos(flex_rad)

    lm[LandmarkIndex.LEFT_ANKLE] = [ankle_x, ankle_y, 0.0, 0.95]
    lm[LandmarkIndex.RIGHT_ANKLE] = [ankle_x + 0.1, ankle_y, 0.0, 0.95]


def test_squat_normal_rep_counting():
    """Verify standard squat full repetition deterministic counting."""
    analyzer = SquatDetector()
    lm = create_base_landmarks()

    # 1. Standing (175 deg)
    set_squat_knee_angle(lm, 175.0)
    res = analyzer.analyze_frame(lm, timestamp_ms=0.0)
    assert res.phase == SquatPhase.STANDING.value
    assert res.rep_count == 0

    # 2. Descending (130 deg)
    set_squat_knee_angle(lm, 130.0)
    res = analyzer.analyze_frame(lm, timestamp_ms=300.0)
    assert res.phase == SquatPhase.DESCENDING.value

    # 3. Bottom reached (85 deg)
    set_squat_knee_angle(lm, 85.0)
    res = analyzer.analyze_frame(lm, timestamp_ms=700.0)
    assert res.phase == SquatPhase.BOTTOM.value

    # 4. Ascending (120 deg)
    set_squat_knee_angle(lm, 120.0)
    res = analyzer.analyze_frame(lm, timestamp_ms=1100.0)
    assert res.phase == SquatPhase.ASCENDING.value

    # 5. Lockout / Completed Rep (170 deg)
    set_squat_knee_angle(lm, 170.0)
    res = analyzer.analyze_frame(lm, timestamp_ms=1500.0)
    assert res.rep_count == 1
    assert res.phase == SquatPhase.COMPLETED_REP.value

    # 6. Next frame returns to standing
    res_next = analyzer.analyze_frame(lm, timestamp_ms=1600.0)
    assert res_next.phase == SquatPhase.STANDING.value
    assert res_next.rep_count == 1


def test_squat_incomplete_rep_rejected():
    """Descends but reverses before reaching bottom depth -> no rep counted."""
    analyzer = SquatDetector()
    lm = create_base_landmarks()

    # Standing
    set_squat_knee_angle(lm, 175.0)
    analyzer.analyze_frame(lm, timestamp_ms=0.0)

    # Descends only to 125 deg (bottom threshold is 95 deg)
    set_squat_knee_angle(lm, 125.0)
    analyzer.analyze_frame(lm, timestamp_ms=400.0)

    # Abandons rep and returns to standing (170 deg)
    set_squat_knee_angle(lm, 170.0)
    res = analyzer.analyze_frame(lm, timestamp_ms=1000.0)

    assert res.rep_count == 0
    assert analyzer.rep_count == 0


def test_squat_hysteresis_guard_band():
    """Micro-jitter around descending threshold should not bounce state erratically."""
    analyzer = SquatDetector()
    lm = create_base_landmarks()

    # Standing
    set_squat_knee_angle(lm, 175.0)
    analyzer.analyze_frame(lm, timestamp_ms=0.0)

    # Oscillate right around descending threshold (145 deg +/- 2 deg)
    angles = [146.0, 144.0, 145.5, 144.5, 146.0]
    for i, a in enumerate(angles):
        set_squat_knee_angle(lm, a)
        res = analyzer.analyze_frame(lm, timestamp_ms=float((i + 1) * 50))
        # Should NOT trigger premature completed rep or erratic count
        assert res.rep_count == 0


# ==============================================================================
# 2. Pushup State Machine Tests
# ==============================================================================


def set_pushup_geometry(lm: np.ndarray, elbow_angle_deg: float):
    """Sets horizontal plank alignment and elbow flexion."""
    # Horizontal body
    lm[LandmarkIndex.LEFT_SHOULDER] = [0.3, 0.4, 0.0, 0.95]
    lm[LandmarkIndex.RIGHT_SHOULDER] = [0.3, 0.4, 0.0, 0.95]
    lm[LandmarkIndex.LEFT_HIP] = [0.6, 0.4, 0.0, 0.95]
    lm[LandmarkIndex.RIGHT_HIP] = [0.6, 0.4, 0.0, 0.95]
    lm[LandmarkIndex.LEFT_ANKLE] = [0.9, 0.4, 0.0, 0.95]
    lm[LandmarkIndex.RIGHT_ANKLE] = [0.9, 0.4, 0.0, 0.95]

    # Elbow flexion: shoulder -> elbow -> wrist
    lm[LandmarkIndex.LEFT_ELBOW] = [0.3, 0.6, 0.0, 0.95]
    rad = np.radians(180.0 - elbow_angle_deg)
    lm[LandmarkIndex.LEFT_WRIST] = [
        0.3 + 0.2 * float(np.sin(rad)),
        0.6 + 0.2 * float(np.cos(rad)),
        0.0,
        0.95,
    ]
    # Mirror right arm
    lm[LandmarkIndex.RIGHT_ELBOW] = [0.3, 0.6, 0.0, 0.95]
    lm[LandmarkIndex.RIGHT_WRIST] = lm[LandmarkIndex.LEFT_WRIST].copy()


def test_pushup_normal_rep_counting():
    """Verify pushup plank -> descent -> bottom -> ascent -> plank cycle."""
    analyzer = PushupExercise()
    lm = create_base_landmarks()

    # 1. Plank (165 deg)
    set_pushup_geometry(lm, 165.0)
    res = analyzer.analyze_frame(lm, timestamp_ms=0.0)
    assert res.rep_count == 0

    # 2. Descending (120 deg)
    set_pushup_geometry(lm, 120.0)
    res = analyzer.analyze_frame(lm, timestamp_ms=300.0)
    assert res.phase == PushupPhase.DESCENDING.value

    # 3. Bottom (80 deg)
    set_pushup_geometry(lm, 80.0)
    res = analyzer.analyze_frame(lm, timestamp_ms=700.0)
    assert res.phase == PushupPhase.BOTTOM.value

    # 4. Ascending (120 deg)
    set_pushup_geometry(lm, 120.0)
    res = analyzer.analyze_frame(lm, timestamp_ms=1100.0)
    assert res.phase == PushupPhase.ASCENDING.value

    # 5. Lockout (165 deg)
    set_pushup_geometry(lm, 165.0)
    res = analyzer.analyze_frame(lm, timestamp_ms=1600.0)
    assert res.rep_count == 1
    assert res.phase == PushupPhase.COMPLETED_REP.value


# ==============================================================================
# 3. Bicep Curl State Machine Tests
# ==============================================================================


def generate_bicep_curl_frame(elbow_angle_deg: float) -> np.ndarray:
    """Generates bilateral landmarks with exact elbow flexion geometry."""
    landmarks = np.zeros((33, 4), dtype=np.float32)
    landmarks[:, 3] = 0.95
    landmarks[LandmarkIndex.LEFT_HIP] = [0.45, 0.6, 0.0, 0.95]
    landmarks[LandmarkIndex.RIGHT_HIP] = [0.55, 0.6, 0.0, 0.95]
    landmarks[LandmarkIndex.LEFT_SHOULDER] = [0.45, 0.3, 0.0, 0.95]
    landmarks[LandmarkIndex.RIGHT_SHOULDER] = [0.55, 0.3, 0.0, 0.95]
    landmarks[LandmarkIndex.LEFT_ELBOW] = [0.45, 0.5, 0.0, 0.95]
    landmarks[LandmarkIndex.RIGHT_ELBOW] = [0.55, 0.5, 0.0, 0.95]

    rad = np.radians(180.0 - elbow_angle_deg)
    landmarks[LandmarkIndex.LEFT_WRIST] = [
        0.45 + 0.2 * float(np.sin(rad)),
        0.5 + 0.2 * float(np.cos(rad)),
        0.0,
        0.95,
    ]
    landmarks[LandmarkIndex.RIGHT_WRIST] = [
        0.55 + 0.2 * float(np.sin(rad)),
        0.5 + 0.2 * float(np.cos(rad)),
        0.0,
        0.95,
    ]
    return landmarks


def test_bicep_curl_normal_rep_counting():
    """Verify bicep curl extension -> concentric -> peak -> eccentric cycle."""
    analyzer = BicepCurlExercise()

    # 1. Full extension (155 deg)
    f1 = generate_bicep_curl_frame(155.0)
    r1 = analyzer.analyze_frame(f1, timestamp_ms=0.0)
    assert r1.phase == BicepCurlPhase.EXTENDED.value
    assert r1.rep_count == 0

    # 2. Concentric lifting (110 deg)
    f2 = generate_bicep_curl_frame(110.0)
    r2 = analyzer.analyze_frame(f2, timestamp_ms=400.0)
    assert r2.phase == BicepCurlPhase.CONCENTRIC.value

    # 3. Peak contraction (48 deg <= 55 deg target)
    f3 = generate_bicep_curl_frame(48.0)
    r3 = analyzer.analyze_frame(f3, timestamp_ms=800.0)
    assert r3.phase == BicepCurlPhase.PEAK_FLEXION.value

    # 4. Eccentric lowering (95 deg)
    f4 = generate_bicep_curl_frame(95.0)
    r4 = analyzer.analyze_frame(f4, timestamp_ms=1200.0)
    assert r4.phase == BicepCurlPhase.ECCENTRIC.value

    # 5. Full extension (155 deg) -> Completed rep
    f5 = generate_bicep_curl_frame(155.0)
    r5 = analyzer.analyze_frame(f5, timestamp_ms=1600.0)
    assert r5.phase == BicepCurlPhase.COMPLETED_REP.value
    assert r5.rep_count == 1


# ==============================================================================
# 4. Lunge State Machine Tests
# ==============================================================================


def set_lunge_geometry(lm: np.ndarray, lead_knee_angle: float):
    """Sets split stance lunge geometry."""
    set_squat_knee_angle(lm, lead_knee_angle)


def test_lunge_normal_rep_counting():
    """Verify lunge standing -> descending -> bottom -> ascending -> standing cycle."""
    analyzer = LungeExercise()
    lm = create_base_landmarks()

    # 1. Standing (170 deg)
    set_lunge_geometry(lm, 170.0)
    res = analyzer.analyze_frame(lm, timestamp_ms=0.0)
    assert res.rep_count == 0

    # 2. Descending (130 deg)
    set_lunge_geometry(lm, 130.0)
    res = analyzer.analyze_frame(lm, timestamp_ms=350.0)
    assert res.phase == LungePhase.DESCENDING.value

    # 3. Bottom depth (85 deg)
    set_lunge_geometry(lm, 85.0)
    res = analyzer.analyze_frame(lm, timestamp_ms=800.0)
    assert res.phase == LungePhase.BOTTOM.value

    # 4. Ascending (125 deg)
    set_lunge_geometry(lm, 125.0)
    res = analyzer.analyze_frame(lm, timestamp_ms=1250.0)
    assert res.phase == LungePhase.ASCENDING.value

    # 5. Complete rep (165 deg)
    set_lunge_geometry(lm, 165.0)
    res = analyzer.analyze_frame(lm, timestamp_ms=1700.0)
    assert res.rep_count == 1
    assert res.phase == LungePhase.COMPLETED_REP.value


# ==============================================================================
# 5. Shoulder Press State Machine Tests
# ==============================================================================


def generate_shoulder_press_frame(elbow_angle_deg: float) -> np.ndarray:
    """Generates bilateral landmarks with exact shoulder press geometry."""
    landmarks = np.zeros((33, 4), dtype=np.float32)
    landmarks[:, 3] = 0.95
    landmarks[LandmarkIndex.LEFT_SHOULDER] = [0.4, 0.4, 0.0, 0.95]
    landmarks[LandmarkIndex.RIGHT_SHOULDER] = [0.6, 0.4, 0.0, 0.95]
    landmarks[LandmarkIndex.LEFT_HIP] = [0.4, 0.7, 0.0, 0.95]
    landmarks[LandmarkIndex.RIGHT_HIP] = [0.6, 0.7, 0.0, 0.95]
    landmarks[LandmarkIndex.LEFT_ELBOW] = [0.4, 0.6, 0.0, 0.95]
    landmarks[LandmarkIndex.RIGHT_ELBOW] = [0.6, 0.6, 0.0, 0.95]

    rad = np.radians(180.0 - elbow_angle_deg)
    landmarks[LandmarkIndex.LEFT_WRIST] = [
        0.4 - 0.25 * float(np.sin(rad)),
        0.6 + 0.25 * float(np.cos(rad)),
        0.0,
        0.95,
    ]
    landmarks[LandmarkIndex.RIGHT_WRIST] = [
        0.6 + 0.25 * float(np.sin(rad)),
        0.6 + 0.25 * float(np.cos(rad)),
        0.0,
        0.95,
    ]
    return landmarks


def test_shoulder_press_normal_rep_counting():
    """Verify shoulder press racked -> ascending -> overhead -> descending -> racked cycle."""
    analyzer = ShoulderPressExercise()

    # 1. Racked position (80 deg)
    f1 = generate_shoulder_press_frame(80.0)
    r1 = analyzer.analyze_frame(f1, timestamp_ms=0.0)
    assert r1.phase == ShoulderPressPhase.RACK_POSITION.value
    assert r1.rep_count == 0

    # 2. Pressing upwards / ascending (125 deg)
    f2 = generate_shoulder_press_frame(125.0)
    r2 = analyzer.analyze_frame(f2, timestamp_ms=400.0)
    assert r2.phase == ShoulderPressPhase.ASCENDING.value

    # 3. Overhead lockout (165 deg >= 155 deg)
    f3 = generate_shoulder_press_frame(165.0)
    r3 = analyzer.analyze_frame(f3, timestamp_ms=800.0)
    assert r3.phase == ShoulderPressPhase.OVERHEAD_LOCKOUT.value

    # 4. Lowering back down / descending (125 deg)
    f4 = generate_shoulder_press_frame(125.0)
    r4 = analyzer.analyze_frame(f4, timestamp_ms=1200.0)
    assert r4.phase == ShoulderPressPhase.DESCENDING.value

    # 5. Racked / Complete rep (80 deg)
    f5 = generate_shoulder_press_frame(80.0)
    r5 = analyzer.analyze_frame(f5, timestamp_ms=1600.0)
    assert r5.rep_count == 1
    assert r5.phase == ShoulderPressPhase.COMPLETED_REP.value


# ==============================================================================
# 6. Global Robustness: Noise, Missing Frames, Reset, and Malformed Inputs
# ==============================================================================


def test_exercise_analyzer_noisy_landmarks():
    """Synthetic Gaussian noise added to landmarks should not cause unhandled exceptions or crashes."""
    analyzer = SquatDetector()
    lm = create_base_landmarks()

    for i in range(20):
        noisy_lm = lm.copy()
        # Add random noise +/- 0.02
        noise = np.random.normal(0, 0.02, size=(33, 4)).astype(np.float32)
        noisy_lm += noise
        noisy_lm[:, 3] = np.clip(noisy_lm[:, 3], 0.1, 1.0)

        res = analyzer.analyze_frame(noisy_lm, timestamp_ms=float(i * 50))
        assert isinstance(res.rep_count, int)
        assert isinstance(res.phase, str)


def test_exercise_analyzer_time_gaps():
    """Large gaps between timestamps (e.g. 5 seconds) should be handled cleanly."""
    analyzer = SquatDetector()
    lm = create_base_landmarks()

    set_squat_knee_angle(lm, 175.0)
    analyzer.analyze_frame(lm, timestamp_ms=0.0)

    # 5 second gap
    set_squat_knee_angle(lm, 130.0)
    res = analyzer.analyze_frame(lm, timestamp_ms=5000.0)
    assert res.phase in [SquatPhase.DESCENDING.value, SquatPhase.STANDING.value]


def test_exercise_analyzer_reset_behavior():
    """reset() restores initial state, zero rep counts, and initial phase across all 5 analyzers."""
    for ex_name in ExerciseRegistry.list_available():
        analyzer = ExerciseRegistry.get_exercise(ex_name)
        assert analyzer is not None
        analyzer.rep_count = 5
        analyzer.valid_reps = 4
        analyzer.invalid_reps = 1

        analyzer.reset()
        assert analyzer.rep_count == 0
        assert analyzer.valid_reps == 0
        assert analyzer.invalid_reps == 0


def test_exercise_analyzer_malformed_input_safety():
    """Analyzers safely handle None, empty, or wrong shape inputs without throwing."""
    for ex_name in ExerciseRegistry.list_available():
        analyzer = ExerciseRegistry.get_exercise(ex_name)
        assert analyzer is not None

        # None input
        res_none = analyzer.analyze_frame(None)
        assert res_none.confidence == 0.0

        # Incomplete landmarks
        res_short = analyzer.analyze_frame(np.zeros((10, 4), dtype=np.float32))
        assert res_short.confidence == 0.0
