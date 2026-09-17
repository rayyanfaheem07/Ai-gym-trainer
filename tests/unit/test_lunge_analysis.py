import numpy as np

from ai.exercises.lunge import LungeExercise, LungePhase
from ai.pose.landmarks import LandmarkIndex


def generate_lunge_frame(
    lead_knee_deg: float,
    trail_knee_deg: float = 95.0,
    torso_lean_deg: float = 0.0,
    visibility: float = 0.95,
) -> np.ndarray:
    """
    Generates synthetic 33-point landmarks with lunge geometry:
    - Left leg = Lead leg, Right leg = Trail leg.
    - Hips at (0.45, 0.5) and (0.55, 0.5)
    - Lead knee flexion angle and Trail knee flexion angle
    - Torso inclination from vertical
    """
    landmarks = np.zeros((33, 4), dtype=np.float32)
    landmarks[:, 3] = visibility

    # Torso
    torso_rad = np.radians(torso_lean_deg)
    landmarks[LandmarkIndex.LEFT_SHOULDER] = [
        0.45 - 0.25 * np.sin(torso_rad),
        0.5 - 0.25 * np.cos(torso_rad),
        0.0,
        visibility,
    ]
    landmarks[LandmarkIndex.RIGHT_SHOULDER] = [
        0.55 - 0.25 * np.sin(torso_rad),
        0.5 - 0.25 * np.cos(torso_rad),
        0.0,
        visibility,
    ]
    landmarks[LandmarkIndex.LEFT_HIP] = [0.45, 0.5, 0.0, visibility]
    landmarks[LandmarkIndex.RIGHT_HIP] = [0.55, 0.5, 0.0, visibility]

    # Lead leg (Left): Hip(0.45, 0.5) -> Knee(0.45, 0.75)
    landmarks[LandmarkIndex.LEFT_KNEE] = [0.45, 0.75, 0.0, visibility]
    lead_rad = np.radians(180.0 - lead_knee_deg)
    landmarks[LandmarkIndex.LEFT_ANKLE] = [
        0.45 + 0.25 * np.sin(lead_rad),
        0.75 + 0.25 * np.cos(lead_rad),
        0.0,
        visibility,
    ]

    # Trail leg (Right): Hip(0.55, 0.5) -> Knee(0.55, 0.75)
    landmarks[LandmarkIndex.RIGHT_KNEE] = [0.55, 0.75, 0.0, visibility]
    trail_rad = np.radians(180.0 - trail_knee_deg)
    landmarks[LandmarkIndex.RIGHT_ANKLE] = [
        0.55 + 0.25 * np.sin(trail_rad),
        0.75 + 0.25 * np.cos(trail_rad),
        0.0,
        visibility,
    ]

    return landmarks


def test_valid_lunge_full_cycle():
    exercise = LungeExercise()
    assert exercise.phase == LungePhase.STANDING
    assert exercise.rep_count == 0

    # START -> MOVEMENT -> PEAK/BOTTOM -> RETURN
    # 1. Standing start (165 deg both legs)
    f1 = generate_lunge_frame(165.0, trail_knee_deg=165.0)
    r1 = exercise.analyze_frame(f1, timestamp_ms=0)
    assert r1.phase == LungePhase.STANDING.value

    # 2. Descending (125 deg)
    f2 = generate_lunge_frame(125.0, trail_knee_deg=130.0)
    r2 = exercise.analyze_frame(f2, timestamp_ms=400)
    assert r2.phase == LungePhase.DESCENDING.value

    # 3. Bottom depth (90 deg <= 95 target)
    f3 = generate_lunge_frame(90.0, trail_knee_deg=95.0)
    r3 = exercise.analyze_frame(f3, timestamp_ms=800)
    assert r3.phase == LungePhase.BOTTOM.value

    # 4. Ascending (125 deg)
    f4 = generate_lunge_frame(125.0, trail_knee_deg=130.0)
    r4 = exercise.analyze_frame(f4, timestamp_ms=1200)
    assert r4.phase == LungePhase.ASCENDING.value

    # 5. Lockout (165 deg both legs) -> Completed rep
    f5 = generate_lunge_frame(165.0, trail_knee_deg=165.0)
    r5 = exercise.analyze_frame(f5, timestamp_ms=1600)
    assert r5.phase == LungePhase.COMPLETED_REP.value
    assert r5.rep_count == 1
    assert r5.valid_reps == 1
    assert r5.invalid_reps == 0
    assert r5.is_valid_rep is True
    assert r5.form_score >= 80
    assert len(r5.feedback) > 0


