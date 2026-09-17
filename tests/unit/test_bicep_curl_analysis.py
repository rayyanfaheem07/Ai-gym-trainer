import numpy as np

from ai.exercises.bicep_curl import BicepCurlExercise, BicepCurlPhase
from ai.pose.landmarks import LandmarkIndex


def generate_bicep_curl_frame(
    elbow_angle_deg: float,
    shoulder_sway_deg: float = 0.0,
    torso_pitch_deg: float = 0.0,
    asymmetry_deg: float = 0.0,
    visibility: float = 0.95,
) -> np.ndarray:
    """
    Generates synthetic 33-point landmarks with bicep curl geometry:
    - Shoulders and Hips positioned for torso pitch/lean
    - Elbows pinned or swaying from shoulders
    - Wrists computed based on elbow flexion angle
    """
    landmarks = np.zeros((33, 4), dtype=np.float32)
    landmarks[:, 3] = visibility

    # Torso (Shoulders & Hips)
    torso_rad = np.radians(torso_pitch_deg)
    landmarks[LandmarkIndex.LEFT_HIP] = [0.45, 0.6, 0.0, visibility]
    landmarks[LandmarkIndex.RIGHT_HIP] = [0.55, 0.6, 0.0, visibility]

    landmarks[LandmarkIndex.LEFT_SHOULDER] = [
        0.45 - 0.3 * np.sin(torso_rad),
        0.6 - 0.3 * np.cos(torso_rad),
        0.0,
        visibility,
    ]
    landmarks[LandmarkIndex.RIGHT_SHOULDER] = [
        0.55 - 0.3 * np.sin(torso_rad),
        0.6 - 0.3 * np.cos(torso_rad),
        0.0,
        visibility,
    ]

    # Upper arms / Elbows
    sway_rad = np.radians(shoulder_sway_deg)
    landmarks[LandmarkIndex.LEFT_ELBOW] = [
        landmarks[LandmarkIndex.LEFT_SHOULDER, 0] + 0.2 * np.sin(sway_rad),
        landmarks[LandmarkIndex.LEFT_SHOULDER, 1] + 0.2 * np.cos(sway_rad),
        0.0,
        visibility,
    ]
    landmarks[LandmarkIndex.RIGHT_ELBOW] = [
        landmarks[LandmarkIndex.RIGHT_SHOULDER, 0] + 0.2 * np.sin(sway_rad),
        landmarks[LandmarkIndex.RIGHT_SHOULDER, 1] + 0.2 * np.cos(sway_rad),
        0.0,
        visibility,
    ]

    # Forearms / Wrists based on elbow angle
    left_rad = sway_rad + np.radians(180.0 - elbow_angle_deg)
    right_rad = sway_rad + np.radians(180.0 - (elbow_angle_deg + asymmetry_deg))

    landmarks[LandmarkIndex.LEFT_WRIST] = [
        landmarks[LandmarkIndex.LEFT_ELBOW, 0] + 0.2 * np.sin(left_rad),
        landmarks[LandmarkIndex.LEFT_ELBOW, 1] + 0.2 * np.cos(left_rad),
        0.0,
        visibility,
    ]
    landmarks[LandmarkIndex.RIGHT_WRIST] = [
        landmarks[LandmarkIndex.RIGHT_ELBOW, 0] + 0.2 * np.sin(right_rad),
        landmarks[LandmarkIndex.RIGHT_ELBOW, 1] + 0.2 * np.cos(right_rad),
        0.0,
        visibility,
    ]

    return landmarks


