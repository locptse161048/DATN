"""Đếm số mẫu theo phần mở rộng file gốc trong labels.csv — chạy trên máy có data/raw."""
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "data/interim/labels.csv")
c = Counter()
by_label = Counter()
with open(path, encoding="utf-8") as f:
    for r in csv.DictReader(f):
        ext = Path(r["path"]).suffix.lower()
        c[ext] += 1
        by_label[(ext, r["label"])] += 1

print(f"{'ext':<8}{'total':>8}{'benign':>8}{'malware':>8}")
for ext, n in c.most_common():
    b = by_label.get((ext, "0"), 0)
    m = by_label.get((ext, "1"), 0)
    print(f"{ext:<8}{n:>8}{b:>8}{m:>8}")

drop_exts = {".sys", ".scr", ".ocx", ".cpl"}
kept = sum(n for ext, n in c.items() if ext not in drop_exts)
dropped = sum(n for ext, n in c.items() if ext in drop_exts)
print(f"\nNếu bỏ {sorted(drop_exts)}: còn {kept} / {sum(c.values())} mẫu (mất {dropped}).")
