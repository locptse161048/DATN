"""
make_valid_list.py — Giai đoạn 1 → 2
------------------------------------
Từ labels.csv (hoặc detect_subset.csv) + cấu hình lọc, sinh danh sách
**file HỢP LỆ để train** kèm kích thước ảnh native — tính từ cột `size`,
KHÔNG cần đọc bytes (an toàn, tức thì).

Quy tắc (đọc từ configs/data.yaml, có thể override qua CLI):
  - valid       = size >= min_bytes                 (bỏ file quá nhỏ)
  - effective   = min(size, max_bytes)              (cắt file khổng lồ khi sinh ảnh)
  - native_w    = image_width (cố định)
  - native_h    = ceil(effective / image_width)
  - res_eligible= valid và native_h >= image_width  (đủ ≥448×448 cho resolution sweep)

Output: data/interim/valid_for_train.csv (chỉ các dòng valid) với cột:
  path, sha256, label, family, source, size, native_w, native_h, res_eligible

Usage:
    python scripts/make_valid_list.py --input data/interim/labels.csv
    python scripts/make_valid_list.py --input data/interim/detect_subset.csv \
        --out data/interim/valid_detect.csv
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

try:
    import yaml  # type: ignore
except Exception:
    yaml = None


def load_cfg(path: Path) -> dict:
    if yaml is None or not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Sinh danh sách file hợp lệ để train (từ labels.csv).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("--input", type=Path, default=Path("data/interim/labels.csv"))
    ap.add_argument("--out", type=Path, default=Path("data/interim/valid_for_train.csv"))
    ap.add_argument("--config", type=Path, default=Path("configs/data.yaml"))
    ap.add_argument("--image-width", type=int, default=None)
    ap.add_argument("--min-bytes", type=int, default=None)
    ap.add_argument("--max-bytes", type=int, default=None)
    ap.add_argument("--res-min-bytes", type=int, default=None)
    args = ap.parse_args()

    cfg = load_cfg(args.config)
    width = args.image_width or cfg.get("image_width", 448)
    min_b = args.min_bytes if args.min_bytes is not None else cfg.get("min_bytes", 4096)
    max_b = args.max_bytes if args.max_bytes is not None else cfg.get("max_bytes", 31457280)
    res_min = (args.res_min_bytes if args.res_min_bytes is not None
               else cfg.get("res_sweep_min_bytes", width * width))

    with open(args.input, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    out_rows = []
    n_drop_small = 0
    n_res = 0
    for r in rows:
        size = int(float(r["size"]))
        if size < min_b:
            n_drop_small += 1
            continue
        eff = min(size, max_b)
        native_h = math.ceil(eff / width)
        res_eligible = native_h >= width  # width=448 → cần height ≥ 448
        if res_eligible:
            n_res += 1
        out_rows.append({
            "path": r["path"], "sha256": r["sha256"], "label": r["label"],
            "family": r.get("family", ""), "source": r.get("source", ""),
            "size": size, "native_w": width, "native_h": native_h,
            "res_eligible": int(res_eligible),
        })

    args.out.parent.mkdir(parents=True, exist_ok=True)
    cols = ["path", "sha256", "label", "family", "source",
            "size", "native_w", "native_h", "res_eligible"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out_rows)

    n_mal = sum(1 for r in out_rows if str(r["label"]) == "1")
    n_ben = sum(1 for r in out_rows if str(r["label"]) == "0")
    print(f"Cấu hình: width={width}, min_bytes={min_b}, max_bytes={max_b}, "
          f"res_min_bytes={res_min}")
    print(f"Đầu vào: {len(rows)} | Bỏ (quá nhỏ <{min_b}B): {n_drop_small}")
    print(f"HỢP LỆ để train: {len(out_rows)}  (malware {n_mal} / benign {n_ben})")
    print(f"Đủ cho resolution sweep (native ≥ {width}×{width}): {n_res} "
          f"({100*n_res/max(1,len(out_rows)):.1f}%)")
    print(f"→ {args.out}")


if __name__ == "__main__":
    main()
