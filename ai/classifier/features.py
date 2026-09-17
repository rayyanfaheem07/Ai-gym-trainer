from typing import List, Sequence

import numpy as np

from ai.geometry.angles import calculate_angle_2d
from ai.pose.landmarks import LandmarkIndex
from ai.pose.normalizer import normalize_pose_landmarks

# Key landmark subsets relevant for full-body exercise biomechanics (18 keypoints)
KEY_LANDMARK_INDICES = [
    LandmarkIndex.NOSE,
    LandmarkIndex.LEFT_SHOULDER,
    LandmarkIndex.RIGHT_SHOULDER,
    LandmarkIndex.LEFT_ELBOW,
    LandmarkIndex.RIGHT_ELBOW,
    LandmarkIndex.LEFT_WRIST,
    LandmarkIndex.RIGHT_WRIST,
    LandmarkIndex.LEFT_HIP,
    LandmarkIndex.RIGHT_HIP,
    LandmarkIndex.LEFT_KNEE,
    LandmarkIndex.RIGHT_KNEE,
    LandmarkIndex.LEFT_ANKLE,
    LandmarkIndex.RIGHT_ANKLE,
    LandmarkIndex.LEFT_HEEL,
    LandmarkIndex.RIGHT_HEEL,
    LandmarkIndex.LEFT_FOOT_INDEX,
    LandmarkIndex.RIGHT_FOOT_INDEX,
]


