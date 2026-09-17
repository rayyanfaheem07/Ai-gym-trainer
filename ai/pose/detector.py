import logging
import os
import urllib.request

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from ai.geometry.angles import calculate_joint_angles
from ai.pose.filters import OneEuroFilter
from ai.pose.landmarks import PoseDetectionResult
from ai.pose.normalizer import normalize_pose_landmarks

logger = logging.getLogger(__name__)

# Default model download URL and local path
DEFAULT_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
DEFAULT_MODEL_DIR = os.path.join(os.path.dirname(__file__), "weights")
DEFAULT_MODEL_PATH = os.path.join(DEFAULT_MODEL_DIR, "pose_landmarker_lite.task")


def ensure_model_asset(model_path: str = DEFAULT_MODEL_PATH, model_url: str = DEFAULT_MODEL_URL) -> str:
    """Ensures the MediaPipe pose landmarker model asset exists locally, downloading if necessary."""
    if not os.path.exists(model_path):
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        logger.info(f"Downloading pose model asset to {model_path}...")
        urllib.request.urlretrieve(model_url, model_path)
        logger.info("Pose model downloaded successfully.")
    return model_path


def extract_landmarks_array(landmarker_result) -> np.ndarray | None:
    """
    Unit-testable helper to extract normalized (33, 4) landmark array from MediaPipe PoseLandmarkerResult.

    Returns:
        np.ndarray of shape (33, 4) [x, y, z, visibility] or None if no landmarks detected.
    """
    if not landmarker_result or not landmarker_result.pose_landmarks:
        return None
    if len(landmarker_result.pose_landmarks) == 0:
        return None

    first_person = landmarker_result.pose_landmarks[0]
    if len(first_person) < 33:
        return None

    arr = np.array(
        [[lm.x, lm.y, lm.z, getattr(lm, "visibility", 1.0) or 1.0] for lm in first_person],
        dtype=np.float32,
    )
    return arr


def extract_world_landmarks_array(landmarker_result) -> np.ndarray | None:
    """
    Extracts 3D world landmark coordinates (metric space in meters) from result.
    """
    if not landmarker_result or not hasattr(landmarker_result, "pose_world_landmarks"):
        return None
    if not landmarker_result.pose_world_landmarks or len(landmarker_result.pose_world_landmarks) == 0:
        return None

    first_person = landmarker_result.pose_world_landmarks[0]
    if len(first_person) < 33:
        return None

    arr = np.array(
        [[lm.x, lm.y, lm.z, getattr(lm, "visibility", 1.0) or 1.0] for lm in first_person],
        dtype=np.float32,
    )
    return arr


class PoseDetector:
    """
    Production-grade Pose Detector wrapping MediaPipe Tasks PoseLandmarker.
    Completely independent from web servers / FastAPI.
    """

    def __init__(
        self,
        model_path: str | None = None,
        min_pose_detection_confidence: float = 0.5,
        min_pose_presence_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        enable_filter: bool = True,
        running_mode: vision.RunningMode = vision.RunningMode.VIDEO,
    ):
        self.model_path = model_path or DEFAULT_MODEL_PATH
        ensure_model_asset(self.model_path)

        self.min_detection_confidence = min_pose_detection_confidence
        self.min_presence_confidence = min_pose_presence_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.running_mode = running_mode
        self.enable_filter = enable_filter
        self.filter = OneEuroFilter() if enable_filter else None

        # Initialize MediaPipe PoseLandmarker
        base_options = python.BaseOptions(model_asset_path=self.model_path)
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=self.running_mode,
            min_pose_detection_confidence=self.min_detection_confidence,
            min_pose_presence_confidence=self.min_presence_confidence,
            min_tracking_confidence=self.min_tracking_confidence,
            output_segmentation_masks=False,
        )
        self.detector = vision.PoseLandmarker.create_from_options(options)

    def detect(
        self,
        frame_bgr: np.ndarray,
        timestamp_ms: int | None = None,
    ) -> PoseDetectionResult:
        """
        Detects pose landmarks in a given BGR image frame.

        Args:
            frame_bgr: Input OpenCV BGR image frame (H, W, 3).
            timestamp_ms: Monotonically increasing frame timestamp in milliseconds (required for VIDEO mode).

        Returns:
            PoseDetectionResult dataclass with normalized landmarks and computed joint angles.
        """
        if frame_bgr is None or frame_bgr.size == 0:
            return PoseDetectionResult(has_detection=False)

        # Convert OpenCV BGR to RGB
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

        # Execute MediaPipe Pose detection
        if self.running_mode == vision.RunningMode.VIDEO:
            ts = timestamp_ms if timestamp_ms is not None else int(cv2.getTickCount() / cv2.getTickFrequency() * 1000)
            result = self.detector.detect_for_video(mp_image, ts)
        else:
            result = self.detector.detect(mp_image)

        # Extract landmark arrays
        raw_landmarks = extract_landmarks_array(result)
        if raw_landmarks is None:
            return PoseDetectionResult(has_detection=False, timestamp_ms=timestamp_ms or 0.0)

        world_landmarks = extract_world_landmarks_array(result)

        # Apply 1-Euro adaptive temporal smoothing
        if self.enable_filter and self.filter is not None:
            time_sec = (timestamp_ms / 1000.0) if timestamp_ms else None
            smoothed_xyz = self.filter.filter(raw_landmarks[:, :3], timestamp=time_sec)
            raw_landmarks[:, :3] = smoothed_xyz

        # Calculate scale-invariant normalized coordinates and joint angles
        normalized_landmarks = normalize_pose_landmarks(raw_landmarks)
        angles = calculate_joint_angles(raw_landmarks)

        return PoseDetectionResult(
            has_detection=True,
            landmarks=raw_landmarks,
            world_landmarks=world_landmarks,
            normalized_landmarks=normalized_landmarks,
            angles=angles,
            timestamp_ms=float(timestamp_ms or 0.0),
        )

    def reset(self):
        """Resets filter and detector states."""
        if self.filter:
            self.filter.reset()

    def close(self):
        """Releases MediaPipe detector resources."""
        if hasattr(self, "detector") and self.detector:
            self.detector.close()
