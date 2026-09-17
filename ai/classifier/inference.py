import logging
from collections import deque
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import numpy as np

from ai.classifier.pipeline import ExerciseClassificationPipeline

logger = logging.getLogger("ExerciseInference")

# Standard exercise vocabulary required by specification
CANONICAL_EXERCISES = [
    "squat",
    "push_up",
    "bicep_curl",
    "lunge",
    "shoulder_press",
    "other",
]


class ExerciseInferenceEngine:
    """
    Production inference engine for sequence-level exercise recognition.
    Enforces the required JSON output contract, calibrated class probabilities,
    and fallback to 'other' / 'unknown' when prediction confidence is low.
    """

    def __init__(
        self,
        pipeline: Optional[ExerciseClassificationPipeline] = None,
        model_path: Optional[str | Path] = None,
        confidence_threshold: float = 0.60,
        unknown_label: str = "other",
    ):
        if pipeline is not None:
            self.pipeline = pipeline
        elif model_path is not None:
            self.pipeline = ExerciseClassificationPipeline.load(model_path)
        else:
            self.pipeline = None

        self.confidence_threshold = confidence_threshold
        self.unknown_label = unknown_label

    def is_ready(self) -> bool:
        """Returns True if a valid trained pipeline is loaded."""
        return self.pipeline is not None and self.pipeline.model is not None

    def predict_sequence(
        self,
        window: Sequence[np.ndarray] | np.ndarray,
    ) -> Dict[str, Any]:
        """
        Executes model inference on a temporal sequence of landmarks.

        Args:
            window: Array or list of shape (W, 33, 4) or (W, 33, 3) representing landmarks over time.

        Returns:
            Dictionary matching the strict output contract:
            {
                "exercise": str,
                "confidence": float,
                "probabilities": {
                    "squat": float,
                    "push_up": float,
                    "bicep_curl": float,
                    "lunge": float,
                    "shoulder_press": float,
                    "other": float
                }
            }
        """
        # Default probabilities structure initialized to zero
        prob_dict = {name: 0.0 for name in CANONICAL_EXERCISES}

        if not self.is_ready():
            logger.warning("Inference engine called without a loaded model. Returning unknown/other.")
            prob_dict[self.unknown_label] = 1.0
            return {
                "exercise": self.unknown_label,
                "confidence": 0.0,
                "probabilities": prob_dict,
            }

        if window is None or len(window) == 0:
            prob_dict[self.unknown_label] = 1.0
            return {
                "exercise": self.unknown_label,
                "confidence": 0.0,
                "probabilities": prob_dict,
            }

        # 1. Transform raw window via pipeline preprocessor
        X_scaled = self.pipeline.preprocessor.transform_window(window)

        # 2. Model Prediction & Probabilities
        model = self.pipeline.model
        if hasattr(model, "predict_proba"):
            raw_probs = model.predict_proba(X_scaled)[0]
        elif hasattr(model, "decision_function"):
            # Convert decision scores to pseudo-probabilities via softmax
            scores = model.decision_function(X_scaled)[0]
            exp_scores = np.exp(scores - np.max(scores))
            raw_probs = exp_scores / np.sum(exp_scores)
        else:
            # Fallback if probability estimates unavailable
            raw_pred_idx = model.predict(X_scaled)[0]
            raw_probs = np.zeros(len(self.pipeline.classes), dtype=float)
            raw_probs[raw_pred_idx] = 1.0

        model_classes = self.pipeline.classes
        top_idx = int(np.argmax(raw_probs))
        top_prob = float(raw_probs[top_idx])
        predicted_raw_class = model_classes[top_idx] if top_idx < len(model_classes) else self.unknown_label

        # 3. Populate canonical probabilities dictionary
        for cls_name, p in zip(model_classes, raw_probs):
            canon_name = self._canonicalize_name(cls_name)
            prob_dict[canon_name] = round(float(p), 4)

        # Ensure all canonical exercises are present in dictionary
        for key in CANONICAL_EXERCISES:
            if key not in prob_dict:
                prob_dict[key] = 0.0

        # Normalize probabilities to sum to 1.0 for consistency
        total_p = sum(prob_dict.values())
        if total_p > 0:
            for k in prob_dict:
                prob_dict[k] = round(prob_dict[k] / total_p, 4)

        # 4. Low-confidence / Unknown Handling
        canonical_top = self._canonicalize_name(predicted_raw_class)
        if top_prob < self.confidence_threshold:
            final_exercise = self.unknown_label
            final_confidence = round(top_prob, 4)
        else:
            final_exercise = canonical_top
            final_confidence = round(top_prob, 4)

        return {
            "exercise": final_exercise,
            "confidence": final_confidence,
            "probabilities": prob_dict,
        }

    @staticmethod
    def _canonicalize_name(name: str) -> str:
        clean = name.strip().lower().replace("-", "_").replace(" ", "_")
        if clean == "pushup":
            return "push_up"
        if clean == "idle":
            return "other"
        if clean not in CANONICAL_EXERCISES:
            return "other"
        return clean


