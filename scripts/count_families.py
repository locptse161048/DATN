"""Dem so family (ho malware) trong labels.csv / detect_subset.csv."""
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "data/interim/labels.csv")

c = Counter()
n_no_family = 0
n_benign = 0
with open(path, encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r["label"] == "0":
            n_benign += 1
            continue
        fam = r.get("family", "").strip()
        if not fam:
            n_no_family += 1
        else:
            c[fam] += 1

print(f"File: {path}")
print(f"Benign: {n_benign}")
print(f"Malware co family: {sum(c.values())} | khong co family: {n_no_family}")
print(f"So family khac nhau: {len(c)}\n")

print(f"{'family':<25}{'n_samples':>10}")
for fam, n in c.most_common():
    print(f"{fam:<25}{n:>10}")
