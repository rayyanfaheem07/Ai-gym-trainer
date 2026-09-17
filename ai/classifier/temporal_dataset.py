import logging
from typing import Optional, Tuple, Union

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset

from ai.classifier.dataset import DatasetSplits

logger = logging.getLogger("TemporalDataset")


class PoseSequenceDataset(Dataset):
    """
    PyTorch Dataset for temporal sequence classification of pose features.
    
    Yields:
        x: torch.FloatTensor of shape (sequence_length, feature_dimension)
        y: torch.LongTensor (scalar class label) if targets are provided, else x only
    """

    def __init__(
        self,
        sequences: Union[np.ndarray, torch.Tensor],
        targets: Optional[Union[np.ndarray, torch.Tensor]] = None,
        sequence_length: Optional[int] = None,
        feature_dim: Optional[int] = None,
    ):
        # Convert sequences to float32 torch tensor
        if isinstance(sequences, np.ndarray):
            self.sequences = torch.from_numpy(sequences.astype(np.float32))
        elif isinstance(sequences, torch.Tensor):
            self.sequences = sequences.float()
        else:
            raise TypeError(f"sequences must be np.ndarray or torch.Tensor, got {type(sequences)}")

        if self.sequences.dim() != 3:
            raise ValueError(
                f"Expected 3D sequences tensor of shape (N, sequence_length, feature_dim), "
                f"got shape {tuple(self.sequences.shape)}"
            )

        # Validate or enforce sequence length
        actual_seq_len = self.sequences.shape[1]
        if sequence_length is not None and actual_seq_len != sequence_length:
            if actual_seq_len > sequence_length:
                # Truncate sequence to desired length
                self.sequences = self.sequences[:, :sequence_length, :]
            else:
                # Pad sequence by repeating last frame
                pad_len = sequence_length - actual_seq_len
                last_frame = self.sequences[:, -1:, :].repeat(1, pad_len, 1)
                self.sequences = torch.cat([self.sequences, last_frame], dim=1)

        # Validate feature dimension
        actual_feat_dim = self.sequences.shape[2]
        if feature_dim is not None and actual_feat_dim != feature_dim:
            raise ValueError(
                f"Feature dimension mismatch: expected {feature_dim}, got {actual_feat_dim}."
            )

        # Convert targets to int64 torch tensor if present
        if targets is not None:
            if isinstance(targets, np.ndarray):
                self.targets = torch.from_numpy(targets.astype(np.int64))
            elif isinstance(targets, torch.Tensor):
                self.targets = targets.long()
            else:
                raise TypeError(f"targets must be np.ndarray or torch.Tensor, got {type(targets)}")

            if len(self.targets) != len(self.sequences):
                raise ValueError(
                    f"Number of targets ({len(self.targets)}) does not match sequences ({len(self.sequences)})."
                )
        else:
            self.targets = None

    def __len__(self) -> int:
        return len(self.sequences)

    def __getitem__(self, idx: int) -> Union[Tuple[torch.Tensor, torch.Tensor], torch.Tensor]:
        x = self.sequences[idx]
        if self.targets is not None:
            y = self.targets[idx]
            return x, y
        return x

    @property
    def sequence_length(self) -> int:
        return self.sequences.shape[1] if len(self.sequences) > 0 else 0

    @property
    def feature_dim(self) -> int:
        return self.sequences.shape[2] if len(self.sequences) > 0 else 0


def create_temporal_dataloaders(
    splits: DatasetSplits,
    batch_size: int = 32,
    num_workers: int = 0,
    sequence_length: Optional[int] = None,
    feature_dim: Optional[int] = None,
) -> Tuple[DataLoader, Optional[DataLoader], DataLoader]:
    """
    Creates PyTorch DataLoaders for Train, Validation, and Test splits.

    Returns:
        (train_loader, val_loader, test_loader)
    """
    train_ds = PoseSequenceDataset(
        sequences=splits.X_train,
        targets=splits.y_train,
        sequence_length=sequence_length,
        feature_dim=feature_dim,
    )
    train_loader = DataLoader(
        train_ds,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        drop_last=False,
    )

    val_loader = None
    if len(splits.X_val) > 0 and len(splits.y_val) > 0:
        val_ds = PoseSequenceDataset(
            sequences=splits.X_val,
            targets=splits.y_val,
            sequence_length=sequence_length,
            feature_dim=feature_dim,
        )
        val_loader = DataLoader(
            val_ds,
            batch_size=batch_size,
            shuffle=False,
            num_workers=num_workers,
            drop_last=False,
        )

    test_ds = PoseSequenceDataset(
        sequences=splits.X_test,
        targets=splits.y_test,
        sequence_length=sequence_length,
        feature_dim=feature_dim,
    )
    test_loader = DataLoader(
        test_ds,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        drop_last=False,
    )

    return train_loader, val_loader, test_loader
