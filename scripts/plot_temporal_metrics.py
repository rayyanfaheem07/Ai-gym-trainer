import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib.pyplot as plt
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("PlotTemporalMetrics")


def parse_args():
    parser = argparse.ArgumentParser(description="Plot PyTorch temporal training metrics and confusion matrix.")
    parser.add_argument("--metrics-json", type=str, default="reports/temporal_training_metrics.json")
    parser.add_argument("--eval-json", type=str, default="reports/temporal_evaluation_report.json")
    parser.add_argument("--output-dir", type=str, default="reports")
    return parser.parse_args()


def plot_training_curves(metrics: dict, out_dir: Path):
    epochs = metrics["epochs"]
    train_loss = metrics["train_loss"]
    val_loss = metrics["val_loss"]
    train_acc = [acc * 100 for acc in metrics["train_acc"]]
    val_acc = [acc * 100 for acc in metrics["val_acc"]]
    val_f1 = metrics.get("val_f1", [])
    best_epoch = metrics.get("best_epoch", 1)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    # 1. Loss Subplot
    ax1 = axes[0]
    ax1.plot(epochs, train_loss, label="Training Loss", color="#1f77b4", linewidth=2)
    ax1.plot(epochs, val_loss, label="Validation Loss", color="#ff7f0e", linewidth=2)
    ax1.axvline(x=best_epoch, color="#2ca02c", linestyle="--", alpha=0.7, label=f"Best Checkpoint (Ep {best_epoch})")
    ax1.set_title("Training & Validation Loss", fontsize=13, fontweight="bold")
    ax1.set_xlabel("Epoch", fontsize=11)
    ax1.set_ylabel("CrossEntropy Loss", fontsize=11)
    ax1.legend(loc="upper right", frameon=True)
    ax1.grid(True, linestyle="--", alpha=0.5)

    # 2. Accuracy & F1 Subplot
    ax2 = axes[1]
    ax2.plot(epochs, train_acc, label="Training Acc (%)", color="#1f77b4", linewidth=2)
    ax2.plot(epochs, val_acc, label="Validation Acc (%)", color="#ff7f0e", linewidth=2)
    if val_f1:
        ax2.plot(epochs, [f * 100 for f in val_f1], label="Validation F1 (%)", color="#2ca02c", linewidth=1.8, linestyle=":")
    ax2.axvline(x=best_epoch, color="#2ca02c", linestyle="--", alpha=0.7, label=f"Best Checkpoint (Ep {best_epoch})")
    ax2.set_title("Training & Validation Accuracy / F1", fontsize=13, fontweight="bold")
    ax2.set_xlabel("Epoch", fontsize=11)
    ax2.set_ylabel("Score (%)", fontsize=11)
    ax2.set_ylim(0, 105)
    ax2.legend(loc="lower right", frameon=True)
    ax2.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    dashboard_path = out_dir / "temporal_training_dashboard.png"
    plt.savefig(dashboard_path, dpi=200)
    plt.close()
    logger.info(f"Saved training curves dashboard to {dashboard_path}")


def plot_confusion_matrix(eval_data: dict, out_dir: Path):
    cm = np.array(eval_data["confusion_matrix"])
    classes = eval_data["classes"]

    fig, ax = plt.subplots(figsize=(8, 7))
    cax = ax.matshow(cm, cmap=plt.cm.Blues, alpha=0.85)

    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            val = cm[i, j]
            color = "white" if val > (cm.max() / 2) else "black"
            ax.text(j, i, str(val), va="center", ha="center", color=color, fontsize=12, fontweight="bold")

    fig.colorbar(cax, fraction=0.046, pad=0.04)
    ax.set_xticks(range(len(classes)))
    ax.set_yticks(range(len(classes)))
    ax.set_xticklabels(classes, rotation=45, ha="left", fontsize=10)
    ax.set_yticklabels(classes, fontsize=10)
    ax.set_xlabel("Predicted Exercise", fontsize=12, fontweight="bold", labelpad=10)
    ax.set_ylabel("Actual Ground Truth", fontsize=12, fontweight="bold", labelpad=10)
    ax.set_title("Confusion Matrix - PyTorch Temporal Classifier", fontsize=13, fontweight="bold", pad=20)

    plt.tight_layout()
    cm_path = out_dir / "temporal_confusion_matrix.png"
    plt.savefig(cm_path, dpi=200)
    plt.close()
    logger.info(f"Saved confusion matrix plot to {cm_path}")


def main():
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    metrics_path = Path(args.metrics_json)
    if metrics_path.exists():
        with open(metrics_path, "r", encoding="utf-8") as f:
            metrics_data = json.load(f)
        plot_training_curves(metrics_data, out_dir)
    else:
        logger.warning(f"Metrics JSON not found at {metrics_path}")

    eval_path = Path(args.eval_json)
    if eval_path.exists():
        with open(eval_path, "r", encoding="utf-8") as f:
            eval_data = json.load(f)
        plot_confusion_matrix(eval_data, out_dir)
    else:
        logger.warning(f"Evaluation JSON not found at {eval_path}")


if __name__ == "__main__":
    main()
