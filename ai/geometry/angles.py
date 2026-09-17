from typing import Dict, List, Tuple

import numpy as np


class LandmarkIndex:
    """Landmark index constants used for angle calculations."""
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28


def calculate_angle_2d(
    a: Tuple[float, float] | List[float] | np.ndarray,
    b: Tuple[float, float] | List[float] | np.ndarray,
    c: Tuple[float, float] | List[float] | np.ndarray,
) -> float:
    """
    Calculate the 2D planar angle at vertex point B formed by lines BA and BC in degrees [0, 180].

    Args:
        a: First outer point (x, y)
        b: Center vertex point (x, y)
        c: Second outer point (x, y)

    Returns:
        Angle in degrees [0.0, 180.0]
    """
    a_arr = np.array(a[:2], dtype=np.float64)
    b_arr = np.array(b[:2], dtype=np.float64)
    c_arr = np.array(c[:2], dtype=np.float64)

    ba = a_arr - b_arr
    bc = c_arr - b_arr

    norm_ba = np.linalg.norm(ba)
    norm_bc = np.linalg.norm(bc)

    if norm_ba == 0.0 or norm_bc == 0.0:
        return 0.0

    cosine_angle = np.dot(ba, bc) / (norm_ba * norm_bc)
    cosine_angle = np.clip(cosine_angle, -1.0, 1.0)

    angle = np.degrees(np.arccos(cosine_angle))
    return float(angle)


def calculate_angle_3d(
    a: Tuple[float, float, float] | List[float] | np.ndarray,
    b: Tuple[float, float, float] | List[float] | np.ndarray,
    c: Tuple[float, float, float] | List[float] | np.ndarray,
) -> float:
    """
    Calculate the 3D spatial Euclidean angle at vertex point B formed by vectors BA and BC.

    Args:
        a: First 3D point (x, y, z)
        b: Center vertex 3D point (x, y, z)
        c: Second 3D point (x, y, z)

    Returns:
        Angle in degrees [0.0, 180.0]
    """
    a_arr = np.array(a[:3], dtype=np.float64)
    b_arr = np.array(b[:3], dtype=np.float64)
    c_arr = np.array(c[:3], dtype=np.float64)

    ba = a_arr - b_arr
    bc = c_arr - b_arr

    norm_ba = np.linalg.norm(ba)
    norm_bc = np.linalg.norm(bc)

    if norm_ba == 0.0 or norm_bc == 0.0:
        return 0.0

    cosine_angle = np.dot(ba, bc) / (norm_ba * norm_bc)
    cosine_angle = np.clip(cosine_angle, -1.0, 1.0)

    angle = np.degrees(np.arccos(cosine_angle))
    return float(angle)


def calculate_joint_angles(landmarks: np.ndarray, min_visibility: float = 0.5) -> Dict[str, float]:
    """
    Calculate biomechanical angles for key joints from a (33, 4) landmark array.

    Returns a dictionary mapping joint names to angle degrees.
    """
    angles: Dict[str, float] = {}
    if landmarks is None or len(landmarks) < 33:
        return angles

    def _is_valid(*indices: int) -> bool:
        return all(landmarks[idx, 3] >= min_visibility for idx in indices)

    # Left Elbow: Shoulder(11) - Elbow(13) - Wrist(15)
    if _is_valid(LandmarkIndex.LEFT_SHOULDER, LandmarkIndex.LEFT_ELBOW, LandmarkIndex.LEFT_WRIST):
        angles["left_elbow"] = calculate_angle_2d(
            landmarks[LandmarkIndex.LEFT_SHOULDER],
            landmarks[LandmarkIndex.LEFT_ELBOW],
            landmarks[LandmarkIndex.LEFT_WRIST],
        )

    # Right Elbow: Shoulder(12) - Elbow(14) - Wrist(16)
    if _is_valid(LandmarkIndex.RIGHT_SHOULDER, LandmarkIndex.RIGHT_ELBOW, LandmarkIndex.RIGHT_WRIST):
        angles["right_elbow"] = calculate_angle_2d(
            landmarks[LandmarkIndex.RIGHT_SHOULDER],
            landmarks[LandmarkIndex.RIGHT_ELBOW],
            landmarks[LandmarkIndex.RIGHT_WRIST],
        )

    # Left Knee: Hip(23) - Knee(25) - Ankle(27)
    if _is_valid(LandmarkIndex.LEFT_HIP, LandmarkIndex.LEFT_KNEE, LandmarkIndex.LEFT_ANKLE):
        angles["left_knee"] = calculate_angle_2d(
            landmarks[LandmarkIndex.LEFT_HIP],
            landmarks[LandmarkIndex.LEFT_KNEE],
            landmarks[LandmarkIndex.LEFT_ANKLE],
        )

    # Right Knee: Hip(24) - Knee(26) - Ankle(28)
    if _is_valid(LandmarkIndex.RIGHT_HIP, LandmarkIndex.RIGHT_KNEE, LandmarkIndex.RIGHT_ANKLE):
        angles["right_knee"] = calculate_angle_2d(
            landmarks[LandmarkIndex.RIGHT_HIP],
            landmarks[LandmarkIndex.RIGHT_KNEE],
            landmarks[LandmarkIndex.RIGHT_ANKLE],
        )

    # Left Hip: Shoulder(11) - Hip(23) - Knee(25)
    if _is_valid(LandmarkIndex.LEFT_SHOULDER, LandmarkIndex.LEFT_HIP, LandmarkIndex.LEFT_KNEE):
        angles["left_hip"] = calculate_angle_2d(
            landmarks[LandmarkIndex.LEFT_SHOULDER],
            landmarks[LandmarkIndex.LEFT_HIP],
            landmarks[LandmarkIndex.LEFT_KNEE],
        )

    # Right Hip: Shoulder(12) - Hip(24) - Knee(26)
    if _is_valid(LandmarkIndex.RIGHT_SHOULDER, LandmarkIndex.RIGHT_HIP, LandmarkIndex.RIGHT_KNEE):
        angles["right_hip"] = calculate_angle_2d(
            landmarks[LandmarkIndex.RIGHT_SHOULDER],
            landmarks[LandmarkIndex.RIGHT_HIP],
            landmarks[LandmarkIndex.RIGHT_KNEE],
        )

    # Left Shoulder: Elbow(13) - Shoulder(11) - Hip(23)
    if _is_valid(LandmarkIndex.LEFT_ELBOW, LandmarkIndex.LEFT_SHOULDER, LandmarkIndex.LEFT_HIP):
        angles["left_shoulder"] = calculate_angle_2d(
            landmarks[LandmarkIndex.LEFT_ELBOW],
            landmarks[LandmarkIndex.LEFT_SHOULDER],
            landmarks[LandmarkIndex.LEFT_HIP],
        )

    # Right Shoulder: Elbow(14) - Shoulder(12) - Hip(24)
    if _is_valid(LandmarkIndex.RIGHT_ELBOW, LandmarkIndex.RIGHT_SHOULDER, LandmarkIndex.RIGHT_HIP):
        angles["right_shoulder"] = calculate_angle_2d(
            landmarks[LandmarkIndex.RIGHT_ELBOW],
            landmarks[LandmarkIndex.RIGHT_SHOULDER],
            landmarks[LandmarkIndex.RIGHT_HIP],
        )

    return angles
