"""Unit tests for Computer Vision geometry, landmarks parsing, normalization, and detector edge cases.

Verifies robustness against NaN, Inf, zero-length vectors, extreme coordinates,
incomplete landmarks, empty frames, and malformed inputs.
"""

from unittest.mock import MagicMock

import numpy as np
import pytest

from ai.geometry.angles import (
    calculate_angle_2d,
    calculate_angle_3d,
    calculate_joint_angles,
)
from ai.geometry.metrics import (
    calculate_symmetry_index,
    calculate_vertical_alignment,
)
from ai.pose.detector import (
    PoseDetector,
    extract_landmarks_array,
    extract_world_landmarks_array,
)
from ai.pose.landmarks import LandmarkIndex, PoseDetectionResult
from ai.pose.normalizer import normalize_pose_landmarks

# ==============================================================================
# 1. 2D & 3D Angle Calculations with Edge Cases
# ==============================================================================


def test_calculate_angle_2d_zero_length_vector():
    """Zero-length vectors (vertex identical to outer point) should return 0.0 without ZeroDivisionError."""
    # B identical to A
    assert calculate_angle_2d((0.0, 0.0), (0.0, 0.0), (1.0, 0.0)) == 0.0
    # B identical to C
    assert calculate_angle_2d((1.0, 0.0), (0.0, 0.0), (0.0, 0.0)) == 0.0
    # All identical
    assert calculate_angle_2d((0.0, 0.0), (0.0, 0.0), (0.0, 0.0)) == 0.0


def test_calculate_angle_2d_collinear():
    """Collinear points should produce exact 0.0 or 180.0 degrees."""
    # 180 degrees (opposite directions)
    angle_180 = calculate_angle_2d((0.0, 1.0), (0.0, 0.0), (0.0, -1.0))
    assert pytest.approx(angle_180, 0.01) == 180.0

    # 0 degrees (same direction)
    angle_0 = calculate_angle_2d((0.0, 1.0), (0.0, 0.0), (0.0, 2.0))
    assert pytest.approx(angle_0, 0.01) == 0.0


def test_calculate_angle_2d_extreme_coordinates():
    """Extreme coordinate values (e.g. 1e8) should not cause overflow and compute correct angles."""
    scale = 1e8
    a = (0.0, scale)
    b = (0.0, 0.0)
    c = (scale, 0.0)
    angle = calculate_angle_2d(a, b, c)
    assert pytest.approx(angle, 0.01) == 90.0


def test_calculate_angle_2d_nan_and_inf_safety():
    """Passing NaN or Inf should not raise unhandled exceptions."""
    # Should safely return a float without crashing
    res_nan = calculate_angle_2d((np.nan, 1.0), (0.0, 0.0), (1.0, 0.0))
    assert isinstance(res_nan, float)

    res_inf = calculate_angle_2d((np.inf, 1.0), (0.0, 0.0), (1.0, 0.0))
    assert isinstance(res_inf, float)


def test_calculate_angle_3d_edge_cases():
    """3D angle calculations with zero vectors and orthogonal axes."""
    # Zero vector
    assert calculate_angle_3d((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)) == 0.0

    # 90 degrees along X and Z
    a = (1.0, 0.0, 0.0)
    b = (0.0, 0.0, 0.0)
    c = (0.0, 0.0, 1.0)
    assert pytest.approx(calculate_angle_3d(a, b, c), 0.01) == 90.0

    # Opposite vectors: 180 degrees
    d = (-1.0, 0.0, 0.0)
    assert pytest.approx(calculate_angle_3d(a, b, d), 0.01) == 180.0


# ==============================================================================
# 2. Biomechanical Joint Angles
# ==============================================================================


def test_calculate_joint_angles_missing_or_incomplete():
    """Should return empty dictionary for None, empty, or incomplete landmark arrays."""
    assert calculate_joint_angles(None) == {}
    assert calculate_joint_angles(np.zeros((0, 4))) == {}
    assert calculate_joint_angles(np.zeros((32, 4))) == {}  # Less than 33


def test_calculate_joint_angles_visibility_filtering():
    """Joints with visibility below threshold must be excluded from result dict."""
    landmarks = np.zeros((33, 4), dtype=np.float32)
    landmarks[:, 3] = 0.9  # High visibility default

    # Make left elbow landmarks low visibility (< 0.5)
    landmarks[LandmarkIndex.LEFT_ELBOW, 3] = 0.2

    angles = calculate_joint_angles(landmarks, min_visibility=0.5)
    assert "left_elbow" not in angles
    # Other valid joints should still be calculated
    assert "right_elbow" in angles
    assert "left_knee" in angles


