"""
extract_gray.py — tách bộ ảnh XÁM 1 KÊNH từ ảnh composite 3 kênh.
Kênh 0 (R) của ảnh composite chính là grayscale → lấy ra, lưu ảnh mode 'L'.

An toàn: chỉ đọc/ghi PNG (không đụng bytes malware) → chạy được cả host lẫn Kali.
Dùng cho ablation "gray1" nếu muốn một bộ ảnh xám độc lập (không bắt buộc — dataset
chế độ `channels=gray1` cũng tự lấy kênh 0 từ composite khi train).

Usage:
    python scripts/extract_gray.py --src data/processed/224 --out data/processed/gray224
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def main():
    ap = argparse.ArgumentParser(description="Tách ảnh xám 1 kênh từ composite.")
    ap.add_argument("--src", type=Path, default=Path("data/processed/224"))
    ap.add_argument("--out", type=Path, default=Path("data/processed/gray224"))
    args = ap.parse_args()

    files = list(args.src.rglob("*.png"))
    if not files:
        raise SystemExit(f"Không thấy ảnh trong {args.src}")
    print(f"Tìm thấy {len(files)} ảnh composite. Tách kênh gray...")

    n = 0
    for p in files:
        dst = args.out / p.relative_to(args.src)
        dst.parent.mkdir(parents=True, exist_ok=True)
        Image.open(p).convert("RGB").getchannel(0).save(dst)   # kênh 0 = gray → 'L'
        n += 1
        if n % 1000 == 0:
            print(f"  {n}/{len(files)}")
    print(f"Đã tách {n} ảnh xám 1 kênh → {args.out}")


if __name__ == "__main__":
    main()
