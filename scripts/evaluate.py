"""
evaluate.py — Giai đoạn 6 (S6.2)
---------------------------------
CLI đánh giá 1 hoặc nhiều run đã train: tải best.pt, chạy lại inference trên
test set, xuất bảng so sánh model + kiểm tra THIÊN LỆCH NGUỒN (accuracy theo
từng `source` trong test set có tụt bất thường so với accuracy tổng thể không).

LƯU Ý — kiểm tra TEMPORAL: cột `first_seen` trong data/interim/labels.csv
rỗng 100% (MalwareBazaar API có trả về nhưng chưa được merge vào bước gán
nhãn; figshare/RAT vốn không có ngày per-sample) → không có dữ liệu để tách
theo thời gian phát hiện mẫu. Script chỉ kiểm tra bias NGUỒN; giới hạn temporal
được ghi rõ trong output và docs/BACKLOG.md S6.2.

Usage:
    python scripts/evaluate.py --run experiments/detect_resnet50_224_1783076342
    python scripts/evaluate.py --filter detect_        # tất cả run khớp trong experiments/
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import torch
from torch.utils.data import DataLoader

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.datasets.malware_dataset import MalwareImageDataset  # noqa: E402
from src.models.factory import build_model                    # noqa: E402
from src.utils.config import get                              # noqa: E402
from src.evaluation.metrics import compute_metrics             # noqa: E402

BIAS_WARN_GAP = 0.05   # cảnh báo nếu acc nhóm thấp hơn acc tổng thể > 5 điểm %
MIN_GROUP_N = 20        # nhóm nhỏ hơn n này: vẫn báo cáo nhưng gắn cờ "n nhỏ, không đáng tin"


def load_run(run_dir: Path):
    cfg = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = build_model(get(cfg, "model.name", "vgg16"), get(cfg, "model.num_classes", 2),
                        False, False, get(cfg, "model.in_chans", 3)).to(device)
    ckpt = torch.load(run_dir / "best.pt", map_location=device, weights_only=False)
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    return cfg, model, device


def build_test_loader(cfg, test_csv_override=None):
    sd = Path(get(cfg, "data.split_dir", "data/interim"))
    stats = get(cfg, "data.channel_stats", "data/interim/channel_stats.json")
    img = get(cfg, "data.img_size", 224)
    chan = get(cfg, "data.channels", "full")
    prefix = get(cfg, "data.split_prefix", "split")
    image_root = get(cfg, "data.image_root", None)
    # --test-csv: đánh giá trên tập test ĐÃ LÀM SẠCH NHÃN (split_test_clean.csv)
    csv_path = Path(test_csv_override) if test_csv_override else sd / f"{prefix}_test.csv"

    ds = MalwareImageDataset(csv_path, stats, img, False, False, chan, image_root)
    loader = DataLoader(ds, batch_size=get(cfg, "data.batch_size", 32), shuffle=False,
                        num_workers=get(cfg, "data.num_workers", 4), pin_memory=True)
    return loader, csv_path


@torch.no_grad()
def predict(model, loader, device):
    ys, ps, probs = [], [], []
    for x, y in loader:
        x = x.to(device, non_blocking=True)
        out = model(x)
        prob = torch.softmax(out, dim=1)[:, 1]
        ps += out.argmax(1).cpu().tolist()
        probs += prob.cpu().tolist()
        ys += y.tolist()
    return ys, ps, probs


def read_meta(csv_path: Path) -> list[dict]:
    with open(csv_path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def group_bias_table(meta: list[dict], y_true, y_pred, y_prob, key: str, overall_acc: float) -> list[dict]:
    """Gộp theo `key` (vd 'source') → acc/f1 mỗi nhóm + lệch so với acc tổng thể."""
    groups = defaultdict(lambda: {"y": [], "p": [], "pr": []})
    for m, yt, yp, ypr in zip(meta, y_true, y_pred, y_prob):
        g = groups[m[key]]
        g["y"].append(yt); g["p"].append(yp); g["pr"].append(ypr)

    rows = []
    for name, g in groups.items():
        n = len(g["y"])
        single_class = len(set(g["y"])) < 2
        met = compute_metrics(g["y"], g["p"], g["pr"])
        rows.append({
            "group": name, "n": n,
            "acc": met["acc"], "f1": float("nan") if single_class else met["f1"],
            "delta_acc": met["acc"] - overall_acc,
            "small_n": n < MIN_GROUP_N,
            "single_class": single_class,
        })
    rows.sort(key=lambda r: -r["n"])
    return rows


def print_bias_table(rows: list[dict], overall: dict, title: str) -> None:
    print(f"\n=== {title} (overall acc={overall['acc']:.4f}, f1={overall['f1']:.4f}, n={sum(r['n'] for r in rows)}) ===")
    header = f'{"Group":<22} {"n":<6} {"Acc":<8} {"F1":<8} {"Δacc vs overall":<16} {"Ghi chú"}'
    print(header); print("-" * len(header))
    any_warn = False
    for r in rows:
        flags = []
        if r["delta_acc"] < -BIAS_WARN_GAP:
            flags.append("CẢNH BÁO: acc tụt")
            any_warn = True
        if r["small_n"]:
            flags.append(f"n<{MIN_GROUP_N}, không đáng tin")
        if r["single_class"]:
            flags.append("chỉ 1 lớp trong nhóm, F1 n/a")
        f1_s = "-" if math.isnan(r["f1"]) else f"{r['f1']:.4f}"
        print(f'{r["group"]:<22} {r["n"]:<6} {r["acc"]:.4f}   {f1_s:<8} {r["delta_acc"]:+.4f}           {"; ".join(flags)}')
    if not any_warn:
        print(f"(không có nhóm nào tụt quá {BIAS_WARN_GAP:.0%} so với acc tổng thể)")


def main():
    ap = argparse.ArgumentParser(description="Đánh giá run + kiểm tra bias nguồn (S6.2).")
    ap.add_argument("--run", type=Path, help="1 thư mục run cụ thể (vd experiments/detect_resnet50_224_...).")
    ap.add_argument("--exp-dir", type=Path, default=Path("experiments"))
    ap.add_argument("--filter", default="", help="Chỉ lấy run có chuỗi này trong tên (khi không dùng --run).")
    ap.add_argument("--out-dir", type=Path, default=Path("results/metrics"))
    ap.add_argument("--test-csv", type=Path, default=None,
                    help="Ghi đè tập test (vd data/interim/split_test_clean.csv) để đánh giá trên nhãn đã làm sạch.")
    args = ap.parse_args()

    if args.run:
        run_dirs = [args.run]
    else:
        if not args.filter:
            raise SystemExit("Cần --run <thư mục> hoặc --filter <chuỗi khớp tên run>.")
        run_dirs = [d for d in sorted(args.exp_dir.iterdir())
                    if d.is_dir() and args.filter in d.name and (d / "best.pt").exists()]
        if not run_dirs:
            raise SystemExit(f"Không thấy run nào khớp '{args.filter}' trong {args.exp_dir}")

    summary_rows, bias_rows_all = [], []
    for run_dir in run_dirs:
        print(f"\n{'=' * 70}\nRun: {run_dir.name}\n{'=' * 70}")
        cfg, model, device = load_run(run_dir)
        loader, csv_path = build_test_loader(cfg, args.test_csv)
        y_true, y_pred, y_prob = predict(model, loader, device)
        meta = read_meta(csv_path)
        if len(meta) != len(y_true):
            raise RuntimeError(f"Số dòng meta ({len(meta)}) != số dự đoán ({len(y_true)}) — "
                               f"kiểm tra lại {csv_path}")

        overall = compute_metrics(y_true, y_pred, y_prob)
        print(f"Test: n={len(y_true)} acc={overall['acc']:.4f} precision={overall['precision']:.4f} "
              f"recall={overall['recall']:.4f} f1={overall['f1']:.4f} roc_auc={overall['roc_auc']:.4f}")
        summary_rows.append({
            "run": run_dir.name, "model": get(cfg, "model.name", ""),
            "channels": get(cfg, "data.channels", "full"), "img_size": get(cfg, "data.img_size", 224),
            "n_test": len(y_true),
            "acc": overall["acc"], "precision": overall["precision"],
            "recall": overall["recall"], "f1": overall["f1"], "roc_auc": overall["roc_auc"],
        })

        src_rows = group_bias_table(meta, y_true, y_pred, y_prob, "source", overall["acc"])
        print_bias_table(src_rows, overall, "Bias theo NGUỒN (source)")
        for r in src_rows:
            bias_rows_all.append({"run": run_dir.name, "group_type": "source", **r,
                                  "overall_acc": overall["acc"]})

    args.out_dir.mkdir(parents=True, exist_ok=True)

    summary_cols = ["run", "model", "channels", "img_size", "n_test",
                    "acc", "precision", "recall", "f1", "roc_auc"]
    with open(args.out_dir / "evaluate_summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=summary_cols)
        w.writeheader()
        for r in summary_rows:
            w.writerow(r)

    bias_cols = ["run", "group_type", "group", "n", "acc", "f1", "delta_acc",
                "small_n", "single_class", "overall_acc"]
    with open(args.out_dir / "bias_source.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=bias_cols)
        w.writeheader()
        for r in bias_rows_all:
            w.writerow({k: r.get(k) for k in bias_cols})

    print(f"\n-> Đã lưu: {args.out_dir}/evaluate_summary.csv, {args.out_dir}/bias_source.csv")
    print(
        "\nGIỚI HẠN ĐÃ BIẾT — kiểm tra TEMPORAL bias (accuracy theo thời gian phát hiện mẫu) KHÔNG\n"
        "thực hiện được: cột first_seen trong data/interim/labels.csv rỗng 100% (MalwareBazaar API\n"
        "có trả về first_seen nhưng chưa được merge vào bước gán nhãn; figshare/RAT vốn không có\n"
        "ngày per-sample). Đây là giới hạn đã ghi nhận của đồ án (docs/BACKLOG.md S6.2), không suy\n"
        "ra từ số liệu giả định."
    )


if __name__ == "__main__":
    main()
