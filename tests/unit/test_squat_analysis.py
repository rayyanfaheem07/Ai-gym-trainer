import numpy as np

from ai.exercises.squat import SquatAnalysisResult, SquatDetector, SquatPhase
from ai.pose.landmarks import LandmarkIndex


def generate_squat_frame(
    knee_angle_deg: float,
    hip_angle_deg: float = 170.0,
    noise_std: float = 0.0,
    visibility: float = 0.95,
) -> np.ndarray:
    """
    Generates synthetic 33-point pose landmarks with exact knee and hip angles.

    Geometry:
    - Hip at (0.5, 0.5)
    - Knee at (0.5, 0.8) (Thigh length = 0.3)
    - Ankle calculated based on knee_angle_deg relative to hip-knee vector
    - Torso calculated from hip_angle_deg
    """
    landmarks = np.zeros((33, 4), dtype=np.float32)
    landmarks[:, 3] = visibility

    # Shoulder (Torso)
    torso_rad = np.radians(180.0 - hip_angle_deg)
    landmarks[LandmarkIndex.LEFT_SHOULDER] = [
        0.5 - 0.3 * np.sin(torso_rad),
        0.5 - 0.3 * np.cos(torso_rad),
        0.0,
        visibility,
    ]
    landmarks[LandmarkIndex.RIGHT_SHOULDER] = landmarks[LandmarkIndex.LEFT_SHOULDER].copy()

    # Hips
    landmarks[LandmarkIndex.LEFT_HIP] = [0.45, 0.5, 0.0, visibility]
    landmarks[LandmarkIndex.RIGHT_HIP] = [0.55, 0.5, 0.0, visibility]

    # Knee
    landmarks[LandmarkIndex.LEFT_KNEE] = [0.45, 0.8, 0.0, visibility]
    landmarks[LandmarkIndex.RIGHT_KNEE] = [0.55, 0.8, 0.0, visibility]

    # Ankle based on knee angle
    flexion_rad = np.radians(180.0 - knee_angle_deg)
    shin_length = 0.3
    ankle_x = 0.45 + shin_length * np.sin(flexion_rad)
    ankle_y = 0.8 + shin_length * np.cos(flexion_rad)

    landmarks[LandmarkIndex.LEFT_ANKLE] = [ankle_x, ankle_y, 0.0, visibility]
    landmarks[LandmarkIndex.RIGHT_ANKLE] = [ankle_x + 0.1, ankle_y, 0.0, visibility]

    if noise_std > 0.0:
        noise = np.random.normal(0, noise_std, landmarks[:, :3].shape)
        landmarks[:, :3] += noise

    return landmarks


def test_valid_squat_full_cycle():
    detector = SquatDetector()
    assert detector.phase == SquatPhase.STANDING
    assert detector.rep_count == 0

    # START -> MOVEMENT -> PEAK/BOTTOM -> RETURN
    # Standing (175) -> Descending (140, 115) -> Bottom (88) -> Ascending (115, 145) -> Completed Rep (165)
    timestamps = [0, 200, 400, 700, 1000, 1300, 1600]
    angles = [175.0, 135.0, 115.0, 88.0, 115.0, 145.0, 165.0]

    results = []
    for ts, angle in zip(timestamps, angles, strict=True):
        frame = generate_squat_frame(knee_angle_deg=angle, hip_angle_deg=160.0)
        res = detector.analyze_frame(frame, timestamp_ms=ts)
        results.append(res)

    phases = [r.phase for r in results]
    assert SquatPhase.DESCENDING.value in phases
    assert SquatPhase.BOTTOM.value in phases
    assert SquatPhase.ASCENDING.value in phases
    assert results[-1].phase == SquatPhase.COMPLETED_REP.value

    # Exactly 1 repetition counted
    assert detector.rep_count == 1
    assert detector.valid_reps == 1
    assert detector.invalid_reps == 0
    assert results[-1].is_valid_rep is True
    assert results[-1].form_score >= 80
    assert len(results[-1].feedback) > 0


def test_multiple_valid_squats():
    detector = SquatDetector()

    for rep in range(3):
        base_t = rep * 2000
        detector.analyze_frame(generate_squat_frame(175.0), timestamp_ms=base_t + 0)
        detector.analyze_frame(generate_squat_frame(130.0), timestamp_ms=base_t + 300)
        detector.analyze_frame(generate_squat_frame(85.0), timestamp_ms=base_t + 700)
        detector.analyze_frame(generate_squat_frame(130.0), timestamp_ms=base_t + 1100)
        res = detector.analyze_frame(generate_squat_frame(168.0), timestamp_ms=base_t + 1500)
        assert res.phase == SquatPhase.COMPLETED_REP.value

    assert detector.rep_count == 3
    assert detector.valid_reps == 3
    assert detector.invalid_reps == 0


def test_incomplete_squat_aborted_early():
    detector = SquatDetector()

    # User initiates descent to 125 deg but aborts without reaching bottom (<= 95 deg)
    timestamps = [0, 200, 500, 800, 1200]
    angles = [175.0, 135.0, 125.0, 145.0, 170.0]

    for ts, angle in zip(timestamps, angles, strict=True):
        detector.analyze_frame(generate_squat_frame(angle), timestamp_ms=ts)

    # Incomplete movement must NOT count as a rep
    assert detector.rep_count == 0
    assert detector.valid_reps == 0
    assert detector.invalid_reps == 0
    assert detector.phase == SquatPhase.STANDING


