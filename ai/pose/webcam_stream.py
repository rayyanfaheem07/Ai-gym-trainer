import argparse
import logging
import time

import cv2

from ai.exercises.squat import SquatAnalysisResult, SquatConfig, SquatDetector
from ai.pose.detector import PoseDetector
from ai.pose.landmarks import PoseDetectionResult
from ai.pose.visualizer import PoseVisualizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("WebcamPoseTracker")


class WebcamPoseTracker:
    """
    Real-time webcam pose detection, squat analysis, and visualization engine.
    """

    def __init__(
        self,
        camera_index: int = 0,
        exercise: str = "squat",
        model_path: str = None,
        enable_filter: bool = True,
        show_angles: bool = True,
        show_skeleton: bool = True,
        mirror_display: bool = True,
        squat_config: SquatConfig = None,
    ):
        self.camera_index = camera_index
        self.exercise = exercise.lower()
        self.enable_filter = enable_filter
        self.show_angles = show_angles
        self.show_skeleton = show_skeleton
        self.mirror_display = mirror_display

        self.detector = PoseDetector(
            model_path=model_path,
            enable_filter=self.enable_filter,
        )
        self.visualizer = PoseVisualizer()
        self.squat_detector = SquatDetector(config=squat_config) if self.exercise == "squat" else None
        self.cap: cv2.VideoCapture = None

    def start_camera(self) -> bool:
        """Attempts to open the webcam device gracefully."""
        logger.info(f"Opening webcam device at index {self.camera_index}...")
        self.cap = cv2.VideoCapture(self.camera_index)

        if not self.cap.isOpened():
            logger.warning(f"Could not open camera {self.camera_index}. Trying DirectShow backend...")
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)

        if not self.cap.isOpened():
            logger.error(
                f"Webcam Failure: Unable to connect to camera index {self.camera_index}. "
                "Please verify that your webcam is connected and not in use by another application."
            )
            return False

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        logger.info("Webcam successfully initialized.")
        return True

    def run(self, max_frames: int = None):
        """
        Runs the real-time processing loop with squat analysis overlays.
        """
        if not self.start_camera():
            return False

        fps = 0.0
        frame_count = 0
        prev_time = time.time()
        start_timestamp_ms = int(time.time() * 1000)

        logger.info(f"Starting live tracking loop for exercise: '{self.exercise.upper()}'. Press 'q' or 'ESC' to exit.")

        try:
            while True:
                success, frame = self.cap.read()
                if not success or frame is None:
                    logger.warning("Frame capture failed or stream ended. Exiting loop.")
                    break

                current_time = time.time()
                elapsed = current_time - prev_time
                prev_time = current_time
                if elapsed > 0:
                    fps = 0.9 * fps + 0.1 * (1.0 / elapsed) if fps > 0 else (1.0 / elapsed)

                timestamp_ms = int(current_time * 1000) - start_timestamp_ms

                # 1. Detect human pose
                result: PoseDetectionResult = self.detector.detect(frame, timestamp_ms=timestamp_ms)

                # 2. Run Squat Analyzer if in squat mode
                squat_result: SquatAnalysisResult = None
                if self.squat_detector and result.has_detection:
                    squat_result = self.squat_detector.analyze_frame(
                        result.landmarks, timestamp_ms=timestamp_ms
                    )

                # 3. Render overlays
                display_frame = frame.copy()
                if self.mirror_display:
                    display_frame = cv2.flip(display_frame, 1)

                if result.has_detection and result.landmarks is not None:
                    vis_landmarks = result.landmarks.copy()
                    if self.mirror_display:
                        vis_landmarks[:, 0] = 1.0 - vis_landmarks[:, 0]

                    if self.show_skeleton:
                        display_frame = self.visualizer.draw_skeleton(display_frame, vis_landmarks)
                    if self.show_angles:
                        display_frame = self.visualizer.draw_joint_angles(
                            display_frame, vis_landmarks, result.angles
                        )

                # 4. Draw Top HUD
                display_frame = self.visualizer.draw_hud(
                    display_frame, fps=fps, has_detection=result.has_detection
                )

                # 5. Draw Squat HUD & Depth Analytics
                if squat_result:
                    display_frame = self.visualizer.draw_squat_analytics(
                        frame=display_frame,
                        phase=squat_result.phase,
                        rep_count=squat_result.rep_count,
                        valid_reps=squat_result.valid_reps,
                        knee_angle=squat_result.current_knee_angle,
                        target_bottom_angle=self.squat_detector.config.bottom_knee_angle,
                        feedback=squat_result.feedback,
                    )

                try:
                    cv2.imshow("AI Gym Trainer - Live Pose & Squat Analysis", display_frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key in [ord("q"), 27]:  # 'q' or ESC
                        logger.info("User requested exit.")
                        break
                    elif key == ord("s"):
                        self.show_skeleton = not self.show_skeleton
                    elif key == ord("a"):
                        self.show_angles = not self.show_angles
                    elif key == ord("r") and self.squat_detector:
                        self.squat_detector.reset()
                        logger.info("Squat rep counter reset.")
                except cv2.error:
                    pass

                frame_count += 1
                if max_frames and frame_count >= max_frames:
                    logger.info(f"Reached max frames limit ({max_frames}).")
                    break

        except KeyboardInterrupt:
            logger.info("Interrupted by user.")
        finally:
            self.cleanup()

        return True

    def cleanup(self):
        """Releases camera and OpenCV resources cleanly."""
        if self.cap:
            self.cap.release()
            self.cap = None
        self.detector.close()
        try:
            cv2.destroyAllWindows()
        except Exception as e:
            logger.debug(f"OpenCV window cleanup ignored: {e}")
        logger.info("Camera and detector resources released.")


def main():
    parser = argparse.ArgumentParser(description="Real-Time Human Pose Detection & Squat Analysis")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    parser.add_argument("--exercise", type=str, default="squat", choices=["squat", "pose_only"], help="Mode (default: squat)")
    parser.add_argument("--bottom-angle", type=float, default=95.0, help="Target bottom depth angle (default: 95.0)")
    parser.add_argument("--no-filter", action="store_true", help="Disable 1-Euro jitter filter")
    parser.add_argument("--no-mirror", action="store_true", help="Disable mirror display mode")
    parser.add_argument("--max-frames", type=int, default=None, help="Stop after N frames")
    args = parser.parse_args()

    squat_cfg = SquatConfig(bottom_knee_angle=args.bottom_angle) if args.exercise == "squat" else None

    tracker = WebcamPoseTracker(
        camera_index=args.camera,
        exercise=args.exercise,
        enable_filter=not args.no_filter,
        mirror_display=not args.no_mirror,
        squat_config=squat_cfg,
    )
    tracker.run(max_frames=args.max_frames)


if __name__ == "__main__":
    main()
