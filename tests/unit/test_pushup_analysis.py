import numpy as np

from ai.exercises.pushup import PushupExercise, PushupPhase
from ai.pose.landmarks import LandmarkIndex


def generate_pushup_frame(
    elbow_angle_deg: float,
    body_line_deg: float = 180.0,
    flare_deg: float = 45.0,
    asymmetry_deg: float = 0.0,
    is_piking: bool = False,
    visibility: float = 0.95,
) -> np.ndarray:
    """
    Generates synthetic 33-point landmarks with exact pushup geometry:
    - Shoulders at (0.4, 0.3), (0.6, 0.3)
    - Elbows with flare
    - Wrists computed with exact elbow angle relative to humerus vector
    - Hips and Ankles computed for body line alignment (sagging/piking)
    """
    landmarks = np.zeros((33, 4), dtype=np.float32)
    landmarks[:, 3] = visibility

    # Shoulder positions
    shoulder_y = 0.30
    landmarks[LandmarkIndex.LEFT_SHOULDER] = [0.4, shoulder_y, 0.0, visibility]
    landmarks[LandmarkIndex.RIGHT_SHOULDER] = [0.6, shoulder_y, 0.0, visibility]

    # Elbow positions with flare (symmetrical outward)
    flare_rad = np.radians(flare_deg)
    landmarks[LandmarkIndex.LEFT_ELBOW] = [0.4 - 0.15 * np.sin(flare_rad), shoulder_y + 0.15 * np.cos(flare_rad), 0.0, visibility]
    landmarks[LandmarkIndex.RIGHT_ELBOW] = [0.6 + 0.15 * np.sin(flare_rad), shoulder_y + 0.15 * np.cos(flare_rad), 0.0, visibility]

    # Wrists based on exact elbow angle relative to upper arm vector
    se_left = landmarks[LandmarkIndex.LEFT_ELBOW, :2] - landmarks[LandmarkIndex.LEFT_SHOULDER, :2]
    theta_left = np.arctan2(se_left[1], se_left[0])
    wrist_rad_left = theta_left + np.radians(180.0 - elbow_angle_deg)

    landmarks[LandmarkIndex.LEFT_WRIST] = [
        landmarks[LandmarkIndex.LEFT_ELBOW, 0] + 0.2 * np.cos(wrist_rad_left),
        landmarks[LandmarkIndex.LEFT_ELBOW, 1] + 0.2 * np.sin(wrist_rad_left),
        0.0,
        visibility,
    ]

    se_right = landmarks[LandmarkIndex.RIGHT_ELBOW, :2] - landmarks[LandmarkIndex.RIGHT_SHOULDER, :2]
    theta_right = np.arctan2(se_right[1], se_right[0])
    wrist_rad_right = theta_right - np.radians(180.0 - (elbow_angle_deg + asymmetry_deg))

    landmarks[LandmarkIndex.RIGHT_WRIST] = [
        landmarks[LandmarkIndex.RIGHT_ELBOW, 0] + 0.2 * np.cos(wrist_rad_right),
        landmarks[LandmarkIndex.RIGHT_ELBOW, 1] + 0.2 * np.sin(wrist_rad_right),
        0.0,
        visibility,
    ]

    # Hips & Ankles (Body line angle: Shoulder -> Hip -> Ankle)
    body_rad = np.radians(180.0 - body_line_deg)

    if is_piking:
        hip_y = 0.45
        ankle_y = hip_y + 0.3 * np.cos(body_rad)
        ankle_x_left = 0.4 + 0.3 * np.sin(body_rad)
        ankle_x_right = 0.6 + 0.3 * np.sin(body_rad)
    else:
        hip_y = 0.55
        ankle_y = hip_y + 0.3 * np.cos(body_rad)
        ankle_x_left = 0.4 + 0.3 * np.sin(body_rad)
        ankle_x_right = 0.6 + 0.3 * np.sin(body_rad)

    landmarks[LandmarkIndex.LEFT_HIP] = [0.4, hip_y, 0.0, visibility]
    landmarks[LandmarkIndex.RIGHT_HIP] = [0.6, hip_y, 0.0, visibility]

    landmarks[LandmarkIndex.LEFT_ANKLE] = [ankle_x_left, ankle_y, 0.0, visibility]
    landmarks[LandmarkIndex.RIGHT_ANKLE] = [ankle_x_right, ankle_y, 0.0, visibility]

    return landmarks


