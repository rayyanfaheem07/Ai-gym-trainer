import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai.classifier.preprocessor import DataPreprocessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("PreprocessDataCLI")


def main():
    parser = argparse.ArgumentParser(
        description="Load raw session files, validate samples, extract features, window, scale, and save processed dataset."
    )
    parser.add_argument(
        "--raw-dir",
        type=str,
        default="data/raw",
        help="Directory containing raw JSON session files (default: data/raw).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/processed",
        help="Directory to save processed dataset and preprocessor pipeline (default: data/processed).",
    )
    parser.add_argument(
        "--window-size",
        type=int,
        default=30,
        help="Sequence window size in frames (default: 30).",
    )
    parser.add_argument(
        "--stride",
        type=int,
        default=10,
        help="Sliding window step stride in frames (default: 10).",
    )
    parser.add_argument(
        "--min-detected-ratio",
        type=float,
        default=0.7,
        help="Minimum ratio of detected pose frames required per sequence (default: 0.7).",
    )

    args = parser.parse_args()

    preprocessor = DataPreprocessor(
        window_size=args.window_size,
        stride=args.stride,
        min_detected_ratio=args.min_detected_ratio,
    )

    raw_dir = Path(args.raw_dir)
    if not raw_dir.exists() or not list(raw_dir.glob("*.json")):
        logger.error(f"No raw JSON files found in {raw_dir}. Run scripts/collect_data.py first.")
        sys.exit(1)

    sessions = preprocessor.load_raw_sessions(raw_dir)
    dataset = preprocessor.process_sessions(sessions)
    processed_dataset = preprocessor.fit_transform_dataset(dataset)

    out_path = Path(args.output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Save preprocessor artifact
    preprocessor_file = out_path / "preprocessor.joblib"
    preprocessor.save(preprocessor_file)

    logger.info(
        f"Preprocessing successfully complete!\n"
        f"  Total samples: {len(processed_dataset.X)}\n"
        f"  Feature dimension: {processed_dataset.X.shape[1]}\n"
        f"  Classes ({len(processed_dataset.classes)}): {processed_dataset.classes}\n"
        f"  Saved preprocessor to: {preprocessor_file}"
    )


if __name__ == "__main__":
    main()
