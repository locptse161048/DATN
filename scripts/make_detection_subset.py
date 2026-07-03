"""
make_detection_subset.py
-------------------------
Tạo TẬP CON cho bài toán PHÁT HIỆN nhị phân (benign vs malware) với tỉ lệ mong muốn
(mặc định 1.5:1), bằng cách **cap đều mỗi họ malware** — các họ áp đảo (RAT, Winwebsec)
bị cắt nhiều nhất, các họ nhỏ giữ nguyên.

KHÔNG di chuyển/xóa file. Đọc `labels.csv` (đầy đủ) → ghi `detect_subset.csv`
(danh sách sha256/path được CHỌN cho detection). Tập đầy đủ vẫn dùng nguyên cho
nhánh PHÂN LOẠI họ sau này.

Trong họ 'RAT' (đã gộp ở labeling), chọn **đa dạng sub-family** (cap đều theo thư mục
con) để mẫu RAT không bị 2-3 builder áp đảo.

Usage:
    python scripts/make_detection_subset.py --ratio 1.5 --dry-run
    python scripts/make_detection_subset.py --ratio 1.5
"""

from __future__ import annotations

import argparse
import csv
import logging
import random
from collections import defaultdict
from pathlib import Path

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)


def find_cap(counts: list[int], target: int) -> int:
    """Cap K lớn nhất sao cho sum(min(n,K)) <= target."""
    if not counts or sum(counts) <= target:
        return max(counts) if counts else 0
    lo, hi, best = 0, max(counts), 0
    while lo <= hi:
        mid = (lo + hi) // 2
        if sum(min(n, mid) for n in counts) <= target:
            best, lo = mid, mid + 1
        else:
            hi = mid - 1
    return best


def rat_subfamily(path: str) -> str:
    parts = Path(path).parts
    if "RAT" in parts:
        i = parts.index("RAT")
        if i + 1 < len(parts) - 1:  # còn thư mục con trước file
            return parts[i + 1]
    return "_rat_root"


def select_within_rat(rows: list[dict], budget: int, rng: random.Random) -> list[dict]:
    """Chọn `budget` mẫu RAT, cap đều theo sub-family để đa dạng."""
    by_sub: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_sub[rat_subfamily(r["path"])].append(r)
    counts = [len(v) for v in by_sub.values()]
    cap = find_cap(counts, budget)
    chosen: list[dict] = []
    for sub, items in by_sub.items():
        items = sorted(items, key=lambda r: r["sha256"])
        if len(items) > cap:
            rng.shuffle(items)
            items = items[:cap]
        chosen.extend(items)
    # phân bổ phần dư cho sub-family còn mẫu
    leftover = budget - len(chosen)
    if leftover > 0:
        pool = [r for sub, items in by_sub.items()
                for r in items if r not in chosen]
        rng.shuffle(pool)
        chosen.extend(pool[:leftover])
    return chosen[:budget]


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Tạo tập con detection (benign vs malware) theo tỉ lệ.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("--labels", type=Path, default=Path("data/interim/labels.csv"))
    ap.add_argument("--out", type=Path, default=Path("data/interim/detect_subset.csv"))
    ap.add_argument("--ratio", type=float, default=1.5,
                    help="Tỉ lệ malware:benign mong muốn.")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    with open(args.labels, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    benign = [r for r in rows if r["label"] in ("0", 0)]
    malware = [r for r in rows if r["label"] in ("1", 1)]
    n_benign = len(benign)
    target_mal = int(round(args.ratio * n_benign))

    by_fam: dict[str, list[dict]] = defaultdict(list)
    for r in malware:
        by_fam[r["family"] or "_unknown"].append(r)
    fam_counts = [len(v) for v in by_fam.values()]
    cap = find_cap(fam_counts, target_mal)

    logger.info("benign=%d | malware=%d (%d họ) | mục tiêu malware=%d (tỉ lệ %.2f:1)",
                n_benign, len(malware), len(by_fam), target_mal, args.ratio)
    logger.info("Cap mỗi họ ≈ %d", cap)

    selected_mal: list[dict] = []
    report = []
    for fam, items in by_fam.items():
        before = len(items)
        if before <= cap:
            keep = items
        elif fam == "RAT":
            keep = select_within_rat(items, cap, rng)
        else:
            items2 = sorted(items, key=lambda r: r["sha256"])
            rng.shuffle(items2)
            keep = items2[:cap]
        selected_mal.extend(keep)
        if before != len(keep):
            report.append((fam, before, len(keep)))

    final_mal = len(selected_mal)
    logger.info("Sau cap: malware chọn=%d, benign=%d → tỉ lệ=%.2f:1",
                final_mal, n_benign, final_mal / max(1, n_benign))
    for fam, b, a in sorted(report, key=lambda x: x[1], reverse=True):
        logger.info("   %-14s %6d → %d", fam, b, a)

    if args.dry_run:
        logger.info("[DRY-RUN] không ghi file.")
        return

    args.out.parent.mkdir(parents=True, exist_ok=True)
    cols = list(rows[0].keys())
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in benign + selected_mal:
            w.writerow(r)
    logger.info("Đã ghi %d dòng (benign %d + malware %d) → %s",
                n_benign + final_mal, n_benign, final_mal, args.out)


if __name__ == "__main__":
    main()
