import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

from ai.classifier.dataset import DatasetSplits

logger = logging.getLogger("ClassifierEvaluator")


@dataclass
class EvaluationMetrics:
    accuracy: float
    precision_macro: float
    precision_weighted: float
    recall_macro: float
    recall_weighted: float
    f1_macro: float
    f1_weighted: float
    confusion_matrix: List[List[int]]
    classes: List[str]
    per_class_metrics: Dict[str, Dict[str, float]]
    num_test_samples: int
    classification_report_str: str


class ModelEvaluator:
    """
    Evaluates trained exercise classifiers on strictly held-out test splits.
    Computes empirical multi-class performance metrics without hard-coding or fabrication.
    """

    @staticmethod
    def evaluate(model: Any, splits: DatasetSplits) -> EvaluationMetrics:
        """
        Runs model predictions against the test split and calculates all classification metrics.
        """
        X_test = splits.X_test
        y_test = splits.y_test
        classes = splits.classes

        if len(X_test) == 0:
            raise ValueError("Cannot evaluate model on empty test dataset.")

        y_pred = model.predict(X_test)

        acc = float(accuracy_score(y_test, y_pred))
        prec_macro = float(precision_score(y_test, y_pred, average="macro", zero_division=0))
        prec_weighted = float(precision_score(y_test, y_pred, average="weighted", zero_division=0))
        rec_macro = float(recall_score(y_test, y_pred, average="macro", zero_division=0))
        rec_weighted = float(recall_score(y_test, y_pred, average="weighted", zero_division=0))
        f1_mac = float(f1_score(y_test, y_pred, average="macro", zero_division=0))
        f1_wt = float(f1_score(y_test, y_pred, average="weighted", zero_division=0))

        cm = confusion_matrix(y_test, y_pred, labels=list(range(len(classes)))).tolist()

        # Detailed per-class metrics
        prec_per_class = precision_score(y_test, y_pred, average=None, labels=list(range(len(classes))), zero_division=0)
        rec_per_class = recall_score(y_test, y_pred, average=None, labels=list(range(len(classes))), zero_division=0)
        f1_per_class = f1_score(y_test, y_pred, average=None, labels=list(range(len(classes))), zero_division=0)

        per_class: Dict[str, Dict[str, float]] = {}
        for idx, cls_name in enumerate(classes):
            per_class[cls_name] = {
                "precision": float(prec_per_class[idx]),
                "recall": float(rec_per_class[idx]),
                "f1_score": float(f1_per_class[idx]),
                "support": int(np.sum(y_test == idx)),
            }

        report_str = classification_report(
            y_test,
            y_pred,
            labels=list(range(len(classes))),
            target_names=classes,
            zero_division=0,
        )

        return EvaluationMetrics(
            accuracy=acc,
            precision_macro=prec_macro,
            precision_weighted=prec_weighted,
            recall_macro=rec_macro,
            recall_weighted=rec_weighted,
            f1_macro=f1_mac,
            f1_weighted=f1_wt,
            confusion_matrix=cm,
            classes=classes,
            per_class_metrics=per_class,
            num_test_samples=len(y_test),
            classification_report_str=report_str,
        )

    @classmethod
    def save_report(
        cls,
        metrics: EvaluationMetrics,
        output_json_path: str | Path = "reports/evaluation_report.json",
        output_md_path: Optional[str | Path] = "reports/evaluation_report.md",
    ):
        """Saves evaluation results to JSON and Markdown format."""
        json_path = Path(output_json_path)
        json_path.parent.mkdir(parents=True, exist_ok=True)

        data = asdict(metrics)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved evaluation JSON report to {json_path}")

        if output_md_path:
            md_path = Path(output_md_path)
            md_path.parent.mkdir(parents=True, exist_ok=True)
            md_content = cls.generate_markdown_report(metrics)
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            logger.info(f"Saved evaluation Markdown report to {md_path}")

    @staticmethod
    def generate_markdown_report(metrics: EvaluationMetrics) -> str:
        """Generates a GitHub-flavored Markdown evaluation summary table."""
        lines = [
            "# Exercise Classifier - Model Evaluation Report",
            "",
            "## Summary Metrics",
            f"- **Test Samples**: {metrics.num_test_samples}",
            f"- **Accuracy**: {metrics.accuracy * 100:.2f}%",
            f"- **Macro F1 Score**: {metrics.f1_macro:.4f}",
            f"- **Weighted F1 Score**: {metrics.f1_weighted:.4f}",
            f"- **Macro Precision**: {metrics.precision_macro:.4f}",
            f"- **Macro Recall**: {metrics.recall_macro:.4f}",
            "",
            "## Per-Class Performance",
            "| Class | Precision | Recall | F1 Score | Support |",
            "|---|---|---|---|---|",
        ]

        for cls_name, pcm in metrics.per_class_metrics.items():
            lines.append(
                f"| `{cls_name}` | {pcm['precision']:.4f} | {pcm['recall']:.4f} | {pcm['f1_score']:.4f} | {pcm['support']} |"
            )

        lines.extend([
            "",
            "## Confusion Matrix",
            f"Classes: `{'`, `'.join(metrics.classes)}`",
            "",
            "```",
            np.array2string(np.array(metrics.confusion_matrix)),
            "```",
            "",
            "## Full Scikit-Learn Classification Report",
            "```",
            metrics.classification_report_str,
            "```",
        ])
        return "\n".join(lines)