def test_valid_bicep_curl_full_cycle():
    exercise = BicepCurlExercise()
    assert exercise.phase == BicepCurlPhase.EXTENDED
    assert exercise.rep_count == 0

    # START -> MOVEMENT -> PEAK/BOTTOM -> RETURN
    # 1. Full extension (155 deg)
    f1 = generate_bicep_curl_frame(155.0)
    r1 = exercise.analyze_frame(f1, timestamp_ms=0)
    assert r1.phase == BicepCurlPhase.EXTENDED.value

    # 2. Concentric lifting (110 deg)
    f2 = generate_bicep_curl_frame(110.0)
    r2 = exercise.analyze_frame(f2, timestamp_ms=400)
    assert r2.phase == BicepCurlPhase.CONCENTRIC.value

    # 3. Peak contraction (48 deg <= 55 target)
    f3 = generate_bicep_curl_frame(48.0)
    r3 = exercise.analyze_frame(f3, timestamp_ms=800)
    assert r3.phase == BicepCurlPhase.PEAK_FLEXION.value

    # 4. Eccentric lowering (95 deg)
    f4 = generate_bicep_curl_frame(95.0)
    r4 = exercise.analyze_frame(f4, timestamp_ms=1200)
    assert r4.phase == BicepCurlPhase.ECCENTRIC.value

    # 5. Full extension (155 deg) -> Completed rep
    f5 = generate_bicep_curl_frame(155.0)
    r5 = exercise.analyze_frame(f5, timestamp_ms=1600)
    assert r5.phase == BicepCurlPhase.COMPLETED_REP.value
    assert r5.rep_count == 1
    assert r5.valid_reps == 1
    assert r5.invalid_reps == 0
    assert r5.is_valid_rep is True
    assert r5.form_score >= 80
    assert len(r5.feedback) > 0


def test_bicep_curl_multiple_consecutive_reps():
    exercise = BicepCurlExercise()

    for rep in range(3):
        base_t = rep * 2000
        exercise.analyze_frame(generate_bicep_curl_frame(155.0), timestamp_ms=base_t + 0)
        exercise.analyze_frame(generate_bicep_curl_frame(110.0), timestamp_ms=base_t + 400)
        exercise.analyze_frame(generate_bicep_curl_frame(48.0), timestamp_ms=base_t + 800)
        exercise.analyze_frame(generate_bicep_curl_frame(95.0), timestamp_ms=base_t + 1200)
        r = exercise.analyze_frame(generate_bicep_curl_frame(155.0), timestamp_ms=base_t + 1600)
        assert r.phase == BicepCurlPhase.COMPLETED_REP.value

    assert exercise.rep_count == 3
    assert exercise.valid_reps == 3
    assert exercise.invalid_reps == 0


def test_bicep_curl_incomplete_aborted_movement():
    exercise = BicepCurlExercise()

    # User initiates slight movement (132 deg) and aborts back to full extension (155 deg)
    exercise.analyze_frame(generate_bicep_curl_frame(155.0), timestamp_ms=0)
    exercise.analyze_frame(generate_bicep_curl_frame(132.0), timestamp_ms=300)
    exercise.analyze_frame(generate_bicep_curl_frame(155.0), timestamp_ms=600)

    assert exercise.rep_count == 0
    assert exercise.valid_reps == 0
    assert exercise.invalid_reps == 0
    assert exercise.phase == BicepCurlPhase.EXTENDED


def test_bicep_curl_jitter_and_no_duplicate_counting():
    exercise = BicepCurlExercise()

    # Bottom extension jitter
    for i, angle in enumerate([155.0, 153.0, 156.0, 154.0]):
        exercise.analyze_frame(generate_bicep_curl_frame(angle), timestamp_ms=i * 100)
    assert exercise.rep_count == 0

    # 1 rep
    exercise.analyze_frame(generate_bicep_curl_frame(155.0), timestamp_ms=500)
    exercise.analyze_frame(generate_bicep_curl_frame(105.0), timestamp_ms=900)
    exercise.analyze_frame(generate_bicep_curl_frame(45.0), timestamp_ms=1300)
    exercise.analyze_frame(generate_bicep_curl_frame(105.0), timestamp_ms=1700)
    exercise.analyze_frame(generate_bicep_curl_frame(155.0), timestamp_ms=2100)
    assert exercise.rep_count == 1

    # Post-rep jitter
    for i, angle in enumerate([154.0, 156.0, 155.0]):
        exercise.analyze_frame(generate_bicep_curl_frame(angle), timestamp_ms=2200 + i * 100)
    assert exercise.rep_count == 1


