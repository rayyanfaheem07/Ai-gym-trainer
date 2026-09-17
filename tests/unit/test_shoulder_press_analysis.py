import numpy as np

from ai.exercises.shoulder_press import ShoulderPressExercise, ShoulderPressPhase
from ai.pose.landmarks import LandmarkIndex


def generate_shoulder_press_frame(
    elbow_angle_deg: float,
    torso_pitch_deg: float = 0.0,
    asymmetry_deg: float = 0.0,
    visibility: float = 0.95,
) -> np.ndarray:
    """
    Generates synthetic 33-point landmarks with shoulder press geometry:
    - Shoulders at (0.4, 0.4) and (0.6, 0.4)
    - Hips at (0.4, 0.7) and (0.6, 0.7)
    - Elbows at shoulder level
    - Wrists computed from elbow extension angle (pressing overhead)
    """
    landmarks = np.zeros((33, 4), dtype=np.float32)
    landmarks[:, 3] = visibility

    # Torso (Shoulders and Hips)
    torso_rad = np.radians(torso_pitch_deg)
    landmarks[LandmarkIndex.LEFT_SHOULDER] = [
        0.4 - 0.3 * np.sin(torso_rad),
        0.7 - 0.3 * np.cos(torso_rad),
        0.0,
        visibility,
    ]
    landmarks[LandmarkIndex.RIGHT_SHOULDER] = [
        0.6 - 0.3 * np.sin(torso_rad),
        0.7 - 0.3 * np.cos(torso_rad),
        0.0,
        visibility,
    ]
    landmarks[LandmarkIndex.LEFT_HIP] = [0.4, 0.7, 0.0, visibility]
    landmarks[LandmarkIndex.RIGHT_HIP] = [0.6, 0.7, 0.0, visibility]

    # Upper arms / Elbows
    landmarks[LandmarkIndex.LEFT_ELBOW] = [0.4, 0.6, 0.0, visibility]
    landmarks[LandmarkIndex.RIGHT_ELBOW] = [0.6, 0.6, 0.0, visibility]

    # Forearms / Wrists based on elbow extension (pressing upward)
    left_rad = np.radians(180.0 - elbow_angle_deg)
    right_rad = np.radians(180.0 - (elbow_angle_deg + asymmetry_deg))

    landmarks[LandmarkIndex.LEFT_WRIST] = [
        0.4 - 0.25 * np.sin(left_rad),
        0.6 + 0.25 * np.cos(left_rad),
        0.0,
        visibility,
    ]
    landmarks[LandmarkIndex.RIGHT_WRIST] = [
        0.6 + 0.25 * np.sin(right_rad),
        0.6 + 0.25 * np.cos(right_rad),
        0.0,
        visibility,
    ]

    return landmarks


def test_valid_shoulder_press_full_cycle():
    exercise = ShoulderPressExercise()
    assert exercise.phase == ShoulderPressPhase.RACK_POSITION
    assert exercise.rep_count == 0

    # START -> MOVEMENT -> PEAK/BOTTOM -> RETURN
    # 1. Start at rack position (80 deg)
    f1 = generate_shoulder_press_frame(80.0)
    r1 = exercise.analyze_frame(f1, timestamp_ms=0)
    assert r1.phase == ShoulderPressPhase.RACK_POSITION.value

    # 2. Ascending press (125 deg)
    f2 = generate_shoulder_press_frame(125.0)
    r2 = exercise.analyze_frame(f2, timestamp_ms=400)
    assert r2.phase == ShoulderPressPhase.ASCENDING.value

    # 3. Overhead Lockout (165 deg >= 155 target)
    f3 = generate_shoulder_press_frame(165.0)
    r3 = exercise.analyze_frame(f3, timestamp_ms=800)
    assert r3.phase == ShoulderPressPhase.OVERHEAD_LOCKOUT.value

    # 4. Descending (125 deg)
    f4 = generate_shoulder_press_frame(125.0)
    r4 = exercise.analyze_frame(f4, timestamp_ms=1200)
    assert r4.phase == ShoulderPressPhase.DESCENDING.value

    # 5. Return to rack (80 deg) -> Completed rep
    f5 = generate_shoulder_press_frame(80.0)
    r5 = exercise.analyze_frame(f5, timestamp_ms=1600)
    assert r5.phase == ShoulderPressPhase.COMPLETED_REP.value
    assert r5.rep_count == 1
    assert r5.valid_reps == 1
    assert r5.invalid_reps == 0
    assert r5.is_valid_rep is True
    assert r5.form_score >= 80
    assert len(r5.feedback) > 0


def test_shoulder_press_multiple_consecutive_reps():
    exercise = ShoulderPressExercise()

    for rep in range(3):
        base_t = rep * 2000
        exercise.analyze_frame(generate_shoulder_press_frame(80.0), timestamp_ms=base_t + 0)
        exercise.analyze_frame(generate_shoulder_press_frame(125.0), timestamp_ms=base_t + 400)
        exercise.analyze_frame(generate_shoulder_press_frame(165.0), timestamp_ms=base_t + 800)
        exercise.analyze_frame(generate_shoulder_press_frame(125.0), timestamp_ms=base_t + 1200)
        r = exercise.analyze_frame(generate_shoulder_press_frame(80.0), timestamp_ms=base_t + 1600)
        assert r.phase == ShoulderPressPhase.COMPLETED_REP.value

    assert exercise.rep_count == 3
    assert exercise.valid_reps == 3
    assert exercise.invalid_reps == 0