class PoseFeatureExtractor:
    """
    Standardized, reusable biomechanical feature extractor for human pose sequences.
    Transforms raw or normalized MediaPipe pose landmark windows into fixed-dimensional
    feature vectors used identically across training, validation, testing, and real-time inference.
    """

    def __init__(self, key_landmarks: List[int] | None = None):
        self.key_landmarks = key_landmarks or KEY_LANDMARK_INDICES
        self._feature_names: List[str] | None = None

    def extract_frame_features(self, landmarks: np.ndarray) -> np.ndarray:
        """
        Extracts a 1D vector of geometric, angular, and distance features for a single frame.

        Args:
            landmarks: Array of shape (33, 3) or (33, 4) with [x, y, z, (visibility)].

        Returns:
            1D numpy array of float32 features.
        """
        if landmarks is None or len(landmarks) < 33:
            # Return zero feature vector with appropriate size
            dummy_dim = len(self.feature_names_per_frame)
            return np.zeros((dummy_dim,), dtype=np.float32)

        # 1. Coordinate normalization (torso-centered & scale-invariant)
        norm_lm = normalize_pose_landmarks(landmarks)

        # 2. Extract keypoint coordinates (x, y, z)
        coord_features = []
        for idx in self.key_landmarks:
            coord_features.extend([
                float(norm_lm[idx, 0]),
                float(norm_lm[idx, 1]),
                float(norm_lm[idx, 2]),
            ])

        # 3. Biomechanical Joint Angles
        angle_features = self._compute_angles(norm_lm)

        # 4. Relative Distances & Spatial Ratios
        distance_features = self._compute_distances(norm_lm)

        all_features = coord_features + angle_features + distance_features
        return np.array(all_features, dtype=np.float32)

    def extract_window_features(self, window: Sequence[np.ndarray] | np.ndarray) -> np.ndarray:
        """
        Extracts aggregated temporal features across a sequence/window of frames.

        Args:
            window: Array or list of shape (W, 33, 4) or (W, 33, 3).

        Returns:
            1D numpy array containing temporal summary statistics:
            [mean, std, min, max, range, delta, mean_velocity] across all frame features.
        """
        if window is None or len(window) == 0:
            total_dim = len(self.get_feature_names())
            return np.zeros((total_dim,), dtype=np.float32)

        frame_features_list = [self.extract_frame_features(frame) for frame in window]
        matrix = np.array(frame_features_list, dtype=np.float32)  # Shape: (W, F)

        if matrix.shape[0] == 1:
            mean = matrix[0]
            std = np.zeros_like(mean)
            min_val = matrix[0]
            max_val = matrix[0]
            val_range = np.zeros_like(mean)
            delta = np.zeros_like(mean)
            mean_vel = np.zeros_like(mean)
        else:
            mean = np.mean(matrix, axis=0)
            std = np.std(matrix, axis=0)
            min_val = np.min(matrix, axis=0)
            max_val = np.max(matrix, axis=0)
            val_range = max_val - min_val
            delta = matrix[-1] - matrix[0]
            # Velocity: average absolute rate of change per frame
            diffs = np.abs(np.diff(matrix, axis=0))
            mean_vel = np.mean(diffs, axis=0)

        # Handle any NaN/inf gracefully
        stats = np.concatenate([mean, std, min_val, max_val, val_range, delta, mean_vel])
        return np.nan_to_num(stats, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)

    @property
    def feature_names_per_frame(self) -> List[str]:
        """Returns ordered names of features extracted from a single frame."""
        names = []
        for idx in self.key_landmarks:
            lm_name = LandmarkIndex(idx).name.lower()
            names.extend([f"{lm_name}_x", f"{lm_name}_y", f"{lm_name}_z"])

        angle_names = [
            "angle_left_elbow",
            "angle_right_elbow",
            "angle_left_knee",
            "angle_right_knee",
            "angle_left_hip",
            "angle_right_hip",
            "angle_left_shoulder",
            "angle_right_shoulder",
            "angle_left_arm_elevation",
            "angle_right_arm_elevation",
            "angle_torso_vertical",
            "angle_body_horizontal",
        ]
        names.extend(angle_names)

        dist_names = [
            "dist_left_wrist_shoulder",
            "dist_right_wrist_shoulder",
            "dist_left_wrist_hip",
            "dist_right_wrist_hip",
            "dist_wrists",
            "dist_ankles",
            "dist_knees",
            "dist_left_wrist_nose",
            "dist_right_wrist_nose",
            "dist_hip_to_ankle_y",
        ]
        names.extend(dist_names)
        return names

    def get_feature_names(self) -> List[str]:
        """Returns full list of feature names for temporal window representation."""
        if self._feature_names is None:
            base_names = self.feature_names_per_frame
            stats = ["mean", "std", "min", "max", "range", "delta", "velocity"]
            self._feature_names = [f"{stat}_{name}" for stat in stats for name in base_names]
        return self._feature_names

    def _compute_angles(self, norm_lm: np.ndarray) -> List[float]:
        """Calculates biomechanical and body-orientation angles in degrees [0, 180]."""
        # Joint angles
        l_elbow = calculate_angle_2d(
            norm_lm[LandmarkIndex.LEFT_SHOULDER],
            norm_lm[LandmarkIndex.LEFT_ELBOW],
            norm_lm[LandmarkIndex.LEFT_WRIST],
        )
        r_elbow = calculate_angle_2d(
            norm_lm[LandmarkIndex.RIGHT_SHOULDER],
            norm_lm[LandmarkIndex.RIGHT_ELBOW],
            norm_lm[LandmarkIndex.RIGHT_WRIST],
        )
        l_knee = calculate_angle_2d(
            norm_lm[LandmarkIndex.LEFT_HIP],
            norm_lm[LandmarkIndex.LEFT_KNEE],
            norm_lm[LandmarkIndex.LEFT_ANKLE],
        )
        r_knee = calculate_angle_2d(
            norm_lm[LandmarkIndex.RIGHT_HIP],
            norm_lm[LandmarkIndex.RIGHT_KNEE],
            norm_lm[LandmarkIndex.RIGHT_ANKLE],
        )
        l_hip = calculate_angle_2d(
            norm_lm[LandmarkIndex.LEFT_SHOULDER],
            norm_lm[LandmarkIndex.LEFT_HIP],
            norm_lm[LandmarkIndex.LEFT_KNEE],
        )
        r_hip = calculate_angle_2d(
            norm_lm[LandmarkIndex.RIGHT_SHOULDER],
            norm_lm[LandmarkIndex.RIGHT_HIP],
            norm_lm[LandmarkIndex.RIGHT_KNEE],
        )
        l_shoulder = calculate_angle_2d(
            norm_lm[LandmarkIndex.LEFT_ELBOW],
            norm_lm[LandmarkIndex.LEFT_SHOULDER],
            norm_lm[LandmarkIndex.LEFT_HIP],
        )
        r_shoulder = calculate_angle_2d(
            norm_lm[LandmarkIndex.RIGHT_ELBOW],
            norm_lm[LandmarkIndex.RIGHT_SHOULDER],
            norm_lm[LandmarkIndex.RIGHT_HIP],
        )
        # Arm elevation relative to hip-shoulder line
        l_arm_elev = calculate_angle_2d(
            norm_lm[LandmarkIndex.LEFT_WRIST],
            norm_lm[LandmarkIndex.LEFT_SHOULDER],
            norm_lm[LandmarkIndex.LEFT_HIP],
        )
        r_arm_elev = calculate_angle_2d(
            norm_lm[LandmarkIndex.RIGHT_WRIST],
            norm_lm[LandmarkIndex.RIGHT_SHOULDER],
            norm_lm[LandmarkIndex.RIGHT_HIP],
        )

        # Torso inclination relative to vertical (0, -1 in image coords where Y increases downwards)
        shoulder_mid = (norm_lm[LandmarkIndex.LEFT_SHOULDER, :2] + norm_lm[LandmarkIndex.RIGHT_SHOULDER, :2]) / 2.0
        hip_mid = (norm_lm[LandmarkIndex.LEFT_HIP, :2] + norm_lm[LandmarkIndex.RIGHT_HIP, :2]) / 2.0
        torso_vec = shoulder_mid - hip_mid
        torso_norm = np.linalg.norm(torso_vec)
        if torso_norm > 1e-4:
            # Angle relative to upright vertical (0, -1)
            up_vec = np.array([0.0, -1.0])
            cos_torso = np.dot(torso_vec, up_vec) / torso_norm
            torso_vert_angle = float(np.degrees(np.arccos(np.clip(cos_torso, -1.0, 1.0))))
        else:
            torso_vert_angle = 0.0

        # Body horizontal angle (shoulder midpoint to ankle midpoint vs horizontal)
        ankle_mid = (norm_lm[LandmarkIndex.LEFT_ANKLE, :2] + norm_lm[LandmarkIndex.RIGHT_ANKLE, :2]) / 2.0
        body_vec = shoulder_mid - ankle_mid
        body_norm = np.linalg.norm(body_vec)
        if body_norm > 1e-4:
            horiz_vec = np.array([1.0, 0.0])
            cos_body = abs(np.dot(body_vec, horiz_vec) / body_norm)
            body_horiz_angle = float(np.degrees(np.arccos(np.clip(cos_body, 0.0, 1.0))))
        else:
            body_horiz_angle = 90.0

        return [
            l_elbow,
            r_elbow,
            l_knee,
            r_knee,
            l_hip,
            r_hip,
            l_shoulder,
            r_shoulder,
            l_arm_elev,
            r_arm_elev,
            torso_vert_angle,
            body_horiz_angle,
        ]

    def _compute_distances(self, norm_lm: np.ndarray) -> List[float]:
        """Calculates scale-normalized relative distances."""
        def _dist(idx1: int, idx2: int) -> float:
            return float(np.linalg.norm(norm_lm[idx1, :3] - norm_lm[idx2, :3]))

        d_l_wrist_sh = _dist(LandmarkIndex.LEFT_WRIST, LandmarkIndex.LEFT_SHOULDER)
        d_r_wrist_sh = _dist(LandmarkIndex.RIGHT_WRIST, LandmarkIndex.RIGHT_SHOULDER)
        d_l_wrist_hip = _dist(LandmarkIndex.LEFT_WRIST, LandmarkIndex.LEFT_HIP)
        d_r_wrist_hip = _dist(LandmarkIndex.RIGHT_WRIST, LandmarkIndex.RIGHT_HIP)
        d_wrists = _dist(LandmarkIndex.LEFT_WRIST, LandmarkIndex.RIGHT_WRIST)
        d_ankles = _dist(LandmarkIndex.LEFT_ANKLE, LandmarkIndex.RIGHT_ANKLE)
        d_knees = _dist(LandmarkIndex.LEFT_KNEE, LandmarkIndex.RIGHT_KNEE)
        d_l_wrist_nose = _dist(LandmarkIndex.LEFT_WRIST, LandmarkIndex.NOSE)
        d_r_wrist_nose = _dist(LandmarkIndex.RIGHT_WRIST, LandmarkIndex.NOSE)

        # Depth measure: Hip center Y vs Ankle center Y
        hip_y = (norm_lm[LandmarkIndex.LEFT_HIP, 1] + norm_lm[LandmarkIndex.RIGHT_HIP, 1]) / 2.0
        ankle_y = (norm_lm[LandmarkIndex.LEFT_ANKLE, 1] + norm_lm[LandmarkIndex.RIGHT_ANKLE, 1]) / 2.0
        d_hip_ankle_y = float(abs(ankle_y - hip_y))

        return [
            d_l_wrist_sh,
            d_r_wrist_sh,
            d_l_wrist_hip,
            d_r_wrist_hip,
            d_wrists,
            d_ankles,
            d_knees,
            d_l_wrist_nose,
            d_r_wrist_nose,
            d_hip_ankle_y,
        ]