def test_lunge_multiple_consecutive_reps():
    exercise = LungeExercise()

    for rep in range(3):
        base_t = rep * 2000
        exercise.analyze_frame(generate_lunge_frame(165.0, trail_knee_deg=165.0), timestamp_ms=base_t + 0)
        exercise.analyze_frame(generate_lunge_frame(125.0, trail_knee_deg=130.0), timestamp_ms=base_t + 400)
        exercise.analyze_frame(generate_lunge_frame(90.0, trail_knee_deg=95.0), timestamp_ms=base_t + 800)
        exercise.analyze_frame(generate_lunge_frame(125.0, trail_knee_deg=130.0), timestamp_ms=base_t + 1200)
        r = exercise.analyze_frame(generate_lunge_frame(165.0, trail_knee_deg=165.0), timestamp_ms=base_t + 1600)
        assert r.phase == LungePhase.COMPLETED_REP.value

    assert exercise.rep_count == 3
    assert exercise.valid_reps == 3
    assert exercise.invalid_reps == 0


def test_lunge_incomplete_aborted_movement():
    exercise = LungeExercise()

    # User initiates slight movement (136 deg) and returns to standing without reaching bottom
    exercise.analyze_frame(generate_lunge_frame(165.0, trail_knee_deg=165.0), timestamp_ms=0)
    exercise.analyze_frame(generate_lunge_frame(136.0, trail_knee_deg=145.0), timestamp_ms=300)
    exercise.analyze_frame(generate_lunge_frame(165.0, trail_knee_deg=165.0), timestamp_ms=600)

    assert exercise.rep_count == 0
    assert exercise.valid_reps == 0
    assert exercise.invalid_reps == 0
    assert exercise.phase == LungePhase.STANDING


def test_lunge_jitter_and_no_duplicate_counting():
    exercise = LungeExercise()

    # Top standing jitter
    for i, angle in enumerate([165.0, 163.0, 166.0, 164.0]):
        exercise.analyze_frame(generate_lunge_frame(angle, trail_knee_deg=angle), timestamp_ms=i * 100)
    assert exercise.rep_count == 0

    # 1 rep
    exercise.analyze_frame(generate_lunge_frame(165.0, trail_knee_deg=165.0), timestamp_ms=500)
    exercise.analyze_frame(generate_lunge_frame(120.0, trail_knee_deg=125.0), timestamp_ms=900)
    exercise.analyze_frame(generate_lunge_frame(88.0, trail_knee_deg=92.0), timestamp_ms=1300)
    exercise.analyze_frame(generate_lunge_frame(120.0, trail_knee_deg=125.0), timestamp_ms=1700)
    exercise.analyze_frame(generate_lunge_frame(165.0, trail_knee_deg=165.0), timestamp_ms=2100)
    assert exercise.rep_count == 1

    # Post-rep jitter
    for i, angle in enumerate([164.0, 166.0, 165.0]):
        exercise.analyze_frame(generate_lunge_frame(angle, trail_knee_deg=angle), timestamp_ms=2200 + i * 100)
    assert exercise.rep_count == 1


def test_lunge_fast_movement_rejected():
    exercise = LungeExercise()

    # Fast 100ms movement
    exercise.analyze_frame(generate_lunge_frame(165.0, trail_knee_deg=165.0), timestamp_ms=0)
    exercise.analyze_frame(generate_lunge_frame(120.0, trail_knee_deg=125.0), timestamp_ms=30)
    exercise.analyze_frame(generate_lunge_frame(88.0, trail_knee_deg=92.0), timestamp_ms=60)
    exercise.analyze_frame(generate_lunge_frame(120.0, trail_knee_deg=125.0), timestamp_ms=80)
    exercise.analyze_frame(generate_lunge_frame(165.0, trail_knee_deg=165.0), timestamp_ms=100)

    assert exercise.rep_count == 0