def test_duplicate_counting_and_jitter_protection():
    detector = SquatDetector()

    # Standing jitter around 160 deg
    for i, angle in enumerate([160.0, 158.0, 162.0, 159.0, 161.0, 157.0, 163.0]):
        detector.analyze_frame(generate_squat_frame(angle), timestamp_ms=i * 100)

    assert detector.rep_count == 0

    # 1 valid squat
    detector.analyze_frame(generate_squat_frame(175.0), timestamp_ms=1000)
    detector.analyze_frame(generate_squat_frame(130.0), timestamp_ms=1300)
    detector.analyze_frame(generate_squat_frame(90.0), timestamp_ms=1700)
    detector.analyze_frame(generate_squat_frame(130.0), timestamp_ms=2100)
    detector.analyze_frame(generate_squat_frame(170.0), timestamp_ms=2500)
    assert detector.rep_count == 1

    # Stays at top with jitter - should not recount
    for i, angle in enumerate([168.0, 172.0, 169.0, 171.0, 170.0]):
        detector.analyze_frame(generate_squat_frame(angle), timestamp_ms=2600 + i * 100)

    assert detector.rep_count == 1
    assert detector.valid_reps == 1


def test_extremely_fast_squat_rejected():
    detector = SquatDetector()

    # Cycle completed in 100ms (< min_rep_duration_sec 0.5s)
    detector.analyze_frame(generate_squat_frame(175.0), timestamp_ms=0)
    detector.analyze_frame(generate_squat_frame(130.0), timestamp_ms=20)
    detector.analyze_frame(generate_squat_frame(85.0), timestamp_ms=50)
    detector.analyze_frame(generate_squat_frame(130.0), timestamp_ms=80)
    r = detector.analyze_frame(generate_squat_frame(170.0), timestamp_ms=100)

    assert detector.rep_count == 0
    assert r.rep_count == 0


def test_missing_and_low_confidence_landmarks():
    detector = SquatDetector()

    # None landmarks
    r_none = detector.analyze_frame(None, timestamp_ms=100)
    assert r_none.confidence == 0.0
    assert r_none.exercise == "squat"
    assert "No landmarks" in r_none.feedback[0]

    # Incomplete landmark array
    short_landmarks = np.zeros((10, 4), dtype=np.float32)
    r_short = detector.analyze_frame(short_landmarks, timestamp_ms=200)
    assert r_short.confidence == 0.0

    # Low visibility confidence
    low_conf_frame = generate_squat_frame(175.0, visibility=0.1)
    r_low = detector.analyze_frame(low_conf_frame, timestamp_ms=300)
    assert r_low.confidence < 0.5
    assert any("low tracking" in f.lower() or "confidence" in f.lower() for f in r_low.feedback)


def test_incorrect_movement_form_fault():
    detector = SquatDetector()

    timestamps = [0, 300, 700, 1100, 1500]
    angles = [175.0, 130.0, 88.0, 130.0, 170.0]

    res = None
    for ts, angle in zip(timestamps, angles, strict=True):
        # Severe forward torso lean (hip angle 45 deg)
        frame = generate_squat_frame(knee_angle_deg=angle, hip_angle_deg=45.0)
        res = detector.analyze_frame(frame, timestamp_ms=ts)

    assert detector.rep_count == 1
    assert detector.invalid_reps == 1
    assert detector.valid_reps == 0
    assert any("torso" in f.lower() or "chest" in f.lower() for f in res.feedback)


def test_squat_reset_behavior():
    detector = SquatDetector()

    # Run 1 rep
    detector.analyze_frame(generate_squat_frame(175.0), timestamp_ms=0)
    detector.analyze_frame(generate_squat_frame(130.0), timestamp_ms=300)
    detector.analyze_frame(generate_squat_frame(88.0), timestamp_ms=700)
    detector.analyze_frame(generate_squat_frame(130.0), timestamp_ms=1100)
    detector.analyze_frame(generate_squat_frame(170.0), timestamp_ms=1500)
    assert detector.rep_count == 1

    # Reset
    detector.reset()
    assert detector.rep_count == 0
    assert detector.valid_reps == 0
    assert detector.invalid_reps == 0
    assert detector.phase == SquatPhase.STANDING
    assert len(detector._current_rep_trajectory) == 0


def test_structured_output_schema():
    detector = SquatDetector()
    frame = generate_squat_frame(175.0)
    result = detector.analyze_frame(frame, timestamp_ms=100.0)

    assert isinstance(result, SquatAnalysisResult)
    data = result.to_dict()
    assert data["exercise"] == "squat"
    assert data["phase"] == "standing"
    assert isinstance(data["rep_count"], int)
    assert isinstance(data["confidence"], float)
    assert isinstance(data["current_knee_angle"], float)
    assert isinstance(data["form_score"], int)
    assert isinstance(data["is_valid_rep"], bool)
    assert isinstance(data["issues"], list)
    assert isinstance(data["feedback"], list)
    assert isinstance(data["metrics"], dict)
