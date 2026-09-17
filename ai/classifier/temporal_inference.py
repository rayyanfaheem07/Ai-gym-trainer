import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np
import torch

from ai.classifier.inference import CANONICAL_EXERCISES
from ai.classifier.temporal_pipeline import TemporalClassificationPipeline

logger = logging.getLogger("TemporalInference")


class TemporalExerciseInferenceEngine:
    """
    Production inference engine for temporal PyTorch exercise recognition.
    Complies with the strict JSON output contract, calibrated class probabilities,
    and fallback to 'other' / 'unknown' when prediction confidence is low.
    """

    def __init__(
        self,
        pipeline: Optional[TemporalClassificationPipeline] = None,
        model_path: Optional[Union[str, Path]] = None,
        confidence_threshold: float = 0.60,
        unknown_label: str = "other",
        device: str = "cpu",
    ):
        self.device = torch.device(device)
        if pipeline is not None:
            self.pipeline = pipeline
            self.pipeline.model.to(self.device)
            self.pipeline.model.eval()
        elif model_path is not None:
            self.pipeline = TemporalClassificationPipeline.load(model_path, device=str(self.device))
        else:
            self.pipeline = None

        self.confidence_threshold = confidence_threshold
        self.unknown_label = unknown_label

    def is_ready(self) -> bool:
        """Returns True if a valid trained pipeline is loaded."""
        return self.pipeline is not None and self.pipeline.model is not None

    def predict_sequence(
        self,
        window: Union[Sequence[np.ndarray], np.ndarray],
    ) -> Dict[str, Any]:
        """
        Executes model inference on a temporal sequence of landmarks or features.

        Args:
            window: Array or list of shape (W, 33, 4) / (W, 33, 3) representing landmarks,
                    or pre-extracted features of shape (W, 73) / (1, W, 73).

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

        window_arr = np.array(window)

        # 1. Feature Transformation & Scaling
        if window_arr.ndim == 3 and window_arr.shape[1] == 33:
            # (W, 33, 4) landmark window -> transform to (1, W, 73) scaled features
            x_scaled = self.pipeline.preprocessor.transform_sequence_window(window_arr)
        elif window_arr.ndim == 2 and window_arr.shape[1] == self.pipeline.model.input_size:
            # Already per-frame features (W, F) -> scale and add batch dim
            scaled_seq = self.pipeline.preprocessor.scaler.transform(window_arr).astype(np.float32)
            x_scaled = np.expand_dims(scaled_seq, axis=0)
        elif window_arr.ndim == 3 and window_arr.shape[2] == self.pipeline.model.input_size:
            # Already scaled or unscaled (1, W, F)
            x_scaled = window_arr.astype(np.float32)
        else:
            # Fallback to transform_sequence_window
            x_scaled = self.pipeline.preprocessor.transform_sequence_window(window_arr)

        # 2. PyTorch Model Forward Pass
        tensor_x = torch.from_numpy(x_scaled).to(self.device)
        with torch.no_grad():
            probs_tensor = self.pipeline.model.predict_proba(tensor_x)
            raw_probs = probs_tensor[0].cpu().numpy()

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

    def predict_batch(
        self,
        windows: Union[List[np.ndarray], np.ndarray],
    ) -> List[Dict[str, Any]]:
        """Batched inference for evaluating or processing multiple windows efficiently."""
        return [self.predict_sequence(w) for w in windows]

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
