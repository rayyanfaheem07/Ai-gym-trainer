import copy
import logging
import platform
import random
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import accuracy_score, f1_score
from torch.optim.lr_scheduler import ReduceLROnPlateau

from ai.classifier.dataset import DatasetSplits
from ai.classifier.temporal_dataset import create_temporal_dataloaders
from ai.classifier.temporal_model import PoseSequenceClassifier

logger = logging.getLogger("TemporalTrainer")


def set_seed(seed: int = 42):
    """Sets deterministic random seeds across Python, NumPy, and PyTorch."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


@dataclass
class TrainingHistory:
    epochs: List[int]
    train_loss: List[float]
    val_loss: List[float]
    train_acc: List[float]
    val_acc: List[float]
    val_f1: List[float]
    learning_rates: List[float]


@dataclass
class TemporalTrainingResult:
    model: PoseSequenceClassifier
    history: TrainingHistory
    best_epoch: int
    best_val_loss: float
    best_val_acc: float
    best_val_f1: float
    final_train_acc: float
    final_train_loss: float
    hyperparameters: Dict[str, Any]
    classes: List[str]
    device: str
    metadata: Dict[str, Any]


class TemporalModelTrainer:
    """
    Trains and validates PyTorch temporal exercise sequence classifiers (LSTM / GRU).
    Includes automatic CPU/GPU detection, early stopping, learning rate scheduling,
    class imbalance handling, and comprehensive metrics tracking.
    """

    def __init__(
        self,
        rnn_type: str = "lstm",
        hidden_size: int = 64,
        num_layers: int = 2,
        dropout: float = 0.2,
        bidirectional: bool = True,
        learning_rate: float = 1e-3,
        weight_decay: float = 1e-4,
        batch_size: int = 32,
        epochs: int = 60,
        patience: int = 12,
        min_delta: float = 1e-4,
        seed: int = 42,
        device: Optional[str] = None,
        use_class_weights: bool = True,
    ):
        self.rnn_type = rnn_type.lower()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.dropout = dropout
        self.bidirectional = bidirectional
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.batch_size = batch_size
        self.epochs = epochs
        self.patience = patience
        self.min_delta = min_delta
        self.seed = seed
        self.use_class_weights = use_class_weights

        # Device detection
        if device is not None:
            self.device = torch.device(device)
        else:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def _compute_class_weights(self, y_train: np.ndarray, num_classes: int) -> Optional[torch.Tensor]:
        """Calculates balanced class weights to mitigate class frequency imbalance."""
        if not self.use_class_weights or len(y_train) == 0:
            return None

        counts = np.bincount(y_train, minlength=num_classes)
        total = len(y_train)
        weights = []
        for c in counts:
            if c > 0:
                weights.append(total / (num_classes * float(c)))
            else:
                weights.append(1.0)

        weight_tensor = torch.tensor(weights, dtype=torch.float32, device=self.device)
        logger.info(f"Class weights computed: {[round(w, 3) for w in weights]}")
        return weight_tensor

    def train(self, splits: DatasetSplits) -> TemporalTrainingResult:
        """
        Executes complete training and validation pipeline with early stopping.
        """
        set_seed(self.seed)

        if len(splits.X_train) == 0:
            raise ValueError("Training dataset contains 0 samples.")

        num_classes = len(splits.classes)
        seq_len = splits.X_train.shape[1]
        input_size = splits.X_train.shape[2]

        # Build PyTorch model
        model = PoseSequenceClassifier(
            input_size=input_size,
            hidden_size=self.hidden_size,
            num_layers=self.num_layers,
            num_classes=num_classes,
            rnn_type=self.rnn_type,
            bidirectional=self.bidirectional,
            dropout=self.dropout,
            sequence_length=seq_len,
        ).to(self.device)

        logger.info(
            f"Initialized {self.rnn_type.upper()} model ({model.get_num_parameters():,} params, "
            f"{model.get_model_size_kb():.1f} KB) on device: {self.device}"
        )

        # Create DataLoaders
        train_loader, val_loader, _ = create_temporal_dataloaders(
            splits=splits,
            batch_size=self.batch_size,
            num_workers=0,
        )

        # Loss function with optional class weighting
        class_weights = self._compute_class_weights(splits.y_train, num_classes)
        criterion = nn.CrossEntropyLoss(weight=class_weights)

        # Optimizer and Scheduler
        optimizer = torch.optim.AdamW(
            model.parameters(),
            lr=self.learning_rate,
            weight_decay=self.weight_decay,
        )
        scheduler = ReduceLROnPlateau(
            optimizer,
            mode="min",
            factor=0.5,
            patience=4,
            min_lr=1e-5,
        )

        # Tracking variables
        history = TrainingHistory(
            epochs=[],
            train_loss=[],
            val_loss=[],
            train_acc=[],
            val_acc=[],
            val_f1=[],
            learning_rates=[],
        )

        best_val_loss = float("inf")
        best_val_acc = 0.0
        best_val_f1 = 0.0
        best_epoch = 0
        best_model_weights = copy.deepcopy(model.state_dict())
        patience_counter = 0

        logger.info(f"Starting training for up to {self.epochs} epochs (early stopping patience={self.patience})...")

        for epoch in range(1, self.epochs + 1):
            # --- Training Phase ---
            model.train()
            total_train_loss = 0.0
            all_train_preds = []
            all_train_targets = []

            for batch_x, batch_y in train_loader:
                batch_x = batch_x.to(self.device)
                batch_y = batch_y.to(self.device)

                optimizer.zero_grad()
                logits = model(batch_x)
                loss = criterion(logits, batch_y)
                loss.backward()

                # Gradient clipping to stabilize RNN training
                nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
                optimizer.step()

                total_train_loss += loss.item() * len(batch_y)
                preds = torch.argmax(logits, dim=-1).detach().cpu().numpy()
                all_train_preds.extend(preds)
                all_train_targets.extend(batch_y.detach().cpu().numpy())

            epoch_train_loss = total_train_loss / len(splits.X_train)
            epoch_train_acc = float(accuracy_score(all_train_targets, all_train_preds))

            # --- Validation Phase ---
            model.eval()
            total_val_loss = 0.0
            all_val_preds = []
            all_val_targets = []

            eval_loader = val_loader if val_loader is not None else train_loader
            eval_size = len(splits.X_val) if val_loader is not None else len(splits.X_train)

            with torch.no_grad():
                for batch_x, batch_y in eval_loader:
                    batch_x = batch_x.to(self.device)
                    batch_y = batch_y.to(self.device)

                    logits = model(batch_x)
                    loss = criterion(logits, batch_y)

                    total_val_loss += loss.item() * len(batch_y)
                    preds = torch.argmax(logits, dim=-1).cpu().numpy()
                    all_val_preds.extend(preds)
                    all_val_targets.extend(batch_y.cpu().numpy())

            epoch_val_loss = total_val_loss / eval_size
            epoch_val_acc = float(accuracy_score(all_val_targets, all_val_preds))
            epoch_val_f1 = float(f1_score(all_val_targets, all_val_preds, average="macro", zero_division=0))

            current_lr = optimizer.param_groups[0]["lr"]
            scheduler.step(epoch_val_loss)

            # Record history
            history.epochs.append(epoch)
            history.train_loss.append(round(epoch_train_loss, 5))
            history.val_loss.append(round(epoch_val_loss, 5))
            history.train_acc.append(round(epoch_train_acc, 4))
            history.val_acc.append(round(epoch_val_acc, 4))
            history.val_f1.append(round(epoch_val_f1, 4))
            history.learning_rates.append(current_lr)

            if epoch % 5 == 0 or epoch == 1 or epoch == self.epochs:
                logger.info(
                    f"Epoch [{epoch:02d}/{self.epochs:02d}] - "
                    f"Train Loss: {epoch_train_loss:.4f}, Train Acc: {epoch_train_acc * 100:.1f}% | "
                    f"Val Loss: {epoch_val_loss:.4f}, Val Acc: {epoch_val_acc * 100:.1f}%, Val F1: {epoch_val_f1:.4f} "
                    f"(lr: {current_lr:.1e})"
                )

            # Early Stopping Check (monitor val_loss)
            if epoch_val_loss < (best_val_loss - self.min_delta):
                best_val_loss = epoch_val_loss
                best_val_acc = epoch_val_acc
                best_val_f1 = epoch_val_f1
                best_epoch = epoch
                best_model_weights = copy.deepcopy(model.state_dict())
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= self.patience:
                    logger.info(
                        f"Early stopping triggered at epoch {epoch} (no improvement over best val loss {best_val_loss:.4f} "
                        f"at epoch {best_epoch})."
                    )
                    break

        # Restore best model checkpoint
        model.load_state_dict(best_model_weights)
        model.eval()

        logger.info(
            f"Training finished. Best Epoch: {best_epoch} with Val Loss: {best_val_loss:.4f}, "
            f"Val Acc: {best_val_acc * 100:.2f}%, Val F1: {best_val_f1:.4f}"
        )

        metadata = {
            "python_version": sys.version.split()[0],
            "pytorch_version": torch.__version__,
            "platform": platform.platform(),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "num_train_samples": len(splits.X_train),
            "num_val_samples": len(splits.X_val),
            "num_test_samples": len(splits.X_test),
        }

        hyperparameters = {
            "rnn_type": self.rnn_type,
            "hidden_size": self.hidden_size,
            "num_layers": self.num_layers,
            "dropout": self.dropout,
            "bidirectional": self.bidirectional,
            "learning_rate": self.learning_rate,
            "weight_decay": self.weight_decay,
            "batch_size": self.batch_size,
            "epochs_run": len(history.epochs),
            "early_stopping_patience": self.patience,
            "seed": self.seed,
            "use_class_weights": self.use_class_weights,
        }

        return TemporalTrainingResult(
            model=model,
            history=history,
            best_epoch=best_epoch,
            best_val_loss=best_val_loss,
            best_val_acc=best_val_acc,
            best_val_f1=best_val_f1,
            final_train_acc=history.train_acc[-1] if history.train_acc else 0.0,
            final_train_loss=history.train_loss[-1] if history.train_loss else 0.0,
            hyperparameters=hyperparameters,
            classes=splits.classes,
            device=str(self.device),
            metadata=metadata,
        )