def test_lunge_insufficient_depth():
    exercise = LungeExercise()

    # Shallow bottom (lowest lead angle = 120 deg, target <= 95)
    exercise.analyze_frame(generate_lunge_frame(165.0, trail_knee_deg=165.0), timestamp_ms=0)
    exercise.analyze_frame(generate_lunge_frame(130.0, trail_knee_deg=135.0), timestamp_ms=300)
    exercise.analyze_frame(generate_lunge_frame(120.0, trail_knee_deg=125.0), timestamp_ms=600)
    exercise.analyze_frame(generate_lunge_frame(135.0, trail_knee_deg=140.0), timestamp_ms=900)
    r = exercise.analyze_frame(generate_lunge_frame(165.0, trail_knee_deg=165.0), timestamp_ms=1200)

    assert r.rep_count == 1
    assert r.invalid_reps == 1
    assert r.valid_reps == 0
    assert any(i["type"] == "insufficient_depth" for i in r.issues)
    assert any("depth" in f.lower() or "deeper" in f.lower() for f in r.feedback)


def test_lunge_torso_forward_lean():
    exercise = LungeExercise()

    # Excessive torso lean = 38 deg > 25 threshold
    f = generate_lunge_frame(165.0, trail_knee_deg=165.0, torso_lean_deg=38.0)
    r = exercise.analyze_frame(f, timestamp_ms=100)

    assert any(i["type"] == "excessive_torso_lean" for i in r.issues)
    assert any("upright" in f.lower() or "chest" in f.lower() for f in r.feedback)
    assert r.form_score < 100


def test_lunge_stiff_trail_leg():
    exercise = LungeExercise()

    # Trail leg remains stiff at 150 deg (> 125 threshold)
    exercise.analyze_frame(generate_lunge_frame(165.0, trail_knee_deg=165.0), timestamp_ms=0)
    exercise.analyze_frame(generate_lunge_frame(125.0, trail_knee_deg=155.0), timestamp_ms=400)
    exercise.analyze_frame(generate_lunge_frame(90.0, trail_knee_deg=150.0), timestamp_ms=800)
    exercise.analyze_frame(generate_lunge_frame(125.0, trail_knee_deg=155.0), timestamp_ms=1200)
    r = exercise.analyze_frame(generate_lunge_frame(165.0, trail_knee_deg=165.0), timestamp_ms=1600)

    assert r.rep_count == 1
    assert any(i["type"] == "stiff_trail_leg" for i in r.issues)


def test_lunge_missing_and_low_confidence_landmarks():
    exercise = LungeExercise()

    # None landmarks
    r_none = exercise.analyze_frame(None, timestamp_ms=100)
    assert r_none.confidence == 0.0
    assert r_none.exercise == "lunge"

    # Low visibility
    low_conf_frame = generate_lunge_frame(165.0, visibility=0.1)
    r_low = exercise.analyze_frame(low_conf_frame, timestamp_ms=200)
    assert r_low.confidence < 0.45
    assert any("low tracking" in f.lower() or "visibility" in f.lower() for f in r_low.feedback)


def test_lunge_reset_behavior():
    exercise = LungeExercise()

    # Perform 1 rep
    exercise.analyze_frame(generate_lunge_frame(165.0, trail_knee_deg=165.0), timestamp_ms=0)
    exercise.analyze_frame(generate_lunge_frame(125.0, trail_knee_deg=130.0), timestamp_ms=400)
    exercise.analyze_frame(generate_lunge_frame(90.0, trail_knee_deg=95.0), timestamp_ms=800)
    exercise.analyze_frame(generate_lunge_frame(125.0, trail_knee_deg=130.0), timestamp_ms=1200)
    exercise.analyze_frame(generate_lunge_frame(165.0, trail_knee_deg=165.0), timestamp_ms=1600)
    assert exercise.rep_count == 1

    # Reset
    exercise.reset()
    assert exercise.rep_count == 0
    assert exercise.valid_reps == 0
    assert exercise.invalid_reps == 0
    assert exercise.phase == LungePhase.STANDING
    assert len(exercise._current_rep_trajectory) == 0
