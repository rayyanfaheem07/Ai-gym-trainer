import argparse
import json
import logging
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import torch

from ai.classifier.pipeline import ExerciseClassificationPipeline
from ai.classifier.temporal_pipeline import TemporalClassificationPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("BenchmarkClassifier")


def parse_args():
    parser = argparse.ArgumentParser(description="Benchmark CPU inference latency of Phase 6 vs Phase 7 classifiers.")
    parser.add_argument("--temporal-model", type=str, default="models/temporal_exercise_classifier.pt")
    parser.add_argument("--baseline-model", type=str, default="models/exercise_classifier.joblib")
    parser.add_argument("--num-iterations", type=int, default=500, help="Number of benchmark iterations.")
    parser.add_argument("--warmup", type=int, default=50, help="Number of warmup iterations.")
    parser.add_argument("--output-json", type=str, default="reports/latency_benchmark.json")
    return parser.parse_args()


def benchmark_sklearn(pipeline: ExerciseClassificationPipeline, sample_window: np.ndarray, n_iter: int, warmup: int):
    # Warmup
    for _ in range(warmup):
        feat = pipeline.preprocessor.transform_window(sample_window)
        _ = pipeline.model.predict_proba(feat)

    times = []
    for _ in range(n_iter):
        t0 = time.perf_counter()
        feat = pipeline.preprocessor.transform_window(sample_window)
        _ = pipeline.model.predict_proba(feat)
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000.0)

    times = np.array(times)
    return {
        "mean_ms": float(np.mean(times)),
        "median_ms": float(np.median(times)),
        "min_ms": float(np.min(times)),
        "max_ms": float(np.max(times)),
        "p90_ms": float(np.percentile(times, 90)),
        "p95_ms": float(np.percentile(times, 95)),
        "p99_ms": float(np.percentile(times, 99)),
        "std_ms": float(np.std(times)),
        "throughput_fps": float(1000.0 / np.mean(times)),
    }


def benchmark_torch(pipeline: TemporalClassificationPipeline, sample_window: np.ndarray, n_iter: int, warmup: int):
    pipeline.model.to("cpu")
    pipeline.model.eval()

    # Warmup
    for _ in range(warmup):
        seq = pipeline.preprocessor.transform_sequence_window(sample_window)
        t_seq = torch.from_numpy(seq).to("cpu")
        with torch.no_grad():
            _ = pipeline.model.predict_proba(t_seq)

    times = []
    with torch.no_grad():
        for _ in range(n_iter):
            t0 = time.perf_counter()
            seq = pipeline.preprocessor.transform_sequence_window(sample_window)
            t_seq = torch.from_numpy(seq).to("cpu")
            _ = pipeline.model.predict_proba(t_seq)
            t1 = time.perf_counter()
            times.append((t1 - t0) * 1000.0)

    times = np.array(times)
    return {
        "mean_ms": float(np.mean(times)),
        "median_ms": float(np.median(times)),
        "min_ms": float(np.min(times)),
        "max_ms": float(np.max(times)),
        "p90_ms": float(np.percentile(times, 90)),
        "p95_ms": float(np.percentile(times, 95)),
        "p99_ms": float(np.percentile(times, 99)),
        "std_ms": float(np.std(times)),
        "throughput_fps": float(1000.0 / np.mean(times)),
    }


def main():
    args = parse_args()
    logger.info(f"=== Running Latency Benchmark ({args.num_iterations} iterations, {args.warmup} warmup) ===")

    # Dummy realistic pose window: (30 frames, 33 landmarks, 4 coords)
    sample_window = np.zeros((30, 33, 4), dtype=np.float32)
    sample_window[:, :, 0] = 0.5
    sample_window[:, :, 1] = 0.5
    sample_window[:, :, 3] = 1.0

    results = {}

    # 1. Benchmark PyTorch Temporal Model
    t_path = Path(args.temporal_model)
    if t_path.exists():
        logger.info(f"Benchmarking PyTorch Temporal Model: {t_path}...")
        t_pipeline = TemporalClassificationPipeline.load(t_path, device="cpu")
        t_bench = benchmark_torch(t_pipeline, sample_window, args.num_iterations, args.warmup)
        results["phase7_pytorch_temporal"] = t_bench
        logger.info(f"PyTorch Temporal: Mean = {t_bench['mean_ms']:.2f} ms ({t_bench['throughput_fps']:.1f} FPS)")
    else:
        logger.warning(f"Temporal model not found at {t_path}.")

    # 2. Benchmark scikit-learn Baseline
    b_path = Path(args.baseline_model)
    if b_path.exists():
        logger.info(f"Benchmarking scikit-learn Baseline: {b_path}...")
        b_pipeline = ExerciseClassificationPipeline.load(b_path)
        b_bench = benchmark_sklearn(b_pipeline, sample_window, args.num_iterations, args.warmup)
        results["phase6_sklearn_baseline"] = b_bench
        logger.info(f"scikit-learn Baseline: Mean = {b_bench['mean_ms']:.2f} ms ({b_bench['throughput_fps']:.1f} FPS)")
    else:
        logger.warning(f"Baseline model not found at {b_path}.")

    out_path = Path(args.output_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    logger.info(f"Saved benchmark results to {out_path}")

    # Print summary table
    print("\n" + "=" * 75)
    print("           END-TO-END CPU INFERENCE LATENCY BENCHMARK")
    print("=" * 75)
    print(f"{'Model':<30} | {'Mean':<8} | {'Median':<8} | {'P95':<8} | {'P99':<8} | {'FPS':<8}")
    print("-" * 75)
    for model_name, stats in results.items():
        print(
            f"{model_name:<30} | {stats['mean_ms']:>6.2f}ms | {stats['median_ms']:>6.2f}ms | "
            f"{stats['p95_ms']:>6.2f}ms | {stats['p99_ms']:>6.2f}ms | {stats['throughput_fps']:>7.1f}"
        )
    print("=" * 75 + "\n")


if __name__ == "__main__":
    main()
