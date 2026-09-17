import logging
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Union

import numpy as np

from ai.classifier.inference import CANONICAL_EXERCISES, ExerciseInferenceEngine
from ai.classifier.pipeline import ExerciseClassificationPipeline
try:
    from ai.classifier.temporal_inference import TemporalExerciseInferenceEngine
    from ai.classifier.temporal_pipeline import TemporalClassificationPipeline
except ImportError:
    TemporalExerciseInferenceEngine = None  # type: ignore
    TemporalClassificationPipeline = None  # type: ignore

logger = logging.getLogger("ExerciseClassifier")

DEFAULT_MODEL_DIR = Path(__file__).parent / "weights"
DEFAULT_MODEL_PATH = DEFAULT_MODEL_DIR / "exercise_classifier.joblib"
DEFAULT_TEMPORAL_MODEL_PATH = DEFAULT_MODEL_DIR / "temporal_exercise_classifier.pt"


class ExerciseClassifier:
    """
    High-level modular Exercise Classifier for the AI Gym Trainer.
    Supports trained PyTorch temporal deep learning (.pt) and scikit-learn ML pipeline (.joblib)
    with graceful geometric heuristic fallback.
    """

    def __init__(
        self,
        model_path: Optional[Union[str, Path]] = None,
        confidence_threshold: float = 0.60,
        unknown_label: str = "other",
    ):
        if model_path:
            self.model_path = Path(model_path)
        elif DEFAULT_TEMPORAL_MODEL_PATH.exists():
            self.model_path = DEFAULT_TEMPORAL_MODEL_PATH
        else:
            self.model_path = DEFAULT_MODEL_PATH

        self.confidence_threshold = confidence_threshold
        self.unknown_label = unknown_label
        self.classes = CANONICAL_EXERCISES

        self.inference_engine: Optional[Union[ExerciseInferenceEngine, TemporalExerciseInferenceEngine]] = None
        self._initialize_pipeline()

    def _initialize_pipeline(self):
        """Attempts to load serialized PyTorch or scikit-learn ML pipeline; logs heuristic mode if unavailable."""
        if self.model_path.exists():
            try:
                suffix = self.model_path.suffix.lower()
                if suffix in [".pt", ".pth"]:
                    temporal_pipeline = TemporalClassificationPipeline.load(self.model_path)
                    self.inference_engine = TemporalExerciseInferenceEngine(
                        pipeline=temporal_pipeline,
                        confidence_threshold=self.confidence_threshold,
                        unknown_label=self.unknown_label,
                    )
                    logger.info(f"Loaded trained PyTorch temporal classifier from {self.model_path}")
                else:
                    pipeline = ExerciseClassificationPipeline.load(self.model_path)
                    self.inference_engine = ExerciseInferenceEngine(
                        pipeline=pipeline,
                        confidence_threshold=self.confidence_threshold,
                        unknown_label=self.unknown_label,
                    )
                    logger.info(f"Loaded trained scikit-learn classifier pipeline from {self.model_path}")
            except Exception as e:
                logger.warning(f"Could not load ML pipeline from {self.model_path}: {e}. Operating in heuristic mode.")
                self.inference_engine = None
        else:
            logger.info(f"No trained ML model found at {self.model_path}. Operating in heuristic fallback mode.")
            self.inference_engine = None

    def predict(self, landmarks_window: np.ndarray) -> str:
        """
        Classifies the exercise from a temporal window of landmarks.
        Returns the top predicted exercise string (e.g. 'squat', 'push_up', 'bicep_curl', 'lunge', 'shoulder_press', 'other').
        """
        result = self.predict_detailed(landmarks_window)
        return result["exercise"]

    def predict_detailed(self, landmarks_window: np.ndarray | Sequence[np.ndarray]) -> Dict[str, Any]:
        """
        Infers the exercise type and returns full probability breakdown and confidence score.

        Returns:
            {
                "exercise": "squat",
                "confidence": 0.95,
                "probabilities": {
                    "squat": 0.95,
                    "push_up": 0.01,
                    "bicep_curl": 0.01,
                    "lunge": 0.01,
                    "shoulder_press": 0.01,
                    "other": 0.01
                }
            }
        """
        if self.inference_engine and self.inference_engine.is_ready():
            return self.inference_engine.predict_sequence(landmarks_window)

        # Heuristic fallback if ML model is not yet trained
        return self._heuristic_predict(landmarks_window)

    def _heuristic_predict(self, landmarks_window: np.ndarray | Sequence[np.ndarray]) -> Dict[str, Any]:
        """Biomechanical geometric heuristic fallback when no serialized ML model is present."""
        prob_dict = {name: 0.0 for name in CANONICAL_EXERCISES}

        if landmarks_window is None or len(landmarks_window) == 0:
            prob_dict[self.unknown_label] = 1.0
            return {
                "exercise": self.unknown_label,
                "confidence": 0.0,
                "probabilities": prob_dict,
            }

        last_frame = landmarks_window[-1] if len(np.shape(landmarks_window)) == 3 else landmarks_window
        if len(last_frame) < 33:
            prob_dict[self.unknown_label] = 1.0
            return {
                "exercise": self.unknown_label,
                "confidence": 0.0,
                "probabilities": prob_dict,
            }

        # Check orientation: horizontal (pushup) vs vertical
        shoulder_y = (last_frame[11, 1] + last_frame[12, 1]) / 2.0
        hip_y = (last_frame[23, 1] + last_frame[24, 1]) / 2.0
        ankle_y = (last_frame[27, 1] + last_frame[28, 1]) / 2.0

        if abs(shoulder_y - hip_y) < 0.15 and abs(hip_y - ankle_y) < 0.2:
            prob_dict["push_up"] = 0.85
            prob_dict["other"] = 0.15
            return {"exercise": "push_up", "confidence": 0.85, "probabilities": prob_dict}

        # Check hands overhead vs near hips
        wrist_y = (last_frame[15, 1] + last_frame[16, 1]) / 2.0
        if wrist_y < shoulder_y:
            prob_dict["shoulder_press"] = 0.80
            prob_dict["other"] = 0.20
            return {"exercise": "shoulder_press", "confidence": 0.80, "probabilities": prob_dict}

        # Default vertical movement
        prob_dict["squat"] = 0.75
        prob_dict["other"] = 0.25
        return {"exercise": "squat", "confidence": 0.75, "probabilities": prob_dict}
