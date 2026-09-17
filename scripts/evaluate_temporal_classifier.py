import argparse
import logging
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np

from ai.classifier.dataset import GroupAwareDatasetSplitter
from ai.classifier.evaluator import ModelEvaluator
from ai.classifier.pipeline import ExerciseClassificationPipeline
from ai.classifier.preprocessor import DataPreprocessor
from ai.classifier.temporal_evaluator import TemporalModelEvaluator
from ai.classifier.temporal_pipeline import TemporalClassificationPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("EvaluateTemporalClassifier")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Evaluate PyTorch Temporal Exercise Classifier and compare with Phase 6 baseline."
    )
    parser.add_argument(
        "--temporal-model",
        type=str,
        default="models/temporal_exercise_classifier.pt",
        help="Path to trained PyTorch temporal model (.pt).",
    )
    parser.add_argument(
        "--baseline-model",
        type=str,
        default="models/exercise_classifier.joblib",
        help="Path to Phase 6 scikit-learn baseline model (.joblib).",
    )
    parser.add_argument(
        "--raw-dir",
        type=str,
        default="data/raw",
        help="Directory containing raw JSON session test files.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="reports",
        help="Directory to save evaluation and comparison reports.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Seed for split consistency.")
    return parser.parse_args()


def measure_latency_sklearn(pipeline: ExerciseClassificationPipeline, sample_window: np.ndarray, n_iter: int = 200) -> float:
    """Measures single-window inference latency in milliseconds for scikit-learn pipeline."""
    # Warmup
    for _ in range(20):
        _ = pipeline.preprocessor.transform_window(sample_window)
        _ = pipeline.model.predict_proba(np.zeros((1, len(pipeline.preprocessor.feature_extractor.get_feature_names()))))

    latencies = []
    x_scaled = pipeline.preprocessor.transform_window(sample_window)
    for _ in range(n_iter):
        t0 = time.perf_counter()
        _ = pipeline.model.predict_proba(x_scaled)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)
    return float(np.mean(latencies))


def measure_latency_torch(pipeline: TemporalClassificationPipeline, sample_window: np.ndarray, n_iter: int = 200) -> float:
    """Measures single-window inference latency in milliseconds for PyTorch temporal model on CPU."""
    import torch
    pipeline.model.to("cpu")
    pipeline.model.eval()

    # Warmup
    x_scaled = pipeline.preprocessor.transform_sequence_window(sample_window)
    tensor_x = torch.from_numpy(x_scaled).to("cpu")
    with torch.no_grad():
        for _ in range(20):
            _ = pipeline.model.predict_proba(tensor_x)

    latencies = []
    with torch.no_grad():
        for _ in range(n_iter):
            t0 = time.perf_counter()
            _ = pipeline.model.predict_proba(tensor_x)
            t1 = time.perf_counter()
            latencies.append((t1 - t0) * 1000.0)
    return float(np.mean(latencies))


def main():
    args = parse_args()
    logger.info("=== Phase 7: PyTorch Temporal Model Evaluation & Comparison ===")

    temporal_path = Path(args.temporal_model)
    if not temporal_path.exists():
        logger.error(f"Temporal model not found at {temporal_path}. Run training first.")
        sys.exit(1)

    temporal_pipeline = TemporalClassificationPipeline.load(temporal_path, device="cpu")
    logger.info(f"Loaded temporal pipeline from {temporal_path}")

    # Load and process raw dataset
    raw_dir = Path(args.raw_dir)
    preprocessor = temporal_pipeline.preprocessor
    sessions = preprocessor.load_raw_sessions(raw_dir)
    if not sessions:
        logger.error(f"No sessions found in {raw_dir}.")
        sys.exit(1)

    # 1. Temporal Dataset Processing & Test Split
    temporal_raw_ds = preprocessor.process_sessions_temporal(sessions)
    splitter = GroupAwareDatasetSplitter(test_size=0.2, val_size=0.15, random_state=args.seed)
    temporal_splits = splitter.split(temporal_raw_ds)

    # Transform test features
    feat_dim = temporal_raw_ds.feature_dim
    temporal_splits.X_test = preprocessor.scaler.transform(
        temporal_splits.X_test.reshape(-1, feat_dim)
    ).reshape(temporal_splits.X_test.shape).astype(np.float32)

    # Evaluate Temporal PyTorch Model
    temporal_metrics = TemporalModelEvaluator.evaluate(
        model=temporal_pipeline.model,
        splits=temporal_splits,
        device="cpu",
    )

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    eval_json_path = out_dir / "temporal_evaluation_report.json"
    eval_md_path = out_dir / "temporal_evaluation_report.md"
    ModelEvaluator.save_report(
        temporal_metrics,
        output_json_path=eval_json_path,
        output_md_path=eval_md_path,
    )

    print("\n" + "=" * 60)
    print("  PHASE 7 TEMPORAL MODEL EVALUATION (HELD-OUT TEST SET)")
    print("=" * 60)
    print(f"  Test Samples:      {temporal_metrics.num_test_samples}")
    print(f"  Test Accuracy:     {temporal_metrics.accuracy * 100:.2f}%")
    print(f"  Macro F1 Score:    {temporal_metrics.f1_macro:.4f}")
    print(f"  Macro Precision:   {temporal_metrics.precision_macro:.4f}")
    print(f"  Macro Recall:      {temporal_metrics.recall_macro:.4f}")
    print("=" * 60 + "\n")

    # Sample window for latency measurement
    sample_window = np.zeros((30, 33, 4), dtype=np.float32)
    sample_window[:, :, 0] = 0.5
    sample_window[:, :, 1] = 0.5
    sample_window[:, :, 3] = 1.0

    temporal_size_kb = os.path.getsize(temporal_path) / 1024.0
    temporal_latency_ms = measure_latency_torch(temporal_pipeline, sample_window)

    # Check if Phase 6 Baseline exists for fair comparison
    baseline_path = Path(args.baseline_model)
    if baseline_path.exists():
        logger.info(f"Found Phase 6 baseline at {baseline_path}. Computing comparison...")
        baseline_pipeline = ExerciseClassificationPipeline.load(baseline_path)

        # Process 2D baseline features
        baseline_raw_ds = baseline_pipeline.preprocessor.process_sessions(sessions)
        baseline_splits = splitter.split(baseline_raw_ds)
        baseline_splits.X_test = baseline_pipeline.preprocessor.scaler.transform(baseline_splits.X_test).astype(np.float32)

        baseline_metrics = ModelEvaluator.evaluate(
            model=baseline_pipeline.model,
            splits=baseline_splits,
        )

        baseline_size_kb = os.path.getsize(baseline_path) / 1024.0
        baseline_latency_ms = measure_latency_sklearn(baseline_pipeline, sample_window)

        comparison = TemporalModelEvaluator.compare_models(
            phase6_metrics=baseline_metrics,
            phase7_metrics=temporal_metrics,
            phase6_latency_ms=baseline_latency_ms,
            phase7_latency_ms=temporal_latency_ms,
            phase6_size_kb=baseline_size_kb,
            phase7_size_kb=temporal_size_kb,
        )

        comp_json = out_dir / "phase6_vs_phase7_comparison.json"
        comp_md = out_dir / "phase6_vs_phase7_comparison.md"
        TemporalModelEvaluator.save_comparison_report(comparison, comp_json, comp_md)

        print("\n" + comparison.comparison_summary + "\n")
    else:
        logger.info(f"No Phase 6 baseline found at {baseline_path}. Comparison skipped.")


if __name__ == "__main__":
    main()
