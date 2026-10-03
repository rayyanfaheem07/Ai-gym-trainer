import logging
from dataclasses import dataclass
from typing import List, Set, Union

import numpy as np
from sklearn.model_selection import GroupShuffleSplit

from ai.classifier.preprocessor import ProcessedDataset, ProcessedTemporalDataset

logger = logging.getLogger("DatasetSplitter")


@dataclass
class DatasetSplits:
    """Encapsulates Train, Validation, and Test partitions with leakage verification."""
    X_train: np.ndarray
    y_train: np.ndarray
    groups_train: List[str]

    X_val: np.ndarray
    y_val: np.ndarray
    groups_val: List[str]

    X_test: np.ndarray
    y_test: np.ndarray
    groups_test: List[str]

    classes: List[str]
    feature_names: List[str]

    def verify_no_leakage(self) -> bool:
        """
        Validates that session/subject groups across train, val, and test are strictly disjoint.
        """
        train_set: Set[str] = set(self.groups_train)
        val_set: Set[str] = set(self.groups_val)
        test_set: Set[str] = set(self.groups_test)

        leakage_train_val = train_set.intersection(val_set)
        leakage_train_test = train_set.intersection(test_set)
        leakage_val_test = val_set.intersection(test_set)

        if leakage_train_val or leakage_train_test or leakage_val_test:
            logger.error(
                f"Data Leakage Detected! Intersections: train-val: {leakage_train_val}, "
                f"train-test: {leakage_train_test}, val-test: {leakage_val_test}"
            )
            return False
        return True


class GroupAwareDatasetSplitter:
    """
    Partitions datasets into Train, Validation, and Test sets based on recording session/subject groups.
    Ensures zero temporal or participant leakage between training and evaluation splits.
    """

    def __init__(
        self,
        test_size: float = 0.2,
        val_size: float = 0.15,
        random_state: int = 42,
    ):
        self.test_size = test_size
        self.val_size = val_size
        self.random_state = random_state

    def split(self, dataset: Union[ProcessedDataset, ProcessedTemporalDataset]) -> DatasetSplits:
        """
        Splits a ProcessedDataset or ProcessedTemporalDataset into strictly disjoint Train, Validation, and Test partitions.
        """
        X = dataset.X
        y = dataset.y
        groups = np.array(dataset.groups)
        unique_groups = np.unique(groups)

        if len(unique_groups) < 3:
            logger.warning(
                f"Only {len(unique_groups)} unique session groups available. "
                "Falling back to sample-level stratified split (Note: collect more sessions for production-grade group isolation)."
            )
            return self._fallback_sample_split(dataset)

        # 1. Split into (Train+Val) and Test by Groups
        gss_test = GroupShuffleSplit(
            n_splits=1,
            test_size=self.test_size,
            random_state=self.random_state,
        )
        train_val_idx, test_idx = next(gss_test.split(X, y, groups=groups))

        X_train_val = X[train_val_idx]
        y_train_val = y[train_val_idx]
        groups_train_val = groups[train_val_idx]

        # 2. Split (Train+Val) into Train and Val by Groups
        # Adjust val_size relative to remaining train_val subset
        adjusted_val_size = self.val_size / (1.0 - self.test_size)
        unique_train_val_groups = np.unique(groups_train_val)

        if len(unique_train_val_groups) >= 2:
            gss_val = GroupShuffleSplit(
                n_splits=1,
                test_size=adjusted_val_size,
                random_state=self.random_state,
            )
            train_sub_idx, val_sub_idx = next(gss_val.split(X_train_val, y_train_val, groups=groups_train_val))

            train_idx = train_val_idx[train_sub_idx]
            val_idx = train_val_idx[val_sub_idx]
        else:
            # Only 1 group left in train_val: put in train, create empty/minimal val
            train_idx = train_val_idx
            val_idx = np.array([], dtype=int)

        empty_val_shape = (0,) + X.shape[1:]
        splits = DatasetSplits(
            X_train=X[train_idx],
            y_train=y[train_idx],
            groups_train=list(groups[train_idx]),
            X_val=X[val_idx] if len(val_idx) > 0 else np.empty(empty_val_shape, dtype=X.dtype),
            y_val=y[val_idx] if len(val_idx) > 0 else np.empty((0,), dtype=y.dtype),
            groups_val=list(groups[val_idx]) if len(val_idx) > 0 else [],
            X_test=X[test_idx],
            y_test=y[test_idx],
            groups_test=list(groups[test_idx]),
            classes=dataset.classes,
            feature_names=dataset.feature_names,
        )

        if not splits.verify_no_leakage():
            raise ValueError("Data leakage assertion failed in group splitting.")
        logger.info(
            f"Dataset split completed without leakage: Train={len(splits.X_train)} samples ({len(set(splits.groups_train))} groups), "
            f"Val={len(splits.X_val)} samples ({len(set(splits.groups_val))} groups), "
            f"Test={len(splits.X_test)} samples ({len(set(splits.groups_test))} groups)."
        )
        return splits

    def _fallback_sample_split(self, dataset: Union[ProcessedDataset, ProcessedTemporalDataset]) -> DatasetSplits:
        """Stratified sample-level split when insufficient groups exist in dev/synthetic test datasets."""
        from sklearn.model_selection import train_test_split

        X = dataset.X
        y = dataset.y
        groups = dataset.groups

        # Check if stratification is possible (at least 2 samples per class)
        unique_y, counts = np.unique(y, return_counts=True)
        can_stratify = np.all(counts >= 2)
        strat = y if can_stratify else None

        X_train_val, X_test, y_train_val, y_test, g_train_val, g_test = train_test_split(
            X, y, groups, test_size=self.test_size, random_state=self.random_state, stratify=strat
        )

        adjusted_val = self.val_size / (1.0 - self.test_size)
        u_y_tv, c_tv = np.unique(y_train_val, return_counts=True)
        can_strat_val = np.all(c_tv >= 2)
        strat_val = y_train_val if can_strat_val else None

        X_train, X_val, y_train, y_val, g_train, g_val = train_test_split(
            X_train_val, y_train_val, g_train_val, test_size=adjusted_val, random_state=self.random_state, stratify=strat_val
        )

        return DatasetSplits(
            X_train=X_train,
            y_train=y_train,
            groups_train=g_train,
            X_val=X_val,
            y_val=y_val,
            groups_val=g_val,
            X_test=X_test,
            y_test=y_test,
            groups_test=g_test,
            classes=dataset.classes,
            feature_names=dataset.feature_names,
        )