# ==============================================================================
# 3. Geometry Metrics: Alignment & Symmetry
# ==============================================================================


def test_calculate_vertical_alignment_cases():
    """Verifies vertical alignment with zero vectors and known angles."""
    # Zero vector (top == bottom)
    assert calculate_vertical_alignment((0.5, 0.5), (0.5, 0.5)) == 0.0

    # Perfectly vertical in screen coordinates (vector = top - bottom = (0, -0.5), vertical = (0, -1))
    top = (0.5, 0.2)
    bottom = (0.5, 0.7)
    assert pytest.approx(calculate_vertical_alignment(top, bottom), 0.01) == 0.0

    # 45-degree tilt
    top_45 = (0.5, 0.2)
    bottom_45 = (0.8, 0.5)
    # vector = (-0.3, -0.3) -> angle with (0, -1) is 45 deg
    assert pytest.approx(calculate_vertical_alignment(top_45, bottom_45), 0.5) == 45.0


def test_calculate_symmetry_index_cases():
    """Verifies symmetry calculation edge cases."""
    # Both zero
    assert calculate_symmetry_index(0.0, 0.0) == 100.0

    # Perfect symmetry
    assert calculate_symmetry_index(90.0, 90.0) == 100.0

    # Moderate asymmetry: 80 and 100 -> avg=90, diff=20 -> dev = 22.22% -> score = 77.78
    sym = calculate_symmetry_index(80.0, 100.0)
    assert pytest.approx(sym, 0.1) == 77.78

    # Extreme asymmetry (one is 0, one is 100) -> clamped at 0.0 minimum
    assert calculate_symmetry_index(0.0, 100.0) == 0.0


# ==============================================================================
# 4. Landmark Parsing & Normalization
# ==============================================================================


def test_extract_landmarks_array_edge_cases():
    """extract_landmarks_array handles missing objects, missing attributes, and malformed lists."""
    assert extract_landmarks_array(None) is None

    mock_res = MagicMock()
    mock_res.pose_landmarks = None
    assert extract_landmarks_array(mock_res) is None

    mock_res.pose_landmarks = []
    assert extract_landmarks_array(mock_res) is None

    # Incomplete landmarks (<33 points)
    mock_res.pose_landmarks = [[MagicMock() for _ in range(20)]]
    assert extract_landmarks_array(mock_res) is None


def test_extract_world_landmarks_array_edge_cases():
    """extract_world_landmarks_array handles missing pose_world_landmarks safely."""
    assert extract_world_landmarks_array(None) is None

    mock_res = MagicMock(spec=[])  # No pose_world_landmarks attribute
    assert extract_world_landmarks_array(mock_res) is None

    mock_res.pose_world_landmarks = []
    assert extract_world_landmarks_array(mock_res) is None


def test_normalize_pose_landmarks_degenerate_geometry():
    """Normalizer handles degenerate geometry (zero torso height) gracefully without ZeroDivisionError."""
    degenerate_landmarks = np.zeros((33, 4), dtype=np.float32)
    degenerate_landmarks[:, 3] = 0.95
    # Both shoulders and hips at y = 0.5 (torso height = 0.0)
    degenerate_landmarks[LandmarkIndex.LEFT_SHOULDER] = [0.4, 0.5, 0.0, 0.95]
    degenerate_landmarks[LandmarkIndex.RIGHT_SHOULDER] = [0.6, 0.5, 0.0, 0.95]
    degenerate_landmarks[LandmarkIndex.LEFT_HIP] = [0.45, 0.5, 0.0, 0.95]
    degenerate_landmarks[LandmarkIndex.RIGHT_HIP] = [0.55, 0.5, 0.0, 0.95]

    normalized = normalize_pose_landmarks(degenerate_landmarks)
    assert normalized.shape == (33, 4)
    # Should not produce NaN or Inf
    assert not np.isnan(normalized).any()
    assert not np.isinf(normalized).any()


# ==============================================================================
# 5. PoseDetector Input Dimensions & Resource Cleanup
# ==============================================================================


def test_pose_detector_empty_and_zero_dimension_frames():
    """PoseDetector safely rejects None, empty, or 0x0 frames without throwing."""
    detector = PoseDetector()

    # None frame
    res_none = detector.detect(None)
    assert isinstance(res_none, PoseDetectionResult)
    assert res_none.has_detection is False

    # 0x0 frame
    res_empty = detector.detect(np.empty((0, 0, 3), dtype=np.uint8))
    assert res_empty.has_detection is False

    # 1x1 frame
    res_tiny = detector.detect(np.zeros((1, 1, 3), dtype=np.uint8), timestamp_ms=10)
    assert res_tiny.has_detection is False

    # Idempotent cleanup
    detector.close()
    detector.close()
