import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import joblib
import numpy as np
from sklearn.preprocessing import LabelEncoder, StandardScaler

from ai.classifier.features import PoseFeatureExtractor

logger = logging.getLogger("DataPreprocessor")


@dataclass
class ProcessedDataset:
    X: np.ndarray                  # (N, D) feature matrix
    y: np.ndarray                  # (N,) integer-encoded target labels
    labels: List[str]              # (N,) raw string label names
    groups: List[str]              # (N,) session/subject group IDs for leakage-free splitting
    feature_names: List[str]
    classes: List[str]


@dataclass
class ProcessedTemporalDataset:
    X: np.ndarray                  # (N, T, F) temporal feature tensor
    y: np.ndarray                  # (N,) integer-encoded target labels
    labels: List[str]              # (N,) raw string label names
    groups: List[str]              # (N,) session/subject group IDs for leakage-free splitting
    feature_names: List[str]       # (F,) per-frame feature names
    classes: List[str]
    sequence_length: int
    feature_dim: int


class DataPreprocessor:
    """
    Validates, cleans, windows, extracts features, and normalizes pose sequence datasets.
    Supports both 2D statistical window representation (scikit-learn baseline) and 3D
    temporal sequence representation (PyTorch LSTM/GRU).
    Can be serialized alongside the model to guarantee 100% identical transformations during inference.
    """

    def __init__(
        self,
        window_size: int = 30,
        stride: int = 10,
        min_detected_ratio: float = 0.7,
        feature_extractor: Optional[PoseFeatureExtractor] = None,
    ):
        self.window_size = window_size
        self.stride = stride
        self.min_detected_ratio = min_detected_ratio
        self.feature_extractor = feature_extractor or PoseFeatureExtractor()
        self.scaler = StandardScaler()
        self.label_encoder = LabelEncoder()
        self.is_fitted = False

    def load_raw_sessions(self, raw_dir_or_files: str | Path | Sequence[str | Path]) -> List[Dict[str, Any]]:
        """Loads raw JSON session files from a directory or file list."""
        paths: List[Path] = []
        if isinstance(raw_dir_or_files, (str, Path)):
            p = Path(raw_dir_or_files)
            if p.is_dir():
                paths = sorted(p.glob("*.json"))
            elif p.is_file():
                paths = [p]
        else:
            paths = [Path(p) for p in raw_dir_or_files]

        sessions = []
        for file_path in paths:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    sessions.append(data)
            except Exception as e:
                logger.error(f"Failed to load {file_path}: {e}")
        logger.info(f"Loaded {len(sessions)} raw session files.")
        return sessions

    def validate_and_impute_sequence(self, frames: List[Dict[str, Any]]) -> Optional[np.ndarray]:
        """
        Validates a sequence of frame dictionaries and linearly interpolates missing frames.

        Returns:
            np.ndarray of shape (T, 33, 4) with [x, y, z, visibility] or None if sequence is invalid.
        """
        if not frames:
            return None

        total_frames = len(frames)
        detected_frames = [f for f in frames if f.get("detected") and f.get("landmarks") is not None]

        if (len(detected_frames) / total_frames) < self.min_detected_ratio:
            logger.debug(f"Sequence rejected: detection ratio {len(detected_frames)}/{total_frames} < {self.min_detected_ratio}")
            return None

        # Build raw array with NaNs for undetected frames
        arr = np.full((total_frames, 33, 4), np.nan, dtype=np.float32)
        for i, f in enumerate(frames):
            if f.get("detected") and f.get("landmarks") is not None:
                lm = np.array(f["landmarks"], dtype=np.float32)
                if lm.shape[0] == 33:
                    if lm.shape[1] == 3:
                        # Append default visibility 1.0 if missing
                        vis = np.ones((33, 1), dtype=np.float32)
                        lm = np.hstack([lm, vis])
                    arr[i] = lm[:, :4]

        # Linear interpolation across temporal axis for any NaN coordinates
        for lm_idx in range(33):
            for coord_idx in range(4):
                series = arr[:, lm_idx, coord_idx]
                nans = np.isnan(series)
                if np.all(nans):
                    return None
                if np.any(nans):
                    valid_indices = np.where(~nans)[0]
                    nan_indices = np.where(nans)[0]
                    series[nan_indices] = np.interp(nan_indices, valid_indices, series[valid_indices])
                    arr[:, lm_idx, coord_idx] = series

        return arr

    def create_windows_from_sequence(self, sequence_arr: np.ndarray) -> List[np.ndarray]:
        """
        Slices a (T, 33, 4) sequence into fixed-length sliding windows of shape (window_size, 33, 4).
        """
        t = sequence_arr.shape[0]
        if t < self.window_size:
            # If sequence is shorter than window_size, pad or repeat the last frame
            pad_len = self.window_size - t
            pad_arr = np.repeat(sequence_arr[-1:], pad_len, axis=0)
            return [np.vstack([sequence_arr, pad_arr])]

        windows = []
        for start in range(0, t - self.window_size + 1, self.stride):
            windows.append(sequence_arr[start : start + self.window_size])
        return windows

    def extract_sequence_features(self, window: Sequence[np.ndarray] | np.ndarray) -> np.ndarray:
        """
        Extracts temporal sequence of per-frame feature vectors.
        Shape: (T, F) where T = len(window) and F = len(feature_names_per_frame).
        """
        if window is None or len(window) == 0:
            dummy_dim = len(self.feature_extractor.feature_names_per_frame)
            return np.zeros((self.window_size, dummy_dim), dtype=np.float32)

        frame_feats = [self.feature_extractor.extract_frame_features(frame) for frame in window]
        return np.array(frame_feats, dtype=np.float32)

    def process_sessions(self, sessions: List[Dict[str, Any]]) -> ProcessedDataset:
        """
        Processes loaded raw sessions into a structured statistical feature dataset (2D).
        """
        raw_features: List[np.ndarray] = []
        raw_labels: List[str] = []
        raw_groups: List[str] = []

        for session in sessions:
            session_id = session.get("session_id", "unknown_session")
            session_label = session.get("label", "other")
            sequences = session.get("sequences", [])

            for seq in sequences:
                seq_label = seq.get("label", session_label)
                frames = seq.get("frames", [])
                seq_arr = self.validate_and_impute_sequence(frames)
                if seq_arr is None:
                    continue

                windows = self.create_windows_from_sequence(seq_arr)
                for win in windows:
                    feat_vec = self.feature_extractor.extract_window_features(win)
                    raw_features.append(feat_vec)
                    raw_labels.append(seq_label)
                    raw_groups.append(session_id)

        if not raw_features:
            raise ValueError("No valid movement sequences found in the provided sessions.")

        X_raw = np.array(raw_features, dtype=np.float32)
        classes = sorted(list(set(raw_labels)))

        return ProcessedDataset(
            X=X_raw,
            y=np.zeros(len(raw_labels), dtype=np.int64),
            labels=raw_labels,
            groups=raw_groups,
            feature_names=self.feature_extractor.get_feature_names(),
            classes=classes,
        )

    def process_sessions_temporal(self, sessions: List[Dict[str, Any]]) -> ProcessedTemporalDataset:
        """
        Processes loaded raw sessions into a structured 3D temporal sequence dataset: (N, T, F).
        """
        raw_sequences: List[np.ndarray] = []
        raw_labels: List[str] = []
        raw_groups: List[str] = []

        for session in sessions:
            session_id = session.get("session_id", "unknown_session")
            session_label = session.get("label", "other")
            sequences = session.get("sequences", [])

            for seq in sequences:
                seq_label = seq.get("label", session_label)
                frames = seq.get("frames", [])
                seq_arr = self.validate_and_impute_sequence(frames)
                if seq_arr is None:
                    continue

                windows = self.create_windows_from_sequence(seq_arr)
                for win in windows:
                    seq_feats = self.extract_sequence_features(win)  # (T, F)
                    raw_sequences.append(seq_feats)
                    raw_labels.append(seq_label)
                    raw_groups.append(session_id)

        if not raw_sequences:
            raise ValueError("No valid movement sequences found in the provided sessions.")

        X_temporal = np.array(raw_sequences, dtype=np.float32)  # Shape: (N, T, F)
        classes = sorted(list(set(raw_labels)))
        feature_names = self.feature_extractor.feature_names_per_frame

        return ProcessedTemporalDataset(
            X=X_temporal,
            y=np.zeros(len(raw_labels), dtype=np.int64),
            labels=raw_labels,
            groups=raw_groups,
            feature_names=feature_names,
            classes=classes,
            sequence_length=X_temporal.shape[1],
            feature_dim=X_temporal.shape[2],
        )

    def fit(self, dataset: ProcessedDataset) -> "DataPreprocessor":
        """Fits StandardScaler and LabelEncoder on 2D processed dataset."""
        self.scaler.fit(dataset.X)
        self.label_encoder.fit(dataset.labels)
        self.is_fitted = True
        return self

    def fit_temporal(self, dataset: ProcessedTemporalDataset) -> "DataPreprocessor":
        """Fits StandardScaler across all time frames and LabelEncoder on temporal dataset."""
        n, t, f = dataset.X.shape
        x_flat = dataset.X.reshape(n * t, f)
        self.scaler.fit(x_flat)
        self.label_encoder.fit(dataset.labels)
        self.is_fitted = True
        return self

    def transform_dataset(self, dataset: ProcessedDataset) -> ProcessedDataset:
        """Standardizes 2D features and encodes integer labels."""
        if not self.is_fitted:
            raise RuntimeError("DataPreprocessor must be fitted before calling transform_dataset().")

        X_scaled = self.scaler.transform(dataset.X).astype(np.float32)
        y_encoded = self.label_encoder.transform(dataset.labels).astype(np.int64)

        return ProcessedDataset(
            X=X_scaled,
            y=y_encoded,
            labels=dataset.labels,
            groups=dataset.groups,
            feature_names=dataset.feature_names,
            classes=list(self.label_encoder.classes_),
        )

    def transform_temporal_dataset(self, dataset: ProcessedTemporalDataset) -> ProcessedTemporalDataset:
        """Standardizes 3D temporal sequence features and encodes integer labels."""
        if not self.is_fitted:
            raise RuntimeError("DataPreprocessor must be fitted before calling transform_temporal_dataset().")

        n, t, f = dataset.X.shape
        x_flat = dataset.X.reshape(n * t, f)
        x_scaled_flat = self.scaler.transform(x_flat).astype(np.float32)
        x_scaled = x_scaled_flat.reshape(n, t, f)
        y_encoded = self.label_encoder.transform(dataset.labels).astype(np.int64)

        return ProcessedTemporalDataset(
            X=x_scaled,
            y=y_encoded,
            labels=dataset.labels,
            groups=dataset.groups,
            feature_names=dataset.feature_names,
            classes=list(self.label_encoder.classes_),
            sequence_length=t,
            feature_dim=f,
        )

    def fit_transform_dataset(self, dataset: ProcessedDataset) -> ProcessedDataset:
        """Fits scaler & label encoder, then transforms 2D dataset."""
        return self.fit(dataset).transform_dataset(dataset)

    def fit_transform_temporal_dataset(self, dataset: ProcessedTemporalDataset) -> ProcessedTemporalDataset:
        """Fits scaler & label encoder on temporal dataset, then transforms it."""
        return self.fit_temporal(dataset).transform_temporal_dataset(dataset)

    def transform_window(self, window: Sequence[np.ndarray] | np.ndarray) -> np.ndarray:
        """
        Extracts statistical features from a live window and scales them using fitted scaler (1, D).
        """
        if not self.is_fitted:
            raise RuntimeError("DataPreprocessor must be fitted before calling transform_window().")

        features_1d = self.feature_extractor.extract_window_features(window)
        features_2d = features_1d.reshape(1, -1)
        return self.scaler.transform(features_2d).astype(np.float32)

    def transform_sequence_window(self, window: Sequence[np.ndarray] | np.ndarray) -> np.ndarray:
        """
        Extracts temporal sequence of features from a live window and scales them (1, T, F).
        """
        if not self.is_fitted:
            raise RuntimeError("DataPreprocessor must be fitted before calling transform_sequence_window().")

        seq = self.extract_sequence_features(window)  # (T, F)
        scaled_seq = self.scaler.transform(seq).astype(np.float32)  # (T, F)
        return np.expand_dims(scaled_seq, axis=0)  # (1, T, F)

    def save(self, filepath: str | Path):
        """Serializes the preprocessor pipeline to disk."""
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "window_size": self.window_size,
                "stride": self.stride,
                "min_detected_ratio": self.min_detected_ratio,
                "scaler": self.scaler,
                "label_encoder": self.label_encoder,
                "feature_extractor": self.feature_extractor,
                "is_fitted": self.is_fitted,
            },
            filepath,
        )
        logger.info(f"Preprocessor saved to {filepath}")

    @classmethod
    def load(cls, filepath: str | Path) -> "DataPreprocessor":
        """Loads a preprocessor pipeline from disk."""
        data = joblib.load(filepath)
        instance = cls(
            window_size=data["window_size"],
            stride=data["stride"],
            min_detected_ratio=data["min_detected_ratio"],
            feature_extractor=data["feature_extractor"],
        )
        instance.scaler = data["scaler"]
        instance.label_encoder = data["label_encoder"]
        instance.is_fitted = data["is_fitted"]
        return instance
