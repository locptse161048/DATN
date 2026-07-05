"""
aggregate_results.py — Gom nhiều run trong experiments/ thành 1 bảng so sánh.
Dùng cho ablation kênh (S5b.1) và so sánh model — kèm cả THỜI GIAN + bộ nhớ + FLOPs.

Mỗi run cần: cost.json (do train.py sinh) + figures/test_metrics.json (test) hoặc
best_metrics.json (val, fallback).

Usage:
    python scripts/aggregate_results.py                      # gom tất cả run
    python scripts/aggregate_results.py --filter ablation    # chỉ run có 'ablation' trong tên
    python scripts/aggregate_results.py --out results/metrics/ablation_summary.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def _read_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def collect(exp_dir: Path, name_filter: str) -> list[dict]:
    rows = []
    for run in sorted(exp_dir.iterdir()):
        if not run.is_dir():
            continue
        cost = _read_json(run / "cost.json")
        if not cost:
            continue
        if name_filter and name_filter not in cost.get("run_name", run.name):
            continue
        # test ưu tiên; fallback val (best_metrics.json)
        met = _read_json(run / "figures" / "test_metrics.json")
        split = "test"
        if not met:
            met = _read_json(run / "best_metrics.json")
            split = "val"
        rows.append({
            "run": cost.get("run_name", run.name),
            "model": cost.get("model", ""),
            "channels": cost.get("channels", ""),
            "in_chans": cost.get("in_chans", ""),
            "split": split,
            "acc": met.get("acc"),
            "precision": met.get("precision"),
            "recall": met.get("recall"),
            "f1": met.get("f1"),
            "roc_auc": met.get("roc_auc"),
            "params_m": cost.get("params_m"),
            "gmacs": cost.get("gmacs"),
            "avg_epoch_s": cost.get("avg_epoch_time_s"),
            "total_time_min": (cost.get("total_time_s") or 0) / 60.0,
            "peak_mem_mb": cost.get("peak_gpu_mem_mb"),
            "n_epochs": cost.get("n_epochs"),
        })
    return rows


def _fmt(v, nd=4):
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


def main():
    ap = argparse.ArgumentParser(description="Gom experiments/ → bảng so sánh.")
    ap.add_argument("--exp-dir", type=Path, default=Path("experiments"))
    ap.add_argument("--filter", default="", help="Chỉ lấy run có chuỗi này trong tên.")
    ap.add_argument("--out", type=Path, default=Path("results/metrics/summary.csv"))
    args = ap.parse_args()

    rows = collect(args.exp_dir, args.filter)
    if not rows:
        raise SystemExit(f"Không thấy run nào (cost.json) trong {args.exp_dir}")
    rows.sort(key=lambda r: (r["model"], r["channels"]))

    cols = ["model", "channels", "in_chans", "split", "acc", "precision", "recall",
            "f1", "roc_auc", "params_m", "gmacs", "avg_epoch_s", "total_time_min",
            "peak_mem_mb", "n_epochs"]
    # in bảng
    widths = {c: max(len(c), max(len(_fmt(r.get(c))) for r in rows)) for c in cols}
    line = " | ".join(c.ljust(widths[c]) for c in cols)
    print(line); print("-" * len(line))
    for r in rows:
        print(" | ".join(_fmt(r.get(c)).ljust(widths[c]) for c in cols))

    # lưu CSV
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["run"] + cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in ["run"] + cols})
    print(f"\n-> Da luu bang: {args.out}  ({len(rows)} run)")


if __name__ == "__main__":
    main()
