from pathlib import Path

import numpy as np

from ai.classifier.dataset import GroupAwareDatasetSplitter
from ai.classifier.preprocessor import DataPreprocessor, ProcessedDataset
from ai.classifier.synthetic import BiomechanicalDataGenerator


def test_group_aware_splitting_zero_leakage(tmp_path: Path):
    # Generate dataset with 4 distinct subject sessions per class
    session_files = BiomechanicalDataGenerator.generate_synthetic_dataset(
        output_dir=tmp_path / "raw",
        num_sessions_per_class=4,
        sequences_per_session=2,
    )

    preprocessor = DataPreprocessor()
    sessions = preprocessor.load_raw_sessions(session_files)
    dataset = preprocessor.process_sessions(sessions)
    processed = preprocessor.fit_transform_dataset(dataset)

    splitter = GroupAwareDatasetSplitter(test_size=0.25, val_size=0.25, random_state=42)
    splits = splitter.split(processed)

    # 1. Check shapes & non-empty partitions
    assert len(splits.X_train) > 0
    assert len(splits.X_val) > 0
    assert len(splits.X_test) > 0
    assert len(splits.X_train) + len(splits.X_val) + len(splits.X_test) == len(processed.X)

    # 2. Strict Data Leakage Verification
    assert splits.verify_no_leakage() is True

    train_groups = set(splits.groups_train)
    val_groups = set(splits.groups_val)
    test_groups = set(splits.groups_test)

    assert train_groups.isdisjoint(val_groups)
    assert train_groups.isdisjoint(test_groups)
    assert val_groups.isdisjoint(test_groups)


def test_fallback_split_when_few_groups():
    # Only 2 groups total
    X = np.random.randn(20, 10).astype(np.float32)
    y = np.array([0, 1] * 10)
    groups = ["session_A"] * 10 + ["session_B"] * 10

    dataset = ProcessedDataset(
        X=X,
        y=y,
        labels=["squat", "push_up"] * 10,
        groups=groups,
        feature_names=[f"f_{i}" for i in range(10)],
        classes=["squat", "push_up"],
    )

    splitter = GroupAwareDatasetSplitter(test_size=0.2, val_size=0.2, random_state=42)
    splits = splitter.split(dataset)

    assert len(splits.X_train) > 0
    assert len(splits.X_test) > 0
