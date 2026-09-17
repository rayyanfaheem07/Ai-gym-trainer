import json
import math
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import List

import numpy as np

from ai.classifier.collector import FrameData, SequenceData, SessionRecording
from ai.pose.landmarks import LandmarkIndex


class BiomechanicalDataGenerator:
    """
    Generates synthetic, physically plausible 3D landmark trajectories for all 6 target exercises:
    - squat
    - push_up
    - bicep_curl
    - lunge
    - shoulder_press
    - other

    Used for automated CI/CD validation, unit testing, and pipeline dry-runs without live camera requirements.
    """

    @staticmethod
    def _create_base_skeleton(posture: str = "standing") -> np.ndarray:
        """Creates a default baseline 33x4 skeleton array [x, y, z, visibility]."""
        lm = np.zeros((33, 4), dtype=np.float32)
        lm[:, 3] = 1.0  # Default visibility

        if posture == "standing":
            # Head / Face
            lm[LandmarkIndex.NOSE] = [0.5, 0.15, 0.0, 1.0]
            lm[LandmarkIndex.LEFT_EYE] = [0.48, 0.13, 0.0, 1.0]
            lm[LandmarkIndex.RIGHT_EYE] = [0.52, 0.13, 0.0, 1.0]
            lm[LandmarkIndex.LEFT_EAR] = [0.45, 0.15, 0.0, 1.0]
            lm[LandmarkIndex.RIGHT_EAR] = [0.55, 0.15, 0.0, 1.0]

            # Shoulders
            lm[LandmarkIndex.LEFT_SHOULDER] = [0.40, 0.25, 0.0, 1.0]
            lm[LandmarkIndex.RIGHT_SHOULDER] = [0.60, 0.25, 0.0, 1.0]

            # Elbows & Wrists (arms down)
            lm[LandmarkIndex.LEFT_ELBOW] = [0.38, 0.40, 0.0, 1.0]
            lm[LandmarkIndex.RIGHT_ELBOW] = [0.62, 0.40, 0.0, 1.0]
            lm[LandmarkIndex.LEFT_WRIST] = [0.37, 0.55, 0.0, 1.0]
            lm[LandmarkIndex.RIGHT_WRIST] = [0.63, 0.55, 0.0, 1.0]

            # Hips
            lm[LandmarkIndex.LEFT_HIP] = [0.43, 0.50, 0.0, 1.0]
            lm[LandmarkIndex.RIGHT_HIP] = [0.57, 0.50, 0.0, 1.0]

            # Knees
            lm[LandmarkIndex.LEFT_KNEE] = [0.43, 0.70, 0.0, 1.0]
            lm[LandmarkIndex.RIGHT_KNEE] = [0.57, 0.70, 0.0, 1.0]

            # Ankles & Feet
            lm[LandmarkIndex.LEFT_ANKLE] = [0.43, 0.90, 0.0, 1.0]
            lm[LandmarkIndex.RIGHT_ANKLE] = [0.57, 0.90, 0.0, 1.0]
            lm[LandmarkIndex.LEFT_FOOT_INDEX] = [0.42, 0.93, -0.05, 1.0]
            lm[LandmarkIndex.RIGHT_FOOT_INDEX] = [0.58, 0.93, -0.05, 1.0]

        elif posture == "horizontal":  # Push-up position
            lm[LandmarkIndex.NOSE] = [0.25, 0.48, 0.0, 1.0]
            lm[LandmarkIndex.LEFT_SHOULDER] = [0.35, 0.50, -0.08, 1.0]
            lm[LandmarkIndex.RIGHT_SHOULDER] = [0.35, 0.50, 0.08, 1.0]
            lm[LandmarkIndex.LEFT_ELBOW] = [0.35, 0.60, -0.10, 1.0]
            lm[LandmarkIndex.RIGHT_ELBOW] = [0.35, 0.60, 0.10, 1.0]
            lm[LandmarkIndex.LEFT_WRIST] = [0.35, 0.70, -0.10, 1.0]
            lm[LandmarkIndex.RIGHT_WRIST] = [0.35, 0.70, 0.10, 1.0]

            lm[LandmarkIndex.LEFT_HIP] = [0.55, 0.52, -0.06, 1.0]
            lm[LandmarkIndex.RIGHT_HIP] = [0.55, 0.52, 0.06, 1.0]
            lm[LandmarkIndex.LEFT_KNEE] = [0.70, 0.54, -0.05, 1.0]
            lm[LandmarkIndex.RIGHT_KNEE] = [0.70, 0.54, 0.05, 1.0]
            lm[LandmarkIndex.LEFT_ANKLE] = [0.85, 0.56, -0.04, 1.0]
            lm[LandmarkIndex.RIGHT_ANKLE] = [0.85, 0.56, 0.04, 1.0]

        return lm

    @classmethod
    def generate_exercise_trajectory(
        cls,
        exercise: str,
        num_frames: int = 30,
        noise_std: float = 0.005,
    ) -> np.ndarray:
        """
        Synthesizes a (num_frames, 33, 4) landmark trajectory array for a specific exercise.
        """
        ex = exercise.lower().replace("-", "_")
        trajectory = np.zeros((num_frames, 33, 4), dtype=np.float32)

        if ex == "squat":
            base = cls._create_base_skeleton("standing")
            for t in range(num_frames):
                phase = math.sin(math.pi * t / (num_frames - 1))  # 0 -> 1 -> 0
                frame = base.copy()
                # Hips descend and push back
                frame[[LandmarkIndex.LEFT_HIP, LandmarkIndex.RIGHT_HIP], 1] += 0.22 * phase
                frame[[LandmarkIndex.LEFT_HIP, LandmarkIndex.RIGHT_HIP], 2] -= 0.08 * phase
                # Knees bend forward & slightly down
                frame[[LandmarkIndex.LEFT_KNEE, LandmarkIndex.RIGHT_KNEE], 1] += 0.10 * phase
                frame[[LandmarkIndex.LEFT_KNEE, LandmarkIndex.RIGHT_KNEE], 2] += 0.05 * phase
                # Shoulders follow torso forward-down lean
                frame[[LandmarkIndex.LEFT_SHOULDER, LandmarkIndex.RIGHT_SHOULDER], 1] += 0.18 * phase
                frame[[LandmarkIndex.LEFT_SHOULDER, LandmarkIndex.RIGHT_SHOULDER], 2] += 0.05 * phase
                # Add noise
                frame[:, :3] += np.random.normal(0, noise_std, (33, 3))
                trajectory[t] = frame

        elif ex in ["pushup", "push_up"]:
            base = cls._create_base_skeleton("horizontal")
            for t in range(num_frames):
                phase = math.sin(math.pi * t / (num_frames - 1))  # 0 -> 1 -> 0
                frame = base.copy()
                # Torso and shoulders descend towards wrists
                frame[[LandmarkIndex.LEFT_SHOULDER, LandmarkIndex.RIGHT_SHOULDER], 1] += 0.15 * phase
                frame[[LandmarkIndex.LEFT_HIP, LandmarkIndex.RIGHT_HIP], 1] += 0.12 * phase
                frame[[LandmarkIndex.NOSE], 1] += 0.15 * phase
                # Elbows flare out
                frame[LandmarkIndex.LEFT_ELBOW, 2] -= 0.10 * phase
                frame[LandmarkIndex.RIGHT_ELBOW, 2] += 0.10 * phase
                frame[:, :3] += np.random.normal(0, noise_std, (33, 3))
                trajectory[t] = frame

        elif ex == "bicep_curl":
            base = cls._create_base_skeleton("standing")
            for t in range(num_frames):
                phase = math.sin(math.pi * t / (num_frames - 1))
                frame = base.copy()
                # Wrists curl upward towards shoulders
                frame[LandmarkIndex.LEFT_WRIST, 1] -= 0.28 * phase
                frame[LandmarkIndex.RIGHT_WRIST, 1] -= 0.28 * phase
                frame[LandmarkIndex.LEFT_WRIST, 2] += 0.10 * phase
                frame[LandmarkIndex.RIGHT_WRIST, 2] += 0.10 * phase
                # Elbows stay relatively stationary
                frame[:, :3] += np.random.normal(0, noise_std, (33, 3))
                trajectory[t] = frame

        elif ex == "shoulder_press":
            base = cls._create_base_skeleton("standing")
            # Start position: hands up near shoulders
            base[LandmarkIndex.LEFT_ELBOW] = [0.30, 0.25, 0.0, 1.0]
            base[LandmarkIndex.RIGHT_ELBOW] = [0.70, 0.25, 0.0, 1.0]
            base[LandmarkIndex.LEFT_WRIST] = [0.32, 0.20, 0.0, 1.0]
            base[LandmarkIndex.RIGHT_WRIST] = [0.68, 0.20, 0.0, 1.0]

            for t in range(num_frames):
                phase = math.sin(math.pi * t / (num_frames - 1))
                frame = base.copy()
                # Wrists and elbows extend straight overhead
                frame[LandmarkIndex.LEFT_WRIST, 1] -= 0.18 * phase
                frame[LandmarkIndex.RIGHT_WRIST, 1] -= 0.18 * phase
                frame[LandmarkIndex.LEFT_ELBOW, 1] -= 0.12 * phase
                frame[LandmarkIndex.RIGHT_ELBOW, 1] -= 0.12 * phase
                frame[:, :3] += np.random.normal(0, noise_std, (33, 3))
                trajectory[t] = frame

        elif ex == "lunge":
            base = cls._create_base_skeleton("standing")
            for t in range(num_frames):
                phase = math.sin(math.pi * t / (num_frames - 1))
                frame = base.copy()
                # Lead leg lunges forward and drops down
                frame[LandmarkIndex.LEFT_KNEE, 1] += 0.18 * phase
                frame[LandmarkIndex.LEFT_KNEE, 2] += 0.15 * phase
                # Rear leg drops down
                frame[LandmarkIndex.RIGHT_KNEE, 1] += 0.22 * phase
                frame[LandmarkIndex.RIGHT_KNEE, 2] -= 0.10 * phase
                # Torso remains upright but drops
                frame[[LandmarkIndex.LEFT_HIP, LandmarkIndex.RIGHT_HIP], 1] += 0.20 * phase
                frame[[LandmarkIndex.LEFT_SHOULDER, LandmarkIndex.RIGHT_SHOULDER], 1] += 0.20 * phase
                frame[:, :3] += np.random.normal(0, noise_std, (33, 3))
                trajectory[t] = frame

        else:  # "other" / idle / casual movement
            base = cls._create_base_skeleton("standing")
            for t in range(num_frames):
                frame = base.copy()
                # Gentle sway / random small motions
                sway_x = 0.02 * math.sin(2 * math.pi * t / num_frames)
                sway_y = 0.01 * math.cos(2 * math.pi * t / num_frames)
                frame[:, 0] += sway_x
                frame[:, 1] += sway_y
                frame[:, :3] += np.random.normal(0, noise_std * 2, (33, 3))
                trajectory[t] = frame

        return trajectory

    @classmethod
    def generate_synthetic_dataset(
        cls,
        output_dir: str | Path = "data/raw",
        num_sessions_per_class: int = 5,
        sequences_per_session: int = 4,
        window_length: int = 30,
        fps: float = 30.0,
    ) -> List[Path]:
        """
        Generates structured JSON raw session files for all 6 target exercises across multiple distinct sessions/subjects.
        """
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        classes = ["squat", "push_up", "bicep_curl", "lunge", "shoulder_press", "other"]
        created_files: List[Path] = []

        for cls_name in classes:
            for s_idx in range(1, num_sessions_per_class + 1):
                subject_id = f"subject_{s_idx:02d}"
                session_id = f"synthetic_session_{cls_name}_sub{s_idx:02d}_{int(time.time())}_{uuid.uuid4().hex[:4]}"

                sequences: List[SequenceData] = []
                for seq_idx in range(1, sequences_per_session + 1):
                    traj = cls.generate_exercise_trajectory(cls_name, num_frames=window_length)
                    frames: List[FrameData] = []
                    for f_idx in range(window_length):
                        frames.append(
                            FrameData(
                                timestamp_ms=float(f_idx * (1000.0 / fps)),
                                detected=True,
                                landmarks=traj[f_idx].tolist(),
                            )
                        )

                    sequences.append(
                        SequenceData(
                            sequence_id=f"seq_{cls_name}_{s_idx}_{seq_idx}",
                            label=cls_name,
                            fps=fps,
                            num_frames=len(frames),
                            frames=frames,
                        )
                    )

                session = SessionRecording(
                    session_id=session_id,
                    subject_id=subject_id,
                    label=cls_name,
                    target_fps=fps,
                    window_length=window_length,
                    created_at_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    sequences=sequences,
                )

                file_path = out_path / f"{session_id}.json"
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(asdict(session), f, indent=2)
                created_files.append(file_path)

        return created_files

    @classmethod
    def generate_synthetic_sessions(
        cls,
        num_sessions_per_class: int = 3,
        sequences_per_session: int = 3,
        window_length: int = 30,
        fps: float = 30.0,
    ) -> List[dict]:
        """Generates structured in-memory session dictionaries for all 6 target exercises."""
        classes = ["squat", "push_up", "bicep_curl", "lunge", "shoulder_press", "other"]
        sessions: List[dict] = []

        for cls_name in classes:
            for s_idx in range(1, num_sessions_per_class + 1):
                subject_id = f"subject_{s_idx:02d}"
                session_id = f"synthetic_session_{cls_name}_sub{s_idx:02d}_{int(time.time())}_{uuid.uuid4().hex[:4]}"

                sequences: List[SequenceData] = []
                for seq_idx in range(1, sequences_per_session + 1):
                    traj = cls.generate_exercise_trajectory(cls_name, num_frames=window_length)
                    frames: List[FrameData] = []
                    for f_idx in range(window_length):
                        frames.append(
                            FrameData(
                                timestamp_ms=float(f_idx * (1000.0 / fps)),
                                detected=True,
                                landmarks=traj[f_idx].tolist(),
                            )
                        )

                    sequences.append(
                        SequenceData(
                            sequence_id=f"seq_{cls_name}_{s_idx}_{seq_idx}",
                            label=cls_name,
                            fps=fps,
                            num_frames=len(frames),
                            frames=frames,
                        )
                    )

                session = SessionRecording(
                    session_id=session_id,
                    subject_id=subject_id,
                    label=cls_name,
                    target_fps=fps,
                    window_length=window_length,
                    created_at_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    sequences=sequences,
                )
                sessions.append(asdict(session))

        return sessions