def test_bicep_curl_fast_movement_rejected():
    exercise = BicepCurlExercise()

    # Fast 100ms movement
    exercise.analyze_frame(generate_bicep_curl_frame(155.0), timestamp_ms=0)
    exercise.analyze_frame(generate_bicep_curl_frame(100.0), timestamp_ms=30)
    exercise.analyze_frame(generate_bicep_curl_frame(45.0), timestamp_ms=60)
    exercise.analyze_frame(generate_bicep_curl_frame(100.0), timestamp_ms=80)
    exercise.analyze_frame(generate_bicep_curl_frame(155.0), timestamp_ms=100)

    assert exercise.rep_count == 0


def test_bicep_curl_incomplete_curl():
    exercise = BicepCurlExercise()

    # Shallow top flexion (lowest angle = 80 deg, target <= 55)
    exercise.analyze_frame(generate_bicep_curl_frame(155.0), timestamp_ms=0)
    exercise.analyze_frame(generate_bicep_curl_frame(120.0), timestamp_ms=300)
    exercise.analyze_frame(generate_bicep_curl_frame(80.0), timestamp_ms=600)
    exercise.analyze_frame(generate_bicep_curl_frame(120.0), timestamp_ms=900)
    r = exercise.analyze_frame(generate_bicep_curl_frame(155.0), timestamp_ms=1200)

    assert r.rep_count == 1
    assert r.invalid_reps == 1
    assert r.valid_reps == 0
    assert any(i["type"] == "incomplete_curl_flexion" for i in r.issues)
    assert any("curl higher" in f.lower() or "contraction" in f.lower() for f in r.feedback)


def test_bicep_curl_elbow_swinging():
    exercise = BicepCurlExercise()

    # Excessive upper arm swing (shoulder sway = 35 deg > 20 threshold)
    f = generate_bicep_curl_frame(155.0, shoulder_sway_deg=35.0)
    r = exercise.analyze_frame(f, timestamp_ms=100)

    assert any(i["type"] == "elbow_swinging" for i in r.issues)
    assert any("elbow" in f.lower() or "side" in f.lower() for f in r.feedback)
    assert r.form_score < 100


def test_bicep_curl_torso_momentum():
    exercise = BicepCurlExercise()

    # Torso leaning backward 25 deg (> 15 threshold)
    f = generate_bicep_curl_frame(155.0, torso_pitch_deg=25.0)
    r = exercise.analyze_frame(f, timestamp_ms=100)

    assert any(i["type"] == "torso_momentum" for i in r.issues)
    assert r.form_score < 100


def test_bicep_curl_arm_asymmetry():
    exercise = BicepCurlExercise()

    # Asymmetry delta = 22 deg (> 15 threshold)
    f = generate_bicep_curl_frame(155.0, asymmetry_deg=22.0)
    r = exercise.analyze_frame(f, timestamp_ms=100)

    assert any(i["type"] == "arm_asymmetry" for i in r.issues)
    assert r.form_score < 100


def test_bicep_curl_missing_and_low_confidence_landmarks():
    exercise = BicepCurlExercise()

    # None landmarks
    r_none = exercise.analyze_frame(None, timestamp_ms=100)
    assert r_none.confidence == 0.0
    assert r_none.exercise == "bicep_curl"

    # Low visibility
    low_conf_frame = generate_bicep_curl_frame(155.0, visibility=0.1)
    r_low = exercise.analyze_frame(low_conf_frame, timestamp_ms=200)
    assert r_low.confidence < 0.45
    assert any("low tracking" in f.lower() or "visibility" in f.lower() for f in r_low.feedback)


def test_bicep_curl_reset_behavior():
    exercise = BicepCurlExercise()

    # Perform 1 rep
    exercise.analyze_frame(generate_bicep_curl_frame(155.0), timestamp_ms=0)
    exercise.analyze_frame(generate_bicep_curl_frame(110.0), timestamp_ms=400)
    exercise.analyze_frame(generate_bicep_curl_frame(48.0), timestamp_ms=800)
    exercise.analyze_frame(generate_bicep_curl_frame(95.0), timestamp_ms=1200)
    exercise.analyze_frame(generate_bicep_curl_frame(155.0), timestamp_ms=1600)
    assert exercise.rep_count == 1

    # Reset
    exercise.reset()
    assert exercise.rep_count == 0
    assert exercise.valid_reps == 0
    assert exercise.invalid_reps == 0
    assert exercise.phase == BicepCurlPhase.EXTENDED
    assert len(exercise._current_rep_trajectory) == 0
