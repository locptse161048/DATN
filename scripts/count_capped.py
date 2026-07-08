# Đếm số mẫu bị cap chiều cao ảnh (--max-native-height 8192) khi preprocess.
# File > 8192*448 byte (~3.5 MB) → ảnh gray bị resize BILINEAR trước khi tính entropy/ASCII.
# Chạy: python scripts/count_capped.py [--input data/interim/valid_for_train.csv]
import argparse
import csv
import os
from pathlib import Path

CAP_BYTES = 8192 * 448  # 3,670,016 B ~ 3.5 MB
MAX_BYTES = 31_457_280  # 30 MB (max_bytes trong configs/data.yaml)


def load_shas(prefix: str) -> set:
    shas = set()
    for part in ("train", "val", "test"):
        p = Path(f"data/interim/{prefix}_{part}.csv")
        if p.exists():
            with open(p, encoding="utf-8") as f:
                shas.update(r["sha256"] for r in csv.DictReader(f))
    return shas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, default=Path("data/interim/valid_for_train.csv"),
                    help="CSV có cột sha256 + path (đường dẫn file PE gốc)")
    args = ap.parse_args()

    sweep, split = load_shas("sweep"), load_shas("split")

    tot = capped = trunc = missing = 0
    cap_sweep = cap_split = 0
    cap_mal = cap_ben = 0
    with open(args.input, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            tot += 1
            p = r.get("path") or r.get("filepath") or ""
            if not p or not os.path.exists(p):
                missing += 1
                continue
            sz = os.path.getsize(p)
            if sz > CAP_BYTES:
                capped += 1
                sha = r.get("sha256", "")
                if sha in sweep:
                    cap_sweep += 1
                if sha in split:
                    cap_split += 1
                if str(r.get("label", "")) in ("1", "malware"):
                    cap_mal += 1
                else:
                    cap_ben += 1
            if sz > MAX_BYTES:
                trunc += 1

    print(f"Tổng mẫu trong {args.input}: {tot} (không tìm thấy file: {missing})")
    print(f"Bị cap chiều cao (> {CAP_BYTES:,} B ~3.5 MB): {capped} ({capped/max(tot,1)*100:.1f}%)")
    print(f"  - thuộc tập sweep (lưới 5x3):   {cap_sweep} / {len(sweep)} ({cap_sweep/max(len(sweep),1)*100:.1f}%)")
    print(f"  - thuộc tập split (headline):   {cap_split} / {len(split)} ({cap_split/max(len(split),1)*100:.1f}%)")
    print(f"  - malware: {cap_mal} | benign: {cap_ben}")
    print(f"Bị cắt đọc 30 MB (> {MAX_BYTES:,} B): {trunc}")


if __name__ == "__main__":
    main()
