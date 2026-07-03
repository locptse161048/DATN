"""
eda.py — Giai đoạn 1, task S1.4
--------------------------------
EDA trên metadata (KHÔNG đọc bytes malware — chỉ dùng labels.csv):
  1. Phân bố lớp (benign/malware), họ, nguồn.
  2. Chốt `image_width`: từ cột `size`, ước lượng chiều cao ảnh native cho từng
     width ứng viên → chọn width sao cho ĐA SỐ ảnh có height ≥ 448 (để thí nghiệm
     độ phân giải 224/336/448 có ý nghĩa).
  3. Kiểm tra thiên lệch nguồn: phân bố kích thước benign vs malware, theo nguồn.

Chạy headless trong Kali:
    python scripts/eda.py --labels data/interim/labels.csv --out results/figures

Output: in thống kê ra màn hình + lưu biểu đồ PNG vào --out.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

CANDIDATE_WIDTHS = [128, 256, 384, 512, 768]
MIN_HEIGHT = 448  # ảnh cần đủ cao để sweep 224/336/448 có ý nghĩa


def load(labels: Path) -> pd.DataFrame:
    df = pd.read_csv(labels)
    df["label"] = pd.to_numeric(df["label"], errors="coerce")
    df["size"] = pd.to_numeric(df["size"], errors="coerce")
    df = df.dropna(subset=["label", "size"])
    df["label"] = df["label"].astype(int)
    df["cls"] = df["label"].map({0: "benign", 1: "malware"})
    df["family"] = df["family"].fillna("").replace("", "(benign)")
    return df


def section(title: str) -> None:
    print("\n" + "=" * 60 + f"\n {title}\n" + "=" * 60)


def dist_class(df: pd.DataFrame, out: Path) -> None:
    section("1. Phân bố lớp benign/malware")
    vc = df["cls"].value_counts()
    print(vc.to_string())
    n_mal, n_ben = vc.get("malware", 0), vc.get("benign", 0)
    if n_ben:
        print(f"Tỉ lệ malware:benign = {n_mal / n_ben:.2f} : 1")
    fig, ax = plt.subplots(figsize=(4, 3))
    vc.plot.bar(ax=ax, color=["#3fb950", "#f85149"])
    ax.set_title("Phân bố lớp"); ax.set_ylabel("Số mẫu")
    fig.tight_layout(); fig.savefig(out / "01_class_balance.png", dpi=120); plt.close(fig)


def dist_family_source(df: pd.DataFrame, out: Path) -> None:
    section("2. Phân bố HỌ (malware) và NGUỒN")
    fam = df[df.label == 1]["family"].value_counts()
    print("Top 15 họ malware:"); print(fam.head(15).to_string())
    src = df["source"].value_counts()
    print("\nTheo nguồn:"); print(src.to_string())

    fig, ax = plt.subplots(figsize=(7, 4))
    fam.head(15).iloc[::-1].plot.barh(ax=ax, color="#a371f7")
    ax.set_title("Top 15 họ malware"); ax.set_xlabel("Số mẫu")
    fig.tight_layout(); fig.savefig(out / "02_family_top15.png", dpi=120); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 4))
    src.iloc[::-1].plot.barh(ax=ax, color="#4f9cf9")
    ax.set_title("Phân bố theo nguồn"); ax.set_xlabel("Số mẫu")
    fig.tight_layout(); fig.savefig(out / "03_source.png", dpi=120); plt.close(fig)


def choose_width(df: pd.DataFrame, out: Path) -> int:
    section("3. Chốt image_width (từ kích thước file)")
    sizes = df["size"].to_numpy()
    print(f"Kích thước file (byte): min={sizes.min():.0f} | median={np.median(sizes):.0f} "
          f"| mean={sizes.mean():.0f} | max={sizes.max():.0f}")
    print(f"\n{'width':>6} | {'%ảnh cao≥448':>12} | {'height trung vị':>15}")
    print("-" * 40)
    best = CANDIDATE_WIDTHS[0]
    for w in CANDIDATE_WIDTHS:
        heights = np.ceil(sizes / w)
        pct = float(np.mean(heights >= MIN_HEIGHT)) * 100
        print(f"{w:>6} | {pct:>11.1f}% | {np.median(heights):>15.0f}")
        if pct >= 75:           # width lớn nhất vẫn giữ ≥75% ảnh đủ cao
            best = w
    print(f"\n→ ĐỀ XUẤT image_width = {best} "
          f"(giữ ≥75% ảnh có height ≥ {MIN_HEIGHT}; width lớn hơn → ảnh thấp hơn).")
    print("  Cập nhật giá trị này vào configs/data.yaml (image_width).")

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(np.log10(sizes + 1), bins=60, color="#d29922")
    ax.set_title("Phân bố kích thước file (log10 byte)")
    ax.set_xlabel("log10(size)"); ax.set_ylabel("Số mẫu")
    fig.tight_layout(); fig.savefig(out / "04_filesize_hist.png", dpi=120); plt.close(fig)
    return best


def bias_check(df: pd.DataFrame, out: Path) -> None:
    section("4. Kiểm tra THIÊN LỆCH NGUỒN (size benign vs malware)")
    g = df.groupby("cls")["size"]
    print("Kích thước theo lớp (byte):")
    print(g.agg(["count", "median", "mean"]).to_string())
    med_ben = df[df.cls == "benign"]["size"].median()
    med_mal = df[df.cls == "malware"]["size"].median()
    ratio = max(med_ben, med_mal) / max(1, min(med_ben, med_mal))
    print(f"\nTỉ lệ median size (lớp lớn/nhỏ) = {ratio:.1f}×")
    if ratio >= 3:
        print("⚠️  CHÊNH LỆCH LỚN: model có thể học 'kích thước/định dạng' thay vì tính độc hại.")
        print("   → Cân nhắc đa dạng thêm benign (kích thước lớn) hoặc kiểm soát khi đánh giá.")
    else:
        print("✓ Chênh lệch kích thước benign/malware ở mức chấp nhận.")

    print("\nMedian size theo nguồn (byte):")
    print(df.groupby("source")["size"].median().sort_values(ascending=False).to_string())

    fig, ax = plt.subplots(figsize=(6, 4))
    for cls, color in [("benign", "#3fb950"), ("malware", "#f85149")]:
        s = df[df.cls == cls]["size"]
        ax.hist(np.log10(s + 1), bins=50, alpha=0.6, label=cls, color=color)
    ax.legend(); ax.set_title("Size benign vs malware (log10 byte)")
    ax.set_xlabel("log10(size)"); ax.set_ylabel("Số mẫu")
    fig.tight_layout(); fig.savefig(out / "05_bias_size.png", dpi=120); plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description="EDA metadata (S1.4).")
    ap.add_argument("--labels", type=Path, default=Path("data/interim/labels.csv"))
    ap.add_argument("--out", type=Path, default=Path("results/figures"))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    df = load(args.labels)
    print(f"Đã nạp {len(df)} mẫu từ {args.labels}")
    dist_class(df, args.out)
    dist_family_source(df, args.out)
    choose_width(df, args.out)
    bias_check(df, args.out)
    print(f"\nĐã lưu biểu đồ vào: {args.out}")


if __name__ == "__main__":
    main()
