from unittest.mock import MagicMock

import numpy as np
import pytest

from ai.geometry.angles import calculate_angle_2d, calculate_angle_3d, calculate_joint_angles
from ai.pose.detector import (
    PoseDetector,
    extract_landmarks_array,
)
from ai.pose.landmarks import LandmarkIndex, PoseDetectionResult
from ai.pose.normalizer import normalize_pose_landmarks
from ai.pose.visualizer import PoseVisualizer
from ai.pose.webcam_stream import WebcamPoseTracker


def create_synthetic_landmarks(
    left_knee_angle: float = 90.0,
    torso_height: float = 0.5,
) -> np.ndarray:
    """Helper creating a 33x4 landmark array with known geometry for testing."""
    landmarks = np.zeros((33, 4), dtype=np.float32)
    # Default visibility
    landmarks[:, 3] = 0.95

    # Shoulders (y = 0.3)
    landmarks[LandmarkIndex.LEFT_SHOULDER] = [0.4, 0.3, 0.0, 0.95]
    landmarks[LandmarkIndex.RIGHT_SHOULDER] = [0.6, 0.3, 0.0, 0.95]

    # Hips (y = 0.3 + torso_height = 0.8)
    landmarks[LandmarkIndex.LEFT_HIP] = [0.45, 0.8, 0.0, 0.95]
    landmarks[LandmarkIndex.RIGHT_HIP] = [0.55, 0.8, 0.0, 0.95]

    # Left Knee & Ankle (Right triangle: hip (0.45, 0.8) -> knee (0.45, 1.2) -> ankle (0.85, 1.2))
    # Angle at Knee vertex: 90 degrees
    landmarks[LandmarkIndex.LEFT_KNEE] = [0.45, 1.2, 0.0, 0.95]
    landmarks[LandmarkIndex.LEFT_ANKLE] = [0.85, 1.2, 0.0, 0.95]

    # Left Elbow & Wrist (Elbow at 90 deg: shoulder (0.4, 0.3) -> elbow (0.4, 0.6) -> wrist (0.7, 0.6))
    landmarks[LandmarkIndex.LEFT_ELBOW] = [0.4, 0.6, 0.0, 0.95]
    landmarks[LandmarkIndex.LEFT_WRIST] = [0.7, 0.6, 0.0, 0.95]

    return landmarks


# 1. Landmark Extraction Tests
def test_extract_landmarks_array_none_result():
    assert extract_landmarks_array(None) is None
    mock_result = MagicMock()
    mock_result.pose_landmarks = []
    assert extract_landmarks_array(mock_result) is None


def test_extract_landmarks_array_valid():
    mock_result = MagicMock()
    mock_landmark = MagicMock()
    mock_landmark.x = 0.5
    mock_landmark.y = 0.6
    mock_landmark.z = 0.1
    mock_landmark.visibility = 0.9
    mock_result.pose_landmarks = [[mock_landmark] * 33]

    arr = extract_landmarks_array(mock_result)
    assert arr is not None
    assert arr.shape == (33, 4)
    assert arr[0, 0] == pytest.approx(0.5)
    assert arr[0, 1] == pytest.approx(0.6)
    assert arr[0, 3] == pytest.approx(0.9)


# 2. Angle Calculation Tests
def test_calculate_angle_2d_right_angle():
    a = np.array([0.0, 1.0])
    b = np.array([0.0, 0.0])
    c = np.array([1.0, 0.0])
    angle = calculate_angle_2d(a, b, c)
    assert pytest.approx(angle, 0.01) == 90.0


def test_calculate_angle_2d_collinear_straight():
    a = (0.0, 1.0)
    b = (0.0, 0.0)
    c = (0.0, -1.0)
    assert pytest.approx(calculate_angle_2d(a, b, c), 0.01) == 180.0


def test_calculate_angle_3d():
    a = (1.0, 0.0, 0.0)
    b = (0.0, 0.0, 0.0)
    c = (0.0, 1.0, 0.0)
    assert pytest.approx(calculate_angle_3d(a, b, c), 0.01) == 90.0


def test_calculate_joint_angles():
    synthetic = create_synthetic_landmarks()
    angles = calculate_joint_angles(synthetic)
    assert "left_knee" in angles
    assert pytest.approx(angles["left_knee"], 0.5) == 90.0
    assert "left_elbow" in angles
    assert pytest.approx(angles["left_elbow"], 0.5) == 90.0


# 3. Coordinate Normalization Tests
def test_normalize_pose_landmarks():
    synthetic = create_synthetic_landmarks(torso_height=0.5)
    normalized = normalize_pose_landmarks(synthetic)

    assert normalized.shape == (33, 4)
    # Origin should be the midpoint of hips (0.45+0.55)/2 = 0.5, (0.8+0.8)/2 = 0.8
    # So left hip and right hip x coordinates should be symmetric around 0
    assert pytest.approx(normalized[LandmarkIndex.LEFT_HIP, 1], 0.01) == 0.0
    assert pytest.approx(normalized[LandmarkIndex.RIGHT_HIP, 1], 0.01) == 0.0
    assert normalized[LandmarkIndex.LEFT_HIP, 0] == pytest.approx(-normalized[LandmarkIndex.RIGHT_HIP, 0])


# 4. Pose Detector Robustness (No Person / Empty Frame)
def test_pose_detector_empty_frame():
    detector = PoseDetector()
    black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = detector.detect(black_frame, timestamp_ms=0)
    assert isinstance(result, PoseDetectionResult)
    assert result.has_detection is False
    assert result.landmarks is None
    detector.close()


# 5. Visualizer Tests
def test_pose_visualizer():
    visualizer = PoseVisualizer()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    synthetic = create_synthetic_landmarks()

    # Draw skeleton
    frame_with_skeleton = visualizer.draw_skeleton(frame.copy(), synthetic)
    assert frame_with_skeleton.shape == (480, 640, 3)

    # Draw HUD
    frame_with_hud = visualizer.draw_hud(frame.copy(), fps=30.0, has_detection=True)
    assert frame_with_hud.shape == (480, 640, 3)

    # Draw angles
    angles = {"left_knee": 90.0}
    frame_with_angles = visualizer.draw_joint_angles(frame.copy(), synthetic, angles)
    assert frame_with_angles.shape == (480, 640, 3)


# 6. Webcam Graceful Failure Handling
def test_webcam_tracker_failure_handling(monkeypatch):
    tracker = WebcamPoseTracker(camera_index=999)  # Non-existent camera
    # Verify camera open fails gracefully without throwing unhandled exceptions
    success = tracker.start_camera()
    assert success is False
    tracker.cleanup()
