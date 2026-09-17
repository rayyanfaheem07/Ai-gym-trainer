from pathlib import Path

import numpy as np

from ai.classifier.preprocessor import DataPreprocessor
from ai.classifier.synthetic import BiomechanicalDataGenerator


def test_preprocessor_validation_and_imputation():
    preprocessor = DataPreprocessor(window_size=30, stride=10, min_detected_ratio=0.7)

    # Valid sequence with a missing frame in the middle
    frames = []
    traj = BiomechanicalDataGenerator.generate_exercise_trajectory("bicep_curl", num_frames=30)
    for i in range(30):
        if i == 15:  # simulate undetected frame
            frames.append({"timestamp_ms": i * 33.3, "detected": False, "landmarks": None})
        else:
            frames.append({"timestamp_ms": i * 33.3, "detected": True, "landmarks": traj[i].tolist()})

    cleaned_arr = preprocessor.validate_and_impute_sequence(frames)
    assert cleaned_arr is not None
    assert cleaned_arr.shape == (30, 33, 4)
    assert not np.isnan(cleaned_arr).any()
    # Interpolated frame at index 15 should be average of frame 14 and 16
    expected_15 = (cleaned_arr[14] + cleaned_arr[16]) / 2.0
    np.testing.assert_allclose(cleaned_arr[15], expected_15, atol=1e-4)


def test_preprocessor_rejection_of_corrupt_sequence():
    preprocessor = DataPreprocessor(min_detected_ratio=0.8)

    # Sequence with 50% missing frames
    frames = []
    for i in range(20):
        detected = i % 2 == 0
        frames.append({
            "timestamp_ms": i * 33.3,
            "detected": detected,
            "landmarks": np.zeros((33, 4)).tolist() if detected else None,
        })

    cleaned_arr = preprocessor.validate_and_impute_sequence(frames)
    assert cleaned_arr is None


def test_preprocessor_sliding_windows():
    preprocessor = DataPreprocessor(window_size=30, stride=10)
    dummy_seq = np.zeros((65, 33, 4), dtype=np.float32)

    windows = preprocessor.create_windows_from_sequence(dummy_seq)
    # Length 65 with window 30 and stride 10 -> starts at 0, 10, 20, 30 -> 4 windows
    assert len(windows) == 4
    for win in windows:
        assert win.shape == (30, 33, 4)


def test_preprocessor_fit_transform_and_save(tmp_path: Path):
    preprocessor = DataPreprocessor(window_size=30, stride=10)

    # Synthetic session data
    session_files = BiomechanicalDataGenerator.generate_synthetic_dataset(
        output_dir=tmp_path / "raw",
        num_sessions_per_class=2,
        sequences_per_session=2,
        window_length=30,
    )

    sessions = preprocessor.load_raw_sessions(session_files)
    dataset = preprocessor.process_sessions(sessions)
    assert len(dataset.X) > 0

    # Fit & transform
    transformed = preprocessor.fit_transform_dataset(dataset)
    assert transformed.X.shape == dataset.X.shape
    assert len(transformed.y) == len(dataset.y)
    assert len(transformed.classes) == 6

    # Test save & load
    save_file = tmp_path / "preprocessor.joblib"
    preprocessor.save(save_file)
    assert save_file.exists()

    loaded = DataPreprocessor.load(save_file)
    assert loaded.is_fitted
    assert loaded.window_size == preprocessor.window_size

    # Test transform_window on single live window
    live_win = BiomechanicalDataGenerator.generate_exercise_trajectory("squat", num_frames=30)
    scaled_win = loaded.transform_window(live_win)
    assert scaled_win.shape == (1, transformed.X.shape[1])
    assert not np.isnan(scaled_win).any()
