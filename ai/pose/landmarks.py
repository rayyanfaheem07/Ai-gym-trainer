import enum
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np


class LandmarkIndex(enum.IntEnum):
    """MediaPipe 33 standard Pose Landmark indices."""
    NOSE = 0
    LEFT_EYE_INNER = 1
    LEFT_EYE = 2
    LEFT_EYE_OUTER = 3
    RIGHT_EYE_INNER = 4
    RIGHT_EYE = 5
    RIGHT_EYE_OUTER = 6
    LEFT_EAR = 7
    RIGHT_EAR = 8
    MOUTH_LEFT = 9
    MOUTH_RIGHT = 10
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_PINKY = 17
    RIGHT_PINKY = 18
    LEFT_INDEX = 19
    RIGHT_INDEX = 20
    LEFT_THUMB = 21
    RIGHT_THUMB = 22
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    LEFT_HEEL = 29
    RIGHT_HEEL = 30
    LEFT_FOOT_INDEX = 31
    RIGHT_FOOT_INDEX = 32


# Standard Skeleton Connection pairs (Bone definitions)
POSE_CONNECTIONS: List[Tuple[int, int]] = [
    # Torso
    (LandmarkIndex.LEFT_SHOULDER, LandmarkIndex.RIGHT_SHOULDER),
    (LandmarkIndex.LEFT_SHOULDER, LandmarkIndex.LEFT_HIP),
    (LandmarkIndex.RIGHT_SHOULDER, LandmarkIndex.RIGHT_HIP),
    (LandmarkIndex.LEFT_HIP, LandmarkIndex.RIGHT_HIP),
    # Left Arm
    (LandmarkIndex.LEFT_SHOULDER, LandmarkIndex.LEFT_ELBOW),
    (LandmarkIndex.LEFT_ELBOW, LandmarkIndex.LEFT_WRIST),
    (LandmarkIndex.LEFT_WRIST, LandmarkIndex.LEFT_PINKY),
    (LandmarkIndex.LEFT_WRIST, LandmarkIndex.LEFT_INDEX),
    (LandmarkIndex.LEFT_WRIST, LandmarkIndex.LEFT_THUMB),
    # Right Arm
    (LandmarkIndex.RIGHT_SHOULDER, LandmarkIndex.RIGHT_ELBOW),
    (LandmarkIndex.RIGHT_ELBOW, LandmarkIndex.RIGHT_WRIST),
    (LandmarkIndex.RIGHT_WRIST, LandmarkIndex.RIGHT_PINKY),
    (LandmarkIndex.RIGHT_WRIST, LandmarkIndex.RIGHT_INDEX),
    (LandmarkIndex.RIGHT_WRIST, LandmarkIndex.RIGHT_THUMB),
    # Left Leg
    (LandmarkIndex.LEFT_HIP, LandmarkIndex.LEFT_KNEE),
    (LandmarkIndex.LEFT_KNEE, LandmarkIndex.LEFT_ANKLE),
    (LandmarkIndex.LEFT_ANKLE, LandmarkIndex.LEFT_HEEL),
    (LandmarkIndex.LEFT_HEEL, LandmarkIndex.LEFT_FOOT_INDEX),
    (LandmarkIndex.LEFT_ANKLE, LandmarkIndex.LEFT_FOOT_INDEX),
    # Right Leg
    (LandmarkIndex.RIGHT_HIP, LandmarkIndex.RIGHT_KNEE),
    (LandmarkIndex.RIGHT_KNEE, LandmarkIndex.RIGHT_ANKLE),
    (LandmarkIndex.RIGHT_ANKLE, LandmarkIndex.RIGHT_HEEL),
    (LandmarkIndex.RIGHT_HEEL, LandmarkIndex.RIGHT_FOOT_INDEX),
    (LandmarkIndex.RIGHT_ANKLE, LandmarkIndex.RIGHT_FOOT_INDEX),
    # Face
    (LandmarkIndex.LEFT_EAR, LandmarkIndex.LEFT_EYE_OUTER),
    (LandmarkIndex.LEFT_EYE_OUTER, LandmarkIndex.LEFT_EYE),
    (LandmarkIndex.LEFT_EYE, LandmarkIndex.LEFT_EYE_INNER),
    (LandmarkIndex.LEFT_EYE_INNER, LandmarkIndex.NOSE),
    (LandmarkIndex.NOSE, LandmarkIndex.RIGHT_EYE_INNER),
    (LandmarkIndex.RIGHT_EYE_INNER, LandmarkIndex.RIGHT_EYE),
    (LandmarkIndex.RIGHT_EYE, LandmarkIndex.RIGHT_EYE_OUTER),
    (LandmarkIndex.RIGHT_EYE_OUTER, LandmarkIndex.RIGHT_EAR),
]


@dataclass
class PoseDetectionResult:
    """Encapsulates the detected pose landmarks and biomechanical metrics."""
    has_detection: bool = False
    landmarks: np.ndarray | None = None          # (33, 4): [x, y, z, visibility]
    world_landmarks: np.ndarray | None = None    # (33, 4): metric 3D coords
    normalized_landmarks: np.ndarray | None = None  # Torso-centered scale-invariant
    angles: Dict[str, float] = field(default_factory=dict)  # Calculated joint angles
    timestamp_ms: float = 0.0