def test_shoulder_press_incomplete_aborted_movement():
    exercise = ShoulderPressExercise()

    # User initiates slight movement (108 deg) and aborts back to rack without completing press
    exercise.analyze_frame(generate_shoulder_press_frame(80.0), timestamp_ms=0)
    exercise.analyze_frame(generate_shoulder_press_frame(108.0), timestamp_ms=300)
    exercise.analyze_frame(generate_shoulder_press_frame(80.0), timestamp_ms=600)

    assert exercise.rep_count == 0
    assert exercise.valid_reps == 0
    assert exercise.invalid_reps == 0
    assert exercise.phase == ShoulderPressPhase.RACK_POSITION


def test_shoulder_press_jitter_and_no_duplicate_counting():
    exercise = ShoulderPressExercise()

    # Rack position jitter
    for i, angle in enumerate([80.0, 78.0, 82.0, 81.0]):
        exercise.analyze_frame(generate_shoulder_press_frame(angle), timestamp_ms=i * 100)
    assert exercise.rep_count == 0

    # 1 rep
    exercise.analyze_frame(generate_shoulder_press_frame(80.0), timestamp_ms=500)
    exercise.analyze_frame(generate_shoulder_press_frame(120.0), timestamp_ms=900)
    exercise.analyze_frame(generate_shoulder_press_frame(165.0), timestamp_ms=1300)
    exercise.analyze_frame(generate_shoulder_press_frame(120.0), timestamp_ms=1700)
    exercise.analyze_frame(generate_shoulder_press_frame(80.0), timestamp_ms=2100)
    assert exercise.rep_count == 1

    # Post-rep jitter in rack
    for i, angle in enumerate([78.0, 82.0, 80.0]):
        exercise.analyze_frame(generate_shoulder_press_frame(angle), timestamp_ms=2200 + i * 100)
    assert exercise.rep_count == 1


def test_shoulder_press_fast_movement_rejected():
    exercise = ShoulderPressExercise()

    # Fast 100ms movement
    exercise.analyze_frame(generate_shoulder_press_frame(80.0), timestamp_ms=0)
    exercise.analyze_frame(generate_shoulder_press_frame(120.0), timestamp_ms=30)
    exercise.analyze_frame(generate_shoulder_press_frame(165.0), timestamp_ms=60)
    exercise.analyze_frame(generate_shoulder_press_frame(120.0), timestamp_ms=80)
    exercise.analyze_frame(generate_shoulder_press_frame(80.0), timestamp_ms=100)

    assert exercise.rep_count == 0


def test_shoulder_press_incomplete_lockout():
    exercise = ShoulderPressExercise()

    # Incomplete lockout (peak only 130 deg, target >= 155)
    exercise.analyze_frame(generate_shoulder_press_frame(80.0), timestamp_ms=0)
    exercise.analyze_frame(generate_shoulder_press_frame(120.0), timestamp_ms=300)
    exercise.analyze_frame(generate_shoulder_press_frame(130.0), timestamp_ms=600)
    exercise.analyze_frame(generate_shoulder_press_frame(110.0), timestamp_ms=900)
    r = exercise.analyze_frame(generate_shoulder_press_frame(80.0), timestamp_ms=1200)

    assert r.rep_count == 1
    assert r.invalid_reps == 1
    assert r.valid_reps == 0
    assert any(i["type"] == "incomplete_lockout" for i in r.issues)
    assert any("lockout" in f.lower() or "extend" in f.lower() for f in r.feedback)


def test_shoulder_press_lumbar_hyperextension():
    exercise = ShoulderPressExercise()

    # Backward torso arch = 28 deg > 15 threshold
    f = generate_shoulder_press_frame(80.0, torso_pitch_deg=28.0)
    r = exercise.analyze_frame(f, timestamp_ms=100)

    assert any(i["type"] == "lumbar_hyperextension" for i in r.issues)
    assert any("arch" in f.lower() or "core" in f.lower() for f in r.feedback)
    assert r.form_score < 100


def test_shoulder_press_arm_asymmetry():
    exercise = ShoulderPressExercise()

    # Asymmetry delta = 20 deg (> 12 threshold)
    f = generate_shoulder_press_frame(80.0, asymmetry_deg=20.0)
    r = exercise.analyze_frame(f, timestamp_ms=100)

    assert any(i["type"] == "arm_asymmetry" for i in r.issues)
    assert r.form_score < 100


def test_shoulder_press_missing_and_low_confidence_landmarks():
    exercise = ShoulderPressExercise()

    # None landmarks
    r_none = exercise.analyze_frame(None, timestamp_ms=100)
    assert r_none.confidence == 0.0
    assert r_none.exercise == "shoulder_press"

    # Low visibility
    low_conf_frame = generate_shoulder_press_frame(80.0, visibility=0.1)
    r_low = exercise.analyze_frame(low_conf_frame, timestamp_ms=200)
    assert r_low.confidence < 0.45
    assert any("low tracking" in f.lower() or "visibility" in f.lower() for f in r_low.feedback)


def test_shoulder_press_reset_behavior():
    exercise = ShoulderPressExercise()

    # Perform 1 rep
    exercise.analyze_frame(generate_shoulder_press_frame(80.0), timestamp_ms=0)
    exercise.analyze_frame(generate_shoulder_press_frame(125.0), timestamp_ms=400)
    exercise.analyze_frame(generate_shoulder_press_frame(165.0), timestamp_ms=800)
    exercise.analyze_frame(generate_shoulder_press_frame(125.0), timestamp_ms=1200)
    exercise.analyze_frame(generate_shoulder_press_frame(80.0), timestamp_ms=1600)
    assert exercise.rep_count == 1

    # Reset
    exercise.reset()
    assert exercise.rep_count == 0
    assert exercise.valid_reps == 0
    assert exercise.invalid_reps == 0
    assert exercise.phase == ShoulderPressPhase.RACK_POSITION
    assert len(exercise._current_rep_trajectory) == 0
