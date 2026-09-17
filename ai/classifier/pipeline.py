import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

import joblib

from ai.classifier.preprocessor import DataPreprocessor

logger = logging.getLogger("ClassificationPipeline")


@dataclass
class PipelineMetadata:
    created_at_utc: str
    model_type: str
    version: str
    classes: List[str]
    window_size: int
    num_features: int
    train_samples: int
    train_accuracy: float
    val_accuracy: Optional[float]


class ExerciseClassificationPipeline:
    """
    Unified end-to-end container combining the trained ML model, fitted preprocessor
    (feature extractor + scaler + label encoder), and training metadata.
    Guarantees that inference executes the exact same feature engineering and normalization as training.
    """

    def __init__(
        self,
        model: Any,
        preprocessor: DataPreprocessor,
        metadata: Optional[PipelineMetadata] = None,
    ):
        self.model = model
        self.preprocessor = preprocessor
        self.metadata = metadata

    @property
    def classes(self) -> List[str]:
        if hasattr(self.preprocessor.label_encoder, "classes_"):
            return list(self.preprocessor.label_encoder.classes_)
        if self.metadata:
            return self.metadata.classes
        return []

    def save(self, filepath: str | Path = "models/exercise_classifier.joblib"):
        """Serializes the entire classification pipeline to a single joblib artifact."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "model": self.model,
            "preprocessor": self.preprocessor,
            "metadata": self.metadata,
        }
        joblib.dump(payload, path)
        logger.info(f"Classification pipeline successfully serialized to {path}")

    @classmethod
    def load(cls, filepath: str | Path = "models/exercise_classifier.joblib") -> "ExerciseClassificationPipeline":
        """Loads serialized pipeline artifact from disk."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Model artifact not found at {path}")

        payload = joblib.load(path)
        return cls(
            model=payload["model"],
            preprocessor=payload["preprocessor"],
            metadata=payload.get("metadata"),
        )
