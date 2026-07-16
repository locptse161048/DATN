"""
analyze_grid.py — Tổng hợp lưới hợp nhất 5×3 (S5b.1)
------------------------------------------------------
Đọc toàn bộ run `experiments/sweep_{resnet50,convnext_tiny}_*` (mỗi run cần
`cost.json` + `figures/test_metrics.json`, do train.py tự sinh), rồi:

  1. Gộp theo (model, channels, img_size) → mean±std qua seed (bảng lưới,
     đúng định dạng docs/EXPERIMENTS.md §2).
  2. Kiểm định thống kê (paired t-test trên seed) cho TRỤC ĐỘ PHÂN GIẢI —
     bắt buộc theo docs/EXPERIMENTS.md §6 trước khi kết luận "224 ≈ 336 ≈ 448".
  3. Biểu đồ Pareto accuracy-vs-cost (kênh 'full', cả 2 model) làm nổi 224².

Usage:
    python scripts/analyze_grid.py
    python scripts/analyze_grid.py --exp-dir experiments --out-dir results
"""

from __future__ import annotations

import argparse
import json
import re
import statistics as st
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.evaluation.stats import paired_ttest  # noqa: E402

SIZES = [224, 336, 448]
CHANNEL_ORDER = ["gray1", "gray3", "+entropy", "+ascii", "full"]
SEED_RE = re.compile(r"_s(\d+)$")


def _read_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def collect(exp_dir: Path, prefix: str, variant: str = "clean") -> list[dict]:
    """Đọc mọi run experiments/{prefix}* có đủ cost.json + test_metrics.json.

    variant='clean'    -> chỉ run có '_clean' trong tên (nhãn đã làm sạch).
    variant='original' -> chỉ run KHÔNG có '_clean' (nhãn gốc).
    Cần thiết vì run clean cũng bắt đầu bằng cùng prefix -> phải tách kẻo trộn lẫn.
    """
    rows = []
    for run in sorted(exp_dir.iterdir()):
        if not run.is_dir() or not run.name.startswith(prefix):
            continue
        is_clean = "_clean" in run.name
        if variant == "clean" and not is_clean:
            continue
        if variant == "original" and is_clean:
            continue
        cost = _read_json(run / "cost.json")
        met = _read_json(run / "figures" / "test_metrics.json")
        if not cost or not met:
            continue
        m = SEED_RE.search(cost.get("run_name", run.name))
        rows.append({
            "run": run.name,
            "model": cost.get("model"),
            "channels": cost.get("channels"),
            "img_size": cost.get("img_size"),
            "seed": int(m.group(1)) if m else None,
            "acc": met.get("acc"), "precision": met.get("precision"),
            "recall": met.get("recall"), "f1": met.get("f1"),
            "roc_auc": met.get("roc_auc"),
            "avg_epoch_time_s": cost.get("avg_epoch_time_s"),
            "peak_gpu_mem_mb": cost.get("peak_gpu_mem_mb"),
            "gmacs": cost.get("gmacs"),
        })
    return rows


def _mean_std(vals: list) -> tuple:
    vals = [v for v in vals if v is not None]
    if not vals:
        return None, None
    if len(vals) == 1:
        return vals[0], 0.0
    return st.mean(vals), st.stdev(vals)


def _fmt_ms(mean, sd, nd=4) -> str:
    if mean is None:
        return "-"
    return f"{mean:.{nd}f}±{sd:.{nd}f}" if sd is not None else f"{mean:.{nd}f}"


def build_grid_table(rows: list[dict], channel_order: list[str]) -> list[dict]:
    """Gộp theo (channels, img_size) → 1 dòng/ô lưới, mean±std qua seed."""
    groups = defaultdict(list)
    for r in rows:
        groups[(r["channels"], r["img_size"])].append(r)

    table = []
    for ch in channel_order:
        for size in SIZES:
            rs = groups.get((ch, size), [])
            if not rs:
                continue
            acc_m, acc_s = _mean_std([r["acc"] for r in rs])
            f1_m, f1_s = _mean_std([r["f1"] for r in rs])
            prec_m, prec_s = _mean_std([r["precision"] for r in rs])
            rec_m, rec_s = _mean_std([r["recall"] for r in rs])
            auc_m, auc_s = _mean_std([r["roc_auc"] for r in rs])
            time_m, _ = _mean_std([r["avg_epoch_time_s"] for r in rs])
            mem_m, _ = _mean_std([r["peak_gpu_mem_mb"] for r in rs])
            gmacs_m, _ = _mean_std([r["gmacs"] for r in rs])
            table.append({
                "channels": ch, "img_size": size, "n_seed": len(rs),
                "acc": (acc_m, acc_s), "precision": (prec_m, prec_s),
                "recall": (rec_m, rec_s), "f1": (f1_m, f1_s), "roc_auc": (auc_m, auc_s),
                "avg_epoch_time_s": time_m, "peak_gpu_mem_mb": mem_m, "gmacs": gmacs_m,
            })
    return table


