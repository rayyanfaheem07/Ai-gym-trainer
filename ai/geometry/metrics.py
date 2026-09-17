from typing import List, Tuple

import numpy as np


def calculate_vertical_alignment(
    top_point: Tuple[float, float] | List[float] | np.ndarray,
    bottom_point: Tuple[float, float] | List[float] | np.ndarray,
) -> float:
    """
    Calculate the deviation angle in degrees from the true vertical axis (gravity).
    Useful for measuring torso lean or knee drift.
    """
    top = np.array(top_point[:2], dtype=np.float64)
    bottom = np.array(bottom_point[:2], dtype=np.float64)

    vector = top - bottom
    vertical = np.array([0.0, -1.0])  # In screen space, y points downward

    norm_v = np.linalg.norm(vector)
    if norm_v == 0:
        return 0.0

    cos_val = np.dot(vector, vertical) / norm_v
    cos_val = np.clip(cos_val, -1.0, 1.0)
    return float(np.degrees(np.arccos(cos_val)))


def calculate_symmetry_index(left_val: float, right_val: float) -> float:
    """
    Calculate the symmetry percentage index between bilateral limbs [0, 100%].
    100% = perfectly symmetrical.
    """
    if left_val + right_val == 0:
        return 100.0
    diff = abs(left_val - right_val)
    avg = (left_val + right_val) / 2.0
    deviation = (diff / avg) * 100.0
    return float(max(0.0, 100.0 - deviation))
