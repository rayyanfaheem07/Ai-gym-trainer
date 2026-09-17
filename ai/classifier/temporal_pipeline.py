import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import torch

from ai.classifier.preprocessor import DataPreprocessor
from ai.classifier.temporal_model import PoseSequenceClassifier

logger = logging.getLogger("TemporalPipeline")


@dataclass
class TemporalClassificationPipeline:
    """
    Unified serializable pipeline bundling the trained PyTorch temporal model,
    data preprocessor (scaler & label encoder), and class metadata.
    """
    model: PoseSequenceClassifier
    preprocessor: DataPreprocessor
    classes: List[str]
    model_config: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None

    def save(self, filepath: str | Path):
        """Serializes the PyTorch model, preprocessor state, and metadata to a single file."""
        target_path = Path(filepath)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        bundle = {
            "state_dict": self.model.state_dict(),
            "model_config": self.model_config,
            "classes": self.classes,
            "preprocessor_state": {
                "window_size": self.preprocessor.window_size,
                "stride": self.preprocessor.stride,
                "min_detected_ratio": self.preprocessor.min_detected_ratio,
                "scaler": self.preprocessor.scaler,
                "label_encoder": self.preprocessor.label_encoder,
                "feature_extractor": self.preprocessor.feature_extractor,
                "is_fitted": self.preprocessor.is_fitted,
            },
            "metadata": self.metadata or {},
        }

        torch.save(bundle, target_path)
        logger.info(f"Temporal classification pipeline saved to {target_path}")

    @classmethod
    def load(
        cls,
        filepath: str | Path,
        device: str = "cpu",
    ) -> "TemporalClassificationPipeline":
        """Loads a serialized PyTorch temporal pipeline from disk."""
        target_path = Path(filepath)
        if not target_path.exists():
            raise FileNotFoundError(f"Temporal model pipeline file not found at: {target_path}")

        target_device = torch.device(device)
        bundle = torch.load(target_path, map_location=target_device, weights_only=False)

        # 1. Rebuild model architecture
        model_config = bundle["model_config"]
        model = PoseSequenceClassifier.from_config(model_config)
        model.load_state_dict(bundle["state_dict"])
        model.to(target_device)
        model.eval()

        # 2. Rebuild preprocessor
        prep_state = bundle["preprocessor_state"]
        preprocessor = DataPreprocessor(
            window_size=prep_state["window_size"],
            stride=prep_state["stride"],
            min_detected_ratio=prep_state["min_detected_ratio"],
            feature_extractor=prep_state["feature_extractor"],
        )
        preprocessor.scaler = prep_state["scaler"]
        preprocessor.label_encoder = prep_state["label_encoder"]
        preprocessor.is_fitted = prep_state["is_fitted"]

        classes = bundle["classes"]
        metadata = bundle.get("metadata", {})

        return cls(
            model=model,
            preprocessor=preprocessor,
            classes=classes,
            model_config=model_config,
            metadata=metadata,
        )
