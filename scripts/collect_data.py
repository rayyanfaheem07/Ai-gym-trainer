import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai.classifier.collector import SUPPORTED_EXERCISES, PoseDataCollector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("CollectDataCLI")


def main():
    parser = argparse.ArgumentParser(
        description="Capture labeled pose sequences from webcam or video for exercise classification."
    )
    parser.add_argument(
        "--label",
        type=str,
        required=True,
        choices=SUPPORTED_EXERCISES + ["pushup"],
        help="Exercise category to record (squat, push_up, bicep_curl, lunge, shoulder_press, other).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/raw",
        help="Output directory to save raw JSON session recordings (default: data/raw).",
    )
    parser.add_argument(
        "--subject-id",
        type=str,
        default="subject_01",
        help="Unique identifier for the participant/user to ensure group-isolated splitting (default: subject_01).",
    )
    parser.add_argument(
        "--num-sequences",
        type=int,
        default=5,
        help="Number of consecutive repetitions/sequences to record in this session (default: 5).",
    )
    parser.add_argument(
        "--window-length",
        type=int,
        default=30,
        help="Number of frames per sequence window (default: 30).",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=30.0,
        help="Target frame rate for recording (default: 30.0).",
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=0,
        help="Webcam camera index (default: 0).",
    )
    parser.add_argument(
        "--video-source",
        type=str,
        default=None,
        help="Optional path to an existing video file instead of live webcam.",
    )
    parser.add_argument(
        "--countdown",
        type=int,
        default=3,
        help="Countdown seconds before recording starts (default: 3).",
    )
    parser.add_argument(
        "--rest",
        type=int,
        default=2,
        help="Rest interval seconds between sequences (default: 2).",
    )

    args = parser.parse_args()

    collector = PoseDataCollector(
        label=args.label,
        output_dir=args.output_dir,
        subject_id=args.subject_id,
        window_length=args.window_length,
        fps=args.fps,
        camera_index=args.camera,
        video_source=args.video_source,
    )

    try:
        saved_file = collector.collect_interactive(
            num_sequences=args.num_sequences,
            countdown_sec=args.countdown,
            rest_sec=args.rest,
        )
        logger.info(f"Data collection completed successfully: {saved_file}")
    except Exception as e:
        logger.error(f"Data collection failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
