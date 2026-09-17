import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import numpy as np
from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class BaseAIInferenceService(ABC):
    """
    Abstract AI Inference Service interface for exercise classification.
    Allows PyTorch, scikit-learn, or ONNX runtimes to be hot-swapped without
    modifying application routing or services.
    """

    @abstractmethod
    def predict_exercise(
        self,
        landmarks: np.ndarray,
        exercise_hint: str | None = None,
    ) -> dict[str, Any]:
        """
        Predicts exercise type and probability distribution from landmarks.
        """
        pass

    @abstractmethod
    def is_model_available(self) -> bool:
        """Returns True if a real trained model is loaded on disk."""
        pass


class AIInferenceService(BaseAIInferenceService):
    """
    Production AI Inference Service integrating Phase 6 (scikit-learn) and
    Phase 7 (PyTorch Temporal) pipelines with graceful uncalibrated fallback.
    """

    def __init__(self):
        self._engine = None
        self._model_type = "uninitialized"
        self._is_stub = True
        self._initialize_engine()

    def _initialize_engine(self) -> None:
        """Attempts to load PyTorch temporal model first, then scikit-learn pipeline."""
        # 1. Try PyTorch Temporal Model (Phase 7)
        temporal_path = Path(settings.TEMPORAL_MODEL_PATH)
        if temporal_path.exists():
            try:
                from ai.classifier.temporal_inference import TemporalExerciseInferenceEngine

                self._engine = TemporalExerciseInferenceEngine(
                    model_path=temporal_path,
                    confidence_threshold=settings.MODEL_CONFIDENCE_THRESHOLD,
                )
                if self._engine.is_ready():
                    self._model_type = "pytorch_temporal_v1"
                    self._is_stub = False
                    logger.info("Successfully loaded Phase 7 PyTorch Temporal classifier.")
                    return
            except Exception as e:
                logger.warning(f"Failed loading PyTorch temporal classifier: {e}")

        # 2. Try scikit-learn Pipeline (Phase 6)
        sklearn_path = Path(settings.SKLEARN_MODEL_PATH)
        if sklearn_path.exists():
            try:
                from ai.classifier.inference import ExerciseInferenceEngine

                self._engine = ExerciseInferenceEngine(
                    model_path=sklearn_path,
                    confidence_threshold=settings.MODEL_CONFIDENCE_THRESHOLD,
                )
                if self._engine.is_ready():
                    self._model_type = "sklearn_baseline_v1"
                    self._is_stub = False
                    logger.info("Successfully loaded Phase 6 scikit-learn classifier.")
                    return
            except Exception as e:
                logger.warning(f"Failed loading scikit-learn classifier: {e}")

        # 3. Explicit Stub / Fallback Mode
        self._model_type = "heuristic_fallback_stub"
        self._is_stub = True
        logger.info(
            "Trained ML model checkpoint not found on disk. Operating in explicit heuristic fallback mode."
        )

    def is_model_available(self) -> bool:
        return not self._is_stub and self._engine is not None and self._engine.is_ready()

    def predict_exercise(
        self,
        landmarks: np.ndarray,
        exercise_hint: str | None = None,
    ) -> dict[str, Any]:
        """
        Executes exercise classification on landmark array (W, 33, 4) or (33, 4).
        """
        canonical_classes = [
            "squat",
            "push_up",
            "bicep_curl",
            "lunge",
            "shoulder_press",
            "other",
        ]

        if exercise_hint:
            clean_hint = exercise_hint.lower().replace("-", "_").replace(" ", "_")
            if clean_hint in ["pushup"]:
                clean_hint = "push_up"
            if clean_hint in canonical_classes:
                probs = {c: 0.0 for c in canonical_classes}
                probs[clean_hint] = 1.0
                return {
                    "exercise": clean_hint,
                    "confidence": 1.0,
                    "probabilities": probs,
                    "is_stub": self._is_stub,
                    "model_info": self._model_type,
                }

        # If real model is ready, execute actual inference
        if self.is_model_available() and self._engine is not None:
            # Reshape 2D (33, 4) to 3D (1, 33, 4) if needed
            window = landmarks if landmarks.ndim == 3 else np.expand_dims(landmarks, axis=0)
            res = self._engine.predict_sequence(window)
            return {
                "exercise": res.get("exercise", "other"),
                "confidence": res.get("confidence", 0.0),
                "probabilities": res.get("probabilities", {c: 0.0 for c in canonical_classes}),
                "is_stub": False,
                "model_info": self._model_type,
            }

        # Explicit heuristic / fallback without fabricating false confidence
        probs = {c: round(1.0 / len(canonical_classes), 4) for c in canonical_classes}
        return {
            "exercise": "other",
            "confidence": 0.0,
            "probabilities": probs,
            "is_stub": True,
            "model_info": self._model_type,
        }


# Singleton instance
ai_inference_service = AIInferenceService()