def test_valid_pushup_full_cycle():
    exercise = PushupExercise()
    assert exercise.phase == PushupPhase.PLANK
    assert exercise.rep_count == 0

    # START -> MOVEMENT -> PEAK/BOTTOM -> RETURN
    # 1. Start in plank (160 deg)
    f1 = generate_pushup_frame(160.0)
    r1 = exercise.analyze_frame(f1, timestamp_ms=0)
    assert r1.phase == PushupPhase.PLANK.value

    # 2. Descending (130 deg)
    f2 = generate_pushup_frame(130.0)
    r2 = exercise.analyze_frame(f2, timestamp_ms=400)
    assert r2.phase == PushupPhase.DESCENDING.value

    # 3. Bottom depth (85 deg <= 90 target)
    f3 = generate_pushup_frame(85.0)
    r3 = exercise.analyze_frame(f3, timestamp_ms=800)
    assert r3.phase == PushupPhase.BOTTOM.value

    # 4. Ascending (120 deg)
    f4 = generate_pushup_frame(120.0)
    r4 = exercise.analyze_frame(f4, timestamp_ms=1200)
    assert r4.phase == PushupPhase.ASCENDING.value

    # 5. Lockout (160 deg) -> Completed rep
    f5 = generate_pushup_frame(160.0)
    r5 = exercise.analyze_frame(f5, timestamp_ms=1600)
    assert r5.phase == PushupPhase.COMPLETED_REP.value
    assert r5.rep_count == 1
    assert r5.valid_reps == 1
    assert r5.invalid_reps == 0
    assert r5.is_valid_rep is True
    assert r5.form_score >= 80
    assert len(r5.feedback) > 0


def test_pushup_multiple_consecutive_reps():
    exercise = PushupExercise()

    for rep in range(3):
        base_t = rep * 2000
        exercise.analyze_frame(generate_pushup_frame(160.0), timestamp_ms=base_t + 0)
        exercise.analyze_frame(generate_pushup_frame(130.0), timestamp_ms=base_t + 400)
        exercise.analyze_frame(generate_pushup_frame(85.0), timestamp_ms=base_t + 800)
        exercise.analyze_frame(generate_pushup_frame(120.0), timestamp_ms=base_t + 1200)
        r = exercise.analyze_frame(generate_pushup_frame(160.0), timestamp_ms=base_t + 1600)
        assert r.phase == PushupPhase.COMPLETED_REP.value

    assert exercise.rep_count == 3
    assert exercise.valid_reps == 3
    assert exercise.invalid_reps == 0


def test_pushup_incomplete_aborted_movement():
    exercise = PushupExercise()

    # User initiates slight dip (142 deg) and goes back to plank without completing rep
    exercise.analyze_frame(generate_pushup_frame(160.0), timestamp_ms=0)
    exercise.analyze_frame(generate_pushup_frame(142.0), timestamp_ms=300)
    exercise.analyze_frame(generate_pushup_frame(160.0), timestamp_ms=600)

    assert exercise.rep_count == 0
    assert exercise.valid_reps == 0
    assert exercise.invalid_reps == 0
    assert exercise.phase == PushupPhase.PLANK


def test_pushup_jitter_and_no_duplicate_counting():
    exercise = PushupExercise()

    # Top plank jitter
    for i, angle in enumerate([160.0, 158.0, 162.0, 159.0, 161.0]):
        exercise.analyze_frame(generate_pushup_frame(angle), timestamp_ms=i * 100)
    assert exercise.rep_count == 0

    # 1 rep
    exercise.analyze_frame(generate_pushup_frame(160.0), timestamp_ms=600)
    exercise.analyze_frame(generate_pushup_frame(125.0), timestamp_ms=1000)
    exercise.analyze_frame(generate_pushup_frame(85.0), timestamp_ms=1400)
    exercise.analyze_frame(generate_pushup_frame(125.0), timestamp_ms=1800)
    exercise.analyze_frame(generate_pushup_frame(160.0), timestamp_ms=2200)
    assert exercise.rep_count == 1

    # Post-rep jitter in plank
    for i, angle in enumerate([158.0, 162.0, 160.0]):
        exercise.analyze_frame(generate_pushup_frame(angle), timestamp_ms=2300 + i * 100)
    assert exercise.rep_count == 1


