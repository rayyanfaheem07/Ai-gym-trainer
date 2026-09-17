from dataclasses import dataclass
from typing import List

import numpy as np

from ai.geometry.angles import calculate_angle_2d
from ai.geometry.metrics import calculate_vertical_alignment
from ai.pose.landmarks import LandmarkIndex


@dataclass
class SquatKinematicFeatures:
    """Biomechanical kinematic features extracted from a squat repetition or frame."""
    min_knee_angle: float = 180.0             # Minimum knee angle (peak depth reached, in degrees)
    max_torso_lean_deg: float = 0.0           # Maximum torso forward inclination from vertical (degrees)
    knee_valgus_index: float = 1.0            # Ratio of (knee distance / ankle distance); < 0.85 indicates knee caving
    symmetry_delta_deg: float = 0.0          # Absolute difference between left and right knee flexion (degrees)
    lateral_instability_std: float = 0.0      # Standard deviation of hip center x-coordinate during rep
    tracking_confidence: float = 1.0          # Average landmark detection visibility confidence


class SquatFeatureExtractor:
    """
    Extracts kinematic and postural features from a trajectory of pose landmarks recorded during a repetition.
    """

    @staticmethod
    def extract_from_frame(landmarks: np.ndarray) -> SquatKinematicFeatures:
        """Extract features from a single frame."""
        if landmarks is None or len(landmarks) < 33:
            return SquatKinematicFeatures(tracking_confidence=0.0)

        # 1. Knee flexion angles
        left_knee = calculate_angle_2d(
            landmarks[LandmarkIndex.LEFT_HIP],
            landmarks[LandmarkIndex.LEFT_KNEE],
            landmarks[LandmarkIndex.LEFT_ANKLE],
        )
        right_knee = calculate_angle_2d(
            landmarks[LandmarkIndex.RIGHT_HIP],
            landmarks[LandmarkIndex.RIGHT_KNEE],
            landmarks[LandmarkIndex.RIGHT_ANKLE],
        )
        avg_knee = (left_knee + right_knee) / 2.0
        symmetry_delta = abs(left_knee - right_knee)

        # 2. Torso lean relative to vertical (Shoulder to Hip vector)
        shoulder_center = (landmarks[LandmarkIndex.LEFT_SHOULDER, :2] + landmarks[LandmarkIndex.RIGHT_SHOULDER, :2]) / 2.0
        hip_center = (landmarks[LandmarkIndex.LEFT_HIP, :2] + landmarks[LandmarkIndex.RIGHT_HIP, :2]) / 2.0
        torso_lean = calculate_vertical_alignment(shoulder_center, hip_center)

        # 3. Knee valgus index (distance between knees vs distance between ankles)
        knee_dist = np.linalg.norm(landmarks[LandmarkIndex.LEFT_KNEE, :2] - landmarks[LandmarkIndex.RIGHT_KNEE, :2])
        ankle_dist = np.linalg.norm(landmarks[LandmarkIndex.LEFT_ANKLE, :2] - landmarks[LandmarkIndex.RIGHT_ANKLE, :2])
        valgus_index = float(knee_dist / ankle_dist) if ankle_dist > 1e-3 else 1.0

        # 4. Confidence
        conf = float(np.mean(landmarks[[LandmarkIndex.LEFT_HIP, LandmarkIndex.RIGHT_HIP, LandmarkIndex.LEFT_KNEE, LandmarkIndex.RIGHT_KNEE], 3]))

        return SquatKinematicFeatures(
            min_knee_angle=avg_knee,
            max_torso_lean_deg=torso_lean,
            knee_valgus_index=valgus_index,
            symmetry_delta_deg=symmetry_delta,
            lateral_instability_std=0.0,
            tracking_confidence=conf,
        )

    @staticmethod
    def extract_from_trajectory(trajectory: List[np.ndarray]) -> SquatKinematicFeatures:
        """
        Aggregates kinematic features over a complete sequence of rep frames.
        """
        if not trajectory:
            return SquatKinematicFeatures(tracking_confidence=0.0)

        min_knee_angle = 180.0
        max_torso_lean = 0.0
        valgus_indices = []
        symmetry_deltas = []
        hip_x_coords = []
        confidences = []

        for lm in trajectory:
            if lm is None or len(lm) < 33:
                continue

            left_knee = calculate_angle_2d(lm[LandmarkIndex.LEFT_HIP], lm[LandmarkIndex.LEFT_KNEE], lm[LandmarkIndex.LEFT_ANKLE])
            right_knee = calculate_angle_2d(lm[LandmarkIndex.RIGHT_HIP], lm[LandmarkIndex.RIGHT_KNEE], lm[LandmarkIndex.RIGHT_ANKLE])
            avg_knee = (left_knee + right_knee) / 2.0

            if avg_knee < min_knee_angle:
                min_knee_angle = avg_knee

            # Torso lean
            shoulder_mid = (lm[LandmarkIndex.LEFT_SHOULDER, :2] + lm[LandmarkIndex.RIGHT_SHOULDER, :2]) / 2.0
            hip_mid = (lm[LandmarkIndex.LEFT_HIP, :2] + lm[LandmarkIndex.RIGHT_HIP, :2]) / 2.0
            lean = calculate_vertical_alignment(shoulder_mid, hip_mid)
            if lean > max_torso_lean:
                max_torso_lean = lean

            # Valgus at bottom/deepest third of movement
            if avg_knee < 125.0:
                k_dist = np.linalg.norm(lm[LandmarkIndex.LEFT_KNEE, :2] - lm[LandmarkIndex.RIGHT_KNEE, :2])
                a_dist = np.linalg.norm(lm[LandmarkIndex.LEFT_ANKLE, :2] - lm[LandmarkIndex.RIGHT_ANKLE, :2])
                if a_dist > 1e-3:
                    valgus_indices.append(k_dist / a_dist)

            symmetry_deltas.append(abs(left_knee - right_knee))
            hip_x_coords.append(float(hip_mid[0]))
            confidences.append(float(np.mean(lm[:, 3])))

        avg_valgus = float(np.mean(valgus_indices)) if valgus_indices else 1.0
        avg_symmetry_delta = float(np.mean(symmetry_deltas)) if symmetry_deltas else 0.0
        instability_std = float(np.std(hip_x_coords)) if len(hip_x_coords) > 1 else 0.0
        avg_conf = float(np.mean(confidences)) if confidences else 0.0

        return SquatKinematicFeatures(
            min_knee_angle=float(min_knee_angle),
            max_torso_lean_deg=float(max_torso_lean),
            knee_valgus_index=avg_valgus,
            symmetry_delta_deg=avg_symmetry_delta,
            lateral_instability_std=instability_std,
            tracking_confidence=avg_conf,
        )
