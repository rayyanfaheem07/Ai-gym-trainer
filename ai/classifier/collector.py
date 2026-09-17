import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

from ai.pose.detector import PoseDetector
from ai.pose.landmarks import PoseDetectionResult

logger = logging.getLogger("PoseDataCollector")

SUPPORTED_EXERCISES = [
    "squat",
    "push_up",
    "bicep_curl",
    "lunge",
    "shoulder_press",
    "other",
]


@dataclass
class FrameData:
    timestamp_ms: float
    detected: bool
    landmarks: Optional[List[List[float]]] = None  # (33, 4) [x, y, z, visibility]


@dataclass
class SequenceData:
    sequence_id: str
    label: str
    fps: float
    num_frames: int
    frames: List[FrameData] = field(default_factory=list)


@dataclass
class SessionRecording:
    session_id: str
    subject_id: str
    label: str
    target_fps: float
    window_length: int
    created_at_utc: str
    sequences: List[SequenceData] = field(default_factory=list)


class PoseDataCollector:
    """
    Captures pose landmarks from webcam or video file and stores labeled movement sequences
    in structured, privacy-preserving JSON formats (no raw video or PII).
    """

    def __init__(
        self,
        label: str,
        output_dir: str = "data/raw",
        subject_id: str = "subject_01",
        window_length: int = 30,
        fps: float = 30.0,
        camera_index: int = 0,
        video_source: Optional[str] = None,
        min_visibility: float = 0.5,
    ):
        self.label = self._normalize_label(label)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.subject_id = subject_id
        self.window_length = window_length
        self.fps = fps
        self.camera_index = camera_index
        self.video_source = video_source
        self.min_visibility = min_visibility
        self.detector = PoseDetector(enable_filter=True)

    @staticmethod
    def _normalize_label(label: str) -> str:
        clean = label.strip().lower().replace("-", "_").replace(" ", "_")
        if clean == "pushup":
            return "push_up"
        if clean not in SUPPORTED_EXERCISES:
            logger.warning(f"Label '{label}' is not in standard list {SUPPORTED_EXERCISES}, saving as '{clean}'.")
        return clean

    def collect_interactive(
        self,
        num_sequences: int = 5,
        countdown_sec: int = 3,
        rest_sec: int = 2,
    ) -> Path:
        """
        Interactive webcam collection loop with visual countdown and sequence recording.
        """
        source = self.video_source if self.video_source is not None else self.camera_index
        cap = cv2.VideoCapture(source)

        if not cap.isOpened() and isinstance(source, int):
            cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)

        if not cap.isOpened():
            raise RuntimeError(f"Unable to open video source: {source}")

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, self.fps)

        session_id = f"session_{self.label}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        session = SessionRecording(
            session_id=session_id,
            subject_id=self.subject_id,
            label=self.label,
            target_fps=self.fps,
            window_length=self.window_length,
            created_at_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            sequences=[],
        )

        logger.info(
            f"Starting collection for '{self.label}' ({num_sequences} sequences of {self.window_length} frames)."
        )

        try:
            for seq_idx in range(1, num_sequences + 1):
                # 1. Countdown Phase
                if not self._run_countdown(cap, countdown_sec, seq_idx, num_sequences):
                    logger.info("Collection interrupted during countdown.")
                    break

                # 2. Recording Phase
                seq_data = self._record_single_sequence(cap, seq_idx, num_sequences)
                if seq_data is None:
                    logger.info("Collection interrupted during recording.")
                    break

                session.sequences.append(seq_data)
                logger.info(f"Recorded sequence {seq_idx}/{num_sequences} ({len(seq_data.frames)} frames).")

                # 3. Rest Phase (if not last)
                if seq_idx < num_sequences:
                    if not self._run_rest(cap, rest_sec, seq_idx, num_sequences):
                        logger.info("Collection interrupted during rest.")
                        break

        finally:
            cap.release()
            cv2.destroyAllWindows()
            self.detector.close()

        # Save session file
        output_file = self.output_dir / f"{session_id}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(asdict(session), f, indent=2)

        logger.info(f"Session data saved to: {output_file} (Total sequences: {len(session.sequences)})")
        return output_file

    def _run_countdown(self, cap: cv2.VideoCapture, seconds: int, seq_idx: int, total_seq: int) -> bool:
        start = time.time()
        while time.time() - start < seconds:
            ret, frame = cap.read()
            if not ret or frame is None:
                return False

            remaining = int(np.ceil(seconds - (time.time() - start)))
            display = frame.copy()
            h, w = display.shape[:2]

            # Overlay prompt
            cv2.putText(
                display,
                f"Prepare for {self.label.upper()} ({seq_idx}/{total_seq})",
                (30, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 255),
                2,
            )
            cv2.putText(
                display,
                f"Starting in: {remaining}s",
                (w // 2 - 120, h // 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.5,
                (0, 0, 255),
                3,
            )

            cv2.imshow("AI Gym Trainer - Data Collection", display)
            if (cv2.waitKey(10) & 0xFF) in [27, ord("q")]:
                return False
        return True

    def _run_rest(self, cap: cv2.VideoCapture, seconds: int, seq_idx: int, total_seq: int) -> bool:
        start = time.time()
        while time.time() - start < seconds:
            ret, frame = cap.read()
            if not ret or frame is None:
                return False

            remaining = int(np.ceil(seconds - (time.time() - start)))
            display = frame.copy()
            cv2.putText(
                display,
                f"Completed seq {seq_idx}/{total_seq}. Rest: {remaining}s",
                (30, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 200, 0),
                2,
            )
            cv2.imshow("AI Gym Trainer - Data Collection", display)
            if (cv2.waitKey(10) & 0xFF) in [27, ord("q")]:
                return False
        return True

    def _record_single_sequence(
        self,
        cap: cv2.VideoCapture,
        seq_idx: int,
        total_seq: int,
    ) -> Optional[SequenceData]:
        frames: List[FrameData] = []
        seq_id = f"seq_{self.label}_{uuid.uuid4().hex[:8]}"
        frame_interval = 1.0 / self.fps
        start_time = time.time()

        for f_idx in range(self.window_length):
            loop_start = time.time()
            ret, frame = cap.read()
            if not ret or frame is None:
                return None

            ts_ms = (time.time() - start_time) * 1000.0
            result: PoseDetectionResult = self.detector.detect(frame, timestamp_ms=int(ts_ms))

            if result.has_detection and result.landmarks is not None:
                lm_list = result.landmarks.tolist()
                frames.append(FrameData(timestamp_ms=ts_ms, detected=True, landmarks=lm_list))
            else:
                frames.append(FrameData(timestamp_ms=ts_ms, detected=False, landmarks=None))

            # Visual progress overlay
            display = frame.copy()
            cv2.putText(
                display,
                f"RECORDING: {self.label.upper()} [{seq_idx}/{total_seq}] - Frame {f_idx+1}/{self.window_length}",
                (30, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2,
            )
            bar_w = int((f_idx + 1) / self.window_length * (display.shape[1] - 60))
            cv2.rectangle(display, (30, 70), (30 + bar_w, 85), (0, 0, 255), -1)

            cv2.imshow("AI Gym Trainer - Data Collection", display)
            if (cv2.waitKey(1) & 0xFF) in [27, ord("q")]:
                return None

            # Rate limiting to adhere to target FPS
            elapsed = time.time() - loop_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        return SequenceData(
            sequence_id=seq_id,
            label=self.label,
            fps=self.fps,
            num_frames=len(frames),
            frames=frames,
        )