def print_grid_table(table: list[dict], title: str) -> None:
    if not table:
        print(f"\n{title}: chưa có run nào.")
        return
    best_f1 = max((t["f1"][0] for t in table if t["f1"][0] is not None), default=None)
    print(f"\n=== {title} ===")
    header = f'{"Config x Size":<16} {"n":<3} {"Acc":<14} {"Precision":<14} {"Recall":<14} {"F1":<14} {"ROC-AUC":<14} {"t/epoch(s)":<11} {"mem(MB)":<9} {"GMACs":<7}'
    print(header)
    print("-" * len(header))
    for t in table:
        label = f'{t["channels"]} x {t["img_size"]}'
        star = "*" if best_f1 is not None and t["f1"][0] == best_f1 else ""
        f1_cell = f'{_fmt_ms(*t["f1"])}{star}'
        print(f'{label:<16} {t["n_seed"]:<3} '
              f'{_fmt_ms(*t["acc"]):<14} {_fmt_ms(*t["precision"]):<14} '
              f'{_fmt_ms(*t["recall"]):<14} {f1_cell:<15} '
              f'{_fmt_ms(*t["roc_auc"]):<14} '
              f'{t["avg_epoch_time_s"] or 0:<11.1f} {t["peak_gpu_mem_mb"] or 0:<9.0f} {t["gmacs"] or 0:<7.2f}')
    print("(* = F1 cao nhất trong bảng)")


def save_grid_csv(table: list[dict], out: Path) -> None:
    import csv
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["channels", "img_size", "n_seed", "acc_mean", "acc_std",
                    "precision_mean", "precision_std", "recall_mean", "recall_std",
                    "f1_mean", "f1_std", "roc_auc_mean", "roc_auc_std",
                    "avg_epoch_time_s", "peak_gpu_mem_mb", "gmacs"])
        for t in table:
            w.writerow([t["channels"], t["img_size"], t["n_seed"],
                        *t["acc"], *t["precision"], *t["recall"], *t["f1"], *t["roc_auc"],
                        t["avg_epoch_time_s"], t["peak_gpu_mem_mb"], t["gmacs"]])


def resolution_stats_tests(rows: list[dict], channel_order: list[str]) -> list[dict]:
    """Paired t-test (theo seed) cho mọi cặp độ phân giải, từng cấu hình kênh.
    docs/EXPERIMENTS.md §6: bắt buộc trước khi nói '224 ~ 336 ~ 448'."""
    by_channel = defaultdict(lambda: defaultdict(dict))  # channel -> size -> {seed: f1}
    for r in rows:
        if r["seed"] is None or r["f1"] is None:
            continue
        by_channel[r["channels"]][r["img_size"]][r["seed"]] = r["f1"]

    results = []
    for ch in channel_order:
        sizes_avail = by_channel.get(ch, {})
        for size_a, size_b in combinations(SIZES, 2):
            da, db = sizes_avail.get(size_a, {}), sizes_avail.get(size_b, {})
            common_seeds = sorted(set(da) & set(db))
            if len(common_seeds) < 2:
                continue
            scores_a = [da[s] for s in common_seeds]
            scores_b = [db[s] for s in common_seeds]
            test = paired_ttest(scores_a, scores_b)
            results.append({"channels": ch, "size_a": size_a, "size_b": size_b,
                            "n_seed_paired": len(common_seeds), **test})
    return results


def print_stats_tests(results: list[dict], title: str) -> None:
    if not results:
        print(f"\n{title}: chưa đủ dữ liệu (cần >=2 seed chung ở cả 2 size).")
        return
    print(f"\n=== Kiểm định thống kê — {title} (paired t-test trên F1, theo seed) ===")
    header = f'{"Kênh":<10} {"So sánh":<12} {"n":<3} {"mean_diff":<11} {"t":<8} {"p-value":<10} {"Kết luận"}'
    print(header)
    print("-" * len(header))
    for r in results:
        concl = "224 hơn có ý nghĩa" if r["significant"] and r["mean_diff"] > 0 else \
                ("size lớn hơn có ý nghĩa" if r["significant"] else "tương đương trong nhiễu")
        print(f'{r["channels"]:<10} {f"{r["size_a"]} vs {r["size_b"]}":<12} {r["n_seed_paired"]:<3} '
              f'{r["mean_diff"]:+.4f}     {r["t_stat"]:.3f}   {r["p_value"]:.4f}    {concl}')