class StreamingExerciseClassifier:
    """
    Real-time rolling buffer wrapper for live webcam / frame-by-frame feeds.
    Maintains a rolling window of recent pose landmarks and produces smoothed predictions.
    """

    def __init__(
        self,
        inference_engine: ExerciseInferenceEngine,
        window_size: int = 30,
        prediction_interval: int = 5,
        smoothing_window: int = 3,
    ):
        self.engine = inference_engine
        self.window_size = window_size
        self.prediction_interval = prediction_interval
        self.smoothing_window = smoothing_window

        self.buffer: deque[np.ndarray] = deque(maxlen=window_size)
        self.prob_history: deque[Dict[str, float]] = deque(maxlen=smoothing_window)
        self.frame_counter = 0
        self.last_result: Optional[Dict[str, Any]] = None

    def process_frame(self, landmarks: Optional[np.ndarray]) -> Dict[str, Any]:
        """
        Receives a single frame's (33, 4) landmarks, updates buffer, and runs classification when appropriate.
        """
        self.frame_counter += 1

        if landmarks is not None and len(landmarks) >= 33:
            self.buffer.append(landmarks.copy())
        elif len(self.buffer) > 0:
            # Replicate last valid landmark for temporal continuity
            self.buffer.append(self.buffer[-1].copy())

        # If buffer is still filling up
        if len(self.buffer) < self.window_size:
            prob_dict = {name: 0.0 for name in CANONICAL_EXERCISES}
            prob_dict["other"] = 1.0
            return {
                "exercise": "other",
                "confidence": 0.0,
                "probabilities": prob_dict,
                "buffer_fill_pct": len(self.buffer) / self.window_size,
            }

        # Run inference every `prediction_interval` frames
        if self.frame_counter % self.prediction_interval == 0 or self.last_result is None:
            raw_result = self.engine.predict_sequence(np.array(self.buffer))
            self.prob_history.append(raw_result["probabilities"])

            # Compute smoothed probabilities across history
            smoothed_probs = {k: 0.0 for k in CANONICAL_EXERCISES}
            for ph in self.prob_history:
                for k, v in ph.items():
                    smoothed_probs[k] += v / len(self.prob_history)

            top_ex = max(smoothed_probs.items(), key=lambda x: x[1])
            conf = top_ex[1]
            ex_name = top_ex[0] if conf >= self.engine.confidence_threshold else self.engine.unknown_label

            self.last_result = {
                "exercise": ex_name,
                "confidence": round(float(conf), 4),
                "probabilities": {k: round(v, 4) for k, v in smoothed_probs.items()},
                "buffer_fill_pct": 1.0,
            }

        return self.last_result

    def reset(self):
        """Clears rolling buffers and state."""
        self.buffer.clear()
        self.prob_history.clear()
        self.frame_counter = 0
        self.last_result = None
