import argparse
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai.classifier.dataset import GroupAwareDatasetSplitter
from ai.classifier.preprocessor import DataPreprocessor
from ai.classifier.synthetic import BiomechanicalDataGenerator
from ai.classifier.temporal_pipeline import TemporalClassificationPipeline
from ai.classifier.temporal_trainer import TemporalModelTrainer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("TrainTemporalClassifier")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Train PyTorch Temporal Exercise Classifier (LSTM / GRU) on pose sequences."
    )
    parser.add_argument("--raw-dir", type=str, default="data/raw", help="Directory containing raw JSON session files.")
    parser.add_argument("--output-model", type=str, default="models/temporal_exercise_classifier.pt", help="Path to save trained PyTorch pipeline.")
    parser.add_argument("--rnn-type", type=str, default="lstm", choices=["lstm", "gru"], help="Recurrent backbone architecture.")
    parser.add_argument("--hidden-size", type=int, default=64, help="Hidden state dimension of RNN.")
    parser.add_argument("--num-layers", type=int, default=2, help="Number of stacked RNN layers.")
    parser.add_argument("--dropout", type=float, default=0.2, help="Dropout probability.")
    parser.add_argument("--unidirectional", action="store_true", help="Use unidirectional RNN instead of bidirectional.")
    parser.add_argument("--batch-size", type=int, default=32, help="Mini-batch size.")
    parser.add_argument("--epochs", type=int, default=60, help="Maximum training epochs.")
    parser.add_argument("--learning-rate", type=float, default=1e-3, help="Initial AdamW learning rate.")
    parser.add_argument("--patience", type=int, default=12, help="Early stopping patience.")
    parser.add_argument("--window-size", type=int, default=30, help="Temporal window length in frames.")
    parser.add_argument("--stride", type=int, default=10, help="Sliding window stride.")
    parser.add_argument("--generate-synthetic", action="store_true", help="Generate synthetic session dataset if none found.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility.")
    parser.add_argument("--metrics-out", type=str, default="reports/temporal_training_metrics.json", help="Path to save training metrics history.")
    return parser.parse_args()


def main():
    args = parse_args()
    logger.info("=== Phase 7: PyTorch Temporal Model Training Pipeline ===")

    raw_dir = Path(args.raw_dir)
    json_files = list(raw_dir.glob("*.json")) if raw_dir.exists() else []

    if not json_files:
        if args.generate_synthetic:
            logger.info(f"No raw data found in {raw_dir}. Generating synthetic exercise sessions...")
            generator = BiomechanicalDataGenerator()
            sessions = generator.generate_multiclass_dataset(
                num_subjects=5,
                sequences_per_class=5,
                frames_per_sequence=90,
                output_dir=raw_dir,
            )
        else:
            logger.error(
                f"No session JSON files found in {raw_dir}. "
                "Run data collection or pass --generate-synthetic to create synthetic training data."
            )
            sys.exit(1)
    else:
        preprocessor_temp = DataPreprocessor()
        sessions = preprocessor_temp.load_raw_sessions(raw_dir)

    logger.info(f"Processing {len(sessions)} sessions into temporal sequence windows (W={args.window_size}, S={args.stride})...")
    preprocessor = DataPreprocessor(
        window_size=args.window_size,
        stride=args.stride,
        min_detected_ratio=0.7,
    )
    raw_dataset = preprocessor.process_sessions_temporal(sessions)
    logger.info(
        f"Extracted temporal tensor: {raw_dataset.X.shape} "
        f"(N={raw_dataset.X.shape[0]} sequences, T={raw_dataset.sequence_length} frames, F={raw_dataset.feature_dim} features)"
    )

    # Leakage-free group splitting
    splitter = GroupAwareDatasetSplitter(test_size=0.2, val_size=0.15, random_state=args.seed)
    splits = splitter.split(raw_dataset)

    # Fit scaler on Train split and transform all splits
    preprocessor.fit_temporal(raw_dataset)
    splits.X_train = preprocessor.scaler.transform(
        splits.X_train.reshape(-1, raw_dataset.feature_dim)
    ).reshape(splits.X_train.shape).astype(raw_dataset.X.dtype)

    if len(splits.X_val) > 0:
        splits.X_val = preprocessor.scaler.transform(
            splits.X_val.reshape(-1, raw_dataset.feature_dim)
        ).reshape(splits.X_val.shape).astype(raw_dataset.X.dtype)

    splits.X_test = preprocessor.scaler.transform(
        splits.X_test.reshape(-1, raw_dataset.feature_dim)
    ).reshape(splits.X_test.shape).astype(raw_dataset.X.dtype)

    # Initialize and run PyTorch temporal trainer
    trainer = TemporalModelTrainer(
        rnn_type=args.rnn_type,
        hidden_size=args.hidden_size,
        num_layers=args.num_layers,
        dropout=args.dropout,
        bidirectional=not args.unidirectional,
        learning_rate=args.learning_rate,
        batch_size=args.batch_size,
        epochs=args.epochs,
        patience=args.patience,
        seed=args.seed,
    )

    result = trainer.train(splits)

    # Save trained pipeline
    out_model_path = Path(args.output_model)
    out_model_path.parent.mkdir(parents=True, exist_ok=True)

    pipeline = TemporalClassificationPipeline(
        model=result.model,
        preprocessor=preprocessor,
        classes=splits.classes,
        model_config=result.model.to_config(),
        metadata={
            **result.metadata,
            "hyperparameters": result.hyperparameters,
            "best_epoch": result.best_epoch,
            "best_val_loss": result.best_val_loss,
            "best_val_acc": result.best_val_acc,
            "best_val_f1": result.best_val_f1,
        },
    )
    pipeline.save(out_model_path)
    logger.info(f"Successfully saved trained temporal model to: {out_model_path}")

    # Save training metrics history
    metrics_path = Path(args.metrics_out)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    history_dict = asdict(result.history)
    history_dict["best_epoch"] = result.best_epoch
    history_dict["best_val_loss"] = result.best_val_loss
    history_dict["best_val_acc"] = result.best_val_acc
    history_dict["best_val_f1"] = result.best_val_f1
    history_dict["classes"] = splits.classes
    history_dict["hyperparameters"] = result.hyperparameters

    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(history_dict, f, indent=2)
    logger.info(f"Saved training history to: {metrics_path}")

    print("\n" + "=" * 60)
    print(f"  TEMPORAL MODEL TRAINING SUMMARY ({args.rnn_type.upper()})")
    print("=" * 60)
    print(f"  Best Epoch:           {result.best_epoch} / {len(result.history.epochs)}")
    print(f"  Best Validation Loss: {result.best_val_loss:.4f}")
    print(f"  Best Validation Acc:  {result.best_val_acc * 100:.2f}%")
    print(f"  Best Validation F1:   {result.best_val_f1:.4f}")
    print(f"  Final Train Loss:     {result.final_train_loss:.4f}")
    print(f"  Final Train Acc:      {result.final_train_acc * 100:.2f}%")
    print(f"  Device:               {result.device}")
    print(f"  Model Saved To:       {out_model_path}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