def test_pushup_fast_movement_rejected():
    exercise = PushupExercise()

    # Fast 100ms movement (< 0.5s)
    exercise.analyze_frame(generate_pushup_frame(160.0), timestamp_ms=0)
    exercise.analyze_frame(generate_pushup_frame(120.0), timestamp_ms=30)
    exercise.analyze_frame(generate_pushup_frame(85.0), timestamp_ms=60)
    exercise.analyze_frame(generate_pushup_frame(120.0), timestamp_ms=80)
    exercise.analyze_frame(generate_pushup_frame(160.0), timestamp_ms=100)

    assert exercise.rep_count == 0


def test_pushup_insufficient_depth():
    exercise = PushupExercise()

    # Rep with shallow bottom (lowest elbow angle = 115 deg, target <= 90)
    exercise.analyze_frame(generate_pushup_frame(160.0), timestamp_ms=0)
    exercise.analyze_frame(generate_pushup_frame(130.0), timestamp_ms=300)
    exercise.analyze_frame(generate_pushup_frame(115.0), timestamp_ms=600)
    exercise.analyze_frame(generate_pushup_frame(135.0), timestamp_ms=900)
    r = exercise.analyze_frame(generate_pushup_frame(160.0), timestamp_ms=1200)

    assert r.rep_count == 1
    assert r.invalid_reps == 1
    assert r.valid_reps == 0
    assert any(i["type"] == "insufficient_depth" for i in r.issues)
    assert any("lower" in f.lower() or "depth" in f.lower() for f in r.feedback)


def test_pushup_hips_sagging():
    exercise = PushupExercise()

    # Sagging hips (body line = 140 deg < 155 threshold, is_piking=False)
    f = generate_pushup_frame(160.0, body_line_deg=140.0, is_piking=False)
    r = exercise.analyze_frame(f, timestamp_ms=100)

    assert any(i["type"] == "hips_sagging" for i in r.issues)
    assert any("sag" in f.lower() or "core" in f.lower() for f in r.feedback)
    assert r.form_score < 100


def test_pushup_hips_piking():
    exercise = PushupExercise()

    # Piking hips (body line = 140 deg < 155 threshold, is_piking=True)
    f = generate_pushup_frame(160.0, body_line_deg=140.0, is_piking=True)
    r = exercise.analyze_frame(f, timestamp_ms=100)

    assert any(i["type"] == "hips_piking" for i in r.issues)
    assert any("hip" in f.lower() or "plank" in f.lower() for f in r.feedback)
    assert r.form_score < 100


def test_pushup_arm_asymmetry():
    exercise = PushupExercise()

    # Asymmetry delta = 20 deg (> 12 threshold)
    f = generate_pushup_frame(160.0, asymmetry_deg=20.0)
    r = exercise.analyze_frame(f, timestamp_ms=100)

    assert any(i["type"] == "arm_asymmetry" for i in r.issues)
    assert r.form_score < 100


def test_pushup_missing_and_low_confidence_landmarks():
    exercise = PushupExercise()

    # None landmarks
    r_none = exercise.analyze_frame(None, timestamp_ms=100)
    assert r_none.confidence == 0.0
    assert r_none.exercise == "pushup"

    # Low visibility
    low_conf_frame = generate_pushup_frame(160.0, visibility=0.1)
    r_low = exercise.analyze_frame(low_conf_frame, timestamp_ms=200)
    assert r_low.confidence < 0.45
    assert any("low tracking" in f.lower() or "visibility" in f.lower() for f in r_low.feedback)


def test_pushup_reset_behavior():
    exercise = PushupExercise()

    # Perform 1 rep
    exercise.analyze_frame(generate_pushup_frame(160.0), timestamp_ms=0)
    exercise.analyze_frame(generate_pushup_frame(130.0), timestamp_ms=400)
    exercise.analyze_frame(generate_pushup_frame(85.0), timestamp_ms=800)
    exercise.analyze_frame(generate_pushup_frame(120.0), timestamp_ms=1200)
    exercise.analyze_frame(generate_pushup_frame(160.0), timestamp_ms=1600)
    assert exercise.rep_count == 1

    # Reset
    exercise.reset()
    assert exercise.rep_count == 0
    assert exercise.valid_reps == 0
    assert exercise.invalid_reps == 0
    assert exercise.phase == PushupPhase.PLANK
    assert len(exercise._current_rep_trajectory) == 0
