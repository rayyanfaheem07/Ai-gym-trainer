import argparse
import logging
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai.classifier.dataset import GroupAwareDatasetSplitter
from ai.classifier.evaluator import ModelEvaluator
from ai.classifier.pipeline import ExerciseClassificationPipeline, PipelineMetadata
from ai.classifier.preprocessor import DataPreprocessor
from ai.classifier.synthetic import BiomechanicalDataGenerator
from ai.classifier.trainer import ExerciseModelTrainer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("TrainClassifierCLI")


def main():
    parser = argparse.ArgumentParser(
        description="Train scikit-learn baseline exercise classifier with leakage-free group partitioning."
    )
    parser.add_argument(
        "--raw-dir",
        type=str,
        default="data/raw",
        help="Directory containing raw JSON session recordings (default: data/raw).",
    )
    parser.add_argument(
        "--output-model",
        type=str,
        default="models/exercise_classifier.joblib",
        help="Destination path for serialized pipeline artifact (default: models/exercise_classifier.joblib).",
    )
    parser.add_argument(
        "--model-type",
        type=str,
        default="random_forest",
        choices=["random_forest", "gradient_boosting", "logistic_regression", "svm"],
        help="Model architecture (default: random_forest).",
    )
    parser.add_argument(
        "--n-estimators",
        type=int,
        default=100,
        help="Number of trees or max iterations (default: 100).",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=15,
        help="Maximum tree depth (default: 15).",
    )
    parser.add_argument(
        "--window-size",
        type=int,
        default=30,
        help="Sequence window length in frames (default: 30).",
    )
    parser.add_argument(
        "--stride",
        type=int,
        default=10,
        help="Window sliding stride (default: 10).",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.20,
        help="Held-out group test split fraction (default: 0.20).",
    )
    parser.add_argument(
        "--val-size",
        type=float,
        default=0.15,
        help="Group validation split fraction (default: 0.15).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42).",
    )
    parser.add_argument(
        "--generate-synthetic",
        action="store_true",
        help="Generate synthetic sessions if raw data directory is empty or requested.",
    )

    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    json_files = list(raw_dir.glob("*.json")) if raw_dir.exists() else []

    if not json_files:
        if args.generate_synthetic:
            logger.info("No raw recordings found. Generating synthetic biomechanical training sessions...")
            BiomechanicalDataGenerator.generate_synthetic_dataset(output_dir=raw_dir)
            json_files = list(raw_dir.glob("*.json"))
        else:
            logger.error(
                f"No data files found in {raw_dir}.\n"
                "Please run scripts/collect_data.py to record movement data,\n"
                "or re-run with --generate-synthetic for testing/verification."
            )
            sys.exit(1)

    # 1. Preprocessing & Feature Extraction
    logger.info(f"Loading and preprocessing {len(json_files)} session files from {raw_dir}...")
    preprocessor = DataPreprocessor(window_size=args.window_size, stride=args.stride)
    sessions = preprocessor.load_raw_sessions(json_files)
    dataset = preprocessor.process_sessions(sessions)
    processed_dataset = preprocessor.fit_transform_dataset(dataset)

    # 2. Group-Aware Splitting (Zero Leakage)
    splitter = GroupAwareDatasetSplitter(
        test_size=args.test_size,
        val_size=args.val_size,
        random_state=args.seed,
    )
    splits = splitter.split(processed_dataset)

    # 3. Model Training
    trainer = ExerciseModelTrainer(
        model_type=args.model_type,
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        random_state=args.seed,
    )
    train_res = trainer.train(splits)

    # 4. Evaluation on Held-Out Test Split
    eval_metrics = ModelEvaluator.evaluate(train_res.model, splits)
    logger.info(
        f"Held-out Test Evaluation:\n"
        f"  Accuracy: {eval_metrics.accuracy * 100:.2f}%\n"
        f"  Macro F1: {eval_metrics.f1_macro:.4f}\n"
        f"  Weighted F1: {eval_metrics.f1_weighted:.4f}"
    )

    # 5. Pipeline Packaging & Serialization
    meta = PipelineMetadata(
        created_at_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        model_type=args.model_type,
        version="1.0.0",
        classes=splits.classes,
        window_size=args.window_size,
        num_features=processed_dataset.X.shape[1],
        train_samples=len(splits.X_train),
        train_accuracy=train_res.train_score,
        val_accuracy=train_res.val_score,
    )
    pipeline = ExerciseClassificationPipeline(
        model=train_res.model,
        preprocessor=preprocessor,
        metadata=meta,
    )
    pipeline.save(args.output_model)

    # Also save to ai/classifier/weights/ for automatic discovery by ExerciseClassifier
    weights_path = Path(__file__).resolve().parent.parent / "ai" / "classifier" / "weights" / "exercise_classifier.joblib"
    pipeline.save(weights_path)

    # Save evaluation report alongside
    ModelEvaluator.save_report(eval_metrics)
    logger.info(f"Pipeline training and evaluation complete! Model saved to {args.output_model} and {weights_path}")


if __name__ == "__main__":
    main()
