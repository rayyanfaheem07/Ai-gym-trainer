import argparse
import json
import logging
import sys
import time
from pathlib import Path

import cv2

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai.classifier.inference import ExerciseInferenceEngine, StreamingExerciseClassifier
from ai.classifier.pipeline import ExerciseClassificationPipeline
from ai.classifier.synthetic import BiomechanicalDataGenerator
from ai.pose.detector import PoseDetector
from ai.pose.visualizer import PoseVisualizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("RunInferenceCLI")


def run_synthetic_demo(engine: ExerciseInferenceEngine):
    """Demonstrates inference on synthetic sequences for each canonical exercise."""
    exercises = ["squat", "push_up", "bicep_curl", "lunge", "shoulder_press", "other"]
    print("\n================ ML EXERCISE CLASSIFIER INFERENCE DEMO ================\n")

    for ex in exercises:
        traj = BiomechanicalDataGenerator.generate_exercise_trajectory(ex, num_frames=30)
        result = engine.predict_sequence(traj)
        print(f"--- Input Trajectory: '{ex.upper()}' ---")
        print(json.dumps(result, indent=2))
        print()


def run_live_inference(
    engine: ExerciseInferenceEngine,
    camera_index: int = 0,
    video_source: str = None,
    window_size: int = 30,
):
    """Runs live webcam/video inference with visual HUD overlay."""
    source = video_source if video_source is not None else camera_index
    cap = cv2.VideoCapture(source)

    if not cap.isOpened() and isinstance(source, int):
        cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)

    if not cap.isOpened():
        logger.error(f"Cannot open camera/video source: {source}")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)

    detector = PoseDetector(enable_filter=True)
    visualizer = PoseVisualizer()
    streaming_clf = StreamingExerciseClassifier(inference_engine=engine, window_size=window_size)

    logger.info("Starting live inference. Press 'q' or ESC to exit.")
    start_time = time.time()
    prev_time = time.time()
    fps = 0.0

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            current_time = time.time()
            elapsed = current_time - prev_time
            prev_time = current_time
            if elapsed > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / elapsed)

            ts_ms = int((current_time - start_time) * 1000.0)
            pose_res = detector.detect(frame, timestamp_ms=ts_ms)

            # Process frame through streaming classifier
            clf_res = streaming_clf.process_frame(pose_res.landmarks if pose_res.has_detection else None)

            # Draw visual overlay
            display = frame.copy()
            if pose_res.has_detection and pose_res.landmarks is not None:
                display = visualizer.draw_skeleton(display, pose_res.landmarks)

            display = visualizer.draw_hud(display, fps=fps, has_detection=pose_res.has_detection)

            # Draw Classification HUD Card
            h, w = display.shape[:2]
            cv2.rectangle(display, (10, h - 160), (320, h - 10), (20, 20, 20), -1)
            cv2.rectangle(display, (10, h - 160), (320, h - 10), (0, 255, 255), 1)

            ex_label = clf_res.get("exercise", "other").upper().replace("_", " ")
            confidence = clf_res.get("confidence", 0.0)

            # Header
            cv2.putText(display, f"EXERCISE: {ex_label}", (20, h - 130), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
            cv2.putText(display, f"CONFIDENCE: {confidence * 100:.1f}%", (20, h - 105), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

            # Mini probability breakdown
            probs = clf_res.get("probabilities", {})
            y_offset = h - 85
            for k, v in sorted(probs.items(), key=lambda x: x[1], reverse=True)[:3]:
                k_short = k.replace("_", " ")[:12]
                cv2.putText(display, f"{k_short}: {v*100:.0f}%", (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
                y_offset += 18

            cv2.imshow("AI Gym Trainer - Exercise Classification", display)
            if (cv2.waitKey(1) & 0xFF) in [27, ord("q")]:
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()
        detector.close()


def main():
    parser = argparse.ArgumentParser(description="Run exercise classification inference on live webcam or synthetic data.")
    parser.add_argument(
        "--model-path",
        type=str,
        default="models/exercise_classifier.joblib",
        help="Path to serialized pipeline (default: models/exercise_classifier.joblib).",
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=0,
        help="Webcam device index (default: 0).",
    )
    parser.add_argument(
        "--video-source",
        type=str,
        default=None,
        help="Optional path to video file.",
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.60,
        help="Confidence cutoff below which 'other' is returned (default: 0.60).",
    )
    parser.add_argument(
        "--synthetic-demo",
        action="store_true",
        help="Run inference on synthetic movement trajectories and display JSON outputs.",
    )

    args = parser.parse_args()

    model_path = Path(args.model_path)
    pipeline = None
    if model_path.exists():
        pipeline = ExerciseClassificationPipeline.load(model_path)
    else:
        alt_path = Path(__file__).resolve().parent.parent / "ai" / "classifier" / "weights" / "exercise_classifier.joblib"
        if alt_path.exists():
            pipeline = ExerciseClassificationPipeline.load(alt_path)

    engine = ExerciseInferenceEngine(
        pipeline=pipeline,
        confidence_threshold=args.confidence_threshold,
    )

    if args.synthetic_demo or not sys.stdin.isatty():
        run_synthetic_demo(engine)
    else:
        run_live_inference(
            engine=engine,
            camera_index=args.camera,
            video_source=args.video_source,
        )


if __name__ == "__main__":
    main()