def save_stats_csv(results: list[dict], out: Path) -> None:
    import csv
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["channels", "size_a", "size_b", "n_seed_paired",
                                          "mean_diff", "t_stat", "p_value", "significant"])
        w.writeheader()
        for r in results:
            w.writerow({k: r[k] for k in w.fieldnames})


def plot_pareto(rows: list[dict], out: Path, channel: str = "full") -> None:
    """F1 vs thời gian/epoch cho kênh `full`, cả 2 model — làm nổi điểm 224²."""
    by_model = defaultdict(dict)  # model -> size -> list of (time, f1)
    for r in rows:
        if r["channels"] != channel or r["f1"] is None or r["avg_epoch_time_s"] is None:
            continue
        by_model[r["model"]].setdefault(r["img_size"], []).append((r["avg_epoch_time_s"], r["f1"]))

    if not by_model:
        print(f"\nChưa đủ dữ liệu để vẽ Pareto (cần channels='{channel}').")
        return

    fig, ax = plt.subplots(figsize=(6, 5))
    colors = {"resnet50": "C0", "convnext_tiny": "C1"}
    markers = {224: "o", 336: "s", 448: "^"}
    for model, by_size in by_model.items():
        for size, pts in sorted(by_size.items()):
            times = [p[0] for p in pts]
            f1s = [p[1] for p in pts]
            t_mean, f1_mean = sum(times) / len(times), sum(f1s) / len(f1s)
            ax.scatter(t_mean, f1_mean, color=colors.get(model, "gray"),
                      marker=markers.get(size, "x"), s=90,
                      label=f"{model} @{size}", edgecolors="black", linewidths=0.5)

    ax.set_xlabel("Thời gian trung bình/epoch (s)")
    ax.set_ylabel("F1 (test, mean qua seed)")
    ax.set_title(f"Pareto accuracy-vs-cost (channels='{channel}')")
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"\nĐã lưu biểu đồ Pareto: {out}")


def main():
    ap = argparse.ArgumentParser(description="Tổng hợp lưới hợp nhất 5x3 (S5b.1).")
    ap.add_argument("--exp-dir", type=Path, default=Path("experiments"))
    ap.add_argument("--out-dir", type=Path, default=Path("results"))
    ap.add_argument("--variant", choices=["clean", "original"], default="clean",
                    help="'clean' = run nhãn đã làm sạch (_clean); 'original' = run nhãn gốc.")
    args = ap.parse_args()

    resnet_rows = collect(args.exp_dir, "sweep_resnet50_", args.variant)
    convnext_rows = collect(args.exp_dir, "sweep_convnext_tiny_", args.variant)

    resnet_table = build_grid_table(resnet_rows, CHANNEL_ORDER)
    convnext_table = build_grid_table(convnext_rows, ["full"])

    tag = "" if args.variant == "original" else "_clean"   # tách file để không đè bảng gốc

    print_grid_table(resnet_table, f"ResNet50 — lưới 5 kênh x 3 độ phân giải ({args.variant})")
    print_grid_table(convnext_table, f"ConvNeXt-Tiny — trục độ phân giải ({args.variant})")

    save_grid_csv(resnet_table, args.out_dir / "metrics" / f"grid_resnet50{tag}.csv")
    save_grid_csv(convnext_table, args.out_dir / "metrics" / f"grid_convnext_tiny{tag}.csv")

    resnet_stats = resolution_stats_tests(resnet_rows, CHANNEL_ORDER)
    convnext_stats = resolution_stats_tests(convnext_rows, ["full"])
    print_stats_tests(resnet_stats, "ResNet50")
    print_stats_tests(convnext_stats, "ConvNeXt-Tiny")
    save_stats_csv(resnet_stats + convnext_stats, args.out_dir / "metrics" / f"grid_resolution_ttest{tag}.csv")

    plot_pareto(resnet_rows + convnext_rows, args.out_dir / "figures" / f"pareto_accuracy_vs_cost{tag}.png")

    print(f"\n-> Da luu: {args.out_dir}/metrics/grid_resnet50{tag}.csv, grid_convnext_tiny{tag}.csv, "
          f"grid_resolution_ttest{tag}.csv, {args.out_dir}/figures/pareto_accuracy_vs_cost{tag}.png")


if __name__ == "__main__":
    main()
