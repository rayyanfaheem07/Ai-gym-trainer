import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC

from ai.classifier.dataset import DatasetSplits

logger = logging.getLogger("ClassifierTrainer")


@dataclass
class TrainingResult:
    model: Any
    model_type: str
    hyperparameters: Dict[str, Any]
    train_score: float
    val_score: Optional[float]
    classes: list[str]
    feature_importances: Optional[Dict[str, float]] = None


class ExerciseModelTrainer:
    """
    Trains and tunes scikit-learn baseline classifiers for sequence-level exercise recognition.
    """

    def __init__(
        self,
        model_type: str = "random_forest",
        n_estimators: int = 100,
        max_depth: Optional[int] = 15,
        random_state: int = 42,
        class_weight: str = "balanced",
    ):
        self.model_type = model_type.lower()
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.random_state = random_state
        self.class_weight = class_weight

    def build_model(self) -> Any:
        """Initializes the chosen classifier with configured hyperparameters."""
        if self.model_type == "random_forest":
            return RandomForestClassifier(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                class_weight=self.class_weight,
                random_state=self.random_state,
                n_jobs=-1,
            )
        elif self.model_type == "gradient_boosting":
            return HistGradientBoostingClassifier(
                max_iter=self.n_estimators,
                max_depth=self.max_depth,
                random_state=self.random_state,
            )
        elif self.model_type == "logistic_regression":
            return LogisticRegression(
                max_iter=1000,
                class_weight=self.class_weight,
                random_state=self.random_state,
            )
        elif self.model_type == "svm":
            return SVC(
                class_weight=self.class_weight,
                random_state=self.random_state,
            )
        else:
            raise ValueError(f"Unsupported model_type: '{self.model_type}'. Choose from: 'random_forest', 'gradient_boosting', 'logistic_regression', 'svm'.")

    def train(self, splits: DatasetSplits) -> TrainingResult:
        """
        Fits the baseline classifier on X_train and evaluates on X_val.
        """
        if len(splits.X_train) == 0:
            raise ValueError("Training dataset splits contain 0 training samples.")

        model = self.build_model()
        logger.info(f"Training {self.model_type} on {len(splits.X_train)} samples across {len(splits.classes)} classes...")
        model.fit(splits.X_train, splits.y_train)

        train_score = float(model.score(splits.X_train, splits.y_train))
        val_score = float(model.score(splits.X_val, splits.y_val)) if len(splits.X_val) > 0 else None

        logger.info(f"Training complete. Train Accuracy: {train_score:.4f}, Val Accuracy: {val_score if val_score is not None else 'N/A'}")

        # Extract feature importances if available
        feature_importances = None
        if hasattr(model, "feature_importances_") and splits.feature_names:
            importances = model.feature_importances_
            feature_importances = {
                name: float(imp)
                for name, imp in sorted(zip(splits.feature_names, importances), key=lambda x: x[1], reverse=True)
            }

        params = {
            "model_type": self.model_type,
            "n_estimators": self.n_estimators,
            "max_depth": self.max_depth,
            "class_weight": self.class_weight,
            "random_state": self.random_state,
        }

        return TrainingResult(
            model=model,
            model_type=self.model_type,
            hyperparameters=params,
            train_score=train_score,
            val_score=val_score,
            classes=splits.classes,
            feature_importances=feature_importances,
        )
