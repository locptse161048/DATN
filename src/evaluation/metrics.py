"""
metrics.py — Giai đoạn 6 (S6.1)
--------------------------------
Module đánh giá dùng chung: tính metrics (Acc/P/R/F1/ROC-AUC/confusion) và
xuất biểu đồ (confusion matrix, ROC curve, PR curve) ra file ảnh.

Dùng cho cả val trong lúc train (train.py) lẫn test cuối cùng (evaluate.py).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")  # không cần display, chỉ lưu file
import matplotlib.pyplot as plt

from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, roc_curve, precision_recall_curve,
    average_precision_score,
)

CLASS_NAMES = ("benign", "malware")


def compute_metrics(y_true, y_pred, y_prob) -> dict:
    """Acc, Precision, Recall, F1, ROC-AUC, confusion matrix (2×2)."""
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    y_prob = np.asarray(y_prob)

    m = {
        "acc": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
    }
    try:
        m["roc_auc"] = float(roc_auc_score(y_true, y_prob))
    except ValueError:
        m["roc_auc"] = float("nan")
    m["confusion"] = confusion_matrix(y_true, y_pred, labels=[0, 1]).tolist()
    return m


def plot_confusion_matrix(y_true, y_pred, out_path,
                          class_names=CLASS_NAMES, normalize: bool = False) -> None:
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    disp = cm.astype(float) / cm.sum(axis=1, keepdims=True) if normalize else cm

    fig, ax = plt.subplots(figsize=(4.5, 4))
    im = ax.imshow(disp, cmap="Blues")
    ax.set_xticks(range(len(class_names)), labels=class_names)
    ax.set_yticks(range(len(class_names)), labels=class_names)
    ax.set_xlabel("Dự đoán")
    ax.set_ylabel("Thực tế")
    ax.set_title("Confusion Matrix" + (" (normalized)" if normalize else ""))

    thresh = disp.max() / 2 if disp.max() > 0 else 0.5
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            label = f"{disp[i, j]:.2f}" if normalize else str(cm[i, j])
            ax.text(j, i, label, ha="center", va="center",
                    color="white" if disp[i, j] > thresh else "black")

    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_roc_curve(y_true, y_prob, out_path) -> None:
    fpr, tpr, _ = roc_curve(y_true, y_prob)
    auc = roc_auc_score(y_true, y_prob)

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot(fpr, tpr, label=f"AUC = {auc:.4f}", color="C0", linewidth=2)
    ax.plot([0, 1], [0, 1], "--", color="gray", linewidth=1, label="Random")
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("ROC Curve")
    ax.legend(loc="lower right")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_pr_curve(y_true, y_prob, out_path) -> None:
    precision, recall, _ = precision_recall_curve(y_true, y_prob)
    ap = average_precision_score(y_true, y_prob)

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot(recall, precision, label=f"AP = {ap:.4f}", color="C1", linewidth=2)
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title("Precision-Recall Curve")
    ax.legend(loc="lower left")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_training_curves(history: list[dict], out_path) -> None:
    """history: list các dict {epoch, loss, val_acc, val_f1, val_auc} theo epoch."""
    epochs = [h["epoch"] for h in history]

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].plot(epochs, [h["loss"] for h in history], color="C3")
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("Train loss")
    axes[0].set_title("Loss theo epoch")

    axes[1].plot(epochs, [h["val_f1"] for h in history], label="val F1", color="C0")
    axes[1].plot(epochs, [h["val_auc"] for h in history], label="val ROC-AUC", color="C2")
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylabel("Score")
    axes[1].set_title("Val F1 / ROC-AUC theo epoch")
    axes[1].legend()

    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def save_evaluation_report(y_true, y_pred, y_prob, out_dir,
                           prefix: str = "test", class_names=CLASS_NAMES) -> dict:
    """Tính metrics + lưu JSON + 2 biểu đồ (confusion matrix, ROC) + PR curve."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    metrics = compute_metrics(y_true, y_pred, y_prob)
    (out_dir / f"{prefix}_metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False))

    plot_confusion_matrix(y_true, y_pred, out_dir / f"{prefix}_confusion_matrix.png",
                          class_names=class_names)
    plot_roc_curve(y_true, y_prob, out_dir / f"{prefix}_roc_curve.png")
    plot_pr_curve(y_true, y_prob, out_dir / f"{prefix}_pr_curve.png")

    return metrics


__all__ = [
    "compute_metrics", "plot_confusion_matrix", "plot_roc_curve",
    "plot_pr_curve", "plot_training_curves", "save_evaluation_report",
    "CLASS_NAMES",
]
