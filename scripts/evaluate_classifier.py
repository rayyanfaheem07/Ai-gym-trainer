import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai.classifier.dataset import DatasetSplits
from ai.classifier.evaluator import ModelEvaluator
from ai.classifier.pipeline import ExerciseClassificationPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("EvaluateClassifierCLI")


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate a trained exercise classifier pipeline on test session data."
    )
    parser.add_argument(
        "--model-path",
        type=str,
        default="models/exercise_classifier.joblib",
        help="Path to serialized pipeline artifact (default: models/exercise_classifier.joblib).",
    )
    parser.add_argument(
        "--test-data-dir",
        type=str,
        default="data/raw",
        help="Directory containing test session JSON files (default: data/raw).",
    )
    parser.add_argument(
        "--report-json",
        type=str,
        default="reports/evaluation_report.json",
        help="Path to save evaluation report JSON (default: reports/evaluation_report.json).",
    )
    parser.add_argument(
        "--report-md",
        type=str,
        default="reports/evaluation_report.md",
        help="Path to save evaluation summary markdown (default: reports/evaluation_report.md).",
    )

    args = parser.parse_args()

    model_path = Path(args.model_path)
    if not model_path.exists():
        # Fallback to weights directory if default not found
        alt_path = Path(__file__).resolve().parent.parent / "ai" / "classifier" / "weights" / "exercise_classifier.joblib"
        if alt_path.exists():
            model_path = alt_path
        else:
            logger.error(f"Model file not found at {args.model_path} or {alt_path}. Run scripts/train_classifier.py first.")
            sys.exit(1)

    pipeline = ExerciseClassificationPipeline.load(model_path)
    logger.info(f"Loaded pipeline: Model={pipeline.metadata.model_type if pipeline.metadata else 'Unknown'}, Classes={pipeline.classes}")

    test_dir = Path(args.test_data_dir)
    json_files = list(test_dir.glob("*.json")) if test_dir.exists() else []
    if not json_files:
        logger.error(f"No test session files found in {test_dir}.")
        sys.exit(1)

    preprocessor = pipeline.preprocessor
    sessions = preprocessor.load_raw_sessions(json_files)
    dataset = preprocessor.process_sessions(sessions)
    processed_dataset = preprocessor.transform_dataset(dataset)

    # Wrap as test splits object
    splits = DatasetSplits(
        X_train=processed_dataset.X[:0],
        y_train=processed_dataset.y[:0],
        groups_train=[],
        X_val=processed_dataset.X[:0],
        y_val=processed_dataset.y[:0],
        groups_val=[],
        X_test=processed_dataset.X,
        y_test=processed_dataset.y,
        groups_test=processed_dataset.groups,
        classes=pipeline.classes,
        feature_names=processed_dataset.feature_names,
    )

    metrics = ModelEvaluator.evaluate(pipeline.model, splits)
    ModelEvaluator.save_report(metrics, output_json_path=args.report_json, output_md_path=args.report_md)

    print("\n" + ModelEvaluator.generate_markdown_report(metrics) + "\n")


if __name__ == "__main__":
    main()
