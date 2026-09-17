import numpy as np

from ai.pose.landmarks import LandmarkIndex


def normalize_pose_landmarks(landmarks: np.ndarray) -> np.ndarray:
    """
    Normalizes a (33, 4) landmark array to a torso-centered scale-invariant frame:
    - Root origin (0, 0, 0) is translated to the midpoint of left & right hips.
    - Landmark coordinates are scaled by the torso length (distance from shoulder midpoint to hip midpoint).
    - Visibility values (index 3) remain preserved.

    Args:
        landmarks: (33, 4) or (33, 3) numpy array representing [x, y, z, (visibility)]

    Returns:
        Normalized numpy array of the same shape.
    """
    if landmarks is None or len(landmarks) < 33:
        return landmarks

    norm = landmarks.copy()

    # Calculate hip midpoint as root origin
    left_hip = norm[LandmarkIndex.LEFT_HIP, :3]
    right_hip = norm[LandmarkIndex.RIGHT_HIP, :3]
    hip_center = (left_hip + right_hip) / 2.0

    # Calculate shoulder midpoint
    left_shoulder = norm[LandmarkIndex.LEFT_SHOULDER, :3]
    right_shoulder = norm[LandmarkIndex.RIGHT_SHOULDER, :3]
    shoulder_center = (left_shoulder + right_shoulder) / 2.0

    # Torso height normalization scale factor
    torso_height = float(np.linalg.norm(shoulder_center - hip_center))
    scale = torso_height if torso_height > 1e-4 else 1.0

    # Translate origin and scale
    norm[:, :3] = (norm[:, :3] - hip_center) / scale
    return norm


class PoseNormalizer:
    """Class wrapper for landmark normalization."""

    @staticmethod
    def normalize(landmarks: np.ndarray) -> np.ndarray:
        return normalize_pose_landmarks(landmarks)
